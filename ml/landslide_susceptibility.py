"""Assistive landslide-susceptibility ML framework for SIH 26191.

The ML layer is deliberately assistive. It never replaces the deterministic
hazard/red-zone rules. Training is refused when the authoritative labelled
inventory is unavailable or the schema is invalid.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.base import clone


FEATURES = (
    "slope",
    "aspect",
    "elevation",
    "rainfall",
    "land_cover",
    "distance_to_fault",
    "distance_to_road",
)
TARGET = "landslide_label"
GROUP = "spatial_group"


@dataclass(frozen=True)
class ModelStatus:
    status: str
    message: str
    training_rows: int
    features: tuple[str, ...]
    artifact: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "message": self.message,
            "training_rows": self.training_rows,
            "features": list(self.features),
            "artifact": self.artifact,
            "authoritative": False,
            "role": "assistive susceptibility signal",
        }


def validate_training_frame(frame: pd.DataFrame) -> None:
    required = set(FEATURES) | {TARGET, GROUP}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"missing required ML columns: {missing}")
    if frame.empty:
        raise ValueError("ML training dataset is empty")
    if frame[TARGET].isna().any() or frame[GROUP].isna().any():
        raise ValueError("ML target and spatial_group must not contain nulls")
    labels = set(frame[TARGET].astype(int).unique())
    if not labels.issubset({0, 1}) or labels != {0, 1}:
        raise ValueError("landslide_label must contain both 0 and 1 classes")
    numeric = frame.loc[:, FEATURES].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        raise ValueError("ML features must be numeric and finite")
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("ML features must be finite")


def model_candidates() -> dict[str, object]:
    return {
        "random_forest": RandomForestClassifier(
            n_estimators=300, random_state=26191, class_weight="balanced",
            min_samples_leaf=2, n_jobs=-1
        ),
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]),
    }


def status(training_csv: str | Path = "ml/training/landslide_training.csv") -> ModelStatus:
    path = Path(training_csv)
    if not path.exists():
        return ModelStatus(
            "NOT_TRAINED",
            "Authoritative labelled landslide inventory is not present; deterministic baseline remains authoritative.",
            0, FEATURES
        )
    try:
        frame = pd.read_csv(path)
        validate_training_frame(frame)
    except Exception as exc:
        return ModelStatus("BLOCKED", str(exc), 0, FEATURES)
    return ModelStatus(
        "READY_TO_TRAIN",
        "Training schema validated. No model artifact is promoted automatically.",
        len(frame), FEATURES
    )


def evaluate_spatial_cv(frame: pd.DataFrame, splits: int = 5) -> dict[str, dict[str, float]]:
    validate_training_frame(frame)
    groups = frame[GROUP].astype(str)
    n_groups = groups.nunique()
    if n_groups < 2:
        raise ValueError("at least two spatial groups are required")
    n_splits = min(splits, n_groups)
    X = frame.loc[:, FEATURES].astype(float)
    y = frame[TARGET].astype(int)
    cv = GroupKFold(n_splits=n_splits)
    results: dict[str, dict[str, float]] = {}
    for name, estimator in model_candidates().items():
        cloned = clone(estimator)
        probabilities = cross_val_predict(
            cloned, X, y, cv=cv, groups=groups, method="predict_proba"
        )[:, 1]
        results[name] = {
            "roc_auc": float(roc_auc_score(y, probabilities)),
            "pr_auc": float(average_precision_score(y, probabilities)),
            "spatial_folds": float(n_splits),
        }
    return results


def train_random_forest(frame: pd.DataFrame, artifact_path: str | Path) -> dict:
    validate_training_frame(frame)
    model = model_candidates()["random_forest"]
    model.fit(frame.loc[:, FEATURES].astype(float), frame[TARGET].astype(int))
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump({"model": model, "features": FEATURES, "model_version": "ML-LS-RF-1.0"}, path)
    return {"artifact": str(path), "rows": len(frame), "model_version": "ML-LS-RF-1.0"}


def predict(features: Mapping[str, float], artifact_path: str | Path) -> float:
    missing = [name for name in FEATURES if name not in features]
    if missing:
        raise ValueError(f"missing prediction features: {missing}")
    values = np.array([[float(features[name]) for name in FEATURES]])
    if not np.isfinite(values).all():
        raise ValueError("prediction features must be finite")
    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError("no trained ML artifact is available")
    import joblib
    bundle = joblib.load(path)
    if tuple(bundle.get("features", ())) != FEATURES:
        raise ValueError("ML artifact feature schema mismatch")
    return float(bundle["model"].predict_proba(values)[0, 1])
