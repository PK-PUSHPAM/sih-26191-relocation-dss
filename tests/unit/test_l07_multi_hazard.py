"""Focused L07 tests using synthetic normalized hazard fixtures only."""
from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pytest
from affine import Affine

from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.common.config import get_weights_config
from src.hazards.rainfall import RainfallEvaluationState
from src.risk.multi_hazard import (
    HazardGridInput,
    MultiHazardModelError,
    QualityState,
    RainfallCombinationInput,
    combine_multi_hazard,
    validate_l07_grid,
    validate_l07_weights,
)
from src.spatial.grid import DEFAULT_NODATA_FLOAT, create_canonical_grid


def make_grid():
    return create_canonical_grid((500000, 3000000, 500060, 3000060))


def make_inputs(grid, landslide=None, flood=None, rainfall=None, rainfall_state=None):
    shape = (grid.height, grid.width)
    l = np.full(shape, 0.2 if landslide is None else landslide, dtype=np.float32)
    f = np.full(shape, 0.3 if flood is None else flood, dtype=np.float32)
    r = np.full(shape, 0.0 if rainfall is None else rainfall, dtype=np.float32)
    states = {cell_id: (rainfall_state or RainfallEvaluationState.NOT_TRIGGERED) for cell_id in range(grid.total_cells)}
    return (
        HazardGridInput("landslide", l, grid, "L04-baseline-1.0", {"source": "l04"}),
        HazardGridInput("flood", f, grid, "L05-baseline-1.0", {"source": "l05"}),
        RainfallCombinationInput(r, states, grid, {"source": "l06"}),
    )


