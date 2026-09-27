# Layer Specification: L07 - Multi-Hazard Risk Combination

**Status**: Framework implemented and verified; real hazard data pending
**Processing CRS**: `EPSG:32644`
**Canonical grid**: L03 30 m grid and cell IDs

## Purpose and Scope

L07 combines the normalized L04 landslide hazard, normalized L05 flood hazard,
and the approved binary L06 rainfall trigger index into a normalized prototype
decision-support score `H`.

L07 does not implement red zones, risk tiers, vulnerability, relocation,
suitability, carrying capacity, optimization, APIs, database transactions, or
PostGIS writes. Those responsibilities remain in later layers/integration
components.

## Inputs

Required inputs are:

- L04 normalized landslide grid `L` in `[0,1]`
- L05 normalized flood grid `F` in `[0,1]`
- L06 trigger grid and per-cell trigger states

L06 semantics are fixed for L07:

```text
triggered     -> R = 1.0
not_triggered -> R = 0.0
non-evaluable -> R = NoData
```

L06 rainfall millimetres in `metric_grid` are never used in the L07 formula.
`R` is a rainfall-trigger contribution, not rainfall intensity, probability,
or scientifically calibrated rainfall severity.

## Frozen Formula and Weights

The exact combination is:

$$
H = 0.45L + 0.35F + 0.20R
$$

Weights are loaded from the existing `multi_hazard_risk` block in
`config/weights.yaml`:

```yaml
landslide_weight: 0.45
flood_weight: 0.35
rainfall_weight: 0.20
```

The implementation validates that all three weights are known, finite,
positive, and sum to `1.0`. No hidden or second weight configuration exists.

## Missing and NoData Policy

Strict per-cell NoData propagation is frozen:

```text
If any required hazard is missing, unavailable, or NoData:
    combined_risk = NoData
    quality = non_evaluable
```

L07 does not convert missing data to zero, globally renormalize weights,
per-cell renormalize weights, or calculate partial risk.

Input validation failures produce `invalid` quality. Valid complete cells
produce `complete` quality. The only quality states are:

```text
complete
non_evaluable
invalid
```

Raster NoData `-9999.0` maps to Python non-evaluable/NoData and to `None` in
persistence-ready records for eventual SQL `NULL` storage.

## Spatial Contract

Every input must use the existing L03 canonical grid:

- CRS: `EPSG:32644`
- resolution: exactly `30.0` metres
- same unrotated affine transform
- same dimensions
- same row/column to cell-ID mapping

L07 rejects mismatched grids. It performs no reprojection, resampling,
interpolation, or station assignment.

## Output Contract

`MultiHazardResult` contains:

- `combined_risk`: `float32` canonical grid in `[0,1]` or NoData
- normalized input arrays for `L`, `F`, and binary `R`
- weighted contributions
- per-cell quality grid and quality mapping
- persistence-ready `RiskCellRecord` structures
- combination metadata and provenance

Records contain L07-owned values:

```text
cell_id
h_landslide
h_flood
h_rain
combined_risk
quality_flag
geometry
```

Records intentionally do not write or calculate `red_zone` or `risk_tier`,
which are L08 responsibilities.

## Temporal Compatibility

L07 preserves, where supplied:

- L04 model version and baseline/source metadata
- L05 model version and baseline/source metadata
- L06 rule version
- L06 observation window start/end
- L06 evaluation timestamp
- L07 combination timestamp

Temporal compatibility is an auditable metadata relationship only. L07 does
not claim that L04/L05 baseline layers are temporally equivalent to the L06
rainfall window and does not invent a temporal validity model.

## Provenance

The result metadata preserves each input provenance mapping, exact weights,
formula version, model version, grid metadata, missing-data policy, quality
states, combination timestamp, temporal compatibility statement, and the fact
that L08 fields were not written.

No provenance is fabricated for missing or unavailable inputs.

## Persistence Ownership

L07 returns persistence-ready records but does not open database sessions,
manage transactions, write PostGIS rows, or add migrations. Database/API
integration remains a later responsibility.

## Limitations

`H` is a deterministic prototype decision-support score, not a probability,
validated disaster-risk prediction, official classification, or legal
notification. The rainfall component is binary trigger activation only. Real
hazard generation remains data-pending because authoritative local L04/L05/L06
inputs are not present in the repository.

## Non-goals

L07 does not implement L08 red zones or risk tiers, L09 vulnerability, L10 site
suitability, L11 carrying capacity, L12 priority, L13 optimization, ML,
forecasting, interpolation, resampling, APIs, or database persistence.
