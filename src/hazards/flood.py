"""Layer L05 deterministic flood and flash-flood baseline framework.

L05 deliberately does not perform hydraulic simulation, rainfall triggering, or
flash-flood prediction. It provides auditable evidence processing for real
river geometry and documented observed flood extents.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import CRS
from rasterio.enums import MergeAlg
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import Affine, array_bounds
from shapely.geometry import Point, box
from shapely.validation import make_valid

from src.common.config import get_config_dir, get_weights_config
from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.common.provenance import compute_sha256
from src.ingestion.adapters import get_adapter_for_file
from src.spatial.grid import DEFAULT_NODATA_FLOAT, CanonicalGridDefinition
from src.spatial.raster import is_aligned_to_canonical_grid, resample_and_align_raster
from src.spatial.vector import validate_and_reproject_vector, load_and_prepare_study_area


L05_FACTOR_NAMES = frozenset({"river_proximity", "observed_extent"})


class FloodModelError(ValueError):
    """Raised when an L05 input, factor, or configuration is invalid."""


class FloodDataPendingError(FloodModelError):
    """Raised when required real L05 input files are absent."""


@dataclass(frozen=True)
class FloodBaselineResult:
    """Flood hazard grid and explainability artifacts."""

    hazard: np.ndarray
    factors: Dict[str, np.ndarray]
    nodata_mask: np.ndarray
    contributions: Dict[str, np.ndarray]
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class FloodInventoryEvidenceResult:
    """Observed flood extent evidence with explicit readiness status."""

    evidence: np.ndarray
    status: str
    overlapping_records: int


@dataclass(frozen=True)
class HydrologicalValidationResult:
    """Validated observations without deriving unsupported hydraulic thresholds."""

    observations: pd.DataFrame
    report: Dict[str, Any]


def _require_canonical_grid(grid: CanonicalGridDefinition) -> None:
    if CRS.from_user_input(grid.crs) != CRS.from_user_input(CANONICAL_PROJECTED_CRS_STR):
        raise FloodModelError(f"L05 requires a canonical grid in {CANONICAL_PROJECTED_CRS_STR}")


def normalize_flood_factor(values: np.ndarray, nodata: float = DEFAULT_NODATA_FLOAT) -> np.ndarray:
    """Validate an already normalized flood evidence grid without clipping."""
    array = np.asarray(values, dtype=np.float32)
    valid = array != nodata
    if np.any(~np.isfinite(array[valid])):
        raise FloodModelError("Flood factor contains NaN or infinity")
    if np.any((array[valid] < 0.0) | (array[valid] > 1.0)):
        raise FloodModelError("Flood factor values must be within [0, 1]")
    return array


def validate_flood_weights(weights: Mapping[str, float], tolerance: float = 1e-6) -> Dict[str, float]:
    """Validate positive known L05 weights summing to one."""
    if not weights:
        raise FloodModelError("At least one L05 factor weight is required")
    unknown = set(weights) - L05_FACTOR_NAMES
    if unknown:
        raise FloodModelError(f"Unknown L05 factor weights: {sorted(unknown)}")
    result = {name: float(value) for name, value in weights.items()}
    if any(not np.isfinite(value) or value <= 0.0 for value in result.values()):
        raise FloodModelError("L05 factor weights must be finite and positive")
    if not np.isclose(sum(result.values()), 1.0, atol=tolerance):
        raise FloodModelError("L05 factor weights must sum to 1.0")
    return result


def weighted_flood_combine(
    factors: Mapping[str, np.ndarray],
    weights: Mapping[str, float],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Combine selected normalized evidence; omitted factors are renormalized."""
    if not factors:
        raise FloodModelError("At least one usable L05 factor is required")
    configured = validate_flood_weights(weights)
    unknown = set(factors) - L05_FACTOR_NAMES
    if unknown:
        raise FloodModelError(f"Unknown L05 factors: {sorted(unknown)}")
    missing_weights = set(factors) - set(configured)
    if missing_weights:
        raise FloodModelError(f"No configured weights for L05 factors: {sorted(missing_weights)}")
    selected = {name: configured[name] for name in factors}
    selected_total = sum(selected.values())
    if selected_total <= 0.0:
        raise FloodModelError("Selected L05 factor weights have zero total")
    selected = {name: value / selected_total for name, value in selected.items()}
    arrays = {name: normalize_flood_factor(value, nodata) for name, value in factors.items()}
    shape = next(iter(arrays.values())).shape
    if any(array.shape != shape for array in arrays.values()):
        raise FloodModelError("All L05 factor arrays must have the same shape")
    valid = np.ones(shape, dtype=bool)
    for array in arrays.values():
        valid &= np.isfinite(array) & (array != nodata)
    contributions = {name: np.where(valid, array * selected[name], nodata).astype(np.float32) for name, array in arrays.items()}
    hazard = np.full(shape, nodata, dtype=np.float32)
    if np.any(valid):
        hazard[valid] = np.clip(sum(contribution[valid] for contribution in contributions.values()), 0.0, 1.0)
    return hazard, contributions


