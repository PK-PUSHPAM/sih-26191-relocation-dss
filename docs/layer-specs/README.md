# Layer Specifications (`docs/layer-specs/`)

This directory contains the authoritative implementation specifications (contracts) for each of the 17 layers of the **SIH 26191 Relocation DSS**.

---

## 1. Principles of Layer Specifications

1. **One Layer = One Contract**: Each layer has a standalone specification defining its exact inputs, outputs, database tables, schemas, formulas, error-handling rules, and acceptance criteria.
2. **Sequential Implementation**: Layers must be implemented sequentially from **L01 to L17**. No layer may be started until the preceding layer passes its acceptance tests.
3. **No Architecture Redesign**: Layer specifications detail the implementation of the frozen architecture ([docs/PROJECT_CONTEXT.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/PROJECT_CONTEXT.md)). They cannot change frozen decisions, formulas, or system boundaries.
4. **Test-Driven Acceptance**: Every layer specification defines required unit tests, spatial tests (where applicable), and integration tests required for verification.

---

## 2. Layer Index & Mapping

| Layer ID | Specification Document | Layer Name | Core Output |
| :--- | :--- | :--- | :--- |
| **L01** | `L01_data_ingestion.md` | Data Ingestion & Validation | Raw/staging datasets, checksum manifests, validation reports |
| **L02** | `L02_spatial_database.md` | PostGIS Spatial Database | Database tables, indexes, constraints, migrations |
| **L03** | `L03_gis_processing.md` | Common Spatial Grid | 30m analysis grid, slope/aspect derivatives (`EPSG:32644`) |
| **L04** | `L04_landslide_hazard.md` | Landslide Baseline | Normalized landslide hazard raster/vectors |
| **L05** | `L05_flood_hazard.md` | Flood / Flash Flood Baseline | Flood exposure masks and inundation levels |
| **L06** | `L06_rainfall_trigger.md` | Rainfall Trigger Index | Rolling precipitation triggers & telemetry updates |
| **L07** | `L07_multi_hazard_risk.md`| Multi-Hazard Risk Engine | Normalized multi-hazard score $H = 0.45L + 0.35F + 0.20R$ |
| **L08** | `L08_red_zone.md` | Red-Zone Engine | Red/amber/lower risk cell classifications + explanations |
| **L09** | `L09_vulnerability.md` | Exposure & Vulnerability Engine| Habitation-level vulnerability score $V$ and exposed population |
| **L10** | `L10_site_suitability.md`| Relocation Site Suitability | Candidate relocation site polygons and suitability score $S$ |
| **L11** | `L11_carrying_capacity.md`| Carrying Capacity Engine | Bottleneck analysis and effective carrying capacity |
| **L12** | `L12_relocation_priority.md`| Relocation Priority Engine | Relocation priority score $RP$ and action tiers |
| **L13** | `L13_optimization.md` | Allocation Optimization | Constrained integer optimization (OR-Tools CP-SAT) |
| **L14** | `L14_recompute_engine.md`| Update / Recompute Engine | Automated pipeline recomputation on updated telemetry/data |
| **L15** | `L15_api_endpoints.md` | FastAPI Integration Layer | REST endpoints (`/api/v1/...`) serving GeoJSON and analytics |
| **L16** | `L16_dashboard_reports.md`| Interactive UI & Reports | React + MapLibre 10-screen decision interface & PDF export |
| **L17** | `L17_testing_deploy.md` | Testing, Docker & Final Audit | End-to-end acceptance suite, Docker compose verification |
