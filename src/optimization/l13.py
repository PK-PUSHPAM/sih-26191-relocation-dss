"""L13 allocation optimization using OR-Tools CP-SAT.

The solver is deterministic for fixed inputs, objective weights, and solver
parameters. It performs no database writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


class L13Error(ValueError):
    """Raised for invalid L13 inputs or solver configuration."""


MODEL_VERSION = "L13-allocation-optimization-1.0"
FORMULA_VERSION = "ALLOC-distance-unmet-hazard-1.0"


@dataclass(frozen=True)
class HabitationDemand:
    habitation_id: str
    exposed_population: int


@dataclass(frozen=True)
class CandidateSite:
    site_id: str
    effective_capacity: int
    hazard: float
    feasible_habitations: tuple[str, ...]
    suitability: float | None = None


@dataclass(frozen=True)
class AllocationRecord:
    habitation_id: str
    site_id: str
    allocated_population: int
    distance: float
    constraint_flags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "habitation_id": self.habitation_id,
            "site_id": self.site_id,
            "allocated_population": self.allocated_population,
            "distance": self.distance,
            "constraint_flags": self.constraint_flags,
        }


@dataclass(frozen=True)
class UnmetDemand:
    habitation_id: str
    exposed_population: int
    allocated_population: int
    unmet_population: int


@dataclass(frozen=True)
class L13Result:
    status: str
    objective_value: float | None
    allocations: tuple[AllocationRecord, ...]
    unmet: tuple[UnmetDemand, ...]
    metadata: dict[str, Any]


def _valid_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_nonnegative_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and float(value) >= 0.0
    )


def _valid_hazard(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
    )


def _validate_inputs(
    habitations: Sequence[HabitationDemand],
    sites: Sequence[CandidateSite],
    distances: Mapping[tuple[str, str], float],
    distance_weight: float,
    unmet_penalty: float,
    hazard_weight: float,
) -> None:
    if not _valid_nonnegative_number(distance_weight) or distance_weight <= 0:
        raise L13Error("distance_weight must be > 0")
    if not _valid_nonnegative_number(unmet_penalty) or unmet_penalty <= 0:
        raise L13Error("unmet_penalty must be > 0")
    if not _valid_nonnegative_number(hazard_weight) or hazard_weight < 0:
        raise L13Error("hazard_weight must be >= 0")

    h_ids = [h.habitation_id for h in habitations]
    s_ids = [s.site_id for s in sites]
    if len(h_ids) != len(set(h_ids)):
        raise L13Error("duplicate habitation_id")
    if len(s_ids) != len(set(s_ids)):
        raise L13Error("duplicate site_id")

    for h in habitations:
        if not h.habitation_id:
            raise L13Error("habitation_id is required")
        if not _valid_nonnegative_int(h.exposed_population):
            raise L13Error("exposed_population must be a non-negative integer")

    for s in sites:
        if not s.site_id:
            raise L13Error("site_id is required")
        if not _valid_nonnegative_int(s.effective_capacity):
            raise L13Error("effective_capacity must be a non-negative integer")
        if not _valid_hazard(s.hazard):
            raise L13Error("site hazard must be within [0,1]")
        if s.suitability is not None and not (
            isinstance(s.suitability, (int, float))
            and not isinstance(s.suitability, bool)
            and 0.0 <= float(s.suitability) <= 1.0
        ):
            raise L13Error("site suitability must be within [0,1]")

    for pair, distance in distances.items():
        if pair[0] not in h_ids or pair[1] not in s_ids:
            raise L13Error("distance references an unknown habitation or site")
        if not _valid_nonnegative_number(distance):
            raise L13Error("distance must be non-negative")


def run_l13(
    habitations: Sequence[HabitationDemand],
    sites: Sequence[CandidateSite],
    distances: Mapping[tuple[str, str], float],
    *,
    distance_weight: float,
    unmet_penalty: float,
    hazard_weight: float,
    time_limit_seconds: float = 30.0,
    num_workers: int = 1,
    source_metadata: Mapping[str, Any] | None = None,
) -> L13Result:
    """Solve integer population allocation without database writes.

    Objective:
      distance_weight * sum(distance*x)
      + unmet_penalty * sum(unmet)
      + hazard_weight * sum(site_hazard*x)

    A habitation may allocate only to sites listed in that site's
    feasible_habitations. Missing distance entries are not treated as zero.
    """
    _validate_inputs(
        habitations, sites, distances,
        distance_weight, unmet_penalty, hazard_weight,
    )
    if time_limit_seconds <= 0 or num_workers <= 0:
        raise L13Error("solver limits must be positive")

    try:
        from ortools.sat.python import cp_model
    except ImportError as exc:
        raise L13Error(
            "OR-Tools is required for L13; install the ortools package"
        ) from exc

    h_by_id = {h.habitation_id: h for h in habitations}
    s_by_id = {s.site_id: s for s in sites}
    scale = 1_000_000

    model = cp_model.CpModel()
    x: dict[tuple[str, str], Any] = {}
    unmet: dict[str, Any] = {}

    for h in habitations:
        unmet[h.habitation_id] = model.NewIntVar(
            0, h.exposed_population, f"unmet_{h.habitation_id}"
        )
        allowed_sites = [
            s for s in sites if h.habitation_id in s.feasible_habitations
        ]
        vars_for_h = []
        for s in allowed_sites:
            if (h.habitation_id, s.site_id) not in distances:
                raise L13Error(
                    f"missing distance for feasible pair "
                    f"{h.habitation_id}->{s.site_id}"
                )
            var = model.NewIntVar(
                0, min(h.exposed_population, s.effective_capacity),
                f"x_{h.habitation_id}_{s.site_id}",
            )
            x[(h.habitation_id, s.site_id)] = var
            vars_for_h.append(var)
        model.Add(sum(vars_for_h) + unmet[h.habitation_id] == h.exposed_population)

    for s in sites:
        vars_for_s = [
            x[(h.habitation_id, s.site_id)]
            for h in habitations
            if (h.habitation_id, s.site_id) in x
        ]
        model.Add(sum(vars_for_s) <= s.effective_capacity)

    objective_terms = []
    for (h_id, s_id), var in x.items():
        s = s_by_id[s_id]
        cost = (
            distance_weight * float(distances[(h_id, s_id)])
            + hazard_weight * float(s.hazard)
        )
        objective_terms.append(int(round(cost * scale)) * var)
    for h_id, var in unmet.items():
        objective_terms.append(int(round(unmet_penalty * scale)) * var)
    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_workers = int(num_workers)
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return L13Result(
            status=status_name,
            objective_value=None,
            allocations=(),
            unmet=tuple(
                UnmetDemand(h.habitation_id, h.exposed_population, 0,
                            h.exposed_population)
                for h in habitations
            ),
            metadata=_metadata(
                distance_weight, unmet_penalty, hazard_weight,
                time_limit_seconds, num_workers, source_metadata,
            ),
        )

    allocations = []
    for (h_id, s_id), var in x.items():
        amount = int(solver.Value(var))
        if amount > 0:
            allocations.append(
                AllocationRecord(
                    habitation_id=h_id,
                    site_id=s_id,
                    allocated_population=amount,
                    distance=float(distances[(h_id, s_id)]),
                    constraint_flags={"feasible_pair": True},
                )
            )

    unmet_rows = []
    for h in habitations:
        allocated = sum(
            r.allocated_population
            for r in allocations
            if r.habitation_id == h.habitation_id
        )
        unmet_rows.append(
            UnmetDemand(
                h.habitation_id, h.exposed_population, allocated,
                h.exposed_population - allocated,
            )
        )

    return L13Result(
        status=status_name,
        objective_value=float(solver.ObjectiveValue()) / scale,
        allocations=tuple(allocations),
        unmet=tuple(unmet_rows),
        metadata=_metadata(
            distance_weight, unmet_penalty, hazard_weight,
            time_limit_seconds, num_workers, source_metadata,
        ),
    )


def _metadata(distance_weight, unmet_penalty, hazard_weight,
              time_limit_seconds, num_workers, source_metadata):
    return {
        "layer": "L13",
        "model_version": MODEL_VERSION,
        "formula_version": FORMULA_VERSION,
        "objective": "distance_weight*travel_distance + unmet_penalty*unmet_population + hazard_weight*residual_hazard_exposure",
        "distance_weight": distance_weight,
        "unmet_penalty": unmet_penalty,
        "hazard_weight": hazard_weight,
        "solver": "OR-Tools CP-SAT",
        "time_limit_seconds": time_limit_seconds,
        "num_workers": num_workers,
        "source_metadata": dict(source_metadata or {}),
        "database_write": False,
    }
