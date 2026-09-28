"""Layer L04 deterministic landslide susceptibility baseline.

This module contains array-level, deterministic scoring primitives. It does not
download data, infer missing factors, or fabricate geographic values.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import MergeAlg
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box
from pyproj import CRS
from shapely.validation import make_valid

from src.common.config import get_hazards_config, get_weights_config
from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.common.provenance import compute_sha256
from src.ingestion.adapters import get_adapter_for_file
from src.spatial.grid import DEFAULT_NODATA_FLOAT, CanonicalGridDefinition
from src.spatial.raster import is_aligned_to_canonical_grid, resample_and_align_raster
from src.spatial.terrain import calculate_slope_and_aspect_arrays
from src.spatial.vector import validate_and_reproject_vector, load_and_prepare_study_area


L04_FACTOR_NAMES = frozenset({"slope", "lulc", "geology", "drainage", "roads", "inventory"})
L04_CATEGORICAL_FACTORS = frozenset({"lulc", "geology"})


def _require_canonical_grid(grid: CanonicalGridDefinition) -> None:
    """Reject grids whose coordinate units are not the frozen projected CRS."""
    if CRS.from_user_input(grid.crs) != CRS.from_user_input(CANONICAL_PROJECTED_CRS_STR):
        raise LandslideModelError(f"L04 requires a canonical grid in {CANONICAL_PROJECTED_CRS_STR}")


class LandslideModelError(ValueError):
    """Raised when L04 inputs or configuration violate the model contract."""


@dataclass(frozen=True)
class LandslideBaselineResult:
    """Normalized L04 result and explainability artifacts."""

    hazard: np.ndarray
    factors: Dict[str, np.ndarray]
    nodata_mask: np.ndarray
    contributions: Dict[str, np.ndarray]
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class InventoryValidationResult:
    """Validated inventory plus deterministic cleaning counts."""

    inventory: gpd.GeoDataFrame
    report: Dict[str, int]


@dataclass(frozen=True)
class InventoryEvidenceResult:
    """Inventory evidence with an explicit status for empty input."""

    evidence: np.ndarray
    status: str
    overlapping_records: int


@dataclass(frozen=True)
class MLEligibility:
    """Auditable decision for whether future supervised ML may be attempted."""

    eligible: bool
    checks: Dict[str, bool]
    reasons: Tuple[str, ...]


class LandslideDataPendingError(LandslideModelError):
    """Raised when a file-based L04 run lacks required real input data."""


def normalize_continuous(values: np.ndarray, nodata: float = DEFAULT_NODATA_FLOAT) -> np.ndarray:
    """Min-max normalize valid values to [0, 1]; constant data maps to 0."""
    array = np.asarray(values, dtype=np.float32)
    valid = np.isfinite(array) & (array != nodata)
    output = np.full(array.shape, nodata, dtype=np.float32)
    if not np.any(valid):
        return output
    minimum = float(np.min(array[valid]))
    maximum = float(np.max(array[valid]))
    if maximum == minimum:
        output[valid] = 0.0
    else:
        output[valid] = np.clip((array[valid] - minimum) / (maximum - minimum), 0.0, 1.0)
    return output


def reclassify_categorical(
    values: np.ndarray,
    mapping: Mapping[Union[int, float, str], float],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> np.ndarray:
    """Apply an explicit mapping; observed classes missing from it become NoData."""
    if not mapping:
        raise LandslideModelError("Categorical factor mapping must not be empty")
    array = np.asarray(values)
    output = np.full(array.shape, nodata, dtype=np.float32)
    for category, score in mapping.items():
        try:
            numeric_score = float(score)
        except (TypeError, ValueError) as exc:
            raise LandslideModelError(f"Categorical score for {category!r} must be numeric") from exc
        if not np.isfinite(numeric_score) or not 0.0 <= numeric_score <= 1.0:
            raise LandslideModelError(f"Categorical score for {category!r} must be within [0, 1]")
        output[array == category] = numeric_score
    valid_scores = output[output != nodata]
    if valid_scores.size and (np.any(valid_scores < 0.0) or np.any(valid_scores > 1.0)):
        raise LandslideModelError("Categorical scores must be within [0, 1]")
    return output


def validate_weights(weights: Mapping[str, float], tolerance: float = 1e-6) -> Dict[str, float]:
    """Validate known, positive factor weights summing to one."""
    if not weights:
        raise LandslideModelError("At least one factor weight is required")
    unknown = set(weights) - L04_FACTOR_NAMES
    if unknown:
        raise LandslideModelError(f"Unknown L04 factor weights: {sorted(unknown)}")
    normalized = {name: float(value) for name, value in weights.items()}
    if any(not np.isfinite(value) or value <= 0.0 for value in normalized.values()):
        raise LandslideModelError("L04 factor weights must be finite and positive")
    if not np.isclose(sum(normalized.values()), 1.0, atol=tolerance):
        raise LandslideModelError("L04 factor weights must sum to 1.0")
    return normalized


def _coerce_and_validate_factor_array(
    name: str,
    values: np.ndarray,
    nodata: float,
) -> np.ndarray:
    """Validate one normalized factor grid without clipping invalid input."""
    try:
        array = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise LandslideModelError(f"Factor '{name}' must be numeric") from exc
    valid = array != nodata
    if np.any(~np.isfinite(array[valid])):
        raise LandslideModelError(f"Factor '{name}' contains NaN or infinity")
    if np.any((array[valid] < 0.0) | (array[valid] > 1.0)):
        raise LandslideModelError(f"Factor '{name}' contains values outside [0, 1]")
    return array


def weighted_combine(
    factors: Mapping[str, np.ndarray],
    weights: Mapping[str, float],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Combine complete factor grids and return per-factor weighted contributions."""
    if not factors:
        raise LandslideModelError("At least one usable factor is required")
    configured = validate_weights(weights)
    unknown_factors = set(factors) - L04_FACTOR_NAMES
    if unknown_factors:
        raise LandslideModelError(f"Unknown L04 factors: {sorted(unknown_factors)}")
    missing_weights = set(factors) - set(configured)
    if missing_weights:
        raise LandslideModelError(f"No configured weights for factors: {sorted(missing_weights)}")
    selected_weights = {name: configured[name] for name in factors}
    total = sum(selected_weights.values())
    if total <= 0.0:
        raise LandslideModelError("Selected factor weights must contain a positive value")
    selected_weights = {name: value / total for name, value in selected_weights.items()}

    arrays = {
        name: _coerce_and_validate_factor_array(name, value, nodata)
        for name, value in factors.items()
    }
    shape = next(iter(arrays.values())).shape
    if any(array.shape != shape for array in arrays.values()):
        raise LandslideModelError("All factor arrays must have the same shape")
    valid = np.ones(shape, dtype=bool)
    for array in arrays.values():
        valid &= np.isfinite(array) & (array != nodata)
    contributions = {
        name: np.where(valid, array * selected_weights[name], nodata).astype(np.float32)
        for name, array in arrays.items()
    }
    result = np.full(shape, nodata, dtype=np.float32)
    if np.any(valid):
        result[valid] = sum(contribution[valid] for contribution in contributions.values())
        result[valid] = np.clip(result[valid], 0.0, 1.0)
    return result, contributions


