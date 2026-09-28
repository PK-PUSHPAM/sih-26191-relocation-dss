"""Unit tests for L10 relocation-site suitability engine."""
from datetime import datetime, timezone

import numpy as np
import pytest
from shapely.geometry import Polygon

from src.suitability.l10 import (
    FORMULA_VERSION,
    L10Error,
    L10_MODEL_VERSION,
    SiteCandidateInput,
    SiteQuality,
    SiteStatus,
    SUITABILITY_WEIGHTS,
    run_l10,
)

def square(size=100.0, x=0.0, y=0.0):
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])

def make_candidate(site_id="S1", **overrides):
    values = {
        "geometry": square(),
        "combined_risk": 0.0,
        "slope_score": 1.0,
        "road_score": 1.0,
        "water_score": 1.0,
        "health_score": 1.0,
        "education_score": 1.0,
        "land_use_score": 1.0,
        "services_score": 1.0,
        "slope_degrees": 10.0,
        "road_distance_m": 100.0,
        "red_zone": False,
        "water_body": False,
        "protected_land": False,
    }
    values.update(overrides)
    return SiteCandidateInput(site_id=site_id, **values)

def test_frozen_formula_all_one_components():
    result = run_l10([make_candidate()])
    record = result.records[0]
    assert record.suitability == 1.0
    assert record.status is SiteStatus.ELIGIBLE
    assert record.quality_flag is SiteQuality.COMPLETE

def test_weighted_formula():
    candidate = make_candidate(
        combined_risk=0.2,
        slope_score=0.4,
        road_score=0.6,
        water_score=0.8,
        health_score=0.2,
        education_score=1.0,
        land_use_score=0.3,
        services_score=0.7,
    )
    result = run_l10([candidate])
    expected = (
        0.30 * 0.8 + 0.15 * 0.4 + 0.15 * 0.6 + 0.15 * 0.8
        + 0.10 * 0.2 + 0.05 * 1.0 + 0.05 * 0.3 + 0.05 * 0.7
    )
    assert result.records[0].suitability == round(expected, 4)

@pytest.mark.parametrize("flag", ["red_zone", "water_body", "protected_land"])
def test_hard_exclusions_reject_before_scoring(flag):
    result = run_l10([make_candidate(**{flag: True, "combined_risk": None})])
    record = result.records[0]
    assert record.status is SiteStatus.REJECTED
    assert record.quality_flag is SiteQuality.COMPLETE
    assert record.suitability is None
    assert flag in record.explanation["exclusion_reasons"]

def test_hard_exclusion_precedes_invalid_scoring_input():
    result = run_l10([make_candidate(red_zone=True, combined_risk=np.nan)])
    record = result.records[0]
    assert record.status is SiteStatus.REJECTED
    assert record.quality_flag is SiteQuality.COMPLETE
    assert "red_zone" in record.explanation["exclusion_reasons"]

def test_area_below_one_hectare_rejected():
    result = run_l10([make_candidate(geometry=square(99.9))])
    record = result.records[0]
    assert record.status is SiteStatus.REJECTED
    assert "area_below_1_ha" in record.explanation["exclusion_reasons"]

def test_slope_above_threshold_rejected():
    result = run_l10([make_candidate(slope_degrees=30.0001)])
    record = result.records[0]
    assert record.status is SiteStatus.REJECTED
    assert "slope_above_30_degrees" in record.explanation["exclusion_reasons"]

def test_slope_boundary_is_allowed():
    assert run_l10([make_candidate(slope_degrees=30.0)]).records[0].status is SiteStatus.ELIGIBLE

def test_road_distance_above_threshold_rejected():
    result = run_l10([make_candidate(road_distance_m=2000.0001)])
    record = result.records[0]
    assert record.status is SiteStatus.REJECTED
    assert "road_distance_above_2000m" in record.explanation["exclusion_reasons"]

def test_road_distance_boundary_is_allowed():
    assert run_l10([make_candidate(road_distance_m=2000.0)]).records[0].status is SiteStatus.ELIGIBLE

@pytest.mark.parametrize("name", [
    "slope_score", "road_score", "water_score", "health_score",
    "education_score", "land_use_score", "services_score",
])
def test_missing_score_is_conditional_not_zero(name):
    result = run_l10([make_candidate(**{name: None})])
    record = result.records[0]
    assert record.status is SiteStatus.CONDITIONAL
    assert record.quality_flag is SiteQuality.NON_EVALUABLE
    assert record.suitability is None
    assert name in record.explanation["missing_fields"]

