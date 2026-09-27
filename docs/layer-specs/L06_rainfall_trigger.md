# Layer Specification: L06 - Rainfall Trigger

**Status**: Data-driven deterministic framework implemented; real rainfall data pending
**Study area**: Chamoli District, Uttarakhand
**Processing CRS**: `EPSG:32644`
**Canonical grid**: L03 30 m grid and cell IDs

## Purpose

L06 evaluates observed rainfall over an explicitly supplied time window against
an explicitly supplied trigger parameter. It produces an auditable trigger
state that can later feed L07 multi-hazard combination.

L06 does not claim real-time rainfall, operational warning capability, a
scientifically validated disaster threshold, rainfall probability, or forecast.

## Current Data and Provider Status

The project source registry documents `nwic_imd_daily_rainfall` as a partially
verified NWIC/IMD daily rainfall source with CSV/JSON formats, station-point
geometry, and daily time series coverage. No rainfall files exist in the
repository and no live API client is implemented. The current provider support
is therefore:

- `LocalCsvRainfallProvider`: deterministic local/curated/test input only;
  `operational=false` and `real_time=false` are preserved in provenance.
- `UnavailableRainfallProvider`: explicit non-available provider state.
- `RainfallProvider` protocol: replaceable interface for a future verified
  provider.

No local or test rainfall input may be labeled real-time or operational.

## Input Contract

`RainfallObservation` contains:

- `rainfall_mm`: non-negative finite millimetres or explicit `None` for missing
- `observed_at`: timezone-aware timestamp; missing values are retained only to
  produce the explicit `missing_timestamp` non-evaluable state
- `cell_id`: existing canonical L03 cell ID, or
- `station_id`: source station identifier when no cell mapping exists
- optional `window_start` and `window_end`
- optional source observation identifier

L06 does not assign station observations to cells and does not interpolate.
Grid evaluation requires an existing valid `cell_id` and validates it against
`CanonicalGridDefinition.row_col_from_cell_id()`.

## Provider Contract

The `RainfallProvider` protocol exposes:

```text
fetch(window_start=None, window_end=None) -> RainfallProviderResult
```

`RainfallProviderResult` contains observations, `RainfallProvenance`, an
explicit availability/evaluation state, and an optional message. Provenance
includes source ID, provider name, source kind, source path, SHA-256 checksum
when available, operational status, and temporal metadata.
An available provider returns `provider_available`; this is not a trigger
decision. Trigger evaluation remains the evaluator's responsibility.

## Deterministic Trigger Rule

The current supported metric is the sum of valid rainfall observations in the
declared evaluation window:

$$
R_{window}=\sum_{k=1}^{n} rainfall_{k,mm}
$$

The trigger rule is:

$$
Trigger = (R_{window} \ge T_{mm})
$$

The comparison is inclusive at the configured threshold. The result state is
`triggered` or `not_triggered`, with an explanation containing the observed
window total and threshold.

The supported completeness rule is intentionally limited: when
`expected_observation_count` is supplied, the count must be met. L06 does not
infer cadence or detect gaps between timestamps. Callers requiring cadence
validation must perform it before evaluation.

## Threshold Configuration and Status

`config/thresholds.yaml` contains:

```yaml
rainfall_trigger:
  threshold_mm: null
  metric: "window_total_mm"
  comparison: "greater_equal"
  rule_version: "L06-trigger-1.0"
  parameter_status: "UNVALIDATED_PROTOTYPE_CONFIGURATION_REQUIRED"
```

No scientifically validated rainfall threshold currently exists in project
documentation or configuration. `RainfallRule.from_config()` therefore fails
unless the caller supplies an explicit numeric `threshold_mm`. Any supplied
value is an **unvalidated prototype/configuration parameter**, not an official
warning threshold.

No hidden numeric rainfall threshold is hard-coded in Python.

## Evaluation States and Missing Data

The framework distinguishes:

- `triggered`
- `not_triggered`
- `missing_data`
- `invalid_data`
- `missing_timestamp`
- `duplicate_observation`
- `incomplete_window`
- `provider_unavailable`
- `invalid_configuration`
- `provider_available` (provider state before trigger evaluation)

Blank/null rainfall remains `None` and produces `missing_data`. Numeric NaN,
infinity, negative rainfall, and malformed timestamps produce `invalid_data`.
Missing timestamp fields/values produce `missing_timestamp`. Rainfall is never
converted to zero. Duplicate observation identities, incomplete expected-count
windows, and unavailable providers remain explicit non-evaluable states.

## Spatial Output

`evaluate_rainfall_grid()` returns:

- `metric_grid`: rainfall window total in millimetres, or `-9999.0` NoData
- `trigger_grid`: `1.0` triggered, `0.0` not triggered, `-9999.0` non-evaluable
- `states_by_cell`
- `results_by_cell`
- canonical grid/provenance metadata

The supplied grid must have CRS `EPSG:32644`, resolution exactly `30.0`, the
L03 unrotated transform, and the existing L03 cell-ID convention. Only existing
L03 cell IDs are used. No second grid, coordinate invention, or spatial
interpolation is performed. `states_by_cell` intentionally covers observed
cells only; unobserved canonical cells remain NoData in both grids and are
described by `state_scope` metadata.

## Provenance

`build_rainfall_provenance()` records the provider/rule baseline metadata, while
the final `RainfallTriggerResult.provenance` produced by
`evaluate_provider_result()` additionally records:

- layer and rule/model version
- provider state and message
- source ID, provider name, source kind, path, checksum, and operational status
- real-time flag
- observation timestamps
- evaluation window and evaluation timestamp
- spatial/cell ID and rainfall metric
- threshold/rule configuration
- canonical grid metadata when supplied
- explicit missing-data policy
- UTC generation timestamp

The existing L01 `IngestionPipeline` and `ProvenanceRecord` remain available for
promotion and source manifests when real rainfall files are ingested.

`evaluate_provider_result()` connects provider state and provenance directly to
the final trigger result. Provider unavailable, invalid-data, and duplicate
states are not hidden or reconstructed by the caller.

## Limitations and Future Integration

The current implementation has no verified local rainfall data, live provider,
spatial interpolation, rainfall forecast, rolling climatology, return-period
analysis, calibration, warning validation, or timestamp-cadence/gap detection.
A future verified provider can
implement `RainfallProvider`, preserve the same observation/provenance contract,
and supply validated timestamps and source metadata without changing the
trigger evaluator. Threshold validation and operational use require authoritative
source documentation and domain validation outside this prototype framework.

L06 does not implement L05 flood logic, L07 combined risk, L08 red zones, or any
later vulnerability, relocation, suitability, capacity, priority, or
optimization logic.
