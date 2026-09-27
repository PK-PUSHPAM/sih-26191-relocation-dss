"""L12 relocation priority engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Mapping, Sequence


class L12Error(ValueError):
    """Raised when L12 inputs or frozen configuration are invalid."""


class PriorityQuality(str, Enum):
    COMPLETE = "complete"
    NON_EVALUABLE = "non_evaluable"
    INVALID = "invalid"


class PriorityTier(str, Enum):
    IMMEDIATE = "Immediate"
    SHORT_TERM = "Short-term"
    MEDIUM_TERM = "Medium-term"
    MONITOR = "Monitor"


MODEL_VERSION = "L12-relocation-priority-1.0"
FORMULA_VERSION = "RP-0.40-0.25-0.20-0.10-0.05"
WEIGHTS = {"risk": 0.40, "exposed_pop": 0.25, "vulnerability": 0.20,
           "response_difficulty": 0.10, "recurrence": 0.05}
TIER_THRESHOLDS = {"immediate_min": 0.75, "short_term_min": 0.55,
                   "short_term_max": 0.75, "medium_term_min": 0.35,
                   "medium_term_max": 0.55, "monitor_max": 0.35}


@dataclass(frozen=True)
class PriorityHabitationInput:
    habitation_id: str
    risk: float | None
    exposed_pop: int | None
    exposed_pop_score: float | None
    vulnerability: float | None
    response_difficulty: float | None
    recurrence: float | None


@dataclass(frozen=True)
class PriorityRecord:
    habitation_id: str
    risk: float | None
    exposed_pop: int | None
    vulnerability: float | None
    response_difficulty: float | None
    recurrence: float | None
    priority_score: float | None
    tier: PriorityTier | None
    quality_flag: PriorityQuality
    explanation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "habitation_id": self.habitation_id,
            "risk": self.risk,
            "exposed_pop": self.exposed_pop,
            "vulnerability": self.vulnerability,
            "response_difficulty": self.response_difficulty,
            "recurrence": self.recurrence,
            "priority_score": self.priority_score,
            "tier": self.tier.value if self.tier else None,
            "quality_flag": self.quality_flag.value,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class L12Result:
    records: tuple[PriorityRecord, ...]
    metadata: dict[str, Any]


def _valid_score(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0)


def _valid_population(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_frozen_parameters(weights: Mapping[str, float] | None,
                                 thresholds: Mapping[str, float] | None) -> None:
    if weights is not None and dict(weights) != WEIGHTS:
        raise L12Error("L12 weights are frozen by the project specification")
    if thresholds is not None and dict(thresholds) != TIER_THRESHOLDS:
        raise L12Error("L12 tier thresholds are frozen by the project specification")


def _tier(score: float) -> PriorityTier:
    if score >= 0.75:
        return PriorityTier.IMMEDIATE
    if score >= 0.55:
        return PriorityTier.SHORT_TERM
    if score >= 0.35:
        return PriorityTier.MEDIUM_TERM
    return PriorityTier.MONITOR


def _record(item: PriorityHabitationInput) -> PriorityRecord:
    if not item.habitation_id:
        raise L12Error("habitation_id is required")
    raw = {
        "risk": item.risk, "exposed_pop_score": item.exposed_pop_score,
        "vulnerability": item.vulnerability,
        "response_difficulty": item.response_difficulty, "recurrence": item.recurrence,
    }
    missing = [name for name, value in raw.items() if value is None]
    invalid = [name for name, value in raw.items()
               if value is not None and not _valid_score(value)]
    if item.exposed_pop is None:
        missing.append("exposed_pop")
    elif not _valid_population(item.exposed_pop):
        invalid.append("exposed_pop")
    base = dict(
        habitation_id=item.habitation_id, risk=item.risk, exposed_pop=item.exposed_pop,
        vulnerability=item.vulnerability, response_difficulty=item.response_difficulty,
        recurrence=item.recurrence,
    )
    if invalid:
        return PriorityRecord(**base, priority_score=None, tier=None,
                              quality_flag=PriorityQuality.INVALID,
                              explanation={"invalid_fields": invalid,
                                           "missing_fields": missing,
                                           "formula_version": FORMULA_VERSION})
    if missing:
        return PriorityRecord(**base, priority_score=None, tier=None,
                              quality_flag=PriorityQuality.NON_EVALUABLE,
                              explanation={"missing_fields": missing,
                                           "formula_version": FORMULA_VERSION})
    components = {
        "risk": float(item.risk), "exposed_pop": float(item.exposed_pop_score),
        "vulnerability": float(item.vulnerability),
        "response_difficulty": float(item.response_difficulty),
        "recurrence": float(item.recurrence),
    }
    contributions = {key: round(value * WEIGHTS[key], 6)
                     for key, value in components.items()}
    score = round(sum(contributions.values()), 4)
    return PriorityRecord(
        **base, priority_score=score, tier=_tier(score),
        quality_flag=PriorityQuality.COMPLETE,
        explanation={"components": components, "weights": dict(WEIGHTS),
                     "weighted_contributions": contributions,
                     "exposed_pop_score": float(item.exposed_pop_score),
                     "formula_version": FORMULA_VERSION,
                     "tier_thresholds": dict(TIER_THRESHOLDS)},
    )


def run_l12(habitations: Sequence[PriorityHabitationInput], *,
            execution_timestamp: datetime | None = None,
            source_metadata: Mapping[str, Any] | None = None,
            weights: Mapping[str, float] | None = None,
            thresholds: Mapping[str, float] | None = None) -> L12Result:
    """Run L12 without database writes.

    The existing priority table stores raw exposed_pop, while the frozen
    formula requires a normalized population term. L12 therefore requires
    exposed_pop_score as an already-derived [0,1] input and does not invent
    a normalization function.
    """
    _validate_frozen_parameters(weights, thresholds)
    if execution_timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif execution_timestamp.tzinfo is None or execution_timestamp.utcoffset() is None:
        raise L12Error("execution_timestamp must be timezone-aware")
    else:
        timestamp = execution_timestamp
    records = tuple(_record(item) for item in habitations)
    return L12Result(
        records=records,
        metadata={
            "layer": "L12",
            "model_version": MODEL_VERSION,
            "formula_version": FORMULA_VERSION,
            "formula": "RP = 0.40*Risk + 0.25*Exposed_Pop_Score + 0.20*Vulnerability + 0.10*Response_Difficulty + 0.05*Recurrence",
            "weights": dict(WEIGHTS),
            "tier_thresholds": dict(TIER_THRESHOLDS),
            "execution_timestamp": timestamp.isoformat(),
            "habitation_count": len(records),
            "quality_policy": "missing_or_invalid_inputs never become a valid priority score",
            "source_metadata": dict(source_metadata or {}),
        },
    )