def flood_proximity_factor(
    river_network: gpd.GeoDataFrame,
    grid: CanonicalGridDefinition,
    max_distance_m: Optional[float],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> np.ndarray:
    """Derive river-proximity evidence with ``max(0, 1 - distance/D)``."""
    _require_canonical_grid(grid)
    if max_distance_m is None or not np.isfinite(max_distance_m) or max_distance_m <= 0.0:
        raise FloodModelError("A finite positive max_distance_m is required for river proximity")
    if river_network.crs is None:
        raise FloodModelError("River network has no defined CRS")
    if river_network.empty:
        raise FloodModelError("River network is empty")
    prepared = validate_and_reproject_vector(river_network, target_crs=CANONICAL_PROJECTED_CRS_STR)
    prepared["geometry"] = prepared.geometry.apply(make_valid)
    prepared = prepared[prepared.geometry.notna() & ~prepared.geometry.is_empty & prepared.geometry.is_valid]
    if prepared.empty:
        raise FloodModelError("River network has no usable geometries")
    river_geometry = prepared.geometry.union_all()
    result = np.full((grid.height, grid.width), nodata, dtype=np.float32)
    for row in range(grid.height):
        for col in range(grid.width):
            x, y = grid.cell_center_coords(row, col)
            distance_m = river_geometry.distance(Point(x, y))
            result[row, col] = max(0.0, 1.0 - distance_m / float(max_distance_m))
    return result


def validate_flood_inventory(
    inventory: gpd.GeoDataFrame,
    target_crs: str = CANONICAL_PROJECTED_CRS_STR,
) -> Tuple[gpd.GeoDataFrame, Dict[str, int]]:
    """Repair, reproject, and report observed flood-extent geometries."""
    if inventory.crs is None:
        raise FloodModelError("Flood inventory has no defined CRS")
    original_count = len(inventory)
    working = inventory.copy()
    working["geometry"] = working.geometry.apply(lambda geometry: make_valid(geometry) if geometry is not None else geometry)
    working = working[working.geometry.notna() & ~working.geometry.is_empty & working.geometry.is_valid].copy()
    working = working.to_crs(target_crs)
    working["_geometry_key"] = working.geometry.apply(lambda geometry: geometry.wkb_hex)
    working = working.drop_duplicates("_geometry_key").drop(columns=["_geometry_key"])
    return working, {
        "input_records": original_count,
        "output_records": len(working),
        "removed_records": original_count - len(working),
    }


def observed_flood_extent_evidence(
    inventory: gpd.GeoDataFrame,
    shape: Tuple[int, int],
    transform: Affine,
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> FloodInventoryEvidenceResult:
    """Rasterize observed extent presence; zero overlap is an explicit error."""
    if inventory.crs is None:
        raise FloodModelError("Flood inventory has no defined CRS")
    if inventory.empty:
        return FloodInventoryEvidenceResult(np.full(shape, nodata, dtype=np.float32), "empty_inventory", 0)
    prepared, _ = validate_flood_inventory(inventory)
    left, bottom, right, top = array_bounds(shape[0], shape[1], transform)
    overlap = prepared[prepared.geometry.intersects(box(left, bottom, right, top))]
    if overlap.empty:
        raise FloodModelError("Flood inventory has no spatial overlap with the target grid")
    evidence = rasterize(
        ((geometry, 1.0) for geometry in overlap.geometry),
        out_shape=shape,
        transform=transform,
        fill=0.0,
        dtype="float32",
        merge_alg=MergeAlg.add,
    )
    return FloodInventoryEvidenceResult(np.clip(evidence, 0.0, 1.0), "valid_overlap", len(overlap))


def validate_hydrological_observations(
    observations: pd.DataFrame,
    station_geometry: Optional[gpd.GeoDataFrame] = None,
    study_area: Optional[gpd.GeoDataFrame] = None,
) -> HydrologicalValidationResult:
    """Validate observed discharge/water-level records without inventing thresholds."""
    required = {"station_id", "timestamp"}
    value_columns = [column for column in ("discharge", "water_level") if column in observations.columns]
    missing = required - set(observations.columns)
    if missing or not value_columns:
        raise FloodModelError("Hydrological data require station_id, timestamp, and discharge or water_level")
    if observations.empty:
        raise FloodModelError("Hydrological observations are empty")
    working = observations.copy()
    if working["station_id"].isna().any() or working["station_id"].astype(str).str.strip().eq("").any():
        raise FloodModelError("Hydrological station_id contains missing or empty values")
    parsed = pd.to_datetime(working["timestamp"], errors="coerce", utc=True)
    if parsed.isna().any():
        raise FloodModelError("Hydrological timestamps contain invalid values")
    working["timestamp"] = parsed
    for column in value_columns:
        numeric = pd.to_numeric(working[column], errors="coerce")
        if numeric.isna().any() or (~np.isfinite(numeric)).any() or (numeric < 0.0).any():
            raise FloodModelError(f"Hydrological column '{column}' contains invalid values")
        working[column] = numeric.astype(float)
    if station_geometry is not None:
        if station_geometry.crs is None:
            raise FloodModelError("Hydrological station geometry has no defined CRS")
        stations = validate_and_reproject_vector(station_geometry)
        if stations.empty:
            raise FloodModelError("Hydrological station geometry is empty")
        if study_area is not None:
            if study_area.crs is None:
                raise FloodModelError("Hydrological study-area geometry has no defined CRS")
            area = validate_and_reproject_vector(study_area)
            if area.empty or not stations.geometry.intersects(area.geometry.union_all()).any():
                raise FloodModelError("Hydrological stations have no spatial association with the study area")
    return HydrologicalValidationResult(
        observations=working,
        report={"records": len(working), "value_columns": value_columns, "temporal_min": working["timestamp"].min().isoformat(), "temporal_max": working["timestamp"].max().isoformat()},
    )


def build_flood_provenance(
    input_paths: Mapping[str, Union[str, Path]],
    weights: Mapping[str, float],
    grid: CanonicalGridDefinition,
    parameters: Mapping[str, Any],
    model_version: str = "L05-baseline-1.0",
    config_version: str = "1.0",
) -> Dict[str, Any]:
    """Build reproducibility metadata for an L05 run."""
    return {
        "layer": "L05",
        "model_version": model_version,
        "config_version": config_version,
        "method": "deterministic flood evidence combination",
        "crs": CANONICAL_PROJECTED_CRS_STR,
        "resolution_m": 30.0,
        "canonical_grid": grid.to_dict(),
        "weights": dict(weights),
        "parameters": dict(parameters),
        "inputs": {
            name: {"path": Path(path).as_posix(), "checksum_sha256": compute_sha256(Path(path)) if Path(path).is_file() else None}
            for name, path in input_paths.items()
        },
        "nodata_policy": "Any selected factor NoData yields cell NoData",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def compute_flood_baseline(
    factors: Mapping[str, np.ndarray],
    weights: Optional[Mapping[str, float]] = None,
    nodata: float = DEFAULT_NODATA_FLOAT,
    metadata: Optional[Dict[str, Any]] = None,
) -> FloodBaselineResult:
    """Compute normalized deterministic L05 flood hazard evidence."""
    configured = dict(weights or get_weights_config()["flood_baseline"])
    hazard, contributions = weighted_flood_combine(factors, configured, nodata)
    return FloodBaselineResult(
        hazard=hazard,
        factors={name: np.asarray(value, dtype=np.float32) for name, value in factors.items()},
        nodata_mask=hazard == nodata,
        contributions=contributions,
        metadata=metadata or {"layer": "L05", "model_version": "L05-baseline-1.0", "weights": configured},
    )


def write_flood_hazard_raster(
    output_path: Union[str, Path],
    result: FloodBaselineResult,
    grid: CanonicalGridDefinition,
) -> Path:
    """Write a validated canonical-grid L05 GeoTIFF."""
    _require_canonical_grid(grid)
    if result.hazard.shape != (grid.height, grid.width):
        raise FloodModelError("Flood hazard dimensions do not match canonical grid")
    valid = result.hazard != DEFAULT_NODATA_FLOAT
    if np.any(~np.isfinite(result.hazard[valid])) or np.any((result.hazard[valid] < 0.0) | (result.hazard[valid] > 1.0)):
        raise FloodModelError("Flood hazard output contains values outside [0, 1]")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype="float32", crs=grid.crs, transform=grid.transform, nodata=DEFAULT_NODATA_FLOAT, compress="deflate") as destination:
        destination.write(result.hazard.astype(np.float32), 1)
        destination.update_tags(layer="L05", model_version=str(result.metadata.get("model_version", "L05-baseline-1.0")), nodata_policy=str(result.metadata.get("nodata_policy", "Any selected factor NoData yields cell NoData")))
    return path


def _read_vector_file(path: Path) -> gpd.GeoDataFrame:
    adapter = get_adapter_for_file(path)
    return adapter.read()


def run_flood_baseline(
    input_paths: Mapping[str, Union[str, Path]],
    grid: CanonicalGridDefinition,
    output_path: Union[str, Path],
    max_distance_m: Optional[float] = None,
    weights: Optional[Mapping[str, float]] = None,
    model_version: str = "L05-baseline-1.0",
    config_version: str = "1.0",
) -> FloodBaselineResult:
    """Run L05 from real study boundary, river network, and optional extent files."""
    _require_canonical_grid(grid)
    allowed_inputs = {"study_area", "river_network", "flood_extent"}
    unknown_inputs = set(input_paths) - allowed_inputs
    if unknown_inputs:
        raise FloodModelError(f"Unknown L05 input names: {sorted(unknown_inputs)}")
    required = {"study_area", "river_network"}
    missing = sorted(name for name in required if name not in input_paths or not Path(input_paths[name]).is_file())
    if missing:
        raise FloodDataPendingError(f"Required L05 real inputs are absent: {missing}")
    if max_distance_m is None:
        raise FloodModelError("L05 river proximity requires explicit max_distance_m")
    configured = validate_flood_weights(dict(weights or get_weights_config()["flood_baseline"]))
    boundary = load_and_prepare_study_area(_read_vector_file(Path(input_paths["study_area"])))
    left, bottom, right, top = array_bounds(grid.height, grid.width, grid.transform)
    if not boundary.geometry.union_all().intersects(box(left, bottom, right, top)):
        raise FloodModelError("Study-area boundary has no spatial overlap with the canonical grid")
    mask = geometry_mask(list(boundary.geometry), out_shape=(grid.height, grid.width), transform=grid.transform, invert=True)
    river = _read_vector_file(Path(input_paths["river_network"]))
    factors: Dict[str, np.ndarray] = {"river_proximity": np.where(mask, flood_proximity_factor(river, grid, max_distance_m), DEFAULT_NODATA_FLOAT).astype(np.float32)}
    parameters: Dict[str, Any] = {"max_distance_m": float(max_distance_m), "flash_flood_supported": False}
    if "flood_extent" in input_paths:
        extent = observed_flood_extent_evidence(_read_vector_file(Path(input_paths["flood_extent"])), (grid.height, grid.width), grid.transform)
        factors["observed_extent"] = np.where(mask, extent.evidence, DEFAULT_NODATA_FLOAT).astype(np.float32)
        parameters["flood_extent_status"] = extent.status
    selected = {name: configured[name] for name in factors if name in configured}
    if len(selected) != len(factors):
        missing_weights = sorted(set(factors) - set(selected))
        raise FloodModelError(f"No configured weights for L05 factors: {missing_weights}")
    total = sum(selected.values())
    if total <= 0.0:
        raise FloodModelError("Selected L05 factor weights have zero total")
    metadata = build_flood_provenance(input_paths, {name: value / total for name, value in selected.items()}, grid, parameters, model_version, config_version)
    result = compute_flood_baseline(factors, configured, metadata=metadata)
    write_flood_hazard_raster(output_path, result, grid)
    return result


def audit_l05_data_readiness(repo_root: Union[str, Path]) -> Dict[str, Any]:
    """Report presence of documented L05 data without treating markers as data."""
    root = Path(repo_root)
    data_root = root / "data"
    expected = {
        "study_area": ("admin", "boundary", "chamoli"),
        "dem": ("dem", "elevation", "copernicus", "srtm", "cartodem"),
        "river_network": ("river", "drainage", "stream", "network"),
        "discharge": ("discharge", "flow", "telemetry"),
        "water_level": ("water_level", "waterlevel", "gauge"),
        "flood_inventory": ("flood", "inundation", "flash"),
    }
    files = [path for path in data_root.rglob("*") if path.is_file() and path.name != ".gitkeep"] if data_root.exists() else []
    datasets = {}
    for name, terms in expected.items():
        matches = [path for path in files if any(term in path.name.lower() or term in str(path.parent).lower() for term in terms)]
        datasets[name] = {"present": bool(matches), "paths": [str(path.relative_to(root).as_posix()) for path in matches], "usable": False, "suitable_for_l05": False}
    return {"data_root": data_root.as_posix(), "datasets": datasets, "real_data_available": bool(files), "flash_flood_supported": False}