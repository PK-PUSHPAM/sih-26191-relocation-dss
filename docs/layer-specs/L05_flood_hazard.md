# Layer Specification: L05 - Flood / Flash-Flood Baseline Hazard Model

**Status**: Data-driven framework implemented; real data pending  
**Study area**: Chamoli District, Uttarakhand  
**Processing CRS**: `EPSG:32644`  
**Canonical grid**: 30 m, provided by L03

## Purpose and Scope

L05 produces a deterministic, explainable flood evidence score `F` in `[0,1]`.
It is a modeled flood susceptibility/hazard baseline for planning review. It
is not a flood probability, hydraulic depth/velocity simulation, official
flood-zone certification, guaranteed prediction, or return-period estimate.

L05 owns riverine flood evidence and documented observed flood extent evidence.
It does not implement rainfall triggering (L06), combined risk (L07), red zones
(L08), vulnerability, relocation, suitability, carrying capacity, or
optimization.

## Real-Data Readiness

The current repository contains only `.gitkeep` under `data/raw/`,
`data/staging/`, and `data/curated/`. No usable real flood inputs are present.

| Dataset                     | Status / path         | Expected format and CRS                                      | Coverage/provenance/usability                                                 |
| --------------------------- | --------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| Chamoli boundary            | Absent; no exact path | Shapefile/GeoJSON; declared source CRS, normally `EPSG:4326` | Coverage unavailable; source registry documentation only; not usable          |
| DEM / terrain               | Absent; no exact path | GeoTIFF; declared CRS; L03 alignment                         | Coverage unavailable; no checksum; not usable by L05 currently                |
| River/drainage network      | Absent; no exact path | Shapefile/GeoJSON/GeoPackage; declared CRS                   | No spatial coverage available; source registry documentation only; not usable |
| Observed discharge          | Absent; no exact path | CSV/JSON with station, timestamp, and discharge              | No temporal coverage; no observations or provenance; not usable               |
| Water levels                | Absent; no exact path | CSV/JSON with station, timestamp, and water level            | No temporal coverage; no observations or provenance; not usable               |
| Flood/flash-flood inventory | Absent; no exact path | Shapefile/GeoJSON/GeoPackage; declared CRS                   | No event coverage; no checksum; not usable                                    |
| Observed inundation extents | Absent; no exact path | Polygon vector with event identity/date where available      | No event coverage; no checksum; not usable                                    |

The `audit_l05_data_readiness()` helper ignores `.gitkeep` and empty folders.
No arbitrary sources are downloaded and no flood observations or geographic
values are synthesized.

## Implemented Factors and Configuration

The default configured L05 baseline intentionally contains one factor:

| Factor            | Configured weight | Exact transformation                                                          |
| ----------------- | ----------------: | ----------------------------------------------------------------------------- |
| `river_proximity` |             `1.0` | Distance from each canonical cell centre to the validated river-network union |

Observed flood extent is implemented as an optional factor named
`observed_extent`, but it is not assigned a default blend weight. It may
participate only when the caller explicitly supplies a positive weight. This
avoids inventing a scientific blend in the absence of documented observations.

The default river proximity parameter is not configured. The caller must supply
`max_distance_m` explicitly. Distances use projected metres in `EPSG:32644`.
For distance `d` and configured maximum distance `D`:

$$
f(d;D)=\max\left(0,1-\frac{d}{D}\right)
$$

Distance zero scores `1`; distance at or beyond `D` scores `0`. Missing,
non-finite, or non-positive `D` fails clearly. No authoritative distance
threshold is invented.

No DEM, slope, relative elevation, flow accumulation, discharge threshold,
water-level threshold, or return-period transformation is automatically
included. A future terrain factor must define its own documented physical
rationale and configuration.

## Factor Combination

For selected factors `S`, each valid factor grid `f_i` must be finite and in
`[0,1]`:

$$
F_{r,c}=\sum_{i\in S}
\left(\frac{w_i}{\sum_{j\in S}w_j}\right)f_{i,r,c}
$$

Weights must be known, finite, positive, and sum to `1.0`. Omitted factors are
ignored and selected weights are globally renormalized. No per-cell weight
renormalization occurs. NoData in any selected factor makes that cell NoData.
Invalid factor values, unknown factors, an empty factor set, mismatched shapes,
and missing factor weights fail clearly.

## Riverine and Flash-Flood Treatment

Riverine evidence is supported through `flood_proximity_factor()` and the
`river_proximity` baseline. It is proximity evidence, not hydraulic modelling.

Flash-flood hazard is **not implemented as a scored factor**. The repository
has no real flash-flood observations, discharge series, water levels, or
validated hydrological thresholds. `flash_flood_supported` is explicitly
`false`. Future flash-flood evidence must be added only after real event data,
temporal validation, spatial association, and a documented method are supplied.

## Observed Flood Extent and Inventory

`validate_flood_inventory()` requires a CRS, repairs geometries with
`make_valid`, drops empty/invalid results, reprojects to `EPSG:32644`, and
deduplicates identical geometries. `observed_flood_extent_evidence()` has three
explicit outcomes:

- Empty inventory: returns all NoData with status `empty_inventory`.
- Non-empty inventory with no canonical-grid overlap: raises `FloodModelError`.
- Non-empty inventory with overlap: rasterizes deterministic presence/count
  evidence, clips evidence to `[0,1]`, and returns status `valid_overlap`.

Historical occurrence is not converted into a future probability. Event identity
and dates remain input attributes; L05 does not invent or combine event dates.

## Hydrological Observations

`validate_hydrological_observations()` validates `station_id`, UTC-parsed
`timestamp`, and at least one non-negative finite `discharge` or `water_level`
column. It preserves station and temporal information and can validate station
geometry CRS and spatial association with a supplied study area. It does not
derive design discharge, return periods, hydraulic thresholds, or flash-flood
scores.

## End-to-End Entry Point

`run_flood_baseline()` accepts real `study_area` and `river_network` paths, an
existing L03 canonical grid, an explicit `max_distance_m`, optional observed
flood extent, optional explicit weights, and an output path. It uses L01 file
adapters and L03 boundary/CRS/grid conventions, derives selected evidence,
combines it, records provenance, and writes a GeoTIFF. Missing required files
raise `FloodDataPendingError`; the function is not run against fabricated data.

## Output Contract

`FloodBaselineResult` contains the normalized `hazard`, factor grids, NoData
mask, weighted contributions, and metadata. `write_flood_hazard_raster()`
requires the L03 canonical grid and writes `float32` GeoTIFF with:

- CRS `EPSG:32644`
- canonical dimensions and transform
- 30 m resolution
- NoData `-9999.0`
- valid values in `[0,1]`

Metadata records layer/model/config versions, canonical grid, selected weights,
explicit parameters, source paths, checksums where files exist, CRS, NoData
policy, and UTC timestamp.

## Uncertainty, Validation, and Limitations

The proximity baseline has no hydraulic calibration and does not model channel
capacity, discharge, inundation depth, velocity, rainfall triggers, sediment
surges, or topographic flow routing. Observed extent evidence is historical
presence evidence only. Results are sensitive to the explicit distance
parameter and source geometry quality. L05 tests use synthetic in-memory
fixtures only and do not represent Chamoli observations.

Future ML or advanced hydrological modelling remains an extension requiring
real labelled events, hydrological inputs, calibrated methods, spatial
validation, and reproducible provenance.
