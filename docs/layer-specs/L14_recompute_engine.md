# L14 — Update & Recompute Engine

**Status:** VERIFIED — local full-suite verification completed  
**Model:** `L14-recompute-engine-1.0`

## Scope

L14 is the deterministic invalidation/planning layer for the frozen L01–L13 pipeline. It identifies which downstream layers must be recomputed after a dataset version change or model/configuration change.

L14 **does not execute** downstream layer functions, write analytical results, run database migrations, or expose an API. Those responsibilities remain in later integration layers.

## Frozen dependency policy

The pipeline order is:

`L01 → L02 → L03 → L04/L05/L06 → L07 → L08 → L09 → L10 → L11 → L12 → L13`.

A changed dataset invalidates its direct consuming layer(s) and every downstream layer from the earliest affected layer onward. This conservative policy prevents stale analytical outputs when upstream inputs change.

Supported dataset categories and their direct consumers are encoded explicitly in `DATASET_TO_LAYERS`. No unrecognized dataset category is silently ignored.

## Dataset update contract

Each update contains:
- `dataset_id`
- `previous_version`
- `new_version`
- `dataset_type`

Rules:
- dataset ID and new version are required;
- old and new versions must differ;
- duplicate dataset IDs in one update event are rejected;
- unsupported dataset types are rejected;
- no missing input is converted to a default value.

## Configuration/model changes

`plan_for_config_change()` accepts affected layer IDs. It invalidates that layer and all downstream layers. Unknown layer IDs are rejected.

## Output

`RecomputePlan` contains:
- changed dataset IDs;
- invalidated layers;
- deterministic execution order;
- trigger reason;
- provenance metadata;
- explicit `database_write=False`.

## Verification

- Local full-suite result: **303 passed, 2 skipped in 4.49s**.
- L14 focused tests executed as part of the full suite.
- The two skips remain pre-existing environment/integration skips.
- Verification covers dataset updates, downstream invalidation, deterministic ordering, configuration changes, and explicit rejection of invalid inputs.

## Verification acceptance criteria

- dataset updates trigger downstream invalidation;
- configuration/model changes trigger downstream invalidation;
- invalid updates are rejected explicitly;
- execution order is deterministic;
- no database/API writes;
- no silent ignoring of unknown inputs.
