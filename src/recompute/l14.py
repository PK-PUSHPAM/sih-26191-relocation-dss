"""L14 update/recompute planning engine.

L14 determines which analytical layers must be recomputed after an input
dataset or configuration version changes. It does not execute downstream
layers and does not write to the database.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Any, Mapping, Sequence


class L14Error(ValueError):
    """Raised for invalid update/recompute inputs."""


MODEL_VERSION = "L14-recompute-engine-1.0"

LAYER_ORDER: tuple[str, ...] = (
    "L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08",
    "L09", "L10", "L11", "L12", "L13",
)

DATASET_TO_LAYERS: Mapping[str, tuple[str, ...]] = {
    "boundary": ("L01", "L03"),
    "dem": ("L01", "L03", "L04", "L05", "L10"),
    "landslide": ("L01", "L04"),
    "flood": ("L01", "L05"),
    "rainfall": ("L01", "L06"),
    "river_discharge": ("L01", "L05"),
    "land_cover": ("L01", "L04", "L10"),
    "forest_constraints": ("L01", "L08", "L10"),
    "roads": ("L01", "L10"),
    "infrastructure": ("L01", "L09", "L10", "L11"),
    "habitation": ("L01", "L09", "L12", "L13"),
    "census": ("L01", "L09"),
    "health": ("L01", "L09", "L10", "L11"),
    "water": ("L01", "L10", "L11"),
    "sanitation": ("L01", "L11"),
    "access": ("L01", "L11"),
}


@dataclass(frozen=True)
class DatasetUpdate:
    dataset_id: str
    previous_version: str | None
    new_version: str
    dataset_type: str


@dataclass(frozen=True)
class RecomputePlan:
    changed_datasets: tuple[str, ...]
    invalidated_layers: tuple[str, ...]
    execution_order: tuple[str, ...]
    reason: str
    metadata: dict[str, object]


def _validate_update(update: DatasetUpdate) -> None:
    if not isinstance(update, DatasetUpdate):
        raise L14Error("updates entries must be DatasetUpdate")
    if not isinstance(update.dataset_id, str) or not update.dataset_id.strip():
        raise L14Error("dataset_id is required")
    if not isinstance(update.new_version, str) or not update.new_version.strip():
        raise L14Error("new_version is required")
    if update.previous_version is not None and (not isinstance(update.previous_version, str) or not update.previous_version.strip()):
        raise L14Error("previous_version must be a non-empty string or None")
    if update.previous_version == update.new_version:
        raise L14Error("new_version must differ from previous_version")
    if not isinstance(update.dataset_type, str) or not update.dataset_type.strip():
        raise L14Error("dataset_type is required")
    if update.dataset_type not in DATASET_TO_LAYERS:
        raise L14Error(f"unsupported dataset_type: {update.dataset_type}")


def _downstream_layers(seed_layers: set[str]) -> tuple[str, ...]:
    if not seed_layers:
        return ()
    earliest = min(LAYER_ORDER.index(layer) for layer in seed_layers)
    return LAYER_ORDER[earliest:]


def plan_recompute(updates: Sequence[DatasetUpdate]) -> RecomputePlan:
    """Build a deterministic downstream recomputation plan.

    Any changed source invalidates its direct consumers and all later layers.
    Duplicate dataset updates are rejected rather than silently merged.
    """
    if updates is None:
        raise L14Error("updates input is required")
    if not isinstance(updates, Sequence) or isinstance(updates, (str, bytes)):
        raise L14Error("updates must be a sequence of DatasetUpdate")
    if not updates:
        return RecomputePlan((), (), (), "no_dataset_updates", {
            "layer": "L14",
            "model_version": MODEL_VERSION,
            "database_write": False,
        })

    seen: set[str] = set()
    seed_layers: set[str] = set()
    changed: list[str] = []

    for update in updates:
        _validate_update(update)
        if update.dataset_id in seen:
            raise L14Error(f"duplicate dataset update: {update.dataset_id}")
        seen.add(update.dataset_id)
        changed.append(update.dataset_id)
        seed_layers.update(DATASET_TO_LAYERS[update.dataset_type])

    execution = _downstream_layers(seed_layers)
    return RecomputePlan(
        changed_datasets=tuple(changed),
        invalidated_layers=execution,
        execution_order=execution,
        reason="dataset_version_changed",
        metadata={
            "layer": "L14",
            "model_version": MODEL_VERSION,
            "database_write": False,
            "changed_dataset_count": len(changed),
            "trigger_layers": tuple(sorted(seed_layers, key=LAYER_ORDER.index)),
        },
    )


def plan_for_config_change(changed_layers: Sequence[str]) -> RecomputePlan:
    """Plan recomputation when a model/config change invalidates layers."""
    if changed_layers is None:
        raise L14Error("changed_layers input is required")
    if not isinstance(changed_layers, Sequence) or isinstance(changed_layers, (str, bytes)):
        raise L14Error("changed_layers must be a sequence")
    if not changed_layers:
        return RecomputePlan((), (), (), "no_layer_changes", {
            "layer": "L14",
            "model_version": MODEL_VERSION,
            "database_write": False,
        })

    if any(not isinstance(layer, str) or not layer.strip() for layer in changed_layers):
        raise L14Error("changed layer IDs must be non-empty strings")
    unknown = [layer for layer in changed_layers if layer not in LAYER_ORDER]
    if unknown:
        raise L14Error(f"unknown layer: {unknown[0]}")

    unique = set(changed_layers)
    execution = _downstream_layers(unique)
    return RecomputePlan(
        changed_datasets=(),
        invalidated_layers=execution,
        execution_order=execution,
        reason="model_or_config_changed",
        metadata={
            "layer": "L14",
            "model_version": MODEL_VERSION,
            "database_write": False,
            "trigger_layers": tuple(sorted(unique, key=LAYER_ORDER.index)),
        },
    )
