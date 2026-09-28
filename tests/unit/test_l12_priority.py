from datetime import datetime

import pytest

from src.priority.l12 import L12Error, PriorityHabitationInput, PriorityQuality, PriorityTier, run_l12


def habitation(**overrides):
    data = {"habitation_id":"H1","risk":0.80,"exposed_pop":100,"exposed_pop_score":0.80,
            "vulnerability":0.70,"response_difficulty":0.60,"recurrence":0.40}
    data.update(overrides)
    return PriorityHabitationInput(**data)


def test_computes_frozen_formula():
    record = run_l12([habitation()]).records[0]
    assert record.priority_score == 0.74
    assert record.tier is PriorityTier.SHORT_TERM
    assert record.quality_flag is PriorityQuality.COMPLETE


@pytest.mark.parametrize(("score","expected"), [
    (0.75, PriorityTier.IMMEDIATE), (0.7499, PriorityTier.SHORT_TERM),
    (0.55, PriorityTier.SHORT_TERM), (0.5499, PriorityTier.MEDIUM_TERM),
    (0.35, PriorityTier.MEDIUM_TERM), (0.3499, PriorityTier.MONITOR),
])
def test_tier_boundaries(score, expected):
    record = run_l12([habitation(risk=score, exposed_pop_score=score,
                                  vulnerability=score, response_difficulty=score,
                                  recurrence=score)]).records[0]
    assert record.priority_score == round(score, 4)
    assert record.tier is expected


@pytest.mark.parametrize("field", ["risk","exposed_pop_score","vulnerability",
                                    "response_difficulty","recurrence","exposed_pop"])
def test_missing_input_is_non_evaluable(field):
    record = run_l12([habitation(**{field:None})]).records[0]
    assert record.quality_flag is PriorityQuality.NON_EVALUABLE
    assert record.priority_score is None
    assert record.tier is None


@pytest.mark.parametrize(("field","value"), [
    ("risk",-0.1),("risk",1.1),("risk",float("nan")),("vulnerability",float("inf")),
    ("response_difficulty",-1.0),("recurrence",True),("exposed_pop_score","0.5"),
    ("exposed_pop",-1),("exposed_pop",True),
])
def test_invalid_input_is_invalid(field, value):
    record = run_l12([habitation(**{field:value})]).records[0]
    assert record.quality_flag is PriorityQuality.INVALID
    assert record.priority_score is None


def test_zero_exposed_population_is_valid():
    record = run_l12([habitation(exposed_pop=0, exposed_pop_score=0.0)]).records[0]
    assert record.priority_score == 0.54
    assert record.tier is PriorityTier.MEDIUM_TERM


def test_duplicate_habitation_ids_are_not_merged():
    assert len(run_l12([habitation(), habitation(habitation_id="H1")]).records) == 2


def test_frozen_parameters():
    bad = {"risk":0.41,"exposed_pop":0.25,"vulnerability":0.20,
           "response_difficulty":0.10,"recurrence":0.05}
    with pytest.raises(L12Error):
        run_l12([habitation()], weights=bad)


def test_timestamp_must_be_timezone_aware():
    with pytest.raises(L12Error, match="timezone-aware"):
        run_l12([habitation()], execution_timestamp=datetime(2026,9,27))


def test_to_dict_is_persistence_ready():
    record = run_l12([habitation()]).records[0].to_dict()
    assert record["habitation_id"] == "H1"
    assert record["exposed_pop"] == 100
    assert record["priority_score"] == 0.74
    assert record["tier"] == "Short-term"


def test_provenance_metadata():
    result = run_l12([habitation()], source_metadata={"risk_source":"L08"})
    assert result.metadata["model_version"] == "L12-relocation-priority-1.0"
    assert result.metadata["formula_version"] == "RP-0.40-0.25-0.20-0.10-0.05"
    assert result.metadata["source_metadata"]["risk_source"] == "L08"

def test_duplicate_habitation_ids_are_rejected():
    with pytest.raises(L12Error, match="must be unique"):
        run_l12([habitation(), habitation(habitation_id="H1")])

def test_malformed_weights_are_rejected():
    with pytest.raises(L12Error):
        run_l12([habitation()], weights={"risk":"0.40"})

def test_malformed_thresholds_are_rejected():
    with pytest.raises(L12Error):
        run_l12([habitation()], thresholds={"immediate_min":0.75})

def test_non_mapping_source_metadata_is_rejected():
    with pytest.raises(L12Error, match="source_metadata"):
        run_l12([habitation()], source_metadata=["bad"])

def test_timestamp_type_is_rejected():
    with pytest.raises(L12Error, match="must be a datetime"):
        run_l12([habitation()], execution_timestamp="2026-09-28T00:00:00Z")

def test_non_habitation_input_is_rejected():
    with pytest.raises(L12Error, match="PriorityHabitationInput"):
        run_l12([{"habitation_id":"H1"}])
