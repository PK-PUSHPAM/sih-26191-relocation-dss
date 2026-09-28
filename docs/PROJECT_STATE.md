# Project State — SIH 26191 Relocation DSS

**Current Development & Execution Status**

---

## 1. Current Status Summary

- **Current Layer**: `L17` (Testing, Deployment & Final Audit)
- **Current Status**: **L01-L17 VERIFIED; SIH PRODUCTIZATION + ASSISTIVE ML IMPLEMENTED**
- **Last Verified Backend Commit**: `894b00d` — L15 optimize test module monkeypatch fix
- **Latest Backend Verification**: **398 passed, 11 warnings**
- **Latest L15 Focused Verification**: **8 passed, 1 warning**
- **Frontend Production Build**: **PASSED**
- **Docker Compose Config**: **PASSED**
- **Docker Backend + Frontend Image Build**: **PASSED**
- **Docker Runtime Smoke Test**: **PASSED**
- **API Smoke Checks**: **6/6 endpoints returned HTTP 200**
- **Container Health**: PostgreSQL healthy, backend healthy, frontend running
- **Active Data Limitation**: Authoritative L04-L06 hazard inputs and labelled landslide inventory are absent from local data directories

---

## 2. Layer Implementation Progress

| Layer ID | Name | Status | Tests / Verification | Verified Commit |
| :--- | :--- | :--- | :--- | :--- |
| **L01** | Data Ingestion & Validation | **FOUNDATION VERIFIED** | verified | `49a204a` |
| **L02** | PostGIS Spatial Database | **OFFLINE / DDL VERIFIED** | verified; live-data limitations documented | `7ba343f` |
| **L03** | GIS Processing & Common Grid | **FRAMEWORK VERIFIED** | full-suite verified | hardened |
| **L04** | Landslide Baseline | **FRAMEWORK VERIFIED** | full-suite verified | hardened |
| **L05** | Flood / Flash Flood Baseline | **FRAMEWORK VERIFIED** | full-suite verified | hardened |
| **L06** | Rainfall Trigger Index | **FRAMEWORK VERIFIED** | full-suite verified | hardened |
| **L07** | Multi-Hazard Risk Combination | **FRAMEWORK VERIFIED** | full-suite verified | hardened |
| **L08** | Red-Zone Engine | **VERIFIED** | focused + full-suite verified | hardened |
| **L09** | Exposure & Vulnerability Engine | **VERIFIED** | focused + full-suite verified | `920de72` |
| **L10** | Relocation Site Suitability | **VERIFIED** | focused + full-suite verified | `eded8a2` |
| **L11** | Carrying Capacity Engine | **VERIFIED** | 28 focused; full suite 380 passed | `f5c118c` |
| **L12** | Relocation Priority Engine | **VERIFIED** | 33 focused; full suite 385 passed | `5da9ba9` |
| **L13** | Allocation Optimization (CP-SAT) | **VERIFIED** | 17 focused; full suite 389 passed | `58bb215` |
| **L14** | Update & Recompute Engine | **VERIFIED** | 17 focused; full suite 395 passed | `c35be0f` |
| **L15** | FastAPI Integration Layer | **VERIFIED** | 8 focused; full suite 398 passed | `894b00d` |
| **L16** | Dashboard & Decision Reports | **VERIFIED** | frontend production build passed | current main |
| **L17** | Testing, Docker & Final Audit | **FINAL VERIFICATION PASSED** | Docker Compose config/build/up, health and API smoke checks passed | current main |

---

## 3. L16 Implementation Summary

- React + Vite dashboard foundation with ten required architecture screens.
- MapLibre GL JS spatial view consuming backend GeoJSON/API payloads.
- API client for the L15 versioned endpoints; frontend does not recalculate authoritative metrics.
- Habitation, site, capacity, optimization, allocation, methodology, and report views.
- Report export supports backend JSON retrieval, Markdown download, and browser Print / Save as PDF.
- Backend/API errors are surfaced instead of converted to fabricated values.
- L16 does not introduce new scoring formulas, thresholds, datasets, or ML.
- Frontend production build verified successfully.

## 4. SIH Productization & Assistive ML

- Reworked L16 into an SIH-facing command center with a persistent decision-workspace sidebar, operational header, KPI cards, live GIS workspace, priority queue, relocation-site explorer, capacity bottleneck visualization, allocation register, methodology pipeline, and report workspace.
- Added a dedicated **AI / ML Insights** screen.
- Added an assistive landslide-susceptibility ML framework using Random Forest and Logistic Regression baselines, strict feature/schema validation, spatial-group cross-validation, ROC-AUC/PR-AUC evaluation hooks, and artifact validation.
- Added `GET /api/v1/ml/status` so the dashboard can show model readiness without fabricating predictions or accuracy.
- Added ML contract tests.
- ML remains **assistive only**; deterministic L07/L08 rules remain authoritative.
- Because an authoritative labelled landslide inventory is not present, the ML layer deliberately reports `NOT_TRAINED` rather than inventing predictions or metrics.

## 5. L17 Final Verification Evidence

- Backend L15 focused tests: **8 passed, 1 warning**.
- Complete backend test suite: **398 passed, 11 warnings**.
- Frontend production build: **Vite build passed**.
- Docker Compose configuration validation: **passed**.
- Backend and frontend Docker images: **built successfully**.
- PostgreSQL container: **healthy**.
- Backend container: **healthy**.
- Frontend container: **running**.
- Backend health endpoint: **HTTP 200**, response status `ok`, API version `1.0`.
- Frontend root: **HTTP 200**.
- API smoke endpoints all returned **HTTP 200**:
  - `/api/v1/admin-units`
  - `/api/v1/habitations`
  - `/api/v1/hazards`
  - `/api/v1/risk/map`
  - `/api/v1/sites`
  - `/api/v1/priorities`

Warnings observed are dependency/tooling deprecations and the frontend bundle-size advisory; they did not fail verification.

## 6. Existing Real-Data Limitations

- Authoritative L04-L06 hazard inputs are absent from local data directories.
- No real combined-risk raster, red-zone raster, or real Chamoli vulnerability values are generated.
- L03-L16 verification relies on framework contracts and synthetic/unit fixtures where authoritative inputs are unavailable.
- Current outputs are decision-support artifacts, not legal orders or engineering-certified capacities.

## 7. Active Blockers & Decisions Log

- **Active Data Limitation**: authoritative L04-L06 hazard inputs are absent from local data directories; therefore a real production combined-risk/red-zone result cannot yet be generated.
- **Architectural Decisions**: `OD-01` through `OD-12` strictly respected.
- **Release Verification**: Docker Compose build/up smoke verification is complete and passed.

## 8. L17 Implementation Summary

- Added committed Python runtime dependencies in `requirements.txt`.
- Corrected backend Docker entrypoint to the actual `src.api.app:app` FastAPI module.
- Removed silent Docker dependency-install fallbacks.
- Added backend health check and Docker build exclusions.
- Added frontend Docker build exclusions.
- Added GitHub Actions CI for backend tests, frontend production build, and Docker Compose configuration validation.
- Added L17 deployment-contract tests.
- Added the L17 testing/deployment/final-audit specification.
- Completed final local release verification: **398 backend tests passed**, frontend production build passed, Docker images built, full stack started, health checks passed, and all six API smoke endpoints returned HTTP 200.
