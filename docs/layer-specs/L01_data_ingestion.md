# Layer Specification: L01 — Data Ingestion & Validation

**Layer ID**: `L01`  
**Layer Name**: Data Ingestion & Validation Foundation  
**Status**: ACTIVE IMPLEMENTATION CONTRACT  
**Blueprint Reference**: Section 3 (Data Strategy), Section 11 (Phase 1), Section 13 (data_source table), Section 16 (Data tests), Section 24 (Verified Source Register)  
**Parent Architecture**: [docs/ARCHITECTURE.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/ARCHITECTURE.md)  
**Permanent Context**: [docs/PROJECT_CONTEXT.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/PROJECT_CONTEXT.md)

---

## A. Purpose and Scope

Layer L01 provides the deterministic, reproducible data ingestion, provenance tracking, and quality validation foundation for the Chamoli Relocation DSS.

Its primary responsibilities are:
1. Registering and indexing all raw data sources in a machine-readable manifest (`config/sources.yaml`).
2. Providing robust multi-format ingestion adapters (CSV, GeoJSON, Shapefile, GeoPackage, GeoTIFF) for local and staging workflows.
3. Enforcing an immutable lifecycle: **Raw $\rightarrow$ Staging $\rightarrow$ Curated**.
4. Recording full cryptographic provenance (SHA-256 checksum, timestamps, source versions, geometries, CRS).
5. Performing multi-level validation (schema, null rates, duplicate keys, geometry validity, CRS parseability, spatial bounding extent, numeric ranges).
6. Preventing bad or unvalidated data from advancing to curated storage or downstream layers (L02+).

---

## B. Inputs

1. **Raw Source Files**: Stored in `data/raw/{source_id}/{version}/` (e.g. tabular Census tables, Bhuvan vector files, NWIC rainfall CSVs, DEM rasters).
2. **Source Registry & Manifest**: Sourced from `config/sources.yaml`.
3. **Dataset Schema Definitions**: Data contracts specifying required columns, data types, allowed null rates, and primary keys.

---

## C. Outputs

1. **Provenance Records (`manifest.json` / metadata objects)**: Cryptographic hash, source attribution, vintage, geometry summary, row/cell count, original CRS.
2. **Staging Artifacts (`data/staging/`)**: Cleaned, schema-checked tabular and vector data with validation logs attached.
3. **Curated Artifacts (`data/curated/`)**: Fully verified, normalized, project-ready datasets eligible for PostGIS database loading (L02) and spatial processing (L03).
4. **Validation Quality Reports**: Structured JSON and human-readable logs categorizing validation outcomes as `ERROR`, `WARNING`, or `INFO`.

---

## D. Supported Source Categories

1. **Administrative Boundaries**: District, block/tehsil, and gram panchayat boundaries (Uttarakhand OGD / LGD / NWIC).
2. **Population & Demographics**: Census 2011 Chamoli Primary Census Abstract (PCA / DCHB Part B).
3. **Village Amenities & Infrastructure**: Census 2011 Chamoli Village Directory (DCHB Part A).
4. **Meteorological Triggers**: IMD Daily Rainfall via NWIC.
5. **Hydrology & River Telemetry**: CWC Hourly River Discharge via NWIC.
6. **Landslide Inventory & Hazard**: NRSC/Bhuvan Landslide Geoportal & GSI inventory benchmarks.
7. **Land Use / Land Cover & Ecological Constraints**: Bhuvan Thematic LULC & Uttarakhand Forest Viewer.
8. **Terrain & DEM**: Survey of India / Open DEM elevation rasters.

---

## E. Source Priority Policy

* **Primary Policy**: Authoritative and open Indian government sources first (USDMA, Census India, NRSC/ISRO, NWIC, CWC, IMD, Uttarakhand OGD).
* **Secondary Policy**: Documented open scientific alternatives second (e.g., OpenStreetMap for road geometry where official data lacks topology, Copernicus/SRTM DEM where CartoDEM is unavailable).
* **Strict Constraint**: No arbitrary web scraping, no synthetic data presented as real data, and no invented API endpoints.

---

## F. Raw $\rightarrow$ Staging $\rightarrow$ Curated Data Flow

