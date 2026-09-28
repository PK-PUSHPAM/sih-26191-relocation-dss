import pytest

from src.recompute.l14 import (
    DatasetUpdate,
    L14Error,
    plan_for_config_change,
    plan_recompute,
)


def update(dataset_id, dataset_type, previous="v1", new="v2"):
    return DatasetUpdate(dataset_id, previous, new, dataset_type)


def test_no_updates_is_noop():
    result = plan_recompute([])
    assert result.invalidated_layers == ()
    assert result.reason == "no_dataset_updates"
    assert result.metadata["database_write"] is False


def test_rainfall_update_recomputes_from_l06_downstream():
    result = plan_recompute([update("rainfall-2026-09-27", "rainfall")])
    assert result.invalidated_layers == (
        "L01", "L02", "L03", "L04", "L05", "L06", "L07",
        "L08", "L09", "L10", "L11", "L12", "L13",
    )


def test_habitation_update_recomputes_from_l09_downstream():
    result = plan_recompute([update("hab-2026", "habitation")])
    assert result.invalidated_layers == (
        "L01", "L02", "L03", "L04", "L05", "L06", "L07",
        "L08", "L09", "L10", "L11", "L12", "L13",
    )


def test_multiple_updates_are_deduplicated_by_layer():
    result = plan_recompute([
        update("rain", "rainfall"),
        update("census", "census"),
    ])
    assert result.execution_order == result.invalidated_layers
    assert result.metadata["changed_dataset_count"] == 2


def test_duplicate_dataset_update_is_rejected():
    with pytest.raises(L14Error, match="duplicate dataset update"):
        plan_recompute([
            update("rain", "rainfall"),
            update("rain", "rainfall"),
        ])


def test_same_version_is_rejected():
    with pytest.raises(L14Error, match="must differ"):
        plan_recompute([update("rain", "rainfall", "v2", "v2")])


def test_unknown_dataset_type_is_rejected():
    with pytest.raises(L14Error, match="unsupported dataset_type"):
        plan_recompute([update("x", "unknown")])


def test_config_change_recomputes_from_affected_layer():
    result = plan_for_config_change(["L11"])
    assert result.invalidated_layers == ("L11", "L12", "L13")
    assert result.reason == "model_or_config_changed"


def test_multiple_config_changes_start_at_earliest_layer():
    result = plan_for_config_change(["L13", "L07"])
    assert result.execution_order[0] == "L07"
    assert result.execution_order[-1] == "L13"


def test_unknown_config_layer_is_rejected():
    with pytest.raises(L14Error, match="unknown layer"):
        plan_for_config_change(["L99"])


def test_no_config_change_is_noop():
    result = plan_for_config_change([])
    assert result.invalidated_layers == ()
    assert result.metadata["database_write"] is False

def test_non_dataset_update_is_rejected():
    with pytest.raises(L14Error, match="DatasetUpdate"):
        plan_recompute([{"dataset_id":"x"}])

def test_malformed_dataset_update_fields_are_rejected():
    with pytest.raises(L14Error, match="dataset_id"):
        plan_recompute([update("   ", "rainfall")])

def test_invalid_previous_version_is_rejected():
    with pytest.raises(L14Error, match="previous_version"):
        plan_recompute([update("rain", "rainfall", previous="", new="v2")])

def test_non_sequence_updates_are_rejected():
    with pytest.raises(L14Error, match="sequence"):
        plan_recompute("rainfall")

def test_non_sequence_config_changes_are_rejected():
    with pytest.raises(L14Error, match="sequence"):
        plan_for_config_change("L11")

def test_non_string_config_layer_is_rejected():
    with pytest.raises(L14Error, match="non-empty strings"):
        plan_for_config_change(["L11", None])
