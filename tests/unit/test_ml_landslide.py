import pandas as pd
import pytest

from ml.landslide_susceptibility import FEATURES, status, validate_training_frame


def test_ml_status_does_not_fabricate_training():
    result = status("ml/training/definitely_missing.csv")
    assert result.status == "NOT_TRAINED"
    assert result.training_rows == 0
    assert tuple(result.features) == FEATURES


def test_training_schema_requires_spatial_groups():
    frame = pd.DataFrame({feature: [0.1, 0.2] for feature in FEATURES})
    frame["landslide_label"] = [0, 1]
    with pytest.raises(ValueError, match="spatial_group"):
        validate_training_frame(frame)


def test_training_schema_requires_both_classes():
    frame = pd.DataFrame({feature: [0.1, 0.2] for feature in FEATURES})
    frame["landslide_label"] = [1, 1]
    frame["spatial_group"] = ["A", "B"]
    with pytest.raises(ValueError, match="both 0 and 1"):
        validate_training_frame(frame)