def test_exact_formula_and_boundaries():
    grid = make_grid()
    landslide, flood, rainfall = make_inputs(grid, landslide=0.2, flood=0.4, rainfall=1.0, rainfall_state=RainfallEvaluationState.TRIGGERED)
    result = combine_multi_hazard(grid, landslide, flood, rainfall, combination_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
    configured = get_weights_config()["multi_hazard_risk"]
    expected = configured["landslide_weight"] * 0.2 + configured["flood_weight"] * 0.4 + configured["rainfall_weight"] * 1.0
    assert np.allclose(result.combined_risk, expected)
    zero_l, zero_f, zero_r = make_inputs(grid, landslide=0.0, flood=0.0, rainfall=0.0)
    assert np.all(combine_multi_hazard(grid, zero_l, zero_f, zero_r).combined_risk == 0.0)
    one_l, one_f, one_r = make_inputs(grid, landslide=1.0, flood=1.0, rainfall=1.0, rainfall_state=RainfallEvaluationState.TRIGGERED)
    assert np.allclose(combine_multi_hazard(grid, one_l, one_f, one_r).combined_risk, 1.0)


def test_configured_weights_and_validation():
    configured = get_weights_config()["multi_hazard_risk"]
    assert validate_l07_weights() == {
        "landslide": configured["landslide_weight"],
        "flood": configured["flood_weight"],
        "rainfall": configured["rainfall_weight"],
    }
    with pytest.raises(MultiHazardModelError):
        validate_l07_weights({})
    with pytest.raises(MultiHazardModelError):
        validate_l07_weights({"landslide_weight": 0.5, "flood_weight": 0.5, "rainfall_weight": 0.5})
    with pytest.raises(MultiHazardModelError):
        validate_l07_weights({"landslide_weight": -0.1, "flood_weight": 0.6, "rainfall_weight": 0.5})
    with pytest.raises(MultiHazardModelError, match="exactly"):
        validate_l07_weights({"landslide_weight": 1.0, "flood_weight": 0.0, "other_weight": 0.0})


def test_deterministic_repeated_execution_and_provenance():
    grid = make_grid()
    inputs = make_inputs(grid, landslide=0.7, flood=0.6, rainfall=1.0, rainfall_state=RainfallEvaluationState.TRIGGERED)
    first = combine_multi_hazard(grid, *inputs)
    second = combine_multi_hazard(grid, *inputs)
    assert np.array_equal(first.combined_risk, second.combined_risk)
    assert first.metadata["formula_version"] == "H-0.45-0.35-0.20"
    assert first.metadata["model_version"] == "L07-combination-1.0"
    assert first.metadata["config_version"] == get_weights_config()["version"]
    assert first.metadata["inputs"]["landslide"]["source"] == "l04"
    assert first.metadata["inputs"]["landslide"]["model_version"] == "L04-baseline-1.0"
    assert first.metadata["inputs"]["flood"]["source"] == "l05"
    assert first.metadata["inputs"]["flood"]["model_version"] == "L05-baseline-1.0"
    assert first.metadata["inputs"]["rainfall"]["source"] == "l06"
    assert first.metadata["inputs"]["rainfall"]["model_version"] == "L06-trigger-1.0"
    assert first.metadata["quality_by_cell"]["0"] == "complete"


@pytest.mark.parametrize("missing_name", ["landslide", "flood", "rainfall"])
def test_missing_required_hazard_is_strict_non_evaluable(missing_name):
    grid = make_grid()
    inputs = list(make_inputs(grid, rainfall=1.0, rainfall_state=RainfallEvaluationState.TRIGGERED))
    index = {"landslide": 0, "flood": 1, "rainfall": 2}[missing_name]
    inputs[index] = None
    result = combine_multi_hazard(grid, *inputs)
    assert np.all(result.combined_risk == DEFAULT_NODATA_FLOAT)
    assert all(state == QualityState.NON_EVALUABLE for state in result.quality_by_cell.values())


@pytest.mark.parametrize("hazard_name", ["landslide", "flood"])
def test_l04_l05_per_cell_nodata_propagates(hazard_name):
    grid = make_grid()
    landslide, flood, rainfall = make_inputs(grid, rainfall=1.0, rainfall_state=RainfallEvaluationState.TRIGGERED)
    selected = landslide if hazard_name == "landslide" else flood
    values = selected.values.copy()
    values[0, 0] = DEFAULT_NODATA_FLOAT
    selected = replace(selected, values=values)
    if hazard_name == "landslide":
        landslide = selected
    else:
        flood = selected
    result = combine_multi_hazard(grid, landslide, flood, rainfall)
    assert result.quality_by_cell[0] == QualityState.NON_EVALUABLE
    assert result.combined_risk[0, 0] == DEFAULT_NODATA_FLOAT
    assert result.quality_by_cell[1] == QualityState.COMPLETE


def test_mixed_per_cell_rainfall_states_propagate_independently():
    grid = make_grid()
    landslide, flood, _ = make_inputs(grid, landslide=0.0, flood=0.0)
    trigger = np.zeros((grid.height, grid.width), dtype=np.float32)
    states = {cell_id: RainfallEvaluationState.NOT_TRIGGERED for cell_id in range(grid.total_cells)}
    trigger[0, 0] = 1.0
    states[0] = RainfallEvaluationState.TRIGGERED
    trigger[0, 1] = DEFAULT_NODATA_FLOAT
    states[1] = RainfallEvaluationState.PROVIDER_UNAVAILABLE
    rainfall = RainfallCombinationInput(trigger, states, grid, {"source": "l06"})
    result = combine_multi_hazard(grid, landslide, flood, rainfall)
    assert result.quality_by_cell[0] == QualityState.COMPLETE
    assert result.combined_risk[0, 0] == pytest.approx(0.20)
    assert result.quality_by_cell[1] == QualityState.NON_EVALUABLE
    assert result.combined_risk[0, 1] == DEFAULT_NODATA_FLOAT
    assert result.quality_by_cell[2] == QualityState.COMPLETE


def test_multiple_and_all_hazards_missing():
    grid = make_grid()
    landslide, flood, rainfall = make_inputs(grid)
    result = combine_multi_hazard(grid, None, flood, None)
    assert all(state == QualityState.NON_EVALUABLE for state in result.quality_by_cell.values())
    result_all = combine_multi_hazard(grid, None, None, None)
    assert np.all(result_all.combined_risk == DEFAULT_NODATA_FLOAT)
    assert all(state == QualityState.NON_EVALUABLE for state in result_all.quality_by_cell.values())


@pytest.mark.parametrize(
    "state,expected_quality",
    [
        (RainfallEvaluationState.TRIGGERED, QualityState.COMPLETE),
        (RainfallEvaluationState.NOT_TRIGGERED, QualityState.COMPLETE),
        (RainfallEvaluationState.MISSING_DATA, QualityState.NON_EVALUABLE),
        (RainfallEvaluationState.MISSING_TIMESTAMP, QualityState.NON_EVALUABLE),
        (RainfallEvaluationState.DUPLICATE_OBSERVATION, QualityState.NON_EVALUABLE),
        (RainfallEvaluationState.INCOMPLETE_WINDOW, QualityState.NON_EVALUABLE),
        (RainfallEvaluationState.PROVIDER_UNAVAILABLE, QualityState.NON_EVALUABLE),
        (RainfallEvaluationState.INVALID_DATA, QualityState.INVALID),
        (RainfallEvaluationState.INVALID_CONFIGURATION, QualityState.INVALID),
    ],
)
def test_rainfall_state_mapping(state, expected_quality):
    grid = make_grid()
    rainfall_values = np.full((grid.height, grid.width), 1.0 if state == RainfallEvaluationState.TRIGGERED else 0.0, dtype=np.float32)
    if expected_quality != QualityState.COMPLETE:
        rainfall_values.fill(DEFAULT_NODATA_FLOAT)
    rainfall = RainfallCombinationInput(
        rainfall_values,
        {cell_id: state for cell_id in range(grid.total_cells)},
        grid,
        {"rule_version": "L06-trigger-1.0"},
    )
    landslide, flood, _ = make_inputs(grid)
    result = combine_multi_hazard(grid, landslide, flood, rainfall)
    assert all(value == expected_quality for value in result.quality_by_cell.values())
    if expected_quality == QualityState.COMPLETE:
        expected = 0.45 * 0.2 + 0.35 * 0.3 + 0.20 * (1.0 if state == RainfallEvaluationState.TRIGGERED else 0.0)
        assert np.allclose(result.combined_risk, expected)
    else:
        assert np.all(result.combined_risk == DEFAULT_NODATA_FLOAT)


def test_rainfall_metric_millimetres_are_not_used():
    grid = make_grid()
    landslide, flood, _ = make_inputs(grid, landslide=0.0, flood=0.0)
    trigger = np.zeros((grid.height, grid.width), dtype=np.float32)
    rainfall = RainfallCombinationInput(trigger, {cell_id: RainfallEvaluationState.NOT_TRIGGERED for cell_id in range(grid.total_cells)}, grid, {"metric_grid": 9999.0})
    result = combine_multi_hazard(grid, landslide, flood, rainfall)
    assert np.all(result.combined_risk == 0.0)


@pytest.mark.parametrize(
    "bad_grid",
    [
        replace(make_grid(), crs="EPSG:4326"),
        create_canonical_grid((500000, 3000000, 500060, 3000060), resolution=10.0),
        replace(make_grid(), transform=Affine(30, 1, 499980, 0, -30, 3000060)),
    ],
)
def test_grid_contract_rejects_crs_resolution_and_transform(bad_grid):
    with pytest.raises(MultiHazardModelError):
        validate_l07_grid(bad_grid)


def test_grid_mismatch_and_cell_id_mismatch_rejected():
    grid = make_grid()
    other_grid = create_canonical_grid((500030, 3000000, 500090, 3000060))
    landslide, flood, rainfall = make_inputs(grid)
    with pytest.raises(MultiHazardModelError, match="canonical grid"):
        combine_multi_hazard(grid, replace(landslide, grid=other_grid), flood, rainfall)
    invalid_cell_states = {grid.total_cells: RainfallEvaluationState.TRIGGERED}
    invalid_rainfall = replace(rainfall, states_by_cell=invalid_cell_states)
    with pytest.raises(MultiHazardModelError, match="conflicts|cell"):
        combine_multi_hazard(grid, landslide, flood, invalid_rainfall)


@pytest.mark.parametrize("hazard_name", ["landslide", "flood"])
def test_value_range_and_quality_validation(hazard_name):
    grid = make_grid()
    landslide, flood, rainfall = make_inputs(grid)
    selected = landslide if hazard_name == "landslide" else flood
    for invalid_value in (-0.1, 1.1, np.nan, np.inf):
        with pytest.raises(MultiHazardModelError):
            invalid = replace(selected, values=np.full((grid.height, grid.width), invalid_value))
            combine_multi_hazard(grid, invalid if hazard_name == "landslide" else landslide, flood if hazard_name == "landslide" else invalid, rainfall)
    invalid = replace(landslide, quality_state=QualityState.INVALID)
    result = combine_multi_hazard(grid, invalid, flood, rainfall)
    assert all(state == QualityState.INVALID for state in result.quality_by_cell.values())


def test_unknown_hazard_and_shape_mismatch_rejected():
    grid = make_grid()
    landslide, flood, rainfall = make_inputs(grid)
    unknown = replace(landslide, hazard_name="rainfall")
    with pytest.raises(MultiHazardModelError, match="Expected L07 hazard"):
        combine_multi_hazard(grid, unknown, flood, rainfall)
    wrong_shape = replace(landslide, values=np.zeros((1, 1), dtype=np.float32))
    with pytest.raises(MultiHazardModelError, match="dimensions"):
        combine_multi_hazard(grid, wrong_shape, flood, rainfall)


def test_persistence_records_are_sql_null_ready_and_do_not_set_l08_fields():
    grid = make_grid()
    landslide, flood, rainfall = make_inputs(grid)
    result = combine_multi_hazard(grid, landslide, flood, rainfall)
    record = result.records[0].to_dict()
    assert record["quality_flag"] == "complete"
    assert "red_zone" not in record
    assert "risk_tier" not in record
    missing = combine_multi_hazard(grid, None, flood, rainfall).records[0].to_dict()
    assert missing["combined_risk"] is None
    assert missing["h_landslide"] is None


def test_output_bounds_and_spatial_metadata():
    grid = make_grid()
    landslide, flood, rainfall = make_inputs(grid, landslide=1.0, flood=1.0, rainfall=1.0, rainfall_state=RainfallEvaluationState.TRIGGERED)
    result = combine_multi_hazard(grid, landslide, flood, rainfall)
    valid = result.combined_risk[result.combined_risk != DEFAULT_NODATA_FLOAT]
    assert np.all((valid >= 0.0) & (valid <= 1.0))
    assert result.metadata["crs"] == CANONICAL_PROJECTED_CRS_STR
    assert result.metadata["resolution_m"] == 30.0
    assert result.metadata["l08_fields_written"] is False