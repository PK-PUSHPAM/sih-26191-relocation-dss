"""Focused L06 tests using synthetic/test rainfall fixtures only."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from affine import Affine

from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.hazards.rainfall import (
    LocalCsvRainfallProvider,
    RainfallConfigurationError,
    RainfallEvaluationState,
    RainfallModelError,
    RainfallObservation,
    RainfallProvenance,
    RainfallRule,
    RainfallValidationError,
    UnavailableRainfallProvider,
    build_rainfall_provenance,
    evaluate_rainfall_grid,
    evaluate_rainfall_window,
    evaluate_provider_result,
)
from src.spatial.grid import DEFAULT_NODATA_FLOAT, create_canonical_grid


UTC = timezone.utc


def observation(rainfall, cell_id=0, minutes=0, **kwargs):
    return RainfallObservation(
        rainfall_mm=rainfall,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes),
        cell_id=cell_id,
        **kwargs,
    )


def test_threshold_below_boundary_and_above_are_deterministic():
    rule = RainfallRule(threshold_mm=10.0)
    below = evaluate_rainfall_window([observation(9.9)], 0, rule)
    boundary = evaluate_rainfall_window([observation(10.0)], 0, rule)
    above = evaluate_rainfall_window([observation(10.1)], 0, rule)
    assert below.state == RainfallEvaluationState.NOT_TRIGGERED
    assert boundary.state == RainfallEvaluationState.TRIGGERED
    assert above.state == RainfallEvaluationState.TRIGGERED
    assert "below" in below.explanation
    assert "greater than or equal" in boundary.explanation
    repeat = evaluate_rainfall_window([observation(10.0)], 0, rule)
    assert boundary == repeat


def test_missing_rainfall_is_non_evaluable_not_zero():
    result = evaluate_rainfall_window([observation(None)], 0, RainfallRule(10.0))
    assert result.state == RainfallEvaluationState.MISSING_DATA
    assert result.rainfall_metric_mm is None


def test_invalid_rainfall_and_timestamp_are_rejected():
    with pytest.raises(RainfallValidationError):
        observation(-1.0)
    with pytest.raises(RainfallValidationError):
        RainfallObservation(rainfall_mm=1.0, observed_at=datetime(2026, 1, 1), cell_id=0)
    with pytest.raises(RainfallValidationError, match="Missing observed_at"):
        RainfallObservation.from_mapping({"cell_id": 0, "rainfall_mm": 1.0})
    with pytest.raises(RainfallValidationError, match="Invalid observed_at"):
        RainfallObservation.from_mapping({"cell_id": 0, "rainfall_mm": 1.0, "observed_at": "invalid"})
    missing_timestamp = evaluate_rainfall_window(
        [RainfallObservation(1.0, None, cell_id=0)], 0, RainfallRule(1.0)
    )
    assert missing_timestamp.state == RainfallEvaluationState.MISSING_TIMESTAMP


def test_multiple_observations_and_incomplete_window():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=2)
    observations = [observation(3.0, minutes=0), observation(4.0, minutes=60)]
    result = evaluate_rainfall_window(observations, 0, RainfallRule(7.0), start, end, expected_observation_count=2)
    assert result.state == RainfallEvaluationState.TRIGGERED
    incomplete = evaluate_rainfall_window(observations[:1], 0, RainfallRule(7.0), start, end, expected_observation_count=2)
    assert incomplete.state == RainfallEvaluationState.INCOMPLETE_WINDOW
    missing_bounds = evaluate_rainfall_window(observations, 0, RainfallRule(7.0), expected_observation_count=2)
    assert missing_bounds.state == RainfallEvaluationState.INCOMPLETE_WINDOW


def test_duplicate_observation_provider_and_evaluation():
    duplicated = [observation(1.0), observation(2.0)]
    result = evaluate_rainfall_window(duplicated, 0, RainfallRule(2.0))
    assert result.state == RainfallEvaluationState.DUPLICATE_OBSERVATION

def test_local_provider_preserves_missingness_and_provenance(tmp_path):
    csv_path = tmp_path / "rainfall_test_fixture.csv"
    pd.DataFrame([
        {"cell_id": 0, "rainfall_mm": "", "observed_at": "2026-01-01T00:00:00Z"},
        {"cell_id": 1, "rainfall_mm": 12.0, "observed_at": "2026-01-01T00:00:00Z"},
    ]).to_csv(csv_path, index=False)
    provider_result = LocalCsvRainfallProvider(csv_path, source_id="test_rainfall_fixture").fetch()
    assert provider_result.state == RainfallEvaluationState.PROVIDER_AVAILABLE
    assert provider_result.provenance.operational is False
    assert provider_result.provenance.source_kind == "local_or_test_input"
    assert provider_result.observations[0].rainfall_mm is None


def test_local_provider_duplicate_invalid_and_unavailable_states(tmp_path):
    duplicate_path = tmp_path / "duplicate.csv"
    pd.DataFrame([
        {"cell_id": 0, "rainfall_mm": 1.0, "observed_at": "2026-01-01T00:00:00Z"},
        {"cell_id": 0, "rainfall_mm": 2.0, "observed_at": "2026-01-01T00:00:00Z"},
    ]).to_csv(duplicate_path, index=False)
    duplicate = LocalCsvRainfallProvider(duplicate_path).fetch()
    assert duplicate.state == RainfallEvaluationState.DUPLICATE_OBSERVATION

    invalid_path = tmp_path / "invalid.csv"
    pd.DataFrame([{"cell_id": 0, "rainfall_mm": 1.0, "observed_at": "not-a-timestamp"}]).to_csv(invalid_path, index=False)
    invalid = LocalCsvRainfallProvider(invalid_path).fetch()
    assert invalid.state == RainfallEvaluationState.INVALID_DATA

    unavailable = LocalCsvRainfallProvider(tmp_path / "missing.csv").fetch()
    assert unavailable.state == RainfallEvaluationState.PROVIDER_UNAVAILABLE
    assert unavailable.provenance.operational is False
    explicit = UnavailableRainfallProvider().fetch()
    assert explicit.state == RainfallEvaluationState.PROVIDER_UNAVAILABLE


def test_local_provider_blank_and_nan_rainfall_have_distinct_states(tmp_path):
    blank_path = tmp_path / "blank.csv"
    pd.DataFrame([{"cell_id": 0, "rainfall_mm": "", "observed_at": "2026-01-01T00:00:00Z"}]).to_csv(blank_path, index=False)
    blank_provider = LocalCsvRainfallProvider(blank_path).fetch()
    assert blank_provider.state == RainfallEvaluationState.PROVIDER_AVAILABLE
    blank_result = evaluate_provider_result(blank_provider, 0, RainfallRule(1.0))
    assert blank_result.state == RainfallEvaluationState.MISSING_DATA

    nan_path = tmp_path / "nan.csv"
    nan_path.write_text("cell_id,rainfall_mm,observed_at\n0,NaN,2026-01-01T00:00:00Z\n", encoding="utf-8")
    nan_provider = LocalCsvRainfallProvider(nan_path).fetch()
    assert nan_provider.state == RainfallEvaluationState.INVALID_DATA


def test_grid_mapping_uses_existing_cell_ids_without_interpolation():
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    provenance = RainfallProvenance("test", "fixture", "local_or_test_input", operational=False)
    result = evaluate_rainfall_grid([observation(12.0, cell_id=0)], grid, RainfallRule(10.0), provenance=provenance)
    assert result.states_by_cell[0] == RainfallEvaluationState.TRIGGERED
    assert result.trigger_grid[0, 0] == 1.0
    assert result.metric_grid[0, 0] == pytest.approx(12.0)
    assert result.metadata["interpolation"] is False
    assert result.metadata["state_scope"] == "observed_cells_only; unobserved cells are NoData"
    assert 1 not in result.states_by_cell
    station_observation = RainfallObservation(12.0, datetime(2026, 1, 1, tzinfo=UTC), station_id="S1")
    with pytest.raises(RainfallModelError, match="interpolation"):
        evaluate_rainfall_grid([station_observation], grid, RainfallRule(10.0))


def test_grid_invalid_cell_id_and_missing_cell_are_explicit():
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    with pytest.raises(RainfallModelError, match="outside"):
        evaluate_rainfall_grid([observation(1.0, cell_id=grid.total_cells)], grid, RainfallRule(10.0))
    result = evaluate_rainfall_grid([], grid, RainfallRule(10.0))
    assert result.states_by_cell == {}
    assert np.all(result.metric_grid == DEFAULT_NODATA_FLOAT)


@pytest.mark.parametrize(
    "invalid_grid",
    [
        replace(create_canonical_grid((500000, 3000000, 500060, 3000060)), crs="EPSG:4326"),
        create_canonical_grid((500000, 3000000, 500060, 3000060), resolution=10.0),
        replace(create_canonical_grid((500000, 3000000, 500060, 3000060)), transform=Affine(30, 1, 499980, 0, -30, 3000060)),
    ],
)
def test_grid_contract_rejects_wrong_crs_resolution_or_transform(invalid_grid):
    with pytest.raises(RainfallModelError, match="canonical|30 m|CRS"):
        evaluate_rainfall_grid([observation(1.0)], invalid_grid, RainfallRule(1.0))


def test_rule_configuration_requires_explicit_threshold():
    with pytest.raises(RainfallConfigurationError, match="No rainfall threshold"):
        RainfallRule.from_config()
    rule = RainfallRule.from_config(threshold_mm=25.0)
    assert rule.threshold_mm == 25.0
    assert rule.parameter_status == "UNVALIDATED_PROTOTYPE_CONFIGURATION_REQUIRED"
    with pytest.raises(RainfallConfigurationError):
        RainfallRule(1.0, comparison="greater_than")
    with pytest.raises(RainfallConfigurationError):
        RainfallRule("not-numeric")


def test_provider_state_propagates_to_trigger_result(tmp_path):
    unavailable = UnavailableRainfallProvider("missing-source").fetch()
    unavailable_result = evaluate_provider_result(unavailable, 0, RainfallRule(1.0))
    assert unavailable_result.state == RainfallEvaluationState.PROVIDER_UNAVAILABLE

    duplicate_path = tmp_path / "duplicate.csv"
    pd.DataFrame([
        {"cell_id": 0, "rainfall_mm": 1.0, "observed_at": "2026-01-01T00:00:00Z"},
        {"cell_id": 0, "rainfall_mm": 2.0, "observed_at": "2026-01-01T00:00:00Z"},
    ]).to_csv(duplicate_path, index=False)
    duplicate = LocalCsvRainfallProvider(duplicate_path).fetch()
    assert evaluate_provider_result(duplicate, 0, RainfallRule(1.0)).state == RainfallEvaluationState.DUPLICATE_OBSERVATION

    invalid_path = tmp_path / "invalid-rainfall.csv"
    invalid_path.write_text("cell_id,rainfall_mm,observed_at\n0,-1,2026-01-01T00:00:00Z\n", encoding="utf-8")
    invalid = LocalCsvRainfallProvider(invalid_path).fetch()
    assert evaluate_provider_result(invalid, 0, RainfallRule(1.0)).state == RainfallEvaluationState.INVALID_DATA


def test_provider_result_provenance_metadata():
    provider_result = UnavailableRainfallProvider("test-unavailable").fetch()
    metadata = build_rainfall_provenance(provider_result, None)
    assert metadata["layer"] == "L06"
    assert metadata["provider"]["source_id"] == "test-unavailable"
    assert metadata["provider"]["operational"] is False
    assert "never impute zero" in metadata["missing_data_policy"]
    with pytest.raises(RainfallModelError):
        RainfallProvenance("local", "fixture", "local_or_test_input", operational=True)


def test_complete_provider_to_evaluator_provenance_chain(tmp_path):
    csv_path = tmp_path / "rainfall.csv"
    csv_path.write_text("cell_id,rainfall_mm,observed_at\n0,12,2026-01-01T00:00:00Z\n", encoding="utf-8")
    provider = LocalCsvRainfallProvider(csv_path, source_id="source-1").fetch()
    end = datetime(2026, 1, 1, 1, tzinfo=UTC)
    result = evaluate_provider_result(provider, 0, RainfallRule(10.0), window_end=end)
    assert result.state == RainfallEvaluationState.TRIGGERED
    assert result.provenance is not None
    provenance = result.provenance.to_dict()
    assert provenance["source_id"] == "source-1"
    assert provenance["source_path"] == csv_path.as_posix()
    assert provenance["checksum_sha256"]
    assert provenance["operational"] is False
    assert provenance["real_time"] is False
    assert provenance["observation_timestamps"] == ["2026-01-01T00:00:00+00:00"]
    assert provenance["evaluation_window_end"] == end.isoformat()
    assert provenance["evaluation_timestamp"] == end.isoformat()
    assert provenance["spatial_id"] == 0
    assert provenance["rainfall_metric_mm"] == pytest.approx(12.0)
    assert provenance["threshold_mm"] == pytest.approx(10.0)
    assert provenance["rule_version"] == "L06-trigger-1.0"


def test_timestamp_gap_detection_is_explicitly_not_supported():
    observations = [observation(1.0, minutes=0), observation(1.0, minutes=120)]
    result = evaluate_rainfall_window(
        observations,
        0,
        RainfallRule(2.0),
        window_start=datetime(2026, 1, 1, tzinfo=UTC),
        window_end=datetime(2026, 1, 1, 3, tzinfo=UTC),
        expected_observation_count=2,
    )
    assert result.state == RainfallEvaluationState.TRIGGERED