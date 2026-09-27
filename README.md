# SIH 26191 — Relocation Decision Support System (DSS)

> **Smart India Hackathon 2026 — Problem Statement 26191**  
> **Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations**

---

## 1. Project Purpose

The prototype is a GIS-enabled decision-support system for proactive relocation planning in Chamoli District, Uttarakhand. It is **not** merely a disaster map, a landslide predictor, or a population database. The system integrates hazard, exposure, vulnerability, disaster history, site suitability, carrying-capacity constraints, relocation priority, and mathematical allocation into one transparent, auditable workflow.

The system answers five core decision questions:
1. **Which parts of Chamoli are unsuitable for permanent habitation** under the prototype's multi-hazard rules?
2. **Which vulnerable habitations are exposed** to those hazards, and how severe is their relocation need?
3. **Which candidate sites are comparatively safer** and operationally suitable for relocation?
4. **How many people can each candidate site realistically support** under modeled constraints?
5. **Which habitation should be addressed first, to which site, and why?**

---

## 2. Current Status & Active Progress

For real-time development status, active layer contracts, and verified milestones, refer to:
* **Active Status & Progress Tracker**: [docs/PROJECT_STATE.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/PROJECT_STATE.md)
* **Permanent Architecture Context**: [docs/PROJECT_CONTEXT.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/PROJECT_CONTEXT.md)
* **Layer Contracts & Specifications**: [docs/layer-specs/README.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/README.md)

*Current Development Stage*: **L17: Testing, Deployment & Final Audit** (`IMPLEMENTED — Docker smoke verification pending locally`).

---

## 3. Frozen Scope & Core Decisions (OD-01 to OD-12)

* **Frozen Prototype Geography**: Chamoli District, Uttarakhand (OD-01).
* **Core Hazards**: Landslide + Flood / Flash Flood + Extreme/Heavy Rainfall trigger (OD-02).
* **Primary Data Policy**: Authoritative/open government sources first; documented open alternatives second. No fabricated inputs (OD-03).
* **Spatial & Temporal Resolution**: Vector boundaries at native resolution; canonical 30 m analysis grid (`EPSG:32644`); daily rainfall and hourly CWC discharge telemetry where available (OD-04).
* **Red Zone Rule**: Hybrid hard exclusions + normalized multi-hazard risk $H = 0.45L + 0.35F + 0.20R$ with configurable threshold ($H \ge 0.70$) (OD-05).
* **Vulnerability Weights**: Population exposure 35%, Social vulnerability proxies 25%, Critical-service access 20%, Infrastructure dependency 10%, Historical disaster recurrence 10% (OD-06).
* **Site Suitability Weights**: Hazard safety 30%, Slope 15%, Road access 15%, Water 15%, Healthcare 10%, Education 5%, Land-use 5%, Service proximity 5% (OD-07).
* **Carrying Capacity**: Bottleneck-based effective capacity: $\lfloor \min(\text{land}, \text{water}, \text{sanitation}, \text{health}, \text{access}) \times 0.80 \rfloor$ (OD-08).
* **Relocation Priority**: Risk 40%, Exposed population 25%, Vulnerability 20%, Response difficulty 10%, Recurrence 5%. Tiers: Immediate ($\ge 0.75$), Short-term ($0.55\text{--}0.75$), Medium-term ($0.35\text{--}0.55$), Monitor ($< 0.35$) (OD-09).
* **Role of AI/ML**: Controlled supervised landslide susceptibility model if labeled inventory data is adequate; otherwise deterministic susceptibility baseline is authoritative (OD-10).
* **Optimization Objective**: Transparent mathematical allocation minimizing weighted travel distance, unmet demand, and residual hazard exposure using OR-Tools CP-SAT / MILP (OD-11).
* **Technology Stack**: Python + FastAPI + PostgreSQL/PostGIS + GeoPandas/Rasterio + scikit-learn/XGBoost (optional) + OR-Tools + React + MapLibre/Leaflet + Docker (OD-12).

---

## 4. Technology Stack

| Layer | Component | Technology Selection |
| :--- | :--- | :--- |
| **Database** | Spatial Storage & Querying | PostgreSQL 16 + PostGIS 3.4 (`EPSG:32644`) |
| **Backend Core** | API & Orchestration | Python 3.11, FastAPI, Pydantic, SQLAlchemy / GeoAlchemy2 |
| **GIS & Raster** | Spatial Analysis | GeoPandas, Rasterio, Shapely, PyPROJ, GDAL |
| **Optimization** | Relocation Assignment | Google OR-Tools (CP-SAT / Linear Solver) |
| **ML (Optional)** | Susceptibility Modeling | scikit-learn, XGBoost |
| **Frontend** | Interactive UI & Maps | React, MapLibre GL JS / Leaflet, Tailwind / CSS Modules |
| **Infrastructure** | Containerization | Docker & Docker Compose |

