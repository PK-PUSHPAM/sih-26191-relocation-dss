# L11 — Carrying Capacity Engine

**Status:** IMPLEMENTED — verification pending full repository test run  
**Model:** `L11-carrying-capacity-1.0`  
**Formula:** `CC-floor-min-0.80`

## Purpose

Estimate the **modeled effective additional carrying capacity** of each eligible candidate relocation site and expose the limiting component. This is decision-support output, not engineering certification or a legal occupancy limit.

## Frozen rule

```
Physical_Capacity = min(Cap_land, Cap_water, Cap_sanitation, Cap_health, Cap_access)
Effective_Capacity = floor(Physical_Capacity * 0.80)
```

The safety factor is fixed at **0.80** for this implementation.

## Component derivations

The repository configuration freezes these prototype parameters:

- Land: `floor(area_m2 / 10,000 * 150 people/hectare)`
- Water: `floor(daily_water_liters / 70 L/person/day)`
- Sanitation: `floor(sanitation_capacity * 1.0)`
- Health: `floor(health_beds * 1000 people/bed * 0.12)`
- Access: `floor(access_capacity)`

The master specification requires service/infrastructure constraints where data permit, but it does not define a further scientific derivation for sanitation or access capacity. Therefore L11 accepts those two as already-derived people-capacity inputs rather than inventing a new proxy.

## Input contract

Each `CapacitySiteInput` contains:

- `site_id`: stable candidate-site identifier.
- `area_m2`: usable site area.
- `daily_water_liters`: available daily water quantity for the site.
- `sanitation_capacity`: already-derived people capacity supported by sanitation.
- `health_beds`: available beds used with the frozen people-per-bed proxy.
- `access_capacity`: already-derived people capacity supported by access/transport.

No database/API writes occur in L11.

## Missing and invalid data

- Missing component input → `effective_cap = NULL/None`, quality `non_evaluable`.
- Missing values are never converted to zero.
- Negative, NaN, infinity, boolean-as-number, or non-numeric values → `invalid`.
- Invalid inputs never produce a valid effective capacity.
- Ties use stable order: land → water → sanitation → health → access.

## Output contract

Each record contains the fields already present in the existing `capacity` table:

`site_id`, `land_cap`, `water_cap`, `sanitation_cap`, `health_cap`, `access_cap`, `binding_bottleneck`, `effective_cap`.

The application-level record additionally carries `quality_flag` and an explanation/provenance breakdown.

## Dependencies and boundaries

- L10 candidate relocation sites.
- Existing capacity database schema; **no migration is required**.
- No ML, forecasting, interpolation, resampling, API, dashboard, or database write in L11.
- Canonical processing CRS remains EPSG:32644 for project provenance.

## Acceptance criteria

1. All five component capacities are considered.
2. Effective capacity is exactly the floor of the minimum component multiplied by 0.80.
3. The binding bottleneck is always surfaced for complete records.
4. Missing inputs remain NoData/non-evaluable.
5. Invalid inputs cannot become valid capacity.
6. Output names remain compatible with the existing `capacity` table.
7. Results carry model/formula/config provenance.
8. No scientific formula is invented for sanitation or access beyond the frozen project configuration.

## Known limitation

L11 does not claim that the configured density, water, sanitation, health, or access proxies are engineering standards. They are frozen prototype parameters from the repository configuration and must be validated against authoritative project data before operational use.
