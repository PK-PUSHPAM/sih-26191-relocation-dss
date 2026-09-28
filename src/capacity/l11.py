"""L11 carrying-capacity engine.

Frozen rule:
Physical_Capacity = min(Cap_land, Cap_water, Cap_sanitation, Cap_health, Cap_access)
Effective_Capacity = floor(Physical_Capacity * 0.80)

L11 is deterministic and persistence-ready. It does not fetch data, invent missing
values, write to the database, or claim certified engineering capacity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import floor
from numbers import Real
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

L11_MODEL_VERSION = "L11-carrying-capacity-1.0"
FORMULA_VERSION = "CC-floor-min-0.80"
DEFAULT_SAFETY_FACTOR = 0.80
TARGET_DENSITY_PER_HECTARE = 150.0
DAILY_WATER_LITERS_PER_CAPITA = 70.0
SANITATION_SERVICE_FACTOR = 1.0
HEALTHCARE_PERSON_PER_BED = 1000.0

COMPONENT_ORDER = ("land", "water", "sanitation", "health", "access")


class L11Error(ValueError):
    """Raised when the L11 input contract is violated."""


class CapacityQuality(str, Enum):
    COMPLETE = "complete"
    NON_EVALUABLE = "non_evaluable"
    INVALID = "invalid"


@dataclass(frozen=True)
class CapacitySiteInput:
    """Inputs for one candidate site.

    area_m2 and daily_water_liters are source quantities used to derive land and
    water capacity. Sanitation and access are already-derived people capacities
    because the frozen project specification does not define a source formula for
    those two components. health_beds is converted using the frozen
    people-per-bed proxy.
    """

    site_id: str
    area_m2: Optional[float]
    daily_water_liters: Optional[float]
    sanitation_capacity: Optional[float]
    health_beds: Optional[float]
    access_capacity: Optional[float]


@dataclass(frozen=True)
class CapacityRecord:
    site_id: str
    land_cap: Optional[int]
    water_cap: Optional[int]
    sanitation_cap: Optional[int]
    health_cap: Optional[int]
    access_cap: Optional[int]
    binding_bottleneck: Optional[str]
    effective_cap: Optional[int]
    quality_flag: CapacityQuality
    explanation: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "land_cap": self.land_cap,
            "water_cap": self.water_cap,
            "sanitation_cap": self.sanitation_cap,
            "health_cap": self.health_cap,
            "access_cap": self.access_cap,
            "binding_bottleneck": self.binding_bottleneck,
            "effective_cap": self.effective_cap,
            "quality_flag": self.quality_flag.value,
            "explanation": dict(self.explanation),
        }


@dataclass(frozen=True)
class L11Result:
    records: Tuple[CapacityRecord, ...]
    metadata: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "records": [record.to_dict() for record in self.records],
            "metadata": dict(self.metadata),
        }


def _validate_nonnegative(name: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise L11Error(f"{name} must be numeric or None")
    numeric = float(value)
    if not np.isfinite(numeric) or numeric < 0.0:
        raise L11Error(f"{name} must be finite and non-negative")
    return numeric


def _validate_parameters(
    safety_factor: float,
    target_density_per_hectare: float,
    daily_water_liters_per_capita: float,
    sanitation_service_factor: float,
    healthcare_person_per_bed: float,
) -> None:
    expected = {
        "safety_factor": DEFAULT_SAFETY_FACTOR,
        "target_density_per_hectare": TARGET_DENSITY_PER_HECTARE,
        "daily_water_liters_per_capita": DAILY_WATER_LITERS_PER_CAPITA,
        "sanitation_service_factor": SANITATION_SERVICE_FACTOR,
        "healthcare_person_per_bed": HEALTHCARE_PERSON_PER_BED,
    }
    actual = {
        "safety_factor": safety_factor,
        "target_density_per_hectare": target_density_per_hectare,
        "daily_water_liters_per_capita": daily_water_liters_per_capita,
        "sanitation_service_factor": sanitation_service_factor,
        "healthcare_person_per_bed": healthcare_person_per_bed,
    }
    for name, value in actual.items():
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise L11Error(f"{name} must be numeric")
        if not np.isfinite(float(value)) or float(value) < 0:
            raise L11Error(f"{name} must be finite and non-negative")
        if float(value) != expected[name]:
            raise L11Error(
                f"{name} must match the frozen L11 configuration value {expected[name]}"
            )


def _derive_capacities(site: CapacitySiteInput) -> Dict[str, int]:
    area_m2 = _validate_nonnegative("area_m2", site.area_m2)
    water_liters = _validate_nonnegative("daily_water_liters", site.daily_water_liters)
    sanitation = _validate_nonnegative("sanitation_capacity", site.sanitation_capacity)
    beds = _validate_nonnegative("health_beds", site.health_beds)
    access = _validate_nonnegative("access_capacity", site.access_capacity)

    missing = [
        name for name, value in (
            ("area_m2", area_m2),
            ("daily_water_liters", water_liters),
            ("sanitation_capacity", sanitation),
            ("health_beds", beds),
            ("access_capacity", access),
        ) if value is None
    ]
    if missing:
        raise KeyError(", ".join(missing))

    land_cap = floor((area_m2 / 10_000.0) * TARGET_DENSITY_PER_HECTARE)
    water_cap = floor(water_liters / DAILY_WATER_LITERS_PER_CAPITA)
    sanitation_cap = floor(sanitation * SANITATION_SERVICE_FACTOR)
    health_cap = floor(beds * HEALTHCARE_PERSON_PER_BED)
    access_cap = floor(access)

    return {
        "land": land_cap,
        "water": water_cap,
        "sanitation": sanitation_cap,
        "health": health_cap,
        "access": access_cap,
    }


def _record_non_evaluable(site_id: str, missing: Sequence[str]) -> CapacityRecord:
    return CapacityRecord(
        site_id=site_id,
        land_cap=None,
        water_cap=None,
        sanitation_cap=None,
        health_cap=None,
        access_cap=None,
        binding_bottleneck=None,
        effective_cap=None,
        quality_flag=CapacityQuality.NON_EVALUABLE,
        explanation={
            "missing_fields": list(missing),
            "reason": "All five capacity components are required; missing inputs are not treated as zero.",
        },
    )


def run_l11(
    sites: Sequence[CapacitySiteInput],
    *,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
    target_density_per_hectare: float = TARGET_DENSITY_PER_HECTARE,
    daily_water_liters_per_capita: float = DAILY_WATER_LITERS_PER_CAPITA,
    sanitation_service_factor: float = SANITATION_SERVICE_FACTOR,
    healthcare_person_per_bed: float = HEALTHCARE_PERSON_PER_BED,
    execution_timestamp: Optional[datetime] = None,
    source_metadata: Optional[Mapping[str, Any]] = None,
) -> L11Result:
    """Calculate modeled carrying capacity for candidate relocation sites."""
    if sites is None:
        raise L11Error("sites input is required")

    _validate_parameters(
        safety_factor,
        target_density_per_hectare,
        daily_water_liters_per_capita,
        sanitation_service_factor,
        healthcare_person_per_bed,
    )
    timestamp = execution_timestamp or datetime.now(timezone.utc)
    if not isinstance(timestamp, datetime):
        raise L11Error("L11 execution timestamp must be a datetime")
    if timestamp.tzinfo is None:
        raise L11Error("L11 execution timestamp must be timezone-aware")
    if source_metadata is not None and not isinstance(source_metadata, Mapping):
        raise L11Error("L11 source_metadata must be a mapping when supplied")

    records = []
    for idx, site in enumerate(tuple(sites)):
        if not isinstance(site, CapacitySiteInput):
            raise L11Error(f"sites[{idx}] must be a CapacitySiteInput")
        if not isinstance(site.site_id, str) or not site.site_id.strip():
            raise L11Error("site_id must be a non-empty string")

        raw_values = {
            "area_m2": site.area_m2,
            "daily_water_liters": site.daily_water_liters,
            "sanitation_capacity": site.sanitation_capacity,
            "health_beds": site.health_beds,
            "access_capacity": site.access_capacity,
        }
        missing = [name for name, value in raw_values.items() if value is None]

        try:
            for name, value in raw_values.items():
                if value is not None:
                    _validate_nonnegative(name, value)
        except L11Error as exc:
            records.append(
                CapacityRecord(
                    site_id=site.site_id,
                    land_cap=None,
                    water_cap=None,
                    sanitation_cap=None,
                    health_cap=None,
                    access_cap=None,
                    binding_bottleneck=None,
                    effective_cap=None,
                    quality_flag=CapacityQuality.INVALID,
                    explanation={"invalid_input": str(exc), "missing_fields": missing},
                )
            )
            continue

        if missing:
            records.append(_record_non_evaluable(site.site_id, missing))
            continue

        try:
            capacities = _derive_capacities(site)
        except KeyError as exc:
            records.append(_record_non_evaluable(site.site_id, [str(exc)]))
            continue
        except L11Error as exc:
            records.append(
                CapacityRecord(
                    site_id=site.site_id,
                    land_cap=None,
                    water_cap=None,
                    sanitation_cap=None,
                    health_cap=None,
                    access_cap=None,
                    binding_bottleneck=None,
                    effective_cap=None,
                    quality_flag=CapacityQuality.INVALID,
                    explanation={"invalid_input": str(exc)},
                )
            )
            continue

        minimum = min(capacities.values())
        bottleneck = next(name for name in COMPONENT_ORDER if capacities[name] == minimum)
        effective = floor(minimum * safety_factor)

        records.append(
            CapacityRecord(
                site_id=site.site_id,
                land_cap=capacities["land"],
                water_cap=capacities["water"],
                sanitation_cap=capacities["sanitation"],
                health_cap=capacities["health"],
                access_cap=capacities["access"],
                binding_bottleneck=bottleneck,
                effective_cap=effective,
                quality_flag=CapacityQuality.COMPLETE,
                explanation={
                    "physical_capacity": minimum,
                    "safety_factor": safety_factor,
                    "binding_bottleneck": bottleneck,
                    "derivations": {
                        "land": "floor(area_m2 / 10000 * 150 people/ha)",
                        "water": "floor(daily_water_liters / 70 L/person/day)",
                        "sanitation": "floor(sanitation_capacity * 1.0)",
                        "health": "floor(health_beds * 1000 people/bed)",
                        "access": "floor(access_capacity)",
                    },
                },
            )
        )

    metadata = {
        "layer": "L11",
        "model_version": L11_MODEL_VERSION,
        "formula_version": FORMULA_VERSION,
        "formula": "Effective_Capacity = floor(min(land, water, sanitation, health, access) * 0.80)",
        "physical_capacity_formula": "min(Cap_land, Cap_water, Cap_sanitation, Cap_health, Cap_access)",
        "safety_factor": safety_factor,
        "target_density_per_hectare": target_density_per_hectare,
        "daily_water_liters_per_capita": daily_water_liters_per_capita,
        "sanitation_service_factor": sanitation_service_factor,
        "healthcare_person_per_bed": healthcare_person_per_bed,
        "execution_timestamp": timestamp.isoformat(),
        "crs": "EPSG:32644",
        "quality_states": [q.value for q in CapacityQuality],
        "missing_data_policy": "Missing component inputs produce NoData/non_evaluable; missing is never imputed as zero.",
        "scope": "Modeled decision-support capacity, not engineering certification or a legal occupancy limit.",
        "source_metadata": dict(source_metadata or {}),
    }
    return L11Result(tuple(records), metadata)