---

## 5. 17-Layer Architecture Overview

```
DATA SOURCES
  │
  ▼
L01: Data Ingestion & Validation
  │
  ▼
L02: PostGIS Spatial Database
  │
  ▼
L03: GIS Processing & Common Spatial Grid (30 m, EPSG:32644)
  │
  ▼
┌──────────────────────── Hazard Stack ────────────────────────┐
│ L04: Landslide Baseline │ L05: Flood Baseline │ L06: Rainfall │
└───────────────────────────────┬──────────────────────────────┘
  │
  ▼
L07: Multi-Hazard Risk (H = 0.45L + 0.35F + 0.20R)
  │
  ▼
L08: Red-Zone Engine (Hard Exclusions + H >= 0.70)
  │
  ▼
L09: Exposure & Vulnerability Engine (V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D)
  │
  ▼
L10: Relocation-Site Suitability Engine (S = 0.30Hsafe + 0.15Slope + ...)
  │
  ▼
L11: Carrying Capacity Engine (Bottleneck-based Effective Capacity)
  │
  ▼
L12: Relocation Priority Engine (RP Tiers: Immediate, Short, Medium, Monitor)
  │
  ▼
L13: Allocation / Optimization Engine (OR-Tools CP-SAT)
  │
  ▼
L14: Update / Recompute Engine
  │
  ▼
L15: FastAPI Integration Layer
  │
  ▼
L16: Dashboard & Reports (10 screens)
  │
  ▼
L17: Testing, Deployment & Audit
```

---

## 6. Development Workflow & AI Rules

This repository follows a strict **Layer-by-Layer 7-Step Development Loop**:
1. Provide the master blueprint and specific layer contract.
2. Provide the repository tree and permissible files.
3. Provide input/output schemas and acceptance tests.
4. AI inspects existing code and identifies any interface conflicts without redesigning architecture.
5. AI implements **only that single layer**.
6. Run unit tests, spatial tests, and real-data smoke tests.
7. Advance to the next layer only after acceptance criteria pass.

### Human Checkpoints
* **After L01**: Verify actual raw datasets are downloaded and validated.
* **After L03**: Visually inspect projected terrain, boundaries, and 30 m grid.
* **After L04–L06**: Compare baseline hazard outputs against historical disaster events.
* **After L08**: Manually inspect Red Zone polygons against satellite imagery.
* **After L10–L11**: Review candidate relocation sites and verify capacity bottlenecks.
* **After L13**: Audit allocation matrix for feasibility and travel distances.
* **Before Final Demo**: Execute complete clean-install pipeline end-to-end.

---

## 7. Repository Layout

```
sih-26191-relocation-dss/
├── config/              # YAML configuration files (hazards, weights, thresholds, sources)
├── data/                # Data lifecycle (raw, staging, curated, derived)
├── db/                  # PostGIS migrations and seed scripts
├── docker/              # Dockerfiles for backend and frontend
├── docs/                # Architecture, source register, data dictionary, layer specs
├── frontend/            # React + MapLibre/Leaflet user interface
├── ml/                  # Optional landslide ML feature engineering & training
├── notebooks/           # Exploratory spatial analysis notebooks
├── scripts/             # Operational and pipeline automation scripts
├── src/                 # Backend Python source code modularized by layer
├── tests/               # Unit, spatial, integration, and acceptance tests
├── .env.example         # Template for environment variables
├── .gitignore           # Git ignore rules
├── docker-compose.yml   # Multi-container local orchestration
└── README.md            # Master repository overview
```

---

## 8. System Boundaries & Explicit Non-Claims

| Inside Prototype Scope | Explicitly Outside Scope / Not Claimed |
| :--- | :--- |
| GIS hazard layers and normalized scoring | Legal declaration of a Red Zone |
| Relative relocation site suitability ranking | Official government approval of relocation sites |
| Modeled effective carrying capacity | Engineering certification of infrastructure |
| Evidence-backed relocation prioritization | Compulsory relocation orders |
| Mathematical optimization scenarios | Guaranteed real-world optimal allocation |
| Configurable ML susceptibility models | Guaranteed disaster prediction |
| Ingestion pipelines for government sources | Universal real-time early-warning system |