def slope_factor_from_dem(
    dem: np.ndarray,
    dx: float = 30.0,
    dy: float = 30.0,
    nodata: float = DEFAULT_NODATA_FLOAT,
    classes: Optional[Sequence[Mapping[str, float]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Derive a slope score using L03 Horn slope and explicit interval classes."""
    slope, _ = calculate_slope_and_aspect_arrays(dem, dx=dx, dy=dy, nodata=nodata)
    configured = classes or get_hazards_config()["landslide_baseline"]["slope_classes"]
    return reclassify_slope(slope, configured, nodata=nodata), slope


def reclassify_slope(
    slope: np.ndarray,
    classes: Sequence[Mapping[str, float]],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> np.ndarray:
    """Apply ordered half-open slope classes, with the final class closed at 90."""
    if not classes:
        raise LandslideModelError("Slope class configuration must not be empty")
    previous_max: Optional[float] = None
    for index, rule in enumerate(classes):
        try:
            minimum = float(rule["min_degrees"])
            maximum = float(rule["max_degrees"])
            score = float(rule["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LandslideModelError("Each slope class needs numeric min_degrees, max_degrees, and score") from exc
        if not (np.isfinite(minimum) and np.isfinite(maximum) and np.isfinite(score)):
            raise LandslideModelError("Slope class parameters must be finite")
        if minimum < 0.0 or maximum <= minimum or maximum > 90.0:
            raise LandslideModelError("Slope classes must be within 0..90 degrees and increasing")
        if previous_max is not None and minimum != previous_max:
            raise LandslideModelError("Slope classes must be contiguous and ordered")
        if not 0.0 <= score <= 1.0:
            raise LandslideModelError("Slope class scores must be within [0, 1]")
        if index == len(classes) - 1 and maximum != 90.0:
            raise LandslideModelError("The final slope class must end at 90 degrees")
        previous_max = maximum

    array = np.asarray(slope, dtype=np.float32)
    valid = np.isfinite(array) & (array != nodata)
    if np.any(array[valid] < 0.0) or np.any(array[valid] > 90.0):
        raise LandslideModelError("Slope values must be within [0, 90] degrees")
    score = np.full(slope.shape, nodata, dtype=np.float32)
    for index, rule in enumerate(classes):
        minimum = float(rule["min_degrees"])
        maximum = float(rule["max_degrees"])
        upper = (array <= maximum) if index == len(classes) - 1 else (array < maximum)
        score[(array >= minimum) & upper] = float(rule["score"])
    return score


def validate_landslide_inventory(
    inventory: gpd.GeoDataFrame,
    target_crs: str = CANONICAL_PROJECTED_CRS_STR,
) -> InventoryValidationResult:
    """Validate, repair, reproject, and deduplicate real inventory geometries."""
    if inventory.crs is None:
        raise LandslideModelError("Landslide inventory has no defined CRS")
    working = inventory.copy()
    original_count = len(working)
    working["geometry"] = working.geometry.apply(lambda geometry: make_valid(geometry) if geometry is not None else geometry)
    working = working[working.geometry.notna() & ~working.geometry.is_empty].copy()
    working = working[working.geometry.is_valid].copy()
    working = working.to_crs(target_crs)
    working["_geometry_key"] = working.geometry.apply(lambda geometry: geometry.wkb_hex)
    working = working.drop_duplicates("_geometry_key").drop(columns=["_geometry_key"])
    return InventoryValidationResult(
        inventory=working,
        report={"input_records": original_count, "output_records": len(working), "removed_records": original_count - len(working)},
    )


def inventory_evidence(
    inventory: gpd.GeoDataFrame,
    shape: Tuple[int, int],
    transform: Affine,
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> np.ndarray:
    """Rasterize inventory counts and report empty/overlap status explicitly."""
    if inventory.crs is None:
        raise LandslideModelError("Landslide inventory has no defined CRS")
    if inventory.empty:
        return InventoryEvidenceResult(
            evidence=np.full(shape, nodata, dtype=np.float32),
            status="empty_inventory",
            overlapping_records=0,
        )
    prepared = validate_and_reproject_vector(inventory, target_crs=CANONICAL_PROJECTED_CRS_STR)
    left, bottom, right, top = array_bounds(shape[0], shape[1], transform)
    grid_extent = box(left, bottom, right, top)
    overlapping = prepared[prepared.geometry.intersects(grid_extent)].copy()
    if overlapping.empty:
        raise LandslideModelError("Landslide inventory has no spatial overlap with the target grid")
    shapes = ((geometry, 1) for geometry in overlapping.geometry if geometry is not None and not geometry.is_empty)
    evidence = rasterize(shapes, out_shape=shape, transform=transform, fill=0.0, dtype="float32", merge_alg=MergeAlg.add)
    return InventoryEvidenceResult(
        evidence=normalize_continuous(evidence, nodata=nodata),
        status="valid_overlap",
        overlapping_records=len(overlapping),
    )


def proximity_factor_from_vectors(
    source: gpd.GeoDataFrame,
    grid: CanonicalGridDefinition,
    max_distance_m: Optional[float],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> np.ndarray:
    """Create near-to-far evidence from vector distance in projected metres.

    The explicit model parameter is D = ``max_distance_m`` and evidence is
    ``max(0, 1 - distance_m / D)``. Distance at or beyond D scores zero.
    """
    _require_canonical_grid(grid)
    if max_distance_m is None or not np.isfinite(max_distance_m) or max_distance_m <= 0.0:
        raise LandslideModelError("A finite positive max_distance_m is required for proximity factors")
    if source.crs is None:
        raise LandslideModelError("Proximity source vector has no defined CRS")
    if source.empty:
        raise LandslideModelError("Proximity source vector is empty")
    prepared = validate_and_reproject_vector(source, target_crs=CANONICAL_PROJECTED_CRS_STR)
    prepared = prepared[prepared.geometry.notna() & ~prepared.geometry.is_empty].copy()
    if prepared.empty:
        raise LandslideModelError("Proximity source vector has no usable geometries")
    prepared["geometry"] = prepared.geometry.apply(make_valid)
    source_geometry = prepared.geometry.union_all()
    result = np.full((grid.height, grid.width), nodata, dtype=np.float32)
    for row in range(grid.height):
        for col in range(grid.width):
            x, y = grid.cell_center_coords(row, col)
            distance_m = source_geometry.distance(gpd.GeoSeries.from_xy([x], [y], crs=grid.crs).iloc[0])
            result[row, col] = max(0.0, 1.0 - (distance_m / float(max_distance_m)))
    return result


def drainage_proximity_factor(
    drainage: gpd.GeoDataFrame,
    grid: CanonicalGridDefinition,
    max_distance_m: Optional[float],
) -> np.ndarray:
    """Return drainage proximity evidence using the explicit distance model."""
    return proximity_factor_from_vectors(drainage, grid, max_distance_m)


def road_proximity_factor(
    roads: gpd.GeoDataFrame,
    grid: CanonicalGridDefinition,
    max_distance_m: Optional[float],
) -> np.ndarray:
    """Return road/infrastructure proximity evidence using the explicit distance model."""
    return proximity_factor_from_vectors(roads, grid, max_distance_m)


def ml_eligibility_gate(
    label_count: int,
    positive_count: int,
    negative_count: int,
    spatial_coverage: bool,
    leakage_control: bool,
    spatial_validation: bool,
    reproducible: bool,
    minimum_labels: int = 30,
) -> MLEligibility:
    """Check minimum future-ML requirements without training a model."""
    checks = {
        "sufficient_real_labels": label_count >= minimum_labels,
        "spatial_coverage": spatial_coverage,
        "positive_negative_adequacy": positive_count > 0 and negative_count > 0,
        "leakage_prevention": leakage_control,
        "spatial_validation": spatial_validation,
        "reproducibility": reproducible,
    }
    reasons = tuple(name for name, passed in checks.items() if not passed)
    return MLEligibility(eligible=all(checks.values()), checks=checks, reasons=reasons)


def audit_l04_data_readiness(repo_root: Union[str, Path]) -> Dict[str, Any]:
    """Audit expected L04 datasets without treating directory markers as data."""
    root = Path(repo_root)
    data_root = root / "data"
    expected = {
        "study_area_boundary": ("admin", "boundary", "chamoli"),
        "dem": ("dem", "elevation", "copernicus", "srtm", "cartodem"),
        "landslide_inventory": ("landslide", "inventory"),
        "lulc": ("lulc", "land_cover", "landcover"),
        "geology": ("geology", "lithology"),
        "drainage": ("drainage", "river", "stream", "network"),
        "roads": ("road", "infrastructure"),
    }
    files = [path for path in data_root.rglob("*") if path.is_file() and path.name != ".gitkeep"] if data_root.exists() else []
    datasets = {}
    for dataset, terms in expected.items():
        matches = [path for path in files if any(term in path.name.lower() or term in str(path.parent).lower() for term in terms)]
        datasets[dataset] = {"present": bool(matches), "paths": [str(path.relative_to(root).as_posix()) for path in matches], "usable": False}
    return {"data_root": str(data_root.as_posix()), "datasets": datasets, "real_data_available": bool(files)}


def build_provenance_metadata(
    input_paths: Mapping[str, Union[str, Path]],
    weights: Mapping[str, float],
    model_version: str = "L04-baseline-1.0",
    config_version: str = "1.0",
) -> Dict[str, Any]:
    """Build auditable metadata for a run, including checksums where files exist."""
    inputs = {}
    for name, raw_path in input_paths.items():
        path = Path(raw_path)
        inputs[name] = {"path": path.as_posix(), "checksum_sha256": compute_sha256(path) if path.is_file() else None}
    return {
        "layer": "L04",
        "model_version": model_version,
        "config_version": config_version,
        "method": "weighted deterministic reclassification and normalization",
        "crs": CANONICAL_PROJECTED_CRS_STR,
        "resolution_m": 30.0,
        "weights": dict(weights),
        "inputs": inputs,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def compute_landslide_baseline(
    factors: Mapping[str, np.ndarray],
    weights: Optional[Mapping[str, float]] = None,
    nodata: float = DEFAULT_NODATA_FLOAT,
    metadata: Optional[Dict[str, Any]] = None,
) -> LandslideBaselineResult:
    """Compute normalized L04 susceptibility from caller-supplied factor grids."""
    configured = dict(weights or get_weights_config()["landslide_baseline"])
    hazard, contributions = weighted_combine(factors, configured, nodata=nodata)
    return LandslideBaselineResult(
        hazard=hazard,
        factors={name: np.asarray(value, dtype=np.float32) for name, value in factors.items()},
        nodata_mask=hazard == nodata,
        contributions=contributions,
        metadata=metadata or {"layer": "L04", "model_version": "L04-baseline-1.0", "weights": configured},
    )


def write_landslide_hazard_raster(
    output_path: Union[str, Path],
    result: LandslideBaselineResult,
    grid: CanonicalGridDefinition,
) -> Path:
    """Write a normalized L04 GeoTIFF using an existing L03 canonical grid."""
    _require_canonical_grid(grid)
    path = Path(output_path)
    if result.hazard.shape != (grid.height, grid.width):
        raise LandslideModelError("Hazard array dimensions do not match the canonical grid")
    valid = result.hazard != DEFAULT_NODATA_FLOAT
    if np.any(~np.isfinite(result.hazard[valid])) or np.any((result.hazard[valid] < 0.0) | (result.hazard[valid] > 1.0)):
        raise LandslideModelError("Hazard output contains values outside [0, 1]")
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=grid.height, width=grid.width, count=1,
                       dtype="float32", crs=grid.crs, transform=grid.transform,
                       nodata=DEFAULT_NODATA_FLOAT, compress="deflate") as destination:
        destination.write(result.hazard.astype(np.float32), 1)
        destination.update_tags(
            layer="L04",
            model_version=str(result.metadata.get("model_version", "L04-baseline-1.0")),
            config_version=str(result.metadata.get("config_version", "1.0")),
            factor_names=",".join(sorted(result.factors)),
            nodata_policy="Any selected factor NoData yields cell NoData",
        )
    return path


def _read_vector_file(path: Path) -> gpd.GeoDataFrame:
    """Read a supported vector file through the L01 adapter factory."""
    adapter = get_adapter_for_file(path)
    if not hasattr(adapter, "read"):
        raise LandslideModelError(f"Unsupported vector input: {path}")
    return adapter.read()


def _read_aligned_raster(path: Path, grid: CanonicalGridDefinition, categorical: bool, workspace: Path) -> np.ndarray:
    """Use L03 validation/alignment and return one aligned raster band."""
    with rasterio.open(path) as source:
        if source.crs is None:
            raise LandslideModelError(f"Raster input has no CRS: {path}")
        if source.nodata is None:
            raise LandslideModelError(f"Raster input has no explicit NoData value: {path}")
    aligned_path = path
    aligned, _ = is_aligned_to_canonical_grid(path, grid)
    if not aligned:
        aligned_path = workspace / f"aligned_{path.stem}.tif"
        resample_and_align_raster(path, aligned_path, grid, is_categorical=categorical, output_nodata=DEFAULT_NODATA_FLOAT)
    with rasterio.open(aligned_path) as source:
        return source.read(1).astype(np.float32)


def run_landslide_baseline(
    input_paths: Mapping[str, Union[str, Path]],
    grid: CanonicalGridDefinition,
    output_path: Union[str, Path],
    categorical_mappings: Optional[Mapping[str, Mapping[Union[int, float, str], float]]] = None,
    proximity_parameters_m: Optional[Mapping[str, float]] = None,
    weights: Optional[Mapping[str, float]] = None,
    model_version: str = "L04-baseline-1.0",
    config_version: str = "1.0",
) -> LandslideBaselineResult:
    """Run L04 from validated files and write one canonical-grid GeoTIFF.

    ``study_area`` and ``dem`` are required. Other factor files are optional;
    supplied factors participate, omitted factors are excluded and weights are
    renormalized. Real files are never synthesized when an input is absent.
    """
    _require_canonical_grid(grid)
    allowed_inputs = {"study_area", "dem"} | L04_FACTOR_NAMES
    unknown_inputs = set(input_paths) - allowed_inputs
    if unknown_inputs:
        raise LandslideModelError(f"Unknown L04 input names: {sorted(unknown_inputs)}")
    required = {"study_area", "dem"}
    missing = sorted(name for name in required if name not in input_paths or not Path(input_paths[name]).is_file())
    if missing:
        raise LandslideDataPendingError(f"Required L04 real inputs are absent: {missing}")
    mappings = categorical_mappings or {}
    proximity = proximity_parameters_m or {}
    configured_weights = validate_weights(dict(weights or get_weights_config()["landslide_baseline"]))
    factors: Dict[str, np.ndarray] = {}

    with TemporaryDirectory(prefix="l04_") as temporary_directory:
        workspace = Path(temporary_directory)
        boundary = load_and_prepare_study_area(_read_vector_file(Path(input_paths["study_area"])))
        left, bottom, right, top = array_bounds(grid.height, grid.width, grid.transform)
        if not boundary.geometry.union_all().intersects(box(left, bottom, right, top)):
            raise LandslideModelError("Study-area boundary has no spatial overlap with the canonical grid")
        boundary_mask = geometry_mask(
            list(boundary.geometry),
            out_shape=(grid.height, grid.width),
            transform=grid.transform,
            invert=True,
        )
        dem = _read_aligned_raster(Path(input_paths["dem"]), grid, categorical=False, workspace=workspace)
        slope_factor, _ = slope_factor_from_dem(dem)
        factors["slope"] = np.where(boundary_mask, slope_factor, DEFAULT_NODATA_FLOAT).astype(np.float32)

        for factor_name in ("lulc", "geology"):
            if factor_name in input_paths:
                if factor_name not in mappings:
                    raise LandslideModelError(f"A source-specific {factor_name} mapping is required")
                values = _read_aligned_raster(Path(input_paths[factor_name]), grid, categorical=True, workspace=workspace)
                factor = reclassify_categorical(values, mappings[factor_name])
                factors[factor_name] = np.where(boundary_mask, factor, DEFAULT_NODATA_FLOAT).astype(np.float32)

        for factor_name, function in (("drainage", drainage_proximity_factor), ("roads", road_proximity_factor)):
            if factor_name in input_paths:
                if factor_name not in proximity:
                    raise LandslideModelError(f"A max distance parameter is required for {factor_name} proximity")
                vector = _read_vector_file(Path(input_paths[factor_name]))
                factor = function(vector, grid, proximity[factor_name])
                factors[factor_name] = np.where(boundary_mask, factor, DEFAULT_NODATA_FLOAT).astype(np.float32)

        if "inventory" in input_paths:
            inventory = validate_landslide_inventory(_read_vector_file(Path(input_paths["inventory"])))
            evidence = inventory_evidence(inventory.inventory, (grid.height, grid.width), grid.transform)
            factors["inventory"] = np.where(boundary_mask, evidence.evidence, DEFAULT_NODATA_FLOAT).astype(np.float32)

        missing_factor_weights = set(factors) - set(configured_weights)
        if missing_factor_weights:
            raise LandslideModelError(
                f"No configured weights for selected L04 factors: {sorted(missing_factor_weights)}"
            )
        selected_weights = {name: configured_weights[name] for name in factors}
        selected_weight_total = sum(selected_weights.values())
        if selected_weight_total <= 0.0:
            raise LandslideModelError("Selected L04 factor weights have zero total")
        metadata = build_provenance_metadata(
            input_paths,
            {name: value / selected_weight_total for name, value in selected_weights.items()},
            model_version=model_version,
            config_version=config_version,
        )
        metadata["canonical_grid"] = grid.to_dict()
        metadata["factor_names"] = sorted(factors)
        metadata["slope_classes"] = get_hazards_config()["landslide_baseline"]["slope_classes"]
        metadata["categorical_mappings"] = {name: dict(mapping) for name, mapping in mappings.items()}
        metadata["proximity_parameters_m"] = dict(proximity)
        result = compute_landslide_baseline(factors, weights=configured_weights, metadata=metadata)
        write_landslide_hazard_raster(output_path, result, grid)
        return result