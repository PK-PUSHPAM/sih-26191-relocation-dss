# Layer Specification: L04 - Landslide Baseline Hazard Model

**Status**: Framework implemented; real data pending  
**Study area**: Chamoli District, Uttarakhand  
**Processing CRS**: `EPSG:32644`  
**Canonical grid**: 30 m, provided by L03

## Purpose

L04 produces an explainable deterministic landslide susceptibility baseline on
the L03 canonical grid. `L` is a normalized modeled susceptibility score, not a
probability, forecast, or guarantee that a landslide will occur.

## Inputs and Readiness

Inputs are accepted only after L01 validation and L03 alignment/reprojection.
The current repository contains no real files under `data/raw/`,
`data/staging/`, or `data/curated/`; each directory contains only `.gitkeep`.

| Dataset              | Status and exact path | Expected format / CRS                                                | Coverage, provenance, usability                                                           |
| -------------------- | --------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Chamoli boundary     | Absent; no data path  | Shapefile/GeoJSON; source CRS must be declared, normally `EPSG:4326` | Chamoli coverage cannot be determined; source registry is documentation-only; unusable    |
| DEM                  | Absent; no data path  | GeoTIFF; declared CRS required, aligned by L03 to `EPSG:32644`       | No coverage; no file checksum; unusable                                                   |
| Landslide inventory  | Absent; no data path  | Shapefile/GeoJSON/KML; declared CRS required                         | Historical coverage cannot be determined; source registry is documentation-only; unusable |
| LULC                 | Absent; no data path  | GeoTIFF/vector; categorical resampling by L03                        | No coverage; no file checksum; unusable                                                   |
| Geology/lithology    | Absent; no data path  | Vector/raster; declared CRS required                                 | No coverage; no file checksum; unusable                                                   |
| Drainage/network     | Absent; no data path  | Vector; declared CRS required                                        | No coverage; no file checksum; unusable                                                   |
| Roads/infrastructure | Absent; no data path  | Vector; declared CRS required                                        | No coverage; no file checksum; unusable                                                   |

The readiness helper ignores `.gitkeep` and returns dataset paths, presence, and
usability flags. It never downloads or synthesizes data.

## Outputs

- A `float32` landslide hazard raster/grid `L` in `[0, 1]`.
- Factor grids and weighted contribution grids for explainability.
- A Boolean NoData mask; a cell is NoData if any selected factor is NoData.
- Optional GeoTIFF written against an existing L03 `CanonicalGridDefinition`.
- Configuration, model version, input paths/checksums, CRS, resolution, method,
  weights, and UTC timestamp metadata.

## Deterministic Baseline

Only factors supplied as validated real data are selected. The configured
candidate weights are:

| Factor      | Weight | Transformation                                                             |
| ----------- | -----: | -------------------------------------------------------------------------- |
| `slope`     |   0.35 | L03 Horn 3x3 slope in degrees, then configured interval reclassification   |
| `lulc`      |   0.20 | Explicit class-to-score mapping; unmapped observed classes become NoData |
| `geology`   |   0.15 | Explicit lithology-to-score mapping; unmapped observed classes become NoData |
| `drainage`  |   0.10 | Vector distance transformed with an explicit maximum distance parameter |
| `roads`     |   0.10 | Vector distance transformed with an explicit maximum distance parameter |
| `inventory` |   0.10 | Deterministic inventory evidence/density grid when a real inventory exists |

The weights of supplied factors are renormalized by their selected-weight sum.
No factor is inferred merely because it is listed in configuration. The file
orchestration requires real `study_area` and `dem` inputs and permits an
explicit subset of the other factors. A supplied LULC or geology file requires
a non-empty caller mapping. A supplied drainage or roads file requires an
explicit positive `max_distance_m` parameter. The current run selects no
factors because no real input data exists.

For selected factors, the exact formula is:

$$
L_{r,c} = \sum_{i \in S} \left(\frac{w_i}{\sum_{j \in S} w_j}\right) f_{i,r,c}
$$

where `S` is the supplied factor set and each `f` is in `[0,1]`. Invalid finite
factor values outside `[0,1]` fail; they are never clipped. The configured slope classes are `[0,15) -> 0.00`,
`[15,30) -> 0.25`, `[30,45) -> 0.60`, and `[45,90] -> 1.00`.

