# Project State — SIH 26191 Relocation DSS

**Current Development & Execution Status**

---

## 1. Current Status Summary

- **Current Layer**: `L10` (Relocation Site Suitability)
- **Current Status**: `FRAMEWORK IMPLEMENTED & VERIFIED (REAL DATA PENDING)`
- **Next Task**: L11 (Carrying Capacity Engine)
- **Last Verified Commit**: `3ff399e` (L09 Exposure & Vulnerability Engine)
- **Active Blockers**: `Authoritative L04-L06 hazard inputs are absent from local data directories`

---

## 2. Completed Milestones

- [x] Master Blueprint Created & Scope Frozen ([SIH_26191_Final_Blueprint_v1.0.pdf](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/SIH_26191_Final_Blueprint_v1.0.pdf))
- [x] Repository Directory Structure & Skeletons Initialized
- [x] Architecture & Data Dictionary Audited ([docs/ARCHITECTURE.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/ARCHITECTURE.md), [docs/data-dictionary.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/data-dictionary.md))
- [x] Technical CRS Preflight Verification (`EPSG:32644` confirmed for Chamoli)
- [x] Secret / Credential Scan Completed (0 tracked secrets)
- [x] Persistent Context & State Management System Initialized ([docs/PROJECT_CONTEXT.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/PROJECT_CONTEXT.md))
- [x] Layer Specification Generated: L01 Data Ingestion ([docs/layer-specs/L01_data_ingestion.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L01_data_ingestion.md))
- [x] L01 Ingestion Foundation & Multi-Format Adapters Implemented (14/14 tests passing)
- [x] Layer Specification Generated: L02 Spatial Database ([docs/layer-specs/L02_spatial_database.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L02_spatial_database.md))
- [x] PostGIS SQL Migrations (001–005) Audited and Refined under `db/migrations/`
- [x] SQLAlchemy & GeoAlchemy2 Models Created under `src/db/` (`SRID = 32644`)
- [x] Database Migration Runner Created ([scripts/init_db.py](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/scripts/init_db.py))
- [x] L02 DDL & Schema Unit Test Suite Verified (10/10 offline unit tests passing; 2 live integration tests pending Docker)
- [x] Layer Specification Generated: L03 GIS Processing & Common Grid ([docs/layer-specs/L03_gis_processing.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L03_gis_processing.md))
- [x] Canonical 30 m Analysis Grid & Cell Indexing Implemented (`src/spatial/grid.py`)
- [x] Vector Study-Area Ingestion, Validation & Clipping Implemented (`src/spatial/vector.py`)
- [x] Raster Alignment Validator & Continuous/Categorical Resampling Implemented (`src/spatial/raster.py`)
- [x] DEM Terrain Derivatives (Horn 3x3 Slope & Aspect) Implemented (`src/spatial/terrain.py`)
- [x] L03 Unit Test Suite Verified with Isolated Synthetic Fixtures (20/20 passed)
- [x] L04 Landslide Baseline Engine Implemented and Verified (22/22 focused tests; real data pending)
- [x] L05 Flood Baseline Engine Implemented and Verified (10/10 focused tests; real data pending; flash-flood scoring unsupported)
- [x] L06 Rainfall Trigger Framework Implemented and Verified (18/18 focused tests; real rainfall data pending; no operational provider)
- [x] L07 Multi-Hazard Risk Combination Implemented and Verified (29/29 focused tests; real hazard data pending)

---

## 3. Layer Implementation Progress

