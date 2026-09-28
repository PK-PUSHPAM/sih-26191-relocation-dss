"""Layer L07 deterministic multi-hazard risk combination.

L07 combines normalized L04/L05 hazards and the approved binary L06 trigger
index. It does not implement red zones, risk tiers, persistence, APIs, or later
layers.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
from affine import Affine
from pyproj import CRS

from src.common.config import get_weights_config
from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.hazards.rainfall import RainfallEvaluationState, RainfallGridResult
from src.spatial.grid import CANONICAL_RESOLUTION_METERS, DEFAULT_NODATA_FLOAT, CanonicalGridDefinition


class MultiHazardModelError(ValueError):
    """Raised when an L07 input, weight, or grid contract is invalid."""


class QualityState(str, Enum):
    """Approved L07 per-cell quality/evaluability states."""

    COMPLETE = "complete"
    NON_EVALUABLE = "non_evaluable"
    INVALID = "invalid"


L07_HAZARDS = ("landslide", "flood", "rainfall")
L07_FORMULA_VERSION = "H-0.45-0.35-0.20"
L07_MODEL_VERSION = "L07-combination-1.0"


@dataclass(frozen=True)
class HazardGridInput:
    """Normalized L04 or L05 grid plus its source contract."""

    hazard_name: str
    values: np.ndarray
    grid: CanonicalGridDefinition
    model_version: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    quality_state: QualityState = QualityState.COMPLETE


@dataclass(frozen=True)
class RainfallCombinationInput:
    """L06 binary trigger grid and state/provenance metadata for L07."""

    trigger_grid: np.ndarray
    states_by_cell: Mapping[int, RainfallEvaluationState]
    grid: CanonicalGridDefinition
    provenance: Mapping[str, Any] = field(default_factory=dict)
    model_version: str = "L06-trigger-1.0"

    @classmethod
    def from_l06(
        cls,
        result: RainfallGridResult,
        grid: CanonicalGridDefinition,
        provenance: Optional[Mapping[str, Any]] = None,
    ) -> "RainfallCombinationInput":
        return cls(
            trigger_grid=result.trigger_grid,
            states_by_cell=result.states_by_cell,
            grid=grid,
            provenance=dict(provenance or result.metadata.get("provenance") or {}),
            model_version=str(result.metadata.get("model_version", "L06-trigger-1.0")),
        )


@dataclass(frozen=True)
class RiskCellRecord:
    """Persistence-ready L07 fields; L08-owned fields are intentionally absent."""

    cell_id: int
    h_landslide: Optional[float]
    h_flood: Optional[float]
    h_rain: Optional[float]
    combined_risk: Optional[float]
    quality_flag: QualityState
    geometry: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "h_landslide": self.h_landslide,
            "h_flood": self.h_flood,
            "h_rain": self.h_rain,
            "combined_risk": self.combined_risk,
            "quality_flag": self.quality_flag.value,
            "geometry": self.geometry,
        }


@dataclass(frozen=True)
class MultiHazardResult:
    """L07 combined grid, per-cell quality, explanations, and provenance."""

    combined_risk: np.ndarray
    hazard_inputs: Dict[str, np.ndarray]
    quality_grid: np.ndarray
    quality_by_cell: Dict[int, QualityState]
    contributions: Dict[str, np.ndarray]
    records: Tuple[RiskCellRecord, ...]
    metadata: Dict[str, Any]


def validate_l07_weights(weights: Optional[Mapping[str, float]] = None) -> Dict[str, float]:
    """Load and validate the existing multi-hazard weights configuration."""
    configured = dict(get_weights_config().get("multi_hazard_risk", {}) if weights is None else weights)
    expected = {"landslide_weight", "flood_weight", "rainfall_weight"}
    if set(configured) != expected:
        raise MultiHazardModelError("L07 weights must define exactly landslide, flood, and rainfall weights")
    try:
        result = {name.removesuffix("_weight"): float(value) for name, value in configured.items()}
    except (TypeError, ValueError) as exc:
        raise MultiHazardModelError("L07 hazard weights must be numeric") from exc
    if any(not np.isfinite(value) or value <= 0.0 for value in result.values()):
        raise MultiHazardModelError("L07 hazard weights must be finite and positive")
    if not np.isclose(sum(result.values()), 1.0, atol=1e-6):
        raise MultiHazardModelError("L07 hazard weights must sum to 1.0")
    return result


def validate_l07_grid(grid: CanonicalGridDefinition) -> None:
    """Enforce the existing L03 canonical CRS, resolution, and transform."""
    if CRS.from_user_input(grid.crs) != CRS.from_user_input(CANONICAL_PROJECTED_CRS_STR):
        raise MultiHazardModelError(f"L07 requires grid CRS {CANONICAL_PROJECTED_CRS_STR}")
    if not np.isclose(grid.resolution, CANONICAL_RESOLUTION_METERS):
        raise MultiHazardModelError("L07 requires a 30 m canonical grid")
    expected = Affine(
        CANONICAL_RESOLUTION_METERS, 0.0, grid.x_min,
        0.0, -CANONICAL_RESOLUTION_METERS, grid.y_max,
    )
    if grid.transform != expected:
        raise MultiHazardModelError("L07 requires the canonical unrotated grid transform")


def _validate_hazard_grid(hazard: HazardGridInput, grid: CanonicalGridDefinition, expected_name: str) -> np.ndarray:
    if hazard.hazard_name != expected_name:
        raise MultiHazardModelError(f"Expected L07 hazard '{expected_name}', got '{hazard.hazard_name}'")
    validate_l07_grid(hazard.grid)
    if hazard.grid.to_dict() != grid.to_dict():
        raise MultiHazardModelError(f"L07 {expected_name} grid does not match the canonical grid")
    if not isinstance(hazard.quality_state, QualityState):
        raise MultiHazardModelError(f"Invalid quality state for {expected_name}")
    array = np.asarray(hazard.values, dtype=np.float32)
    if array.shape != (grid.height, grid.width):
        raise MultiHazardModelError(f"L07 {expected_name} dimensions do not match the canonical grid")
    valid = array != DEFAULT_NODATA_FLOAT
    if np.any(~np.isfinite(array[valid])):
        raise MultiHazardModelError(f"L07 {expected_name} contains NaN or infinity")
    if np.any((array[valid] < 0.0) | (array[valid] > 1.0)):
        raise MultiHazardModelError(f"L07 {expected_name} values must be within [0,1]")
    return array


def _rainfall_values(rainfall: RainfallCombinationInput, grid: CanonicalGridDefinition) -> Tuple[np.ndarray, np.ndarray]:
    """Map only L06 trigger states to R; rainfall millimetres are never used."""
    validate_l07_grid(rainfall.grid)
    if rainfall.grid.to_dict() != grid.to_dict():
        raise MultiHazardModelError("L07 rainfall grid does not match the canonical grid")
    array = np.asarray(rainfall.trigger_grid, dtype=np.float32)
    if array.shape != (grid.height, grid.width):
        raise MultiHazardModelError("L07 rainfall dimensions do not match the canonical grid")
    valid_grid_values = array != DEFAULT_NODATA_FLOAT
    if np.any(~np.isfinite(array[valid_grid_values])) or np.any(~np.isin(array[valid_grid_values], (0.0, 1.0))):
        raise MultiHazardModelError("L07 rainfall input must contain only binary trigger values or NoData")
    for cell_id, state in rainfall.states_by_cell.items():
        if isinstance(cell_id, bool) or not isinstance(cell_id, int) or not 0 <= cell_id < grid.total_cells:
            raise MultiHazardModelError(f"L07 rainfall state cell_id {cell_id!r} is outside the canonical grid")
        if not isinstance(state, RainfallEvaluationState):
            raise MultiHazardModelError(f"L07 rainfall state for cell {cell_id} is invalid")
    for cell_id in range(grid.total_cells):
        row, col = grid.row_col_from_cell_id(cell_id)
        if array[row, col] != DEFAULT_NODATA_FLOAT and cell_id not in rainfall.states_by_cell:
            raise MultiHazardModelError(f"L07 rainfall trigger value has no L06 state for cell {cell_id}")
    values = np.full(array.shape, DEFAULT_NODATA_FLOAT, dtype=np.float32)
    quality = np.full(array.shape, QualityState.NON_EVALUABLE.value, dtype=object)
    for cell_id in range(grid.total_cells):
        row, col = grid.row_col_from_cell_id(cell_id)
        state = rainfall.states_by_cell.get(cell_id)
        if state in (RainfallEvaluationState.TRIGGERED, RainfallEvaluationState.NOT_TRIGGERED):
            expected = 1.0 if state == RainfallEvaluationState.TRIGGERED else 0.0
            if array[row, col] != DEFAULT_NODATA_FLOAT and array[row, col] != expected:
                raise MultiHazardModelError(f"L07 rainfall trigger state conflicts with trigger grid at cell {cell_id}")
            values[row, col] = expected
            quality[row, col] = QualityState.COMPLETE.value
        elif state in (RainfallEvaluationState.INVALID_DATA, RainfallEvaluationState.INVALID_CONFIGURATION):
            quality[row, col] = QualityState.INVALID.value
        elif state is None and array[row, col] in (0.0, 1.0):
            values[row, col] = array[row, col]
            quality[row, col] = QualityState.COMPLETE.value
    return values, quality


def combine_multi_hazard(
    grid: CanonicalGridDefinition,
    landslide: Optional[HazardGridInput],
    flood: Optional[HazardGridInput],
    rainfall: Optional[RainfallCombinationInput],
    weights: Optional[Mapping[str, float]] = None,
    combination_timestamp: Optional[datetime] = None,
) -> MultiHazardResult:
    """Compute H = 0.45L + 0.35F + 0.20R with strict per-cell NoData."""
    validate_l07_grid(grid)
    selected_weights = validate_l07_weights(weights)
    landslide_values = _validate_hazard_grid(landslide, grid, "landslide") if landslide else None
    flood_values = _validate_hazard_grid(flood, grid, "flood") if flood else None
    if rainfall:
        rainfall_values, rainfall_quality = _rainfall_values(rainfall, grid)
    else:
        rainfall_values = np.full((grid.height, grid.width), DEFAULT_NODATA_FLOAT, dtype=np.float32)
        rainfall_quality = np.full((grid.height, grid.width), QualityState.NON_EVALUABLE.value, dtype=object)

    l_values = landslide_values if landslide_values is not None else np.full_like(rainfall_values, DEFAULT_NODATA_FLOAT)
    f_values = flood_values if flood_values is not None else np.full_like(rainfall_values, DEFAULT_NODATA_FLOAT)
    combined = np.full((grid.height, grid.width), DEFAULT_NODATA_FLOAT, dtype=np.float32)
    quality_grid = np.full((grid.height, grid.width), QualityState.COMPLETE.value, dtype=object)
    contributions = {name: np.full_like(combined, DEFAULT_NODATA_FLOAT) for name in L07_HAZARDS}
    quality_by_cell: Dict[int, QualityState] = {}
    records = []
    for cell_id in range(grid.total_cells):
        row, col = grid.row_col_from_cell_id(cell_id)
        cell_values = {"landslide": l_values[row, col], "flood": f_values[row, col], "rainfall": rainfall_values[row, col]}
        invalid = (landslide is not None and landslide.quality_state == QualityState.INVALID) or (flood is not None and flood.quality_state == QualityState.INVALID) or rainfall_quality[row, col] == QualityState.INVALID.value
        source_non_evaluable = (
            (landslide is not None and landslide.quality_state == QualityState.NON_EVALUABLE)
            or (flood is not None and flood.quality_state == QualityState.NON_EVALUABLE)
        )
        missing = any(value == DEFAULT_NODATA_FLOAT for value in cell_values.values()) or landslide is None or flood is None or rainfall is None
        state = QualityState.INVALID if invalid else QualityState.NON_EVALUABLE if missing or source_non_evaluable else QualityState.COMPLETE
        quality_grid[row, col] = state.value
        quality_by_cell[cell_id] = state
        if state == QualityState.COMPLETE:
            for name, value in cell_values.items():
                contributions[name][row, col] = value * selected_weights[name]
            combined[row, col] = sum(contributions[name][row, col] for name in L07_HAZARDS)
            if not 0.0 <= combined[row, col] <= 1.0:
                raise MultiHazardModelError(f"L07 combined risk is outside [0,1] at cell {cell_id}")
        records.append(RiskCellRecord(
            cell_id=cell_id,
            h_landslide=_nullable_value(l_values[row, col]),
            h_flood=_nullable_value(f_values[row, col]),
            h_rain=_nullable_value(rainfall_values[row, col]),
            combined_risk=_nullable_value(combined[row, col]),
            quality_flag=state,
            geometry=grid.cell_polygon(row, col),
        ))
    timestamp = combination_timestamp or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise MultiHazardModelError("L07 combination timestamp must be timezone-aware")
    input_metadata = {
        "landslide": _input_metadata(landslide),
        "flood": _input_metadata(flood),
        "rainfall": _rainfall_input_metadata(rainfall),
    }
    metadata = {
        "layer": "L07",
        "model_version": L07_MODEL_VERSION,
        "config_version": str(get_weights_config().get("version", "1.0")),
        "formula_version": L07_FORMULA_VERSION,
        "formula": "H = 0.45L + 0.35F + 0.20R",
        "weights": selected_weights,
        "combination_timestamp": timestamp.isoformat(),
        "crs": CANONICAL_PROJECTED_CRS_STR,
        "resolution_m": CANONICAL_RESOLUTION_METERS,
        "grid": grid.to_dict(),
        "missing_data_policy": "Strict per-cell NoData propagation; no weight renormalization",
        "quality_states": [state.value for state in QualityState],
        "quality_by_cell": {str(cell_id): state.value for cell_id, state in quality_by_cell.items()},
        "inputs": input_metadata,
        "temporal_compatibility": "Metadata relationship only; no validated temporal equivalence claimed",
        "l08_fields_written": False,
    }
    return MultiHazardResult(
        combined_risk=combined,
        hazard_inputs={"landslide": l_values, "flood": f_values, "rainfall": rainfall_values},
        quality_grid=quality_grid,
        quality_by_cell=quality_by_cell,
        contributions=contributions,
        records=tuple(records),
        metadata=metadata,
    )


def _nullable_value(value: float) -> Optional[float]:
    return None if value == DEFAULT_NODATA_FLOAT else float(value)


def _input_metadata(hazard: Optional[HazardGridInput]) -> Optional[Dict[str, Any]]:
    if hazard is None:
        return None
    metadata = dict(hazard.provenance)
    metadata["model_version"] = hazard.model_version
    metadata["quality_state"] = hazard.quality_state.value
    return metadata


def _rainfall_input_metadata(rainfall: Optional[RainfallCombinationInput]) -> Optional[Dict[str, Any]]:
    if rainfall is None:
        return None
    metadata = dict(rainfall.provenance)
    metadata["model_version"] = rainfall.model_version
    metadata["quality_state_scope"] = "per-cell from L06 states"
    return metadata