```
┌───────────────────────────────────────────────────────────┐
│                        DATA SOURCE                        │
│          (Official Portal / Documented Release)           │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ DATA/RAW/                                                 │
│ • Write-once, immutable source files                      │
│ • Checksum (SHA-256) calculated immediately on ingestion  │
│ • Preserves native file format, structure, and CRS        │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│ DATA/STAGING/                                             │
│ • Parsed into DataFrame / GeoDataFrame / RasterIO         │
│ • Initial schema validation, type casting, key checks     │
│ • Spatial geometry validation (is_valid, non-empty)       │
│ • Validation report generated (ERROR / WARNING / INFO)    │
└─────────────────────────────┬─────────────────────────────┘
                              │  [If Validation Passes: Zero Critical Errors]
                              ▼
┌───────────────────────────────────────────────────────────┐
│ DATA/CURATED/                                             │
│ • Normalized column naming (snake_case)                   │
│ • Explicit CRS verification (EPSG:32644 for spatial)      │
│ • Missing data explicitly flagged (never silent zero)     │
│ • Packaged with verified provenance manifest              │
└───────────────────────────────────────────────────────────┘
```

---

## G. Source Manifest & Provenance Contract

Every ingested dataset must generate a structured provenance dictionary conforming to:

```json
{
  "dataset_id": "census_2011_chamoli_pca",
  "source_id": "census_2011_chamoli_dchb_b",
  "source_url": "https://censusindia.gov.in/nada/index.php/catalog/1307",
  "retrieval_timestamp": "2026-09-26T16:00:00Z",
  "source_version": "2011_v1.0",
  "local_raw_path": "data/raw/census_2011_chamoli_pca.csv",
  "file_format": "CSV",
  "file_size_bytes": 1048576,
  "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "original_crs": null,
  "target_crs": null,
  "geometry_type": "None",
  "spatial_extent": null,
  "temporal_extent": {
    "start_date": "2011-01-01",
    "end_date": "2011-12-31"
  },
  "row_count": 1245,
  "validation_status": "PASSED",
  "warnings": [],
  "errors": []
}
```

---

## H. Dataset Metadata Contract

Tabular, vector, and raster datasets must carry metadata headers recording:
- `census_year`: Explicitly set to `2011` for demographic baseline data.
- `study_area`: `Chamoli, Uttarakhand`.
- `data_authority`: Official agency responsible for the dataset.
- `license`: Open Government Data (OGD) / ISRO Bhuvan open terms.

---

## I. Schema Validation

1. **Required Columns Check**: All columns marked `required: true` in the schema contract must exist.
2. **Data Type Casting**: Strict type casting for numeric integers (population, households), floats (hazard intensity, precipitation), strings (names, codes), and timestamps.
3. **Column Normalization**: Automatic normalization of raw headers into standard `snake_case` according to explicit column mapping dictionaries.

---

## J. Spatial Validation

1. **Geometry Validity**: `shapely.is_valid` check on all geometries. Self-intersecting polygons or bowtie geometries trigger an error or explicit `make_valid` warning.
2. **Non-Empty Geometries**: Verification that geometries are not null or empty (`geom.is_empty == False`).
3. **Bounding Box Sanity Check**: Geometries must intersect the Chamoli District spatial envelope ($[78.5^\circ\text{E}, 80.5^\circ\text{E}], [29.5^\circ\text{N}, 31.5^\circ\text{N}]$ in WGS84, or corresponding UTM coordinates in `EPSG:32644`).
4. **Dimension & Geometry Type Check**: Ensure geometry types match contract (`Polygon`, `MultiPolygon`, `Point`, `LineString`).

---

## K. Temporal Validation