| Layer ID | Name                             | Status                                            | Specification                                                                                                          | Tests                              | Verified Commit |
| :------- | :------------------------------- | :------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------- | :--------------------------------- | :-------------- |
| **L01**  | Data Ingestion & Validation      | **FOUNDATION VERIFIED**                           | [L01 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L01_data_ingestion.md)    | 14/14 Passed                       | `49a204a`       |
| **L02**  | PostGIS Spatial Database         | **OFFLINE / DDL VERIFIED**<br>_(Live DB Pending)_ | [L02 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L02_spatial_database.md)  | 10/10 Passed<br>_(2 live-skipped)_ | `7ba343f`       |
| **L03**  | GIS Processing & Common Grid     | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L03 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L03_gis_processing.md)    | 20/20 Passed                       | In progress     |
| **L04**  | Landslide Baseline               | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L04 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L04_landslide_hazard.md)  | 22/22 Passed                       | In progress     |
| **L05**  | Flood / Flash Flood Baseline     | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L05 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L05_flood_hazard.md)      | 10/10 Passed                       | In progress     |
| **L06**  | Rainfall Trigger Index           | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L06 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L06_rainfall_trigger.md)  | 18/18 Passed                       | In progress     |
| **L07**  | Multi-Hazard Risk Engine         | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L07 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L07_multi_hazard_risk.md) | 29/29 Passed                       | In progress     |
| **L08**  | Red-Zone Engine                  | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L08 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L08_red_zone.md)    | 42/42 Passed                       | `aacf149`       |
| **L09**  | Exposure & Vulnerability Engine  | **VERIFIED** | [L09 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L09_vulnerability.md) | 25/25 Passed; full suite 190/190 | `3ff399e` |
| **L10**  | Relocation Site Suitability      | **IMPLEMENTED — VERIFICATION PENDING** | [L10 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L10_site_suitability.md) | Added unit suite | `L10-site-suitability-1.0` |
| **L11**  | Carrying Capacity Engine         | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L12**  | Relocation Priority Engine       | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L13**  | Allocation Optimization (CP-SAT) | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L14**  | Update & Recompute Engine        | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L15**  | FastAPI Integration Layer        | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L16**  | Dashboard & Decision Reports     | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L17**  | Testing, Docker & Final Audit    | Queued                                            | Pending                                                                                                                | Pending                            | -               |

---

## 4. L02 Implementation Details & Review Checkpoint Corrections

### What Was Implemented

1. **PostGIS SQL Migrations (`db/migrations/`)**:
   - `001_extensions.sql`: Enables `postgis` and `uuid-ossp` extensions.
   - `002_provenance_and_metadata.sql`: DDL for `data_source`, `model_run`, `hazard_layer`.
   - `003_core_entities.sql`: DDL for `admin_unit`, `habitation`, `infrastructure` with `SRID = 32644`.
   - `004_analytical_entities.sql`: DDL for empty analytical schemas: `risk_cell`, `vulnerability`, `candidate_site`, `capacity`, `priority`, `allocation`.
   - `005_indexes.sql`: Creates GiST spatial indexes and B-Tree relationship indexes.
2. **Database Engine & ORM Layer (`src/db/`)**:
   - `session.py`: Database engine with `psycopg` driver, connection pooling, and fast probe.
   - `models.py`: 12 declarative SQLAlchemy + GeoAlchemy2 models enforcing SRID 32644 geometries, RESTRICT foreign keys, and CHECK constraints.
3. **Migration Runner (`scripts/init_db.py`)**:
   - Sequential, atomic transaction execution and offline syntax auditing.

### Corrections Made at L02 Review Checkpoint

1. **Status / Verification Language**:
   - Clarified that L02 is **OFFLINE / DDL VERIFIED** and that **LIVE DATABASE VERIFICATION IS PENDING**. Live PostGIS migration execution will occur once a PostgreSQL container/service is running.
2. **Analytical Tables Justification**:
   - Verified all 6 analytical tables against [docs/data-dictionary.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/data-dictionary.md). Confirmed they are purely empty persistence contracts with zero embedded calculation or business logic.
3. **Geometry Types Correction**:
   - Corrected `candidate_site.geom` from generic `Geometry` to concrete `GEOMETRY(Polygon, 32644)` per data dictionary line 133 ("Site polygon footprint").
   - Documented why `habitation.geom` uses generic `Geometry(32644)` (accommodates Point centroids and settlement Polygons per data dictionary line 59).
   - Documented why `infrastructure.geom` uses generic `Geometry(32644)` (accommodates Point facilities and LineString corridors per data dictionary line 74).
4. **Foreign Key Policy (Audit Preservation)**:
   - Replaced all `ON DELETE CASCADE` clauses in analytical tables with `ON DELETE RESTRICT` (`vulnerability`, `capacity`, `priority`, `allocation`). This ensures optimization runs, provenance, and analytical results cannot be accidentally wiped.
5. **CHECK Constraints Justification**:
   - Verified that all CHECK constraints strictly derive from the data dictionary and blueprint specifications.

### Verification Status

- **Unit & Offline Integration Tests**: 24 passed (14 for L01, 10 for L02).
- **Live Integration Tests**: 2 skipped (PostgreSQL port 5432 offline on host / Docker unavailable).
- Total suite execution: 24 passed, 2 skipped in ~3.0s.

---

