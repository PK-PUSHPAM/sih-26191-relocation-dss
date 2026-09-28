# Assistive ML — Landslide Susceptibility

This module implements the **optional assistive ML layer** from the frozen SIH 26191 architecture.

## Models
- Random Forest — primary baseline
- Logistic Regression — interpretable comparison
- XGBoost may be added when its dependency is explicitly approved; it is not silently introduced.

## Features
1. slope
2. aspect
3. elevation
4. rainfall
5. land_cover
6. distance_to_fault
7. distance_to_road

Training additionally requires:
- `landslide_label` — binary 0/1 inventory label
- `spatial_group` — spatial block/group used for leakage-resistant validation

## Safety rules
- No labelled inventory => no model training.
- No artifact => no prediction.
- Spatial cross-validation is required for evaluation.
- ML never writes red-zone decisions and never overrides deterministic L07/L08 rules.
- A model is only assistive; deterministic baseline remains authoritative.

The current Chamoli repository does not contain an authoritative labelled training inventory, so the API reports `NOT_TRAINED` rather than fabricating a model or accuracy score.
