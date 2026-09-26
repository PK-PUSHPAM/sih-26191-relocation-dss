# Layer Specification: L02 — PostGIS Spatial Database

**Layer ID**: `L02`  
**Layer Name**: PostGIS Spatial Database Foundation  
**Status**: OFFLINE / DDL VERIFIED (LIVE DATABASE VERIFICATION PENDING)  
**Blueprint Reference**: Section 4 (L02 PostGIS Database), Section 11 (Phase 2), Section 12 (Naming Rules), Section 13 (Core Database Schema), Section 16 (Spatial/DB Tests)  
**Parent Architecture**: [docs/ARCHITECTURE.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/ARCHITECTURE.md)  
**Data Dictionary**: [docs/data-dictionary.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/data-dictionary.md)

---

## A. Purpose and Scope

Layer L02 establishes the persistent spatial relational database infrastructure for the SIH 26191 Relocation DSS.

Its primary responsibilities are:
1. Initializing PostGIS extensions on PostgreSQL 16.
2. Providing deterministic, sequential SQL DDL migrations defining all core relational and spatial tables.
3. Enforcing data integrity through foreign keys, NOT NULL constraints, unique constraints, and numeric range CHECK constraints strictly supported by [docs/data-dictionary.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/data-dictionary.md).
4. Enforcing the canonical projected coordinate system (`SRID = 32644`) on all analytical geometry columns with explicit geometry types.
5. Creating GiST spatial indexes on all geometry columns and B-tree indexes on foreign keys and query filters.
6. Establishing end-to-end data provenance by linking every entity and analytical output back to `data_source.source_id` and `model_run.run_id`.
7. Providing a database migration runner and verification test suite.

> **Verification Distinction**:  
> - **Offline / DDL Verification**: **PASSED** (SQL syntax, migration sequence, constraints, ORM mappings, and geometry types verified via unit tests).  
> - **Live Database Verification**: **PENDING** (PostgreSQL/PostGIS container was offline during local test run; live migration execution will be verified when the database server is running).

---

## B. Database Technology & Version Assumptions

* **RDBMS**: PostgreSQL 16.x
* **Spatial Extension**: PostGIS 3.4.x
* **Python Database Driver**: `psycopg` (v3) / `psycopg_binary`
* **ORM & DDL Toolkit**: SQLAlchemy 2.0+ / GeoAlchemy2 0.14+
* **Container Image**: `postgis/postgis:16-3.4`

---

## C. Schema & Namespaces

The database utilizes standard relational tables under the default `public` schema with explicit table naming conventions (singular nouns: `habitation`, `admin_unit`, `data_source`, `candidate_site`).

---

## D. Tables & Entity Breakdown

| Table Name | Entity Type | Purpose | Primary Key | Geometry Column & Type (SRID 32644) | Justification / Data Dictionary Reference |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `data_source` | Metadata / Provenance | Provenance registry of all ingested sources | `source_id` | None | data-dictionary.md lines 18–31 |
| `model_run` | Metadata / Audit | Execution trace of pipeline / optimization runs | `run_id` | None | data-dictionary.md lines 188–201 |
| `admin_unit` | Core Spatial Entity | Administrative hierarchy (district/block/village) | `unit_id` | `geom` MultiPolygon(32644) | data-dictionary.md lines 34–45 |
| `habitation` | Core Spatial Entity | Habitation / village decision units | `habitation_id` | `geom` Geometry(32644) | data-dictionary.md lines 48–61 (accommodates Point centroids and Polygons) |
| `infrastructure`| Core Spatial Entity | Critical lifelines, facilities & amenities | `asset_id` | `geom` Geometry(32644) | data-dictionary.md lines 64–76 (accommodates facility Points and road LineStrings) |
| `hazard_layer` | Hazard Metadata | Hazard raster & vector layer metadata registry | `hazard_id` | None (references raster/vector assets) | data-dictionary.md lines 79–91 |
| `risk_cell` | Analytical Grid | Canonical 30 m multi-hazard risk cells | `cell_id` | `geom` Polygon(32644) | data-dictionary.md lines 94–109 (pure schema, no L02 computation) |
| `vulnerability` | Analytical Score | Habitation vulnerability scores | `habitation_id` | None (relates to `habitation.geom`) | data-dictionary.md lines 111–125 (pure schema, no L02 computation) |
| `candidate_site`| Analytical Candidate| Relocation candidate site parcels | `site_id` | `geom` Polygon(32644) | data-dictionary.md lines 127–139 (site polygon footprint) |
| `capacity` | Analytical Capacity| Site carrying capacity & bottleneck analysis | `site_id` | None (relates to `candidate_site.geom`) | data-dictionary.md lines 141–155 (pure schema, no L02 computation) |
| `priority` | Analytical Ranking | Relocation urgency & action tiers | `habitation_id` | None (relates to `habitation.geom`) | data-dictionary.md lines 157–171 (pure schema, no L02 computation) |
| `allocation` | Optimization Output | Habitation-to-site population allocation | `allocation_id` | None (relational join to h and s geoms) | data-dictionary.md lines 173–186 (pure schema, no L02 computation) |

---

## E. Analytical Tables Review & Justification

The 6 analytical persistence tables (`risk_cell`, `vulnerability`, `candidate_site`, `capacity`, `priority`, `allocation`) are created in Migration 004 strictly as **empty schema contracts** defined in [docs/data-dictionary.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/data-dictionary.md):