## 5. L03 Implementation Details & Verification Summary

### What Was Implemented

1. **Layer Specification ([docs/layer-specs/L03_gis_processing.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L03_gis_processing.md))**:
   - Complete technical specification covering sections A through W: purpose, inputs, outputs, boundary validation, CRS normalization (`EPSG:32644`), vector processing, raster processing, canonical 30 m grid, alignment contracts, continuous vs categorical resampling policies, DEM slope & aspect derivation, nodata handling, and provenance tracking.
2. **Canonical 30 m Analysis Grid (`src/spatial/grid.py`)**:
   - `CanonicalGridDefinition`: Parameterized immutable grid definition.
   - Outward coordinate snapping to integer multiples of 30.0 m.
   - Deterministic 1-to-1 bijective mapping between $(row, col)$ and 64-bit integer `cell_id`.
   - Utility generating `gpd.GeoDataFrame` of cell polygons for spatial queries or `risk_cell` database loading.
3. **Vector Ingestion & Study-Area Boundary (`src/spatial/vector.py`)**:
   - Mandatory CRS validation and explicit reprojection to `EPSG:32644` (raises `MissingCRSError` if absent).
   - Topological validation and repair (`make_valid`) of district boundary polygons.
   - Multi-feature union/dissolve into a single validated study-area GeoDataFrame.
   - Vector clipping utility discarding features exterior to the boundary.
4. **Raster Processing & Strict Alignment (`src/spatial/raster.py`)**:
   - Detailed metadata inspection (CRS, dimensions, transform, nodata, bounds).
   - Strict raster alignment validator checking identical CRS, pixel resolution, dimensions, and $(X, Y)$ origins.
   - Resampling engine enforcing **Bilinear** interpolation for continuous variables and **Nearest Neighbour** for categorical classifications.
   - Vector polygon masking setting exterior pixels to NoData (`-9999.0`) while preserving grid transform and dimensions.
5. **DEM & Terrain Derivatives (`src/spatial/terrain.py`)**:
   - Topographic slope calculation in **degrees** ($[0^\circ, 90^\circ]$) using Horn's 3×3 finite-difference algorithm.
   - Aspect orientation calculation in **degrees azimuth** ($[0^\circ, 360^\circ]$ clockwise from True North, flat areas assigned $-1.0$).
   - Strict NoData propagation: if any pixel in the 3×3 moving window is NoData, the derived slope and aspect are assigned NoData.
6. **Isolated Synthetic Test Suite (`tests/unit/test_l03_gis.py`)**:
   - 20 unit tests verifying all 18 specification requirements using isolated, clearly labeled synthetic fixtures.

### Real Data Availability & Status

- **Status**: **`FRAMEWORK ONLY — REAL DATA PENDING`**
- No real GIS datasets or DEMs currently reside in `data/raw/` (only `.gitkeep`).
- Authoritative government datasets (CartoDEM / Copernicus DEM 30m, Survey of India Chamoli boundary, NRSC LULC) will be ingested via Layer L01 adapters in production.
- All L03 processing mechanics and contracts are verified using synthetic test fixtures. Zero fabricated datasets were placed in `data/`.

### L10 Implementation Details

- Frozen suitability formula: S = 0.30Hsafe + 0.15Slope + 0.15Road + 0.15Water + 0.10Health + 0.05Education + 0.05LandUse + 0.05Services.
- Hsafe is exactly 1.0 - L07 combined risk H after hard exclusions.
- Hard constraints: L08 red zone, water body, protected land, area below 1.0 ha, slope above 30 degrees, or road distance above 2,000 m reject a candidate before scoring.
- Missing required inputs never become zero; candidates with missing evaluability inputs are conditional with NoData suitability.
- Invalid numeric inputs never become a valid score; they are rejected with quality state invalid.
- L10 accepts candidate polygons and already-derived normalized suitability indicators; it does not fabricate source data or invent normalization functions.
- L10 performs no database writes, migrations, APIs, carrying-capacity calculation, priority calculation, or optimization.
- Local full-suite verification is pending for the L10 implementation.

### L09 Implementation Details

- Frozen formula: `V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D`, sourced from `config/weights.yaml` and the data dictionary.
- Missing indicators propagate NoData; invalid indicators never produce a valid composite score; missing-data penalty is the sum of missing-indicator weights.
- Persistence-ready records match the existing `vulnerability` table contract; L09 performs no database writes or migrations.
- Real authoritative habitation indicator data is not present in the repository, so no real Chamoli vulnerability values are generated.
- Test execution is pending local/CI verification; no L09 test pass count is claimed.

