# SIH 26191 — Data Dictionary & Database Schema

**Project**: Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations  
**Scope**: Chamoli District, Uttarakhand  
**Blueprint Reference**: Section 13 (Core Database Schema)

---

## 1. Spatial Reference System

* **Canonical Processing CRS**: `EPSG:32644` (WGS 84 / UTM Zone 44N) — used for all distance, area, buffering, raster analysis, and vector overlays.
* **Interchange / Display CRS**: `EPSG:4326` (WGS 84 Lat/Long) — used strictly for GeoJSON API payloads and frontend map display.

---

## 2. Core Database Schema Tables

### `data_source`
Provenance registry tracking all ingested files, portals, and licenses.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `source_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier for data source |
| `agency` | VARCHAR(255) | NOT NULL | Providing agency (e.g., USDMA, Census, NRSC, NWIC) |
| `url` | TEXT | NULLABLE | Direct URL or portal origin |
| `access_date` | DATE | NOT NULL | Date when data was retrieved |
| `license` | VARCHAR(128) | NOT NULL | Data usage license or open-access terms |
| `version` | VARCHAR(64) | NOT NULL | Source version / publication year |
| `checksum` | VARCHAR(128) | NOT NULL | SHA256 hash of raw ingested payload |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Ingestion timestamp |

---

### `admin_unit`
Administrative hierarchy (District, Tehsil/Block, Gram Panchayat / Village).

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `unit_id` | VARCHAR(64) | PRIMARY KEY | Unique admin unit identifier |
| `type` | VARCHAR(32) | NOT NULL | Hierarchy level (`district`, `block`, `village`) |
| `parent_id` | VARCHAR(64) | FK -> `admin_unit.unit_id` | Parent administrative unit |
| `name` | VARCHAR(255) | NOT NULL | Administrative unit name |
| `code` | VARCHAR(64) | NULLABLE | Official Census / LGD code |
| `geom` | GEOMETRY(MultiPolygon, 32644) | NOT NULL | Projected administrative boundary geometry |

---

### `habitation`
Decision unit representing villages, hamlets, or settlement clusters.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `habitation_id` | VARCHAR(64) | PRIMARY KEY | Unique habitation identifier |
| `admin_unit_id` | VARCHAR(64) | FK -> `admin_unit.unit_id` | Containing administrative unit |
| `name` | VARCHAR(255) | NOT NULL | Habitation / village name |
| `population_year` | INT | NOT NULL | Baseline year (e.g. 2011) |
| `population` | INT | NOT NULL | Total population count |
| `households` | INT | NOT NULL | Total household count |
| `geom` | GEOMETRY(Geometry, 32644) | NOT NULL | Habitation footprint or centroid polygon |
| `source_id` | VARCHAR(64) | FK -> `data_source.source_id` | Origin dataset |

---

### `infrastructure`
Critical facilities, amenities, and lifelines.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `asset_id` | VARCHAR(64) | PRIMARY KEY | Unique asset ID |
| `type` | VARCHAR(64) | NOT NULL | Asset type (`road`, `hospital`, `school`, `water_point`) |
| `name` | VARCHAR(255) | NULLABLE | Asset name |
| `capacity_or_proxy`| NUMERIC | NULLABLE | Measured capacity or proxy capacity indicator |
| `is_proxy` | BOOLEAN | DEFAULT TRUE | Indicates whether capacity is measured or proxy |
| `geom` | GEOMETRY(Geometry, 32644) | NOT NULL | Asset spatial representation |
| `source_id` | VARCHAR(64) | FK -> `data_source.source_id` | Provenance source |

---

### `hazard_layer`
Raster and vector hazard metadata catalogue.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `hazard_id` | VARCHAR(64) | PRIMARY KEY | Unique hazard layer ID |
| `type` | VARCHAR(32) | NOT NULL | Hazard type (`landslide`, `flood`, `rainfall`) |
| `date_version` | VARCHAR(64) | NOT NULL | Temporal coverage or baseline version |
| `source_id` | VARCHAR(64) | FK -> `data_source.source_id` | Provenance source |
| `model_version` | VARCHAR(64) | NOT NULL | Model / pipeline generation version |
| `raster_vector_ref`| TEXT | NOT NULL | File path or table reference |
| `is_normalized` | BOOLEAN | DEFAULT FALSE | Whether values are normalized to 0–1 |

---

### `risk_cell`
Canonical 30 m grid cell outputs for multi-hazard risk and Red Zone evaluation.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `cell_id` | BIGINT / VARCHAR(64) | PRIMARY KEY | Unique 30m grid cell ID |
| `h_landslide` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | Normalized Landslide Risk ($L$) |
| `h_flood` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | Normalized Flood / Flash Flood Risk ($F$) |
| `h_rain` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | Normalized Rainfall Trigger Index ($R$) |
| `combined_risk` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | Multi-hazard Score $H = 0.45L + 0.35F + 0.20R$ |
| `red_zone` | BOOLEAN | NOT NULL | Decision flag (Hard Exclusion OR $H \ge 0.70$) |
| `risk_tier` | VARCHAR(32) | NOT NULL | `red`, `amber`, `lower_risk` |
| `quality_flag` | VARCHAR(64) | NOT NULL | Data quality / uncertainty indicator |
| `geom` | GEOMETRY(Polygon, 32644) | NOT NULL | 30m grid cell bounding polygon |

---

### `vulnerability`
Habitation-level multi-factor vulnerability assessment.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `habitation_id` | VARCHAR(64) | PRIMARY KEY, FK | Target habitation |
| `population_exposure` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | $P$ score (exposed population share) |
| `social_score` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | $S$ score (demographic vulnerability) |
| `access_score` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | $A$ score (service deficit) |
| `infra_score` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | $I$ score (infrastructure dependency) |
| `recurrence_score` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | $D$ score (historical disaster events) |
| `vulnerability` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | Composite $V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D$ |
| `missing_data_penalty`| NUMERIC(5,4) | DEFAULT 0.0 | Confidence penalty if indicators missing |

---

### `candidate_site`
Algorithmically generated and scored relocation sites.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `site_id` | VARCHAR(64) | PRIMARY KEY | Unique candidate site ID |
| `geom` | GEOMETRY(Polygon, 32644) | NOT NULL | Site polygon footprint |
| `area` | NUMERIC | NOT NULL | Usable site area in square meters / hectares |
| `suitability` | NUMERIC(5,4) | CHECK (0.0 to 1.0) | Multi-criteria Suitability Score ($S$) |
| `status` | VARCHAR(32) | NOT NULL | `eligible`, `conditional`, `rejected` |
| `explanation_json` | JSONB | NOT NULL | Component breakdown ($H_{safe}$, slope, road, water, etc.) |

---

### `capacity`
Modeled carrying capacity and bottleneck analysis per candidate site.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `site_id` | VARCHAR(64) | PRIMARY KEY, FK | Target candidate relocation site |
| `land_cap` | INT | NOT NULL | People supported based on usable area & density |
| `water_cap` | INT | NOT NULL | People supported based on water availability |
| `sanitation_cap` | INT | NOT NULL | People supported based on sanitation capacity |
| `health_cap` | INT | NOT NULL | People supported based on healthcare proximity |
| `access_cap` | INT | NOT NULL | People supported based on road/transport access |
| `binding_bottleneck`| VARCHAR(64) | NOT NULL | Binding limiting factor (`land`, `water`, `health`, etc.) |
| `effective_cap` | INT | NOT NULL | $\lfloor \min(\text{components}) \times \text{safety\_factor} \rfloor$ |

---

### `priority`
Relocation urgency ranking and tier classification for exposed habitations.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `habitation_id` | VARCHAR(64) | PRIMARY KEY, FK | Target habitation |
| `risk` | NUMERIC(5,4) | NOT NULL | Hazard risk intensity at habitation |
| `exposed_pop` | INT | NOT NULL | Total population within hazard/red zones |
| `vulnerability` | NUMERIC(5,4) | NOT NULL | Vulnerability score ($V$) |
| `response_difficulty`| NUMERIC(5,4)| NOT NULL | Remoteness & access difficulty index |
| `recurrence` | NUMERIC(5,4) | NOT NULL | Normalized historical recurrence index |
| `priority_score` | NUMERIC(5,4) | NOT NULL | Composite $RP = 0.40R + 0.25Pop + 0.20V + 0.10Resp + 0.05Rec$ |
| `tier` | VARCHAR(32) | NOT NULL | `Immediate` ($\ge 0.75$), `Short-term`, `Medium-term`, `Monitor` |

---

### `allocation`
Optimization run output allocating populations from vulnerable habitations to candidate sites.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `allocation_id` | BIGSERIAL | PRIMARY KEY | Unique allocation row ID |
| `run_id` | VARCHAR(64) | FK -> `model_run.run_id` | Optimization run ID |
| `habitation_id` | VARCHAR(64) | FK -> `habitation.habitation_id`| Source habitation |
| `site_id` | VARCHAR(64) | FK -> `candidate_site.site_id` | Destination candidate site |
| `allocated_population`| INT | CHECK ($\ge 0$) | Number of people relocated |
| `distance` | NUMERIC | NOT NULL | Travel / road network distance (km/meters) |
| `constraint_flags` | JSONB | NOT NULL | Hard constraints, active penalties, slack status |

---

### `model_run`
Audit and reproducibility log for every pipeline execution.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `run_id` | VARCHAR(64) | PRIMARY KEY | Unique UUID / run hash |
| `model_version` | VARCHAR(64) | NOT NULL | Codebase version / commit hash |
| `config_version` | VARCHAR(64) | NOT NULL | Version of YAML config applied |
| `input_versions` | JSONB | NOT NULL | Map of source dataset versions used |
| `started_at` | TIMESTAMPTZ | NOT NULL | Execution start timestamp |
| `finished_at` | TIMESTAMPTZ | NULLABLE | Execution end timestamp |
| `status` | VARCHAR(32) | NOT NULL | `running`, `completed`, `failed` |
| `logs_or_error` | TEXT | NULLABLE | Execution trace or failure details |
