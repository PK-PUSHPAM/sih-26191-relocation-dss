import pytest

cp_model = pytest.importorskip("ortools.sat.python.cp_model")

from src.optimization.l13 import (
    CandidateSite, HabitationDemand, L13Error, run_l13,
)


def h(i, pop): return HabitationDemand(i, pop)
def s(i, cap, hazard, feasible): return CandidateSite(i, cap, hazard, tuple(feasible))


def base_run(**kwargs):
    return run_l13(
        [h("H1", 100)],
        [s("S1", 60, 0.0, ["H1"]), s("S2", 100, 0.0, ["H1"])],
        {("H1", "S1"): 10.0, ("H1", "S2"): 20.0},
        distance_weight=kwargs.get("distance_weight", 1.0),
        unmet_penalty=kwargs.get("unmet_penalty", 1000.0),
        hazard_weight=kwargs.get("hazard_weight", 0.0),
    )


def test_capacity_and_demand_constraints():
    result = base_run()
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert sum(x.allocated_population for x in result.allocations) == 100
    assert result.unmet[0].unmet_population == 0
    assert sum(x.allocated_population for x in result.allocations if x.site_id == "S1") <= 60


def test_distance_objective_prefers_nearer_site_when_capacity_allows():
    result = base_run()
    assert [(x.site_id, x.allocated_population) for x in result.allocations] == [
        ("S1", 60), ("S2", 40)
    ]


def test_unmet_penalty_allows_capacity_shortfall():
    result = run_l13(
        [h("H1", 100)],
        [s("S1", 40, 0.0, ["H1"])],
        {("H1", "S1"): 10.0},
        distance_weight=1.0, unmet_penalty=1000.0, hazard_weight=0.0,
    )
    assert result.unmet[0].unmet_population == 60


def test_feasible_pair_requires_distance():
    with pytest.raises(L13Error, match="missing distance"):
        run_l13(
            [h("H1", 10)], [s("S1", 10, 0.0, ["H1"])], {},
            distance_weight=1.0, unmet_penalty=1000.0, hazard_weight=0.0,
        )


def test_infeasible_pair_is_not_allocated():
    result = run_l13(
        [h("H1", 10)], [s("S1", 10, 0.0, [])],
        {}, distance_weight=1.0, unmet_penalty=1000.0, hazard_weight=0.0,
    )
    assert result.unmet[0].unmet_population == 10
    assert result.allocations == ()


def test_hazard_term_affects_choice():
    result = run_l13(
        [h("H1", 10)],
        [s("SAFE", 10, 0.0, ["H1"]), s("HAZ", 10, 1.0, ["H1"])],
        {("H1", "SAFE"): 10.0, ("H1", "HAZ"): 0.0},
        distance_weight=1.0, unmet_penalty=1000.0, hazard_weight=100.0,
    )
    assert result.allocations[0].site_id == "SAFE"


def test_unknown_feasible_habitation_is_rejected():
    with pytest.raises(L13Error, match="unknown habitation_id"):
        run_l13(
            [h("H1", 10)],
            [s("S1", 10, 0.0, ["H2"])],
            {},
            distance_weight=1.0, unmet_penalty=1000.0, hazard_weight=0.0,
        )


def test_nonfinite_distance_is_rejected():
    with pytest.raises(L13Error, match="distance must be non-negative"):
        run_l13(
            [h("H1", 10)],
            [s("S1", 10, 0.0, ["H1"])],
            {("H1", "S1"): float("inf")},
            distance_weight=1.0, unmet_penalty=1000.0, hazard_weight=0.0,
        )


def test_nonfinite_weight_is_rejected():
    with pytest.raises(L13Error, match="distance_weight must be > 0"):
        run_l13(
            [h("H1", 10)],
            [s("S1", 10, 0.0, ["H1"])],
            {("H1", "S1"): 1.0},
            distance_weight=float("inf"), unmet_penalty=1000.0, hazard_weight=0.0,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exposed_population", -1),
        ("effective_capacity", -1),
        ("hazard", 1.1),
    ],
)
def test_invalid_input(field, value):
    if field == "exposed_population":
        with pytest.raises(L13Error): run_l13(
            [h("H1", value)], [s("S1", 10, 0.0, ["H1"])],
            {("H1","S1"):1}, distance_weight=1, unmet_penalty=1, hazard_weight=0)
    elif field == "effective_capacity":
        with pytest.raises(L13Error): run_l13(
            [h("H1", 10)], [s("S1", value, 0.0, ["H1"])],
            {("H1","S1"):1}, distance_weight=1, unmet_penalty=1, hazard_weight=0)
    else:
        with pytest.raises(L13Error): run_l13(
            [h("H1", 10)], [s("S1", 10, value, ["H1"])],
            {("H1","S1"):1}, distance_weight=1, unmet_penalty=1, hazard_weight=0)


def test_no_database_write_and_metadata():
    result = base_run()
    assert result.metadata["solver"] == "OR-Tools CP-SAT"
    assert result.metadata["database_write"] is False