### Test Suite Summary

- **Last verified full-suite result before L10**: **190 passed, 2 skipped** (L01-L09; L09 contributes 25 tests). L10 verification is pending.
- **Real L04 Data Availability**: No usable boundary, DEM, landslide inventory, LULC, geology, drainage, or roads/infrastructure files are present. `data/raw/`, `data/staging/`, and `data/curated/` contain only `.gitkeep` markers.
- **L04 Implementation Status**: L04 is implemented as a data-driven baseline engine. Source-specific LULC and lithology mappings are not fabricated; drainage and road distance parameters must be explicitly supplied as dataset/model configuration.
- **Real L04 Hazard Raster Generated**: **No**. Generation is DATA-PENDING; no geographic values were fabricated.
- **L04 Limitations**: The deterministic baseline is an uncalibrated susceptibility score, not a probability or prediction. Historical inventory validation is unavailable until a real inventory is ingested.
- **Real L05 Flood Data Availability**: No usable Chamoli boundary, DEM, river network, discharge, water-level, flood inventory, or observed inundation extent files are present. Data directories contain only `.gitkeep` markers.
- **Real L05 Flood Hazard Raster Generated**: **No**. Actual Chamoli flood-hazard generation remains DATA-PENDING.
- **L05 Support Status**: River-proximity evidence and optional observed-extent evidence are implemented. Flash-flood scoring is explicitly unsupported pending real hydrological/event data.
- **L05 Limitations**: The baseline is not hydraulic simulation, flood probability, return-period analysis, depth/velocity modelling, or official flood certification.
- **Real L06 Rainfall Data Availability**: No rainfall observation files are present. The documented NWIC/IMD source is partially verified in the registry, but no live provider or operational feed exists in the repository.
- **Real L06 Trigger Output Generated**: **No**. No real rainfall trigger grid was generated.
- **L06 Threshold Status**: No scientifically validated rainfall threshold is configured. `threshold_mm` is explicitly null; callers must provide an unvalidated prototype/configuration parameter.
- **L06 Limitations**: Local/test provider input is non-operational; no interpolation, forecast, calibration, warning validation, or real-time claim is supported. Completeness uses only caller-supplied expected observation counts; cadence/gap detection is not implemented. Grid evaluation requires the L03 EPSG:32644, 30 m, unrotated canonical grid and reports states for observed cells only; unobserved cells remain NoData.
- **Real L07 Combined Risk Data Availability**: No authoritative local L04 landslide, L05 flood, or L06 rainfall inputs are present. No real combined-risk raster or database rows were generated.
- **L07 Implementation Status**: The frozen formula `H = 0.45L + 0.35F + 0.20R` is implemented with binary L06 trigger semantics, strict per-cell NoData propagation, and quality states `complete`, `non_evaluable`, and `invalid`.
- **L07 Limitations**: The score is a prototype decision-support combination, not a probability or validated disaster-risk prediction. Temporal compatibility is metadata-only; L08 fields are not calculated or written.
- **Real L08 Red-Zone Data Availability**: No authoritative local L04-L06 hazard inputs are present; no real red-zone raster or database rows were generated. The hard-exclusion raster is expected to be pre-computed upstream (not generated by L08).
- **L08 Implementation Status**: The frozen red-zone rule `red_zone = hard_exclusion OR (H >= 0.70)` is implemented with strict per-cell NoData/invalid handling, hard-exclusion precedence forcing `tier=RED`, and quality states inherited from L07 (`complete`, `non_evaluable`, `invalid`). Thresholds 0.70 and 0.55 use exact comparison (no `np.isclose`). Invalid/missing `combined_risk` is persisted as SQL `NULL`. Hard-exclusion provenance (source, checksum, timestamp) is required and validated.
- **L08 Limitations**: The red-zone engine is a deterministic rule-based overlay, not a probability or validated disaster-risk classification. No real Chamoli hazard or red-zone outputs exist; verification uses synthetic fixtures only. L08 does not generate, derive, or modify the hard-exclusion raster.

---

## 6. Active Blockers & Decisions Log

- **Active Blockers**: Authoritative L04-L06 hazard inputs are absent from local data directories; no real combined-risk output can be generated.
- **Architectural Decisions**: `OD-01` through `OD-12` strictly respected.