## Categorical Mappings

Source-specific LULC and lithology class-to-score mappings remain
**DATASET-DEPENDENT** and must be supplied after the real source schema is
inspected. L04 does not invent class IDs or susceptibility scores. Mapping
values must be numeric and in `[0,1]`; an empty mapping fails clearly. An
observed class missing from a non-empty mapping produces NoData for that cell,
which then propagates through the composite result.

## Drainage and Road Proximity

`drainage_proximity_factor()` and `road_proximity_factor()` accept vector
features, an L03 `CanonicalGridDefinition`, and an explicit positive
`max_distance_m`. Source vectors must have a CRS and are reprojected through
L03 to `EPSG:32644`. Distances are Euclidean projected metres from each grid
cell centre to the union of source geometries. The deterministic monotonic
transformation is:

$$
f(d;D) = \max\left(0, 1 - \frac{d}{D}\right)
$$

where `D` is the caller-supplied maximum distance in metres. Zero distance is
1, distance at or beyond `D` is 0, and no scientifically authoritative default
threshold is assumed. Missing or non-positive `D` fails. Empty or CRS-less
source vectors fail. The resulting factor is finite and in `[0,1]`; the full
grid is valid when the source is valid.

## NoData and Validation

L03 performs CRS normalization, canonical 30 m alignment, categorical versus
continuous resampling, and DEM terrain derivation. L04 calls the existing Horn
slope implementation and preserves its NoData result. Combination requires all
selected factors to be finite and valid at a cell; otherwise that cell remains
`-9999.0` NoData. There is no per-cell weight renormalization. Constant
continuous inputs deterministically normalize to 0. Weights must be finite,
positive, known L04 factors, and sum to 1.0 before selected-factor
renormalization. Unknown factor names and an empty factor set fail.

## Inventory Handling

An inventory must have a declared CRS. L04 repairs geometries with
`make_valid`, drops empty/invalid results, reprojects to `EPSG:32644`, and
deduplicates identical geometries. An actually empty inventory returns an
explicit `empty_inventory` status and an all-NoData evidence grid. A non-empty
inventory with zero overlap with the target grid raises a model error. A
non-empty overlapping inventory returns `valid_overlap`, rasterizes per-cell
record counts deterministically, and min-max normalizes them to `[0,1]`. No
synthetic labels are created.

## Provenance and Explainability

`build_provenance_metadata` records input paths, SHA-256 checksums when files
exist, CRS, 30 m resolution, method, weights actually used, model/config
versions, selected factors, mappings/parameters, and UTC time. The result
exposes each weighted factor contribution so a reviewer can trace a cell score
back to its selected factors. L01 adapters and checksum utility remain the
ingestion/provenance infrastructure.

## End-to-End Entry Point

`run_landslide_baseline()` accepts real input paths, an existing L03 canonical
grid, optional explicit mappings and proximity parameters, and an output path.
It validates the study area and required DEM, uses L01 adapters, uses L03
alignment and Horn terrain code, derives the supplied factors, masks to the
validated boundary, combines factors, records provenance, and writes the
GeoTIFF. It fails with `LandslideDataPendingError` when required files are
absent. It is not executed against synthetic or production data in this
repository.

The writer verifies that dimensions match the canonical grid, writes
`EPSG:32644`, 30 m transform/resolution, `float32`, `-9999.0` NoData, and
valid output values in `[0,1]`.

## Optional ML Eligibility Gate

No ML model or dependency is added and no training runs by default. The gate
requires sufficient real labels, both positive and negative samples, spatial
coverage, leakage prevention, spatially appropriate validation, and
reproducibility. Until all checks pass, this deterministic baseline remains the
prototype method.

## Limitations and Non-goals

This baseline does not claim calibrated probability or predictive accuracy. It
does not implement flood, rainfall, multi-hazard risk, red zones, vulnerability,
relocation, suitability, capacity, or optimization. Real factor mappings and
source-specific uncertainty must be reviewed when authoritative datasets are
ingested. No L04 hazard raster is generated while required real inputs are
absent.

## Tests

The focused suite uses only clearly synthetic in-memory fixtures and verifies
normalization bounds and constants, categorical mapping, weighted combination,
weight validation, NoData, reproducibility, L03 slope integration, inventory
validation/evidence, ML eligibility, absent-data behavior, and provenance.
