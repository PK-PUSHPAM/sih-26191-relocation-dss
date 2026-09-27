from datetime import datetime, timezone

import pytest

from src.capacity.l11 import (
    CapacityQuality,
    CapacitySiteInput,
    L11Error,
    run_l11,
)


def site(**overrides):
    data = {
        "site_id": "S1",
        "area_m2": 10_000.0,
        "daily_water_liters": 14_000.0,
        "sanitation_capacity": 200.0,
        "health_beds": 1.0,
        "access_capacity": 500.0,
    }
    data.update(overrides)
    return CapacitySiteInput(**data)


def test_derives_all_component_capacities_and_effective_capacity():
    result = run_l11([site()])
    record = result.records[0]

    assert record.land_cap == 150
    assert record.water_cap == 200
    assert record.sanitation_cap == 200
    assert record.health_cap == 1000
    assert record.access_cap == 500
    assert record.binding_bottleneck == "land"
    assert record.effective_cap == 120
    assert record.quality_flag is CapacityQuality.COMPLETE


def test_water_is_binding_when_low():
    record = run_l11([site(daily_water_liters=7_000.0)]).records[0]
    assert record.binding_bottleneck == "water"
    assert record.effective_cap == 80


def test_sanitation_is_binding():
    record = run_l11([site(sanitation_capacity=50.0)]).records[0]
    assert record.binding_bottleneck == "sanitation"
    assert record.effective_cap == 40


def test_health_is_binding():
    record = run_l11([site(health_beds=0.1)]).records[0]
    assert record.binding_bottleneck == "health"
    assert record.effective_cap == 12


def test_access_is_binding():
    record = run_l11([site(access_capacity=60.0)]).records[0]
    assert record.binding_bottleneck == "access"
    assert record.effective_cap == 48


def test_missing_input_is_not_zero():
    record = run_l11([site(daily_water_liters=None)]).records[0]
    assert record.quality_flag is CapacityQuality.NON_EVALUABLE
    assert record.effective_cap is None
    assert record.water_cap is None
    assert "daily_water_liters" in record.explanation["missing_fields"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("area_m2", -1),
        ("daily_water_liters", -1),
        ("sanitation_capacity", -1),
        ("health_beds", -1),
        ("access_capacity", -1),
    ],
)
def test_negative_input_is_invalid(field, value):
    record = run_l11([site(**{field: value})]).records[0]
    assert record.quality_flag is CapacityQuality.INVALID
    assert record.effective_cap is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("area_m2", float("nan")),
        ("daily_water_liters", float("inf")),
        ("sanitation_capacity", float("nan")),
        ("health_beds", float("-inf")),
        ("access_capacity", float("nan")),
    ],
)
def test_non_finite_input_is_invalid(field, value):
    record = run_l11([site(**{field: value})]).records[0]
    assert record.quality_flag is CapacityQuality.INVALID
    assert record.effective_cap is None


def test_boolean_numeric_input_is_invalid():
    record = run_l11([site(health_beds=True)]).records[0]
    assert record.quality_flag is CapacityQuality.INVALID


def test_safety_factor_is_frozen():
    with pytest.raises(L11Error, match="frozen L11 configuration"):
        run_l11([site()], safety_factor=0.75)


def test_all_parameters_are_frozen():
    with pytest.raises(L11Error):
        run_l11([site()], target_density_per_hectare=100)


def test_tie_uses_stable_component_order():
    record = run_l11(
        [site(area_m2=10_000, daily_water_liters=10_500, sanitation_capacity=150, health_beds=0.15, access_capacity=150)]
    ).records[0]
    assert record.binding_bottleneck == "land"


def test_timestamp_must_be_timezone_aware():
    with pytest.raises(L11Error, match="timezone-aware"):
        run_l11([site()], execution_timestamp=datetime(2026, 9, 27))


def test_to_dict_is_persistence_ready():
    record = run_l11([site()]).records[0].to_dict()
    assert record["binding_bottleneck"] == "land"
    assert record["effective_cap"] == 120
    assert record["quality_flag"] == "complete"


def test_result_contains_provenance_metadata():
    result = run_l11([site()], source_metadata={"site_source": "validated_input"})
    assert result.metadata["model_version"] == "L11-carrying-capacity-1.0"
    assert result.metadata["formula_version"] == "CC-floor-min-0.80"
    assert result.metadata["source_metadata"]["site_source"] == "validated_input"


def test_duplicate_site_ids_are_not_silently_merged():
    result = run_l11([site(), site(site_id="S1")])
    assert len(result.records) == 2