@pytest.mark.parametrize("name", [
    "slope_score", "road_score", "water_score", "health_score",
    "education_score", "land_use_score", "services_score", "combined_risk",
])
def test_invalid_score_is_invalid_quality(name):
    result = run_l10([make_candidate(**{name: np.nan})])
    record = result.records[0]
    assert record.status is SiteStatus.REJECTED
    assert record.quality_flag is SiteQuality.INVALID
    assert record.suitability is None

@pytest.mark.parametrize("name", ["slope_degrees", "road_distance_m"])
def test_missing_generation_constraint_is_conditional(name):
    result = run_l10([make_candidate(**{name: None})])
    record = result.records[0]
    assert record.status is SiteStatus.CONDITIONAL
    assert record.quality_flag is SiteQuality.NON_EVALUABLE
    assert name in record.explanation["missing_fields"]

def test_h_safe_is_inverse_of_combined_risk():
    result = run_l10([make_candidate(combined_risk=0.25)])
    assert result.records[0].explanation["h_safe"] == 0.75

def test_score_is_bounded_at_zero_and_one():
    zero = make_candidate(
        combined_risk=1.0,
        slope_score=0.0, road_score=0.0, water_score=0.0,
        health_score=0.0, education_score=0.0, land_use_score=0.0, services_score=0.0,
    )
    one = make_candidate(combined_risk=0.0)
    result = run_l10([zero, one])
    assert result.records[0].suitability == 0.0
    assert result.records[1].suitability == 1.0

def test_weights_are_frozen():
    changed = dict(SUITABILITY_WEIGHTS)
    changed["slope"] = 0.20
    with pytest.raises(L10Error):
        run_l10([make_candidate()], weights=changed)

def test_input_validation():
    with pytest.raises(L10Error):
        run_l10(None)
    with pytest.raises(L10Error):
        run_l10([object()])
    with pytest.raises(L10Error):
        run_l10([make_candidate(site_id="")])
    with pytest.raises(L10Error):
        run_l10([make_candidate(geometry=None)])

def test_timestamp_must_be_timezone_aware():
    with pytest.raises(L10Error):
        run_l10([make_candidate()], execution_timestamp=datetime(2026, 1, 1))

def test_provenance():
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = run_l10(
        [make_candidate()],
        execution_timestamp=timestamp,
        source_metadata={"source": "synthetic-test"},
    )
    assert result.metadata["layer"] == "L10"
    assert result.metadata["model_version"] == L10_MODEL_VERSION
    assert result.metadata["formula_version"] == FORMULA_VERSION
    assert result.metadata["crs"] == "EPSG:32644"
    assert result.metadata["execution_timestamp"] == timestamp.isoformat()

def test_serialization():
    result = run_l10([make_candidate()])
    payload = result.to_dict()
    assert set(payload) == {"records", "metadata"}
    assert set(payload["records"][0]) == {
        "site_id", "geometry", "area_m2", "suitability",
        "status", "quality_flag", "explanation",
    }

def test_deterministic_with_fixed_timestamp():
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candidate = make_candidate(
        combined_risk=0.3, slope_score=0.7, road_score=0.4,
        water_score=0.8, health_score=0.6, education_score=0.5,
        land_use_score=0.9, services_score=0.2,
    )
    a = run_l10([candidate], execution_timestamp=timestamp)
    b = run_l10([candidate], execution_timestamp=timestamp)
    assert a.to_dict() == b.to_dict()

def test_empty_input():
    result = run_l10([])
    assert result.records == ()


def test_duplicate_site_ids_are_rejected():
    with pytest.raises(L10Error):
        run_l10([make_candidate("S1"), make_candidate("S1")])


@pytest.mark.parametrize("bad_weights", [
    {"hazard_safety": "0.30", **{k: v for k, v in SUITABILITY_WEIGHTS.items() if k != "hazard_safety"}},
    {**SUITABILITY_WEIGHTS, "extra": 0.0},
    {**SUITABILITY_WEIGHTS, "hazard_safety": np.nan},
    {**SUITABILITY_WEIGHTS, "hazard_safety": True},
])
def test_malformed_weights_are_rejected(bad_weights):
    with pytest.raises(L10Error):
        run_l10([make_candidate()], weights=bad_weights)


def test_non_mapping_weights_are_rejected():
    with pytest.raises(L10Error):
        run_l10([make_candidate()], weights=["bad"])


def test_source_metadata_must_be_mapping():
    with pytest.raises(L10Error):
        run_l10([make_candidate()], source_metadata=["bad"])


def test_timestamp_type_must_be_datetime():
    with pytest.raises(L10Error):
        run_l10([make_candidate()], execution_timestamp="2026-01-01T00:00:00Z")


def test_area_exactly_one_hectare_is_allowed():
    result = run_l10([make_candidate(geometry=square(100.0))])
    assert result.records[0].status is SiteStatus.ELIGIBLE
    assert result.records[0].area_m2 == 10000.0
