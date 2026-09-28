# Layer Specification: L02 — PostGIS Spatial Database

**Layer ID**: `L02`  
**Layer Name**: PostGIS Spatial Database Foundation  
**Status**: **LIVE VERIFIED — CORE SCHEMA + REAL CHAMOLI HABITATION LOAD VERIFIED**  
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

> **Verification distinction**
> - Offline / DDL verification: **PASSED**.
> - Live database verification: **PASSED** for the running PostgreSQL/PostGIS container.
> - Real Chamoli habitation verification: **PASSED** for 1,174 loaded records.

---

## B. Database Technology & Version Assumptions

* **RDBMS**: PostgreSQL 16.x
* **Spatial Extension**: PostGIS 3.4.x
* **Python Database Driver**: `psycopg` / `psycopg2` according to the active runtime
* **ORM & DDL Toolkit**: SQLAlchemy 2.0+ / GeoAlchemy2 0.14+
* **Container Image**: `postgis/postgis:16-3.4`

---

## C. Schemas & Namespaces

The database utilizes standard relational tables under the default `public` schema with explicit table naming conventions (singular nouns: `habitation`, `admin_unit`, `data_source`, `candidate_site`).

---

## D. Tables & Entity Breakdown

| Table Name | Entity Type | Purpose | Primary Key | Geometry Column & Type (SRID 32644) | Justification / Data Dictionary Reference |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `data_source` | Metadata / Provenance | Provenance registry of all ingested sources | `source_id` | None | data-dictionary.md lines 18–31 |
| `model_run` | Metadata / Audit | Execution trace of pipeline / optimization runs | `run_id` | None | data-dictionary.md lines 188–201 |
| `admin_unit` | Core Spatial Entity | Administrative hierarchy (district/block/village) | `unit_id` | `geom` MultiPolygon(32644) | data-dictionary.md lines 34–45 |
| `habitation` | Core Spatial Entity | Habitation / village decision units | `habitation_id` | `geom` Geometry(32644) | data-dictionary.md lines 48–61 |
| `infrastructure`| Core Spatial Entity | Critical lifelines, facilities & amenities | `asset_id` | `geom` Geometry(32644) | data-dictionary.md lines 64–76 |
| `hazard_layer` | Hazard Metadata | Hazard raster & vector layer metadata registry | `hazard_id` | None | data-dictionary.md lines 79–91 |
| `risk_cell` | Analytical Grid | Canonical 30 m multi-hazard risk cells | `cell_id` | `geom` Polygon(32644) | data-dictionary.md lines 94–109 |
| `vulnerability` | Analytical Score | Habitation vulnerability scores | `habitation_id` | None (relates to `habitation.geom`) | data-dictionary.md lines 111–125 |
| `candidate_site`| Analytical Candidate| Relocation candidate site parcels | `site_id` | `geom` Polygon(32644) | data-dictionary.md lines 127–139 |
| `capacity` | Analytical Capacity| Site carrying capacity & bottleneck analysis | `site_id` | None (relates to `candidate_site.geom`) | data-dictionary.md lines 141–155 |
| `priority` | Analytical Ranking | Relocation urgency & action tiers | `habitation_id` | None (relates to `habitation.geom`) | data-dictionary.md lines 157–171 |
| `allocation` | Optimization Output | Habitation-to-site population allocation | `allocation_id` | None (relational join to h and s geoms) | data-dictionary.md lines 173–186 |

---

## E. Analytical Tables Review & Justification

The analytical persistence tables are created as empty schema contracts. L02 does not calculate risk, vulnerability, suitability, capacity, priority, or allocation.

---

## F. Geometry & SRID Decisions

1. `admin_unit.geom`: `GEOMETRY(MultiPolygon, 32644)`.
2. `habitation.geom`: `GEOMETRY(Geometry, 32644)`, allowing point or polygonal habitation representations.
3. `infrastructure.geom`: `GEOMETRY(Geometry, 32644)`, allowing point and linear infrastructure.
4. `risk_cell.geom`: `GEOMETRY(Polygon, 32644)`.
5. `candidate_site.geom`: `GEOMETRY(Polygon, 32644)`.

The verified Survey of India artifact carried a Z ordinate. The PostGIS loader explicitly strips Z before insertion because the core database geometry columns are 2D. No horizontal coordinate transformation or geometry invention occurs during loading.

---

## G. Foreign Key & Cascade Policy

To guarantee that provenance, data sources, and analytical history are never accidentally deleted:

* Provenance references use `ON DELETE RESTRICT`.
* Optimization audit references use `ON DELETE RESTRICT`.
* Dependent analytical records use `ON DELETE RESTRICT`.
* No ingestion operation silently deletes unrelated records.

---

## H. CHECK Constraints Justification

Every CHECK constraint is derived from the blueprint and data dictionary, including non-negative population/households, valid population year, normalized risk/vulnerability/suitability/priority ranges, valid tier values, and non-negative capacity/allocation quantities.

---

## I. Migration Structure

1. `001_extensions.sql`: Enables `postgis` and `uuid-ossp`.
2. `002_provenance_and_metadata.sql`: Creates `data_source`, `model_run`, and `hazard_layer`.
3. `003_core_entities.sql`: Creates `admin_unit`, `habitation`, and `infrastructure`.
4. `004_analytical_entities.sql`: Creates analytical persistence tables.
5. `005_indexes.sql`: Creates spatial and query indexes.

---

## J. Live Chamoli Verification Evidence

The running PostGIS database was verified after loading the official Census + Survey of India matched artifact:

- `habitation` rows: **1,174**
- `admin_unit` rows with `type='village'`: **1,174**
- Sample habitation geometry SRID: **32644**
- Sample habitation geometry type: **ST_MultiPolygon**
- Invalid habitation geometries: **0**
- Non-32644 habitation geometries: **0**
- NULL habitation geometries: **0**

The read-only verification command is:

```powershell
docker compose exec backend python scripts/verify_chamoli_postgis.py
```

The verification script is intentionally read-only and does not calculate any DSS outputs.

---

## K. Explicit Non-Goals

1. No 30 m raster creation; that belongs to L03.
2. No scoring computation; risk, vulnerability, suitability, capacity, and optimization belong to L04–L13.
3. No fabricated or imputed source values.
4. No automatic interpretation of missing authoritative hazard inputs as zero risk.
