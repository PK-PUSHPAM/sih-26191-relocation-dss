"""Layer L06 deterministic rainfall-trigger framework.

The module intentionally provides no live API client, spatial interpolation, or
scientifically validated warning threshold. Local/test observations are explicit
inputs and are never labeled operational or real-time.
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from src.common.config import get_thresholds_config
from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.common.provenance import compute_sha256
from src.spatial.grid import CANONICAL_RESOLUTION_METERS, DEFAULT_NODATA_FLOAT, CanonicalGridDefinition
from pyproj import CRS
from affine import Affine


class RainfallModelError(ValueError):
    """Raised when rainfall input, configuration, or spatial mapping is invalid."""


class RainfallValidationError(RainfallModelError):
    """Raised when a rainfall observation cannot satisfy its input contract."""


class MissingTimestampError(RainfallValidationError):
    """Raised when a timestamp field/value is absent."""


class InvalidTimestampError(RainfallValidationError):
    """Raised when a timestamp is present but malformed."""


class InvalidRainfallError(RainfallValidationError):
    """Raised when rainfall is present but not finite and non-negative."""


class RainfallConfigurationError(RainfallModelError):
    """Raised when trigger configuration is absent or invalid."""


class DuplicateObservationError(RainfallValidationError):
    """Raised when a provider returns duplicate observation identities."""


class RainfallEvaluationState(str, Enum):
    """Explicit states for trigger evaluation and provider availability."""

    TRIGGERED = "triggered"
    NOT_TRIGGERED = "not_triggered"
    PROVIDER_AVAILABLE = "provider_available"
    MISSING_DATA = "missing_data"
    INVALID_DATA = "invalid_data"
    MISSING_TIMESTAMP = "missing_timestamp"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    INCOMPLETE_WINDOW = "incomplete_window"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_CONFIGURATION = "invalid_configuration"


@dataclass(frozen=True)
class RainfallProvenance:
    """Source metadata carried with every provider result."""

    source_id: str
    provider_name: str
    source_kind: str
    source_path: Optional[str] = None
    checksum_sha256: Optional[str] = None
    operational: bool = False
    real_time: bool = False
    temporal_coverage: Optional[Dict[str, str]] = None
    observation_timestamps: Tuple[str, ...] = ()
    evaluation_window_start: Optional[str] = None
    evaluation_window_end: Optional[str] = None
    evaluation_timestamp: Optional[str] = None
    spatial_id: Optional[Union[int, str]] = None
    rainfall_metric_mm: Optional[float] = None
    threshold_mm: Optional[float] = None
    comparison: Optional[str] = None
    rule_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_kind in {"local_or_test_input", "unavailable"} and (self.operational or self.real_time):
            raise RainfallModelError("Local/test or unavailable rainfall provenance cannot be operational or real-time")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "provider_name": self.provider_name,
            "source_kind": self.source_kind,
            "source_path": self.source_path,
            "checksum_sha256": self.checksum_sha256,
            "operational": self.operational,
            "real_time": self.real_time,
            "temporal_coverage": self.temporal_coverage,
            "observation_timestamps": list(self.observation_timestamps),
            "evaluation_window_start": self.evaluation_window_start,
            "evaluation_window_end": self.evaluation_window_end,
            "evaluation_timestamp": self.evaluation_timestamp,
            "spatial_id": self.spatial_id,
            "rainfall_metric_mm": self.rainfall_metric_mm,
            "threshold_mm": self.threshold_mm,
            "comparison": self.comparison,
            "rule_version": self.rule_version,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RainfallObservation:
    """One observed rainfall value associated with a cell or station."""

    rainfall_mm: Optional[float]
    observed_at: Optional[datetime]
    cell_id: Optional[int] = None
    station_id: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    observation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.cell_id is None and not self.station_id:
            raise RainfallValidationError("Rainfall observation requires cell_id or station_id")
        if self.cell_id is not None and (isinstance(self.cell_id, bool) or not isinstance(self.cell_id, int) or self.cell_id < 0):
            raise RainfallValidationError("Rainfall cell_id must be a non-negative integer")
        if self.observed_at is not None and self.observed_at.tzinfo is None:
            raise RainfallValidationError("Rainfall timestamp must be timezone-aware")
        if self.rainfall_mm is not None:
            try:
                value = float(self.rainfall_mm)
            except (TypeError, ValueError) as exc:
                raise InvalidRainfallError("Rainfall must be numeric or missing") from exc
            if not np.isfinite(value) or value < 0.0:
                raise InvalidRainfallError("Rainfall must be finite and non-negative")
        for name in ("window_start", "window_end"):
            timestamp = getattr(self, name)
            if timestamp is not None and timestamp.tzinfo is None:
                raise RainfallValidationError(f"{name} must be timezone-aware")
        if self.window_start and self.window_end and self.window_start > self.window_end:
            raise RainfallValidationError("Rainfall window_start must not be after window_end")

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> "RainfallObservation":
        """Parse a provider record without converting missing rainfall to zero."""
        raw_timestamp = record.get("observed_at", record.get("timestamp"))
        observed_at = _parse_timestamp(raw_timestamp, "observed_at")
        rainfall = record.get("rainfall_mm")
        if rainfall is None or (isinstance(rainfall, str) and not rainfall.strip()):
            rainfall_value = None
        else:
            try:
                rainfall_value = float(rainfall)
            except (TypeError, ValueError) as exc:
                raise InvalidRainfallError("Rainfall must be numeric or missing") from exc
        return cls(
            rainfall_mm=rainfall_value,
            observed_at=observed_at,
            cell_id=_optional_int(record.get("cell_id")),
            station_id=_optional_text(record.get("station_id")),
            window_start=_parse_optional_timestamp(record.get("window_start"), "window_start"),
            window_end=_parse_optional_timestamp(record.get("window_end"), "window_end"),
            observation_id=_optional_text(record.get("observation_id")),
        )


@dataclass(frozen=True)
class RainfallProviderResult:
    """Provider output, including availability state and provenance."""

    observations: Tuple[RainfallObservation, ...]
    provenance: RainfallProvenance
    state: RainfallEvaluationState = RainfallEvaluationState.PROVIDER_AVAILABLE
    message: Optional[str] = None


class RainfallProvider(Protocol):
    """Replaceable provider contract for historical/local rainfall inputs."""

    def fetch(self, window_start: Optional[datetime] = None, window_end: Optional[datetime] = None) -> RainfallProviderResult:
        """Return observations for an optional UTC time window."""


@dataclass(frozen=True)
class RainfallRule:
    """Deterministic threshold rule; threshold status is explicit and unvalidated."""

    threshold_mm: float
    metric: str = "window_total_mm"
    comparison: str = "greater_equal"
    rule_version: str = "L06-trigger-1.0"
    parameter_status: str = "UNVALIDATED_PROTOTYPE_CONFIGURATION"

    def __post_init__(self) -> None:
        try:
            threshold = float(self.threshold_mm)
        except (TypeError, ValueError) as exc:
            raise RainfallConfigurationError("Rainfall threshold_mm must be numeric") from exc
        object.__setattr__(self, "threshold_mm", threshold)
        if not np.isfinite(threshold) or threshold < 0.0:
            raise RainfallConfigurationError("Rainfall threshold_mm must be finite and non-negative")
        if self.metric != "window_total_mm":
            raise RainfallConfigurationError("Only window_total_mm is supported by L06")
        if self.comparison != "greater_equal":
            raise RainfallConfigurationError("Only greater_equal comparison is supported by L06")

    @classmethod
    def from_config(cls, threshold_mm: Optional[float] = None) -> "RainfallRule":
        """Load the configured rule; no numeric threshold is assumed if absent."""
        configured = get_thresholds_config().get("rainfall_trigger", {})
        selected_threshold = threshold_mm if threshold_mm is not None else configured.get("threshold_mm")
        if selected_threshold is None:
            raise RainfallConfigurationError(
                "No rainfall threshold is configured; provide an explicit unvalidated prototype parameter"
            )
        return cls(
            threshold_mm=float(selected_threshold),
            metric=str(configured.get("metric", "window_total_mm")),
            comparison=str(configured.get("comparison", "greater_equal")),
            rule_version=str(configured.get("rule_version", "L06-trigger-1.0")),
            parameter_status=str(configured.get("parameter_status", "UNVALIDATED_PROTOTYPE_CONFIGURATION")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold_mm": self.threshold_mm,
            "metric": self.metric,
            "comparison": self.comparison,
            "rule_version": self.rule_version,
            "parameter_status": self.parameter_status,
        }


@dataclass(frozen=True)
class RainfallTriggerResult:
    """Explainable output of one rainfall window evaluation."""

    spatial_id: Union[int, str]
    rainfall_metric_mm: Optional[float]
    evaluation_timestamp: Optional[datetime]
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    state: RainfallEvaluationState
    trigger_level: str
    explanation: str
    rule: Optional[RainfallRule]
    provenance: Optional[RainfallProvenance]


@dataclass(frozen=True)
class RainfallGridResult:
    """Canonical-grid rainfall trigger output without spatial interpolation."""

    metric_grid: np.ndarray
    trigger_grid: np.ndarray
    states_by_cell: Dict[int, RainfallEvaluationState]
    results_by_cell: Dict[int, RainfallTriggerResult]
    metadata: Dict[str, Any]


class LocalCsvRainfallProvider:
    """Deterministic local CSV provider for curated or clearly synthetic input.

    This provider is not real-time or operational and performs no interpolation.
    """

    def __init__(self, csv_path: Union[str, Path], source_id: str = "local_rainfall_input") -> None:
        self.csv_path = Path(csv_path)
        self.source_id = source_id

    def fetch(self, window_start: Optional[datetime] = None, window_end: Optional[datetime] = None) -> RainfallProviderResult:
        if (window_start is None) != (window_end is None):
            return RainfallProviderResult(
                (),
                RainfallProvenance(
                    source_id=self.source_id,
                    provider_name="LocalCsvRainfallProvider",
                    source_kind="local_or_test_input",
                    source_path=self.csv_path.as_posix(),
                    checksum_sha256=compute_sha256(self.csv_path) if self.csv_path.is_file() else None,
                    operational=False,
                    real_time=False,
                    metadata={"real_time": False, "operational": False},
                ),
                RainfallEvaluationState.INCOMPLETE_WINDOW,
                "Both window bounds are required",
            )
        if window_start is not None and (
            window_start.tzinfo is None
            or window_end is None
            or window_end.tzinfo is None
            or window_start > window_end
        ):
            return RainfallProviderResult(
                (),
                RainfallProvenance(
                    source_id=self.source_id,
                    provider_name="LocalCsvRainfallProvider",
                    source_kind="local_or_test_input",
                    source_path=self.csv_path.as_posix(),
                    checksum_sha256=compute_sha256(self.csv_path) if self.csv_path.is_file() else None,
                    operational=False,
                    real_time=False,
                    metadata={"real_time": False, "operational": False},
                ),
                RainfallEvaluationState.INVALID_DATA,
                "Rainfall provider window bounds are invalid",
            )
        provenance = RainfallProvenance(
            source_id=self.source_id,
            provider_name="LocalCsvRainfallProvider",
            source_kind="local_or_test_input",
            source_path=self.csv_path.as_posix(),
            checksum_sha256=compute_sha256(self.csv_path) if self.csv_path.is_file() else None,
            operational=False,
            metadata={"real_time": False, "operational": False},
        )
        if not self.csv_path.is_file():
            return RainfallProviderResult((), provenance, RainfallEvaluationState.PROVIDER_UNAVAILABLE, "Rainfall CSV is unavailable")
        try:
            frame = pd.read_csv(self.csv_path, keep_default_na=False)
        except Exception as exc:
            return RainfallProviderResult((), provenance, RainfallEvaluationState.PROVIDER_UNAVAILABLE, str(exc))
        observations: List[RainfallObservation] = []
        identities = set()
        try:
            for record in frame.to_dict(orient="records"):
                observation = RainfallObservation.from_mapping(record)
                identity = (
                    observation.cell_id,
                    observation.station_id,
                    observation.observed_at,
                    observation.window_start,
                    observation.window_end,
                )
                if identity in identities:
                    raise DuplicateObservationError(f"Duplicate rainfall observation: {identity}")
                identities.add(identity)
                observations.append(observation)
        except DuplicateObservationError as exc:
            return RainfallProviderResult((), provenance, RainfallEvaluationState.DUPLICATE_OBSERVATION, str(exc))
        except MissingTimestampError as exc:
            state = RainfallEvaluationState.MISSING_TIMESTAMP
            return RainfallProviderResult((), provenance, state, str(exc))
        except RainfallValidationError as exc:
            state = RainfallEvaluationState.INVALID_DATA
            return RainfallProviderResult((), provenance, state, str(exc))
        if window_start is not None or window_end is not None:
            if window_start is None or window_end is None:
                return RainfallProviderResult((), provenance, RainfallEvaluationState.INCOMPLETE_WINDOW, "Both window bounds are required")
            observations = [observation for observation in observations if observation.observed_at and window_start <= observation.observed_at <= window_end]
        return RainfallProviderResult(tuple(observations), provenance)


class UnavailableRainfallProvider:
    """Explicit provider placeholder when no verified operational source exists."""

    def __init__(self, source_id: str = "unavailable_rainfall_provider") -> None:
        self.source_id = source_id

    def fetch(self, window_start: Optional[datetime] = None, window_end: Optional[datetime] = None) -> RainfallProviderResult:
        return RainfallProviderResult(
            observations=(),
            provenance=RainfallProvenance(
                source_id=self.source_id,
                provider_name="UnavailableRainfallProvider",
                source_kind="unavailable",
                operational=False,
                metadata={"real_time": False, "operational": False},
            ),
            state=RainfallEvaluationState.PROVIDER_UNAVAILABLE,
            message="No verified rainfall provider is available",
        )


def evaluate_rainfall_window(
    observations: Sequence[RainfallObservation],
    spatial_id: Union[int, str],
    rule: Optional[RainfallRule],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    expected_observation_count: Optional[int] = None,
    provenance: Optional[RainfallProvenance] = None,
) -> RainfallTriggerResult:
    """Evaluate a rainfall-total threshold without imputing missing observations."""
    if expected_observation_count is not None and (
        isinstance(expected_observation_count, bool)
        or not isinstance(expected_observation_count, (int, np.integer))
        or expected_observation_count < 0
    ):
        return RainfallTriggerResult(
            spatial_id, None, window_end, window_start, window_end,
            RainfallEvaluationState.INVALID_CONFIGURATION, "not_evaluable",
            "expected_observation_count must be a non-negative integer",
            rule,
            _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, window_end, None, rule),
        )
    evaluation_timestamp = window_end or (max((observation.observed_at for observation in observations if observation.observed_at), default=None))
    if any(observation.observed_at is None for observation in observations):
        return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.MISSING_TIMESTAMP, "not_evaluable", "At least one rainfall observation is missing its timestamp", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
    if rule is None:
        return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.INVALID_CONFIGURATION, "not_evaluable", "Rainfall trigger rule is not configured", None, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, None))
    if not observations:
        return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.MISSING_DATA, "not_evaluable", "No rainfall observations are available", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
    if any(observation.rainfall_mm is None for observation in observations):
        return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.MISSING_DATA, "not_evaluable", "At least one rainfall observation is missing", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
    if window_start is None or window_end is None:
        if expected_observation_count is not None:
            return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.INCOMPLETE_WINDOW, "not_evaluable", "Window bounds are required for an expected observation count", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
    else:
        if window_start.tzinfo is None or window_end.tzinfo is None or window_start > window_end:
            return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.INVALID_DATA, "not_evaluable", "Rainfall window bounds are invalid", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
        if any(observation.observed_at is None or not window_start <= observation.observed_at <= window_end for observation in observations):
            return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.INVALID_DATA, "not_evaluable", "Observation timestamp falls outside the evaluation window", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
    if expected_observation_count is not None and len(observations) < expected_observation_count:
        return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.INCOMPLETE_WINDOW, "not_evaluable", "The rainfall observation window is incomplete", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
    identities = [(observation.cell_id, observation.station_id, observation.observed_at) for observation in observations]
    if len(set(identities)) != len(identities):
        return RainfallTriggerResult(spatial_id, None, evaluation_timestamp, window_start, window_end, RainfallEvaluationState.DUPLICATE_OBSERVATION, "not_evaluable", "Duplicate rainfall observations are present", rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, None, rule))
    metric = float(sum(float(observation.rainfall_mm) for observation in observations))
    triggered = metric >= rule.threshold_mm
    state = RainfallEvaluationState.TRIGGERED if triggered else RainfallEvaluationState.NOT_TRIGGERED
    level = "triggered" if triggered else "below_threshold"
    explanation = f"Window rainfall total {metric:.6g} mm is {'greater than or equal to' if triggered else 'below'} configured threshold {rule.threshold_mm:.6g} mm"
    return RainfallTriggerResult(spatial_id, metric, evaluation_timestamp, window_start, window_end, state, level, explanation, rule, _enrich_provenance(provenance, observations, spatial_id, window_start, window_end, evaluation_timestamp, metric, rule))


def validate_cell_id(cell_id: int, grid: CanonicalGridDefinition) -> int:
    """Validate an existing canonical cell ID without changing spatial placement."""
    if not isinstance(cell_id, int) or not 0 <= cell_id < grid.total_cells:
        raise RainfallModelError(f"Rainfall cell_id {cell_id!r} is outside the canonical grid")
    return cell_id


def validate_canonical_grid(grid: CanonicalGridDefinition) -> None:
    """Enforce the existing L03 CRS, 30 m transform, and unrotated grid."""
    if CRS.from_user_input(grid.crs) != CRS.from_user_input(CANONICAL_PROJECTED_CRS_STR):
        raise RainfallModelError(f"L06 requires grid CRS {CANONICAL_PROJECTED_CRS_STR}")
    if not np.isclose(grid.resolution, CANONICAL_RESOLUTION_METERS):
        raise RainfallModelError("L06 requires a 30 m canonical grid")
    expected = Affine(
        CANONICAL_RESOLUTION_METERS, 0.0, grid.x_min,
        0.0, -CANONICAL_RESOLUTION_METERS, grid.y_max,
    )
    if grid.transform != expected:
        raise RainfallModelError("L06 requires the canonical unrotated grid transform")


def evaluate_rainfall_grid(
    observations: Sequence[RainfallObservation],
    grid: CanonicalGridDefinition,
    rule: Optional[RainfallRule],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    expected_observation_count: Optional[int] = None,
    provenance: Optional[RainfallProvenance] = None,
) -> RainfallGridResult:
    """Evaluate observations already associated with canonical cell IDs.

    Station observations without cell IDs are rejected; L06 performs no spatial
    interpolation or station-to-cell assignment.
    """
    validate_canonical_grid(grid)
    metric_grid = np.full((grid.height, grid.width), DEFAULT_NODATA_FLOAT, dtype=np.float32)
    trigger_grid = np.full((grid.height, grid.width), DEFAULT_NODATA_FLOAT, dtype=np.float32)
    grouped: Dict[int, List[RainfallObservation]] = {}
    for observation in observations:
        if observation.cell_id is None:
            raise RainfallModelError("Rainfall grid evaluation requires existing cell_id; interpolation is not implemented")
        cell_id = validate_cell_id(observation.cell_id, grid)
        grouped.setdefault(cell_id, []).append(observation)
    states: Dict[int, RainfallEvaluationState] = {}
    results: Dict[int, RainfallTriggerResult] = {}
    for cell_id, cell_observations in grouped.items():
        result = evaluate_rainfall_window(cell_observations, cell_id, rule, window_start, window_end, expected_observation_count, provenance)
        states[cell_id] = result.state
        results[cell_id] = result
        row, col = grid.row_col_from_cell_id(cell_id)
        if result.rainfall_metric_mm is not None:
            metric_grid[row, col] = result.rainfall_metric_mm
        if result.state in (RainfallEvaluationState.TRIGGERED, RainfallEvaluationState.NOT_TRIGGERED):
            trigger_grid[row, col] = 1.0 if result.state == RainfallEvaluationState.TRIGGERED else 0.0
    return RainfallGridResult(metric_grid, trigger_grid, states, results, {"crs": grid.crs, "resolution_m": grid.resolution, "interpolation": False, "state_scope": "observed_cells_only; unobserved cells are NoData", "provenance": provenance.to_dict() if provenance else None})


def evaluate_provider_result(
    provider_result: RainfallProviderResult,
    spatial_id: Union[int, str],
    rule: Optional[RainfallRule],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    expected_observation_count: Optional[int] = None,
) -> RainfallTriggerResult:
    """Connect provider availability/validation state to final trigger output."""
    if provider_result.state != RainfallEvaluationState.PROVIDER_AVAILABLE:
        timestamp = window_end or None
        return RainfallTriggerResult(
            spatial_id=spatial_id,
            rainfall_metric_mm=None,
            evaluation_timestamp=timestamp,
            window_start=window_start,
            window_end=window_end,
            state=provider_result.state,
            trigger_level="not_evaluable",
            explanation=provider_result.message or f"Provider state is {provider_result.state.value}",
            rule=rule,
            provenance=_enrich_provenance(provider_result.provenance, provider_result.observations, spatial_id, window_start, window_end, timestamp, None, rule),
        )
    return evaluate_rainfall_window(
        provider_result.observations,
        spatial_id,
        rule,
        window_start,
        window_end,
        expected_observation_count,
        provider_result.provenance,
    )


def _enrich_provenance(
    provenance: Optional[RainfallProvenance],
    observations: Sequence[RainfallObservation],
    spatial_id: Union[int, str],
    window_start: Optional[datetime],
    window_end: Optional[datetime],
    evaluation_timestamp: Optional[datetime],
    rainfall_metric_mm: Optional[float],
    rule: Optional[RainfallRule],
) -> Optional[RainfallProvenance]:
    if provenance is None:
        return None
    return replace(
        provenance,
        observation_timestamps=tuple(observation.observed_at.isoformat() for observation in observations if observation.observed_at),
        evaluation_window_start=window_start.isoformat() if window_start else None,
        evaluation_window_end=window_end.isoformat() if window_end else None,
        evaluation_timestamp=evaluation_timestamp.isoformat() if evaluation_timestamp else None,
        spatial_id=spatial_id,
        rainfall_metric_mm=rainfall_metric_mm,
        threshold_mm=rule.threshold_mm if rule else None,
        comparison=rule.comparison if rule else None,
        rule_version=rule.rule_version if rule else None,
    )


def build_rainfall_provenance(
    provider_result: RainfallProviderResult,
    rule: Optional[RainfallRule],
    grid: Optional[CanonicalGridDefinition] = None,
    model_version: str = "L06-trigger-1.0",
) -> Dict[str, Any]:
    """Build provenance for provider and deterministic rule evaluation."""
    metadata: Dict[str, Any] = {
        "layer": "L06",
        "model_version": model_version,
        "provider_state": provider_result.state.value,
        "provider_message": provider_result.message,
        "provider": provider_result.provenance.to_dict(),
        "rule": rule.to_dict() if rule else None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "missing_data_policy": "Missing rainfall remains non-evaluable; never impute zero",
    }
    if grid is not None:
        metadata["canonical_grid"] = grid.to_dict()
        metadata["crs"] = CANONICAL_PROJECTED_CRS_STR
    return metadata


def _parse_timestamp(value: Any, field_name: str) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and np.isnan(value)) or (isinstance(value, str) and not value.strip()):
        raise MissingTimestampError(f"Missing {field_name} timestamp")
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        raise InvalidTimestampError(f"Invalid {field_name} timestamp")
    return parsed.to_pydatetime()


def _parse_optional_timestamp(value: Any, field_name: str) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and np.isnan(value)) or (isinstance(value, str) and not value.strip()):
        return None
    return _parse_timestamp(value, field_name)


def _optional_int(value: Any) -> Optional[int]:
    if value is None or (isinstance(value, float) and np.isnan(value)) or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise RainfallValidationError("cell_id must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RainfallValidationError("cell_id must be an integer") from exc
    if isinstance(value, float) and parsed != value:
        raise RainfallValidationError("cell_id must be an integer")
    return parsed


def _optional_text(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    return text or None