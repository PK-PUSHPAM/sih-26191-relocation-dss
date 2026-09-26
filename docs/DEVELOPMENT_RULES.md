# Development & Engineering Rules

**Project**: SIH Problem Statement 26191 — Relocation Decision Support System (DSS)  
**Document Version**: 1.0  
**Blueprint Reference**: Section 12 (Naming Rules), Section 13 (Schema Rules), Section 16 (Testing Criteria)

---

## 1. Code & Naming Conventions

### Python Code
* **Functions & Variables**: `snake_case` (e.g., `calculate_vulnerability_score`, `hazard_risk_df`)
* **Classes & Pydantic Models**: `PascalCase` (e.g., `HabitationProfile`, `OptimizationRequest`)
* **Constants & Config Keys**: `UPPER_CASE` or `snake_case` inside YAML (e.g., `CANONICAL_CRS_EPSG = 32644`)
* **Module Names**: Concise `snake_case` (e.g., `landslide_processor.py`, `allocation_solver.py`)

### API Routes & Payloads
* All API routes must start with `/api/v1/...` in kebab-case (e.g., `/api/v1/admin-units`, `/api/v1/candidate-sites`).
* JSON request/response keys must use `snake_case` (e.g., `exposed_population`, `binding_bottleneck`).

### Database & SQL
* Table names must follow a consistent singular convention (`habitation`, `candidate_site`, `risk_cell`, `data_source`).
* Foreign keys must explicitly reference the target table and column (e.g., `admin_unit_id` -> `admin_unit.unit_id`).
* Every spatial table MUST include:
  - Valid PostGIS Geometry with explicit SRID: `GEOMETRY(GeometryType, 32644)`
  - `source_id VARCHAR(64)` referencing `data_source.source_id`
  - `created_at TIMESTAMPTZ DEFAULT NOW()`
  - `updated_at TIMESTAMPTZ DEFAULT NOW()`

---

## 2. Spatial Reference & Grid Standards (OD-04, Section 13)

1. **Canonical Projected CRS**: `EPSG:32644` (WGS 84 / UTM Zone 44N) is the **only** coordinate reference system used for spatial analysis, distance computations, raster reprojection, slope derivation, buffering, and area calculations in Chamoli.
2. **Interchange CRS**: `EPSG:4326` (WGS 84 Lat/Long) is used **strictly** at API boundaries for GeoJSON payloads delivered to the frontend map.
3. **No Upsampling**: Coarse datasets must not be arbitrarily upsampled and misrepresented as high-resolution data. Resampling must preserve native source metadata and uncertainty flags.
4. **Canonical Analysis Grid**: 30-meter raster cell resolution aligned to the UTM Zone 44N grid origin.

---

## 3. Data Integrity & Immutability Rules

1. **Raw Data Immutability**: Files in `data/raw/` are immutable. Never modify, overwrite, or delete ingested raw data files. New ingestion runs create new versioned directories.
2. **Missingness Preservation**: Missing or null data in demographic/amenity layers must **never** be silently converted to `0`. Missing values must be recorded as `NULL` / `NaN` and trigger an explicit confidence penalty.
3. **Census 2011 Attribution**: Always explicitly label Census 2011 data with its vintage (`2011`). Never present it without attributing the baseline year.

---

## 4. API & Frontend Boundaries (Section 14 & 15)

1. **Backend Authority**: All mathematical formulas, hazard weights, thresholds, carrying capacities, priority tiers, and optimization routines MUST execute exclusively on the backend.
2. **Frontend Passivity**: The frontend must never recalculate authoritative scores or invent new decision logic. It renders backend GeoJSON and analytics.
3. **Map Legends & Context**: Every colored layer on the frontend map must display a legend, unit of measurement, timestamp/version, and underlying data source.

---

## 5. Security & Configuration Rules

1. **No Hard-Coded Credentials**: Never hard-code database passwords, secret keys, or internal API tokens in source files or scripts. Use environment variables managed via `.env`.
2. **Configuration Driven**: All model weights, score exponents, classification thresholds, and study area parameters must reside in `config/*.yaml` files and be read dynamically.
3. **Auditability**: Every generated output row (risk cell, vulnerability score, candidate site, allocation result) must include `model_version` and `config_version`.

---

## 6. Testing & Acceptance Matrix (Section 16)

Every layer implementation MUST include:
* **Unit Tests**: Test core formulas, boundary conditions, edge cases, and missingness handling.
* **Spatial Tests**: Verify geometry validity, topological integrity, CRS reprojection accuracy, and raster bounding boxes against Chamoli bounds.
* **Integration Tests**: Verify FastAPI endpoint contracts, status codes, and database roundtrips.
* **Acceptance Tests**: Verify end-to-end execution on a clean environment with the baseline dataset.
