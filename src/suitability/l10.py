"""L10 relocation-site suitability engine.

Frozen rule:
S = 0.30Hsafe + 0.15Slope + 0.15Road + 0.15Water
    + 0.10Health + 0.05Education + 0.05LandUse + 0.05Services

L10 evaluates candidate polygons using already-derived normalized suitability
indicators and deterministic hard eligibility constraints. It does not fetch or
fabricate source datasets and does not write to the database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from numbers import Real
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from shapely.geometry import Polygon

L10_MODEL_VERSION = "L10-site-suitability-1.0"
FORMULA_VERSION = "S-0.30-0.15-0.15-0.15-0.10-0.05-0.05-0.05"

SUITABILITY_WEIGHTS: Dict[str, float] = {
    "hazard_safety": 0.30,
    "slope": 0.15,
    "road_access": 0.15,
    "water_availability": 0.15,
    "healthcare_access": 0.10,
    "education_access": 0.05,
    "land_use": 0.05,
    "service_proximity": 0.05,
}

MIN_CONTIGUOUS_AREA_M2 = 10_000.0
MAX_ALLOWABLE_SLOPE_DEGREES = 30.0
MAX_ROAD_DISTANCE_METERS = 2_000.0

class L10Error(ValueError):
    """Raised when the L10 input contract is violated."""

class SiteQuality(str, Enum):
    COMPLETE = "complete"
    NON_EVALUABLE = "non_evaluable"
    INVALID = "invalid"

class SiteStatus(str, Enum):
    ELIGIBLE = "eligible"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"

@dataclass(frozen=True)
class SiteCandidateInput:
    site_id: str
    geometry: Polygon
    combined_risk: Optional[float]
    slope_score: Optional[float]
    road_score: Optional[float]
    water_score: Optional[float]
    health_score: Optional[float]
    education_score: Optional[float]
    land_use_score: Optional[float]
    services_score: Optional[float]
    slope_degrees: Optional[float]
    road_distance_m: Optional[float]
    red_zone: bool = False
    water_body: bool = False
    protected_land: bool = False

@dataclass(frozen=True)
class SiteSuitabilityRecord:
    site_id: str
    geometry: Polygon
    area_m2: float
    suitability: Optional[float]
    status: SiteStatus
    quality_flag: SiteQuality
    explanation: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "geometry": self.geometry,
            "area_m2": self.area_m2,
            "suitability": self.suitability,
            "status": self.status.value,
            "quality_flag": self.quality_flag.value,
            "explanation": dict(self.explanation),
        }

@dataclass(frozen=True)
class L10Result:
    records: Tuple[SiteSuitabilityRecord, ...]
    metadata: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "records": [record.to_dict() for record in self.records],
            "metadata": dict(self.metadata),
        }

def _validate_score(name: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise L10Error(f"{name} must be numeric or None")
    numeric = float(value)
    if not np.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise L10Error(f"{name} must be finite and within [0, 1]")
    return numeric

def _validate_optional_nonnegative(name: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise L10Error(f"{name} must be numeric or None")
    numeric = float(value)
    if not np.isfinite(numeric) or numeric < 0.0:
        raise L10Error(f"{name} must be finite and non-negative")
    return numeric

def _validate_weights(weights: Optional[Mapping[str, float]]) -> Dict[str, float]:
    selected = dict(SUITABILITY_WEIGHTS if weights is None else weights)
    if selected != SUITABILITY_WEIGHTS:
        raise L10Error("L10 weights must exactly match the frozen suitability weights")
    if not np.isclose(sum(selected.values()), 1.0, atol=1e-12):
        raise L10Error("L10 suitability weights must sum to 1.0")
    return selected

def run_l10(
    candidates: Sequence[SiteCandidateInput],
    weights: Optional[Mapping[str, float]] = None,
    execution_timestamp: Optional[datetime] = None,
    source_metadata: Optional[Mapping[str, Any]] = None,
) -> L10Result:
    """Evaluate relocation-site candidates under the frozen L10 contract."""
    if candidates is None:
        raise L10Error("candidates input is required")

    selected_weights = _validate_weights(weights)
    timestamp = execution_timestamp or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise L10Error("L10 execution timestamp must be timezone-aware")

    records: List[SiteSuitabilityRecord] = []
    score_fields = {
        "slope": "slope_score",
        "road_access": "road_score",
        "water_availability": "water_score",
        "healthcare_access": "health_score",
        "education_access": "education_score",
        "land_use": "land_use_score",
        "service_proximity": "services_score",
    }

    for idx, candidate in enumerate(tuple(candidates)):
        if not isinstance(candidate, SiteCandidateInput):
            raise L10Error(f"candidates[{idx}] must be a SiteCandidateInput")
        if not isinstance(candidate.site_id, str) or not candidate.site_id.strip():
            raise L10Error("site_id must be a non-empty string")
        if not isinstance(candidate.geometry, Polygon):
            raise L10Error(f"{candidate.site_id}: geometry must be a Polygon")
        if candidate.geometry.is_empty or not candidate.geometry.is_valid:
            raise L10Error(f"{candidate.site_id}: geometry must be non-empty and valid")
        if any(not isinstance(flag, (bool, np.bool_)) for flag in (
            candidate.red_zone, candidate.water_body, candidate.protected_land
        )):
            raise L10Error(f"{candidate.site_id}: exclusion flags must be boolean")

        area_m2 = float(candidate.geometry.area)
        exclusion_reasons: List[str] = []
        if candidate.red_zone:
            exclusion_reasons.append("red_zone")
        if candidate.water_body:
            exclusion_reasons.append("water_body")
        if candidate.protected_land:
            exclusion_reasons.append("protected_land")
        if area_m2 < MIN_CONTIGUOUS_AREA_M2:
            exclusion_reasons.append("area_below_1_ha")

        if exclusion_reasons:
            records.append(SiteSuitabilityRecord(
                candidate.site_id, candidate.geometry, round(area_m2, 2), None,
                SiteStatus.REJECTED, SiteQuality.COMPLETE,
                {"exclusion_reasons": exclusion_reasons},
            ))
            continue

        try:
            slope_degrees = _validate_optional_nonnegative("slope_degrees", candidate.slope_degrees)
            road_distance_m = _validate_optional_nonnegative("road_distance_m", candidate.road_distance_m)
        except L10Error as exc:
            records.append(SiteSuitabilityRecord(
                candidate.site_id, candidate.geometry, round(area_m2, 2), None,
                SiteStatus.REJECTED, SiteQuality.INVALID,
                {"exclusion_reasons": [], "invalid_input": str(exc)},
            ))
            continue

        if slope_degrees is not None and slope_degrees > MAX_ALLOWABLE_SLOPE_DEGREES:
            exclusion_reasons.append("slope_above_30_degrees")
        if road_distance_m is not None and road_distance_m > MAX_ROAD_DISTANCE_METERS:
            exclusion_reasons.append("road_distance_above_2000m")

        if exclusion_reasons:
            records.append(SiteSuitabilityRecord(
                candidate.site_id, candidate.geometry, round(area_m2, 2), None,
                SiteStatus.REJECTED, SiteQuality.COMPLETE,
                {"exclusion_reasons": exclusion_reasons},
            ))
            continue

        required_constraints = []
        if slope_degrees is None:
            required_constraints.append("slope_degrees")
        if road_distance_m is None:
            required_constraints.append("road_distance_m")
        if combined_risk is None:
            required_constraints.append("combined_risk")
        if required_constraints:
            records.append(SiteSuitabilityRecord(
                candidate.site_id, candidate.geometry, round(area_m2, 2), None,
                SiteStatus.CONDITIONAL, SiteQuality.NON_EVALUABLE,
                {"exclusion_reasons": [], "missing_fields": required_constraints},
            ))
            continue

        indicator_values: Dict[str, Optional[float]] = {}
        try:
            for score_name, field_name in score_fields.items():
                indicator_values[score_name] = _validate_score(
                    field_name, getattr(candidate, field_name)
                )
        except L10Error as exc:
            records.append(SiteSuitabilityRecord(
                candidate.site_id, candidate.geometry, round(area_m2, 2), None,
                SiteStatus.REJECTED, SiteQuality.INVALID,
                {"exclusion_reasons": [], "invalid_input": str(exc)},
            ))
            continue

        missing = [name for name, value in indicator_values.items() if value is None]
        if missing:
            records.append(SiteSuitabilityRecord(
                candidate.site_id, candidate.geometry, round(area_m2, 2), None,
                SiteStatus.CONDITIONAL, SiteQuality.NON_EVALUABLE,
                {"exclusion_reasons": [], "missing_fields": missing},
            ))
            continue

        h_safe = 1.0 - combined_risk
        contributions = {"hazard_safety": round(h_safe * selected_weights["hazard_safety"], 6)}
        for name, value in indicator_values.items():
            contributions[name] = round(value * selected_weights[name], 6)

        score = round(
            h_safe * selected_weights["hazard_safety"]
            + sum(indicator_values[name] * selected_weights[name] for name in indicator_values),
            4,
        )
        records.append(SiteSuitabilityRecord(
            candidate.site_id,
            candidate.geometry,
            round(area_m2, 2),
            score,
            SiteStatus.ELIGIBLE,
            SiteQuality.COMPLETE,
            {
                "exclusion_reasons": [],
                "h_safe": round(h_safe, 4),
                "components": indicator_values,
                "weighted_contributions": contributions,
            },
        ))

    metadata = {
        "layer": "L10",
        "model_version": L10_MODEL_VERSION,
        "formula_version": FORMULA_VERSION,
        "formula": (
            "S = 0.30Hsafe + 0.15Slope + 0.15Road + 0.15Water + "
            "0.10Health + 0.05Education + 0.05LandUse + 0.05Services"
        ),
        "weights": dict(selected_weights),
        "h_safe_definition": "Hsafe = 1.0 - combined_risk after hard exclusions",
        "minimum_contiguous_area_m2": MIN_CONTIGUOUS_AREA_M2,
        "maximum_allowable_slope_degrees": MAX_ALLOWABLE_SLOPE_DEGREES,
        "maximum_road_distance_m": MAX_ROAD_DISTANCE_METERS,
        "execution_timestamp": timestamp.isoformat(),
        "crs": "EPSG:32644",
        "quality_states": [q.value for q in SiteQuality],
        "status_states": [s.value for s in SiteStatus],
        "missing_data_policy": "Missing score inputs do not receive zero; the site is conditional and suitability is NoData.",
        "hard_exclusion_policy": "Red zone, water body, protected land, area below 1 ha, slope above 30 degrees, or road distance above 2000 m rejects the candidate before scoring.",
        "source_metadata": dict(source_metadata or {}),
    }
    return L10Result(tuple(records), metadata)