1. **`risk_cell`**: Defines storage for canonical 30 m grid outputs ($H_{landslide}, H_{flood}, H_{rain}, H_{combined}$, red zone flag). L02 creates only the empty table. No grid generation (L03) or risk scoring (L07/L08) occurs in L02.
2. **`vulnerability`**: Defines storage for multi-factor habitation scores ($P, S, A, I, D, V$). No calculation occurs in L02 (deferred to L09).
3. **`candidate_site`**: Defines storage for candidate relocation polygons ($S_{score}$, status, area, explanation JSON). No site generation occurs in L02 (deferred to L10).
4. **`capacity`**: Defines storage for bottleneck carrying capacities (land, water, sanitation, health, access, effective). No capacity modeling occurs in L02 (deferred to L11).
5. **`priority`**: Defines storage for relocation urgency scores and tiers (Immediate, Short, Medium, Monitor). No prioritization occurs in L02 (deferred to L12).
6. **`allocation`**: Defines storage for mathematical optimization assignments ($x_{h,s}$, distance, constraint flags). No solver execution occurs in L02 (deferred to L13).

---

## F. Geometry & SRID Decisions

1. **`admin_unit.geom`**: `GEOMETRY(MultiPolygon, 32644)` — Explicit concrete type representing administrative region boundaries.
2. **`habitation.geom`**: `GEOMETRY(Geometry, 32644)` — Generic type is required because source datasets represent habitations as either Point coordinates (village centroids) or Polygon/MultiPolygon built-up footprints (as explicitly documented in data dictionary line 59: "Habitation footprint or centroid polygon").
3. **`infrastructure.geom`**: `GEOMETRY(Geometry, 32644)` — Generic type is required because critical infrastructure includes point facilities (hospitals, schools, water treatment plants) and linear network features (road segments, bridges) (documented in data dictionary line 74).
4. **`risk_cell.geom`**: `GEOMETRY(Polygon, 32644)` — Explicit concrete type representing individual 30 m square raster grid cells.
5. **`candidate_site.geom`**: `GEOMETRY(Polygon, 32644)` — Explicit concrete type representing candidate relocation site footprints (per data dictionary line 133: "Site polygon footprint").

---

## G. Foreign Key & Cascade Policy (Audit Preservation)

To guarantee that provenance, data sources, and analytical history are never accidentally deleted:

* **`NO CASCADE DELETION` on Provenance & History**:
  - `data_source` references (`habitation.source_id`, `infrastructure.source_id`, `hazard_layer.source_id`) use `ON DELETE RESTRICT`. Deleting a registered data source is prohibited while entity records reference it.
  - `model_run` references (`allocation.run_id`) use `ON DELETE RESTRICT`. Optimization audit runs cannot be deleted while allocation records depend on them.
  - `habitation` and `candidate_site` references from `allocation` use `ON DELETE RESTRICT`.
  - Dependent 1-to-1 extension tables (`vulnerability`, `capacity`, `priority`) use `ON DELETE RESTRICT` to ensure analytical scores are preserved and cannot be silently orphaned or cascade-wiped.

---

## H. CHECK Constraints Justification

Every CHECK constraint is strictly derived from the blueprint and data dictionary:
1. `habitation.population >= 0`, `households >= 0` (non-negative census counts).
2. `habitation.population_year BETWEEN 1900 AND 2100` (valid calendar year).
3. `risk_cell.h_*` and `combined_risk` in $[0.0, 1.0]$ (normalized hazard range).
4. `risk_cell.risk_tier IN ('red', 'amber', 'lower_risk')` (blueprint Section 5).
5. `vulnerability.vulnerability` in $[0.0, 1.0]$ (blueprint Section 6).
6. `candidate_site.area > 0` and `suitability` in $[0.0, 1.0]$ (blueprint Section 7).
7. `candidate_site.status IN ('eligible', 'conditional', 'rejected')` (data-dictionary line 136).
8. `capacity.effective_cap >= 0` (non-negative population capacity).
9. `priority.priority_score` in $[0.0, 1.0]$ (blueprint Section 9).
10. `priority.tier IN ('Immediate', 'Short-term', 'Medium-term', 'Monitor')` (blueprint OD-09).
11. `allocation.allocated_population >= 0` and `distance >= 0.0` (physical non-negativity).
12. `model_run.status IN ('running', 'completed', 'failed')` (audit status).

---

## I. Migration Structure (`db/migrations/`)

1. `001_extensions.sql`: Enables `postgis` and `uuid-ossp` extensions.
2. `002_provenance_and_metadata.sql`: Creates `data_source`, `model_run`, and `hazard_layer` tables.
3. `003_core_entities.sql`: Creates `admin_unit`, `habitation`, and `infrastructure` tables.
4. `004_analytical_entities.sql`: Creates empty analytical persistence tables: `risk_cell`, `vulnerability`, `candidate_site`, `capacity`, `priority`, and `allocation`.
5. `005_indexes.sql`: Creates all GiST spatial indexes and performance B-Tree indexes.

---

## J. Explicit Non-Goals (Reserved for L03+)

1. **No Data Population in L02**: Loading real data occurs in specific layer ingestion flows.
2. **No 30 m Raster Creation**: Generating the 30 m raster cells belongs to **L03**.
3. **No Scoring Computation**: Risk, vulnerability, suitability, capacity, and optimization calculations belong to **L04–L13**.