1. Date and timestamp parsing to ISO 8601 strings (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`).
2. Monotonicity checks for time series data (e.g. daily rainfall, hourly discharge).
3. Identification and logging of gaps in telemetry sequences.

---

## L. Attribute / Value Range Validation

1. **Numeric Range Checks**:
   - Normalized indices: $[0.0, 1.0]$.
   - Rainfall: $\ge 0.0\text{ mm}$.
   - Population & households: non-negative integers $\ge 0$.
   - Slope: $[0.0^\circ, 90.0^\circ]$.
2. **Categorical Checks**: Categorical amenities (e.g., presence of primary health center, tap water status) must conform to allowed vocabulary.

---

## M. Coordinate Reference System (CRS) Handling

1. **No Silent Assumptions**: If a spatial file lacks CRS metadata (e.g. a Shapefile missing `.prj`), the validator flags an `ERROR` and halts promotion.
2. **Preservation of Raw CRS**: Original raw CRS is recorded in the provenance manifest.
3. **Explicit Reprojection**: Vector datasets intended for spatial computation are explicitly reprojected to `EPSG:32644` (WGS 84 / UTM Zone 44N).
4. **Raster Resampling Prohibition in L01**: L01 does NOT resample rasters to 30 m grid; canonical 30 m grid alignment is strictly deferred to **L03 (GIS Common Grid)**.

---

## N. File Integrity & Checksum Handling

1. Cryptographic hashing using **SHA-256** is executed during ingestion.
2. If a raw file is modified or corrupted, checksum recalculation detects tampering or bitrot.

---

## O. Dataset Versioning

1. Raw storage directory convention: `data/raw/{source_id}/{version_tag}/`
2. Curated storage directory convention: `data/curated/{dataset_id}_{version_tag}.parquet` (or `.geojson` / `.gpkg` / `.tif`).

---

## P. Duplicate Detection

1. **Primary Key Uniqueness**: Validates that administrative codes (`census_village_code`, `unit_id`, `station_id`) have 0 duplicate rows.
2. **Spatial Deduplication**: Identification of overlapping duplicate event polygons (e.g. identical landslide scars reported multiple times) with logging of duplicate count.

---

## Q. Missing-Data & Null Handling

1. **No Silent Imputation**: Null values must **never** be silently replaced with `0` or mean values.
2. **Null Rate Threshold**: If null rate for any required field exceeds configurable threshold (e.g. $0.0\%$ for IDs, $20.0\%$ for auxiliary amenities), a `WARNING` or `ERROR` is emitted.
3. **Explicit Missingness Flagging**: Rows with missing indicators are flagged for downstream confidence penalty calculation in L09.

---

## R. No-Data & Failure Behavior

1. **Deterministic Halting**: A fatal schema mismatch, corrupted file, missing CRS, or invalid geometry prevents promotion from `staging` to `curated`.
2. **Structured Error Payload**: Ingestion failures return a structured validation result detailing exact row indices, column names, and violated constraints.
3. **No Synthetic Substitution**: In production pipelines, missing sources result in explicit `UNAVAILABLE` status rather than synthetic data generation.

---

## S. Error Handling & Severity Classification

* **`ERROR`**: Critical failure that invalidates dataset integrity (e.g. missing primary key, corrupt geometry, missing CRS, null rate violation on mandatory column). **Blocks curation.**
* **`WARNING`**: Non-fatal anomaly (e.g. missing optional amenity field, slight bounding box buffer discrepancy). **Logged in provenance; curation permitted if allowed by contract.**
* **`INFO`**: Informational metrics (e.g. row count, memory footprint, bounding box extents).

---

## T. Logging & Audit Trail

All ingestion and validation operations log structured messages with timestamps, source IDs, step names, and error summaries using Python's standard `logging` module.

---

## U. Reproducibility Requirements

1. Given the same raw input files and `config/sources.yaml`, the ingestion pipeline must produce bit-for-bit identical curated files and provenance manifests.
2. Provenance records are written alongside curated artifacts in JSON format.

---

## V. Acceptance Criteria

1. Ingestion adapters successfully parse CSV, GeoJSON, Shapefile, GeoPackage, and GeoTIFF formats.
2. Validation engine evaluates all 15 validation checks (file existence, readability, schema, null rates, duplicates, geometry validity, CRS, bounding box, ranges).
3. Corrupted or invalid test fixtures (missing column, invalid geometry, missing CRS, duplicate ID) correctly fail validation and are blocked from curation.
4. Clean test fixtures pass validation, generate complete SHA-256 provenance records, and are successfully promoted to `data/curated/`.
5. Unit and validation test suite passes with 100% test success rate.

---

## W. Explicit Non-Goals (Reserved for Downstream Layers)

1. **No Database Loading**: Database migrations, PostGIS spatial tables, and SQL indexing belong to **L02 (Spatial DB)**.
2. **No 30 m Raster Resampling**: Terrain derivatives, 30 m grid resampling, and spatial clipping belong to **L03 (GIS Grid)**.
3. **No Hazard Scoring**: Landslide/flood/rainfall hazard scoring belongs to **L04–L06**.
4. **No Red Zone, Vulnerability, or Optimization**: Decision logic belongs to **L07–L13**.
5. **No Synthetic Real Data**: Test fixtures in `tests/fixtures/` must remain strictly isolated and labeled as tests.
