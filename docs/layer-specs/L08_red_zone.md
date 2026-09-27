# Layer Specification: L08 — Red-Zone Engine

**Status**: Implemented and tested
**Processing CRS**: `EPSG:32644`
**Canonical grid**: L03 30 m grid and cell IDs

## Purpose and Scope

L08 consumes the L07 combined multi-hazard risk raster `H` and a pre-computed
Boolean hard-exclusion raster to produce three per-cell decision fields:

- `red_zone` — BOOLEAN decision flag
- `risk_tier` — one of `red`, `amber`, `lower_risk`
- `quality_flag` — per-cell evaluability state (inherited from L07 semantics)

L08 does **not** generate hard-exclusion, write to the database, create
migrations, expose APIs, or compute downstream layers (L09-L13). L08 does not
modify L07 fields (`h_landslide`, `h_flood`, `h_rain`, `combined_risk`).

## Inputs

- L07 `combined_risk` raster `H` in `[0, 1]`, with sentinel
  `DEFAULT_NODATA_FLOAT` (`-9999.0`) for missing values
- Boolean `hard_exclusion` raster (dtype `bool`) — `True` marks cells that are
  hard-excluded regardless of hazard score
- L07 result metadata (optional, for provenance and hazard value preservation)
- **Required** hard-exclusion provenance metadata — a mapping containing
  `source` (raster origin/identifier), `checksum` (integrity hash), and
  `timestamp` (UTC ISO-8601). L08 does not generate or derive the
  hard-exclusion raster; it validates that provenance is supplied and rejects
  calls missing any of the three fields.

All inputs must use the existing L03 canonical grid. L08 rejects mismatched
grids. It performs no reprojection, resampling, or interpolation.

## Frozen Rule

The red-zone decision is:

```text
red_zone = hard_exclusion OR (H >= 0.70)
```

Hard-exclusion has **precedence**: when `hard_exclusion = True`, the cell is
always `red_zone = True` and `risk_tier = red`, regardless of `H`.

## Exact Thresholds

| Threshold | Value |
|-----------|-------|
| `RED_ZONE_THRESHOLD` | `0.70` |
| `AMBER_THRESHOLD`   | `0.55` |

No epsilon, tolerance, or `np.isclose` is used for threshold semantics.
Thresholds are strict `>=` comparisons.

## Risk Tiers

| Condition | `risk_tier` |
|-----------|-------------|
| `H >= 0.70` | `red` |
| `0.55 <= H < 0.70` | `amber` |
| `H < 0.55` | `lower_risk` |

When `hard_exclusion = True`, `risk_tier` is always `red` regardless of `H`.

## Hard-Exclusion Cases

| `hard_exclusion` | `H` state | `red_zone` | `risk_tier` | `quality_flag` |
|-------------------|-----------|------------|-------------|----------------|
| `True` | NoData | `True` | `red` | `non_evaluable` |
| `True` | Invalid | `True` | `red` | `invalid` |
| `True` | Valid in `[0, 1]` | `True` | `red` | `complete` |
| `False` | NoData | `False` | `lower_risk` | `non_evaluable` |
| `False` | Invalid | `False` | `lower_risk` | `invalid` |
| `False` | Valid in `[0, 1]` | per rule | per rule | `complete` |

## Invalid H Handling

Invalid `H` means any of:

- `NaN`
- `+Inf` or `-Inf`
- `H < 0`
- `H > 1`

Invalid values are handled **per-cell**, not rejected globally. A grid may
contain a mix of valid, NoData, and invalid cells; each is evaluated
independently.

## NoData Handling

`DEFAULT_NODATA_FLOAT` (`-9999.0`) denotes missing data. NoData cells have:

- `combined_risk = None` in persistence records (SQL `NULL`)
- `quality_flag = non_evaluable`
- `red_zone` = value of `hard_exclusion` for that cell
- `risk_tier` = `red` if `hard_exclusion` is `True`, else `lower_risk`

## Persistence Contract

L08 returns persistence-ready `RedZoneRecord` structures matching the
`risk_cell` table schema defined in `db/migrations/004_analytical_entities.sql`
and `src/db/models.py`:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `cell_id` | BIGINT | NOT NULL | Primary key |
| `h_landslide` | NUMERIC(5,4) | NULL | Preserved from L07 |
| `h_flood` | NUMERIC(5,4) | NULL | Preserved from L07 |
| `h_rain` | NUMERIC(5,4) | NULL | Preserved from L07 |
| `combined_risk` | NUMERIC(5,4) | NULL | `None` for NoData/invalid |
| `red_zone` | BOOLEAN | NOT NULL | Hard exclusion OR H >= 0.70 |
| `risk_tier` | VARCHAR(32) | NOT NULL | `red`, `amber`, `lower_risk` |
| `quality_flag` | VARCHAR(64) | NOT NULL | `complete`, `non_evaluable`, `invalid` |
| `geom` | GEOMETRY(Polygon, 32644) | NOT NULL | 30 m cell polygon |

All NoData and invalid `combined_risk` values are stored as `None` (SQL `NULL`),
satisfying the `chk_combined_risk_range` CHECK constraint.

## Spatial Contract

Every input must use the existing L03 canonical grid:

- CRS: `EPSG:32644`
- resolution: exactly `30.0` metres
- same unrotated affine transform
- same dimensions
- same row/column to cell-ID mapping

L08 inherits validation from `validate_l07_grid` and rejects mismatched grids.

## Provenance

The result `metadata` dictionary contains:

- `layer`: `"L08"`
- `model_version`: `"L08-v1.0"`
- `rule_identifier`: `"OD-05"`
- `threshold`: `0.70`
- `amber_threshold`: `0.55`
- `execution_timestamp`: ISO-8601 UTC
- `crs`: `"EPSG:32644"`
- `resolution_m`: `30.0`
- `grid`: canonical grid definition (`to_dict()`)
- `l07_input`: L07 metadata (propagated, not fabricated)
- `hard_exclusion_input`: hard-exclusion provenance containing `source`,
  `checksum`, and `timestamp` (required; rejected if absent)

Hard-exclusion provenance is **required** on every call. L08 validates that the
`hard_exclusion_metadata` argument contains `source`, `checksum`, and `timestamp`
keys before processing. No provenance is fabricated for missing inputs.

## Outputs

`L08Result` contains:

- `red_zone`: 2-D `bool` canonical grid
- `risk_tier`: 2-D string canonical grid (`red`, `amber`, `lower_risk`)
- `records`: tuple of `RedZoneRecord` (one per cell)
- `metadata`: provenance dictionary

## Non-goals

L08 does not generate hard-exclusion rasters, write to the database, create
migrations, expose APIs, compute downstream layers (L09 vulnerability, L10 site
suitability, L11 carrying capacity, L12 priority, L13 optimization), or modify
L07 outputs.
