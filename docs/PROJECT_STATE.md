# Project State — SIH 26191 Relocation DSS

**Current Development & Execution Status**

---

## 1. Current Status Summary

- **Current Layer**: `L17` (Testing, Deployment & Final Audit)
- **Current Status**: `IMPLEMENTED — LOCAL TEST/BUILD VERIFIED; DOCKER SMOKE TEST PENDING`
- **Next Task**: Docker Compose build/up smoke verification, then final release audit
- **Last Verified Backend Commit**: L15 local full-suite verification — **306 passed, 2 skipped**
- **Active Blockers**: Authoritative L04-L06 hazard inputs are absent from local data directories

---

## 2. Layer Implementation Progress

| Layer ID | Name | Status | Tests | Verified Commit |
| :--- | :--- | :--- | :--- | :--- |
| **L01** | Data Ingestion & Validation | **FOUNDATION VERIFIED** | 14/14 | `49a204a` |
| **L02** | PostGIS Spatial Database | **OFFLINE / DDL VERIFIED** | 10/10; 2 live-skipped | `7ba343f` |
| **L03** | GIS Processing & Common Grid | **FRAMEWORK VERIFIED** | 20/20 | In progress |
| **L04** | Landslide Baseline | **FRAMEWORK VERIFIED** | 22/22 | In progress |
| **L05** | Flood / Flash Flood Baseline | **FRAMEWORK VERIFIED** | 10/10 | In progress |
| **L06** | Rainfall Trigger Index | **FRAMEWORK VERIFIED** | 18/18 | In progress |
| **L07** | Multi-Hazard Risk Combination | **FRAMEWORK VERIFIED** | 29/29 | In progress |
| **L08** | Red-Zone Engine | **FRAMEWORK VERIFIED** | 42/42 | `aacf149` |
| **L09** | Exposure & Vulnerability Engine | **VERIFIED** | 25/25; full suite 190/190 | `3ff399e` |
| **L10** | Relocation Site Suitability | **VERIFIED** | 37/37; full suite 227/227, 2 skipped | `cdae582` |
| **L11** | Carrying Capacity Engine | **VERIFIED** | 17; full suite 251 passed, 2 skipped | `66aafd5` |
| **L12** | Relocation Priority Engine | **VERIFIED** | 18; full suite 279 passed, 2 skipped | `5aaa695` |
| **L13** | Allocation Optimization (CP-SAT) | **VERIFIED** | full suite 289 passed, 2 skipped | `0d1a7cd` |
| **L14** | Update & Recompute Engine | **VERIFIED** | full suite 303 passed, 2 skipped | `2b5ab535` |
| **L15** | FastAPI Integration Layer | **VERIFIED** | full suite **306 passed, 2 skipped, 1 warning** | local verification |
| **L16** | Dashboard & Decision Reports | **VERIFIED** | 310 passed, 2 skipped; frontend production build passed | verified locally |
| **L17** | Testing, Docker & Final Audit | **IMPLEMENTED — LOCAL CODE CONTRACTS VERIFIED** | L17 deployment-contract tests added; Docker smoke pending | current |

---

## 3. L16 Implementation Summary

- React + Vite dashboard foundation with ten required architecture screens.
- MapLibre GL JS spatial view consuming backend GeoJSON/API payloads.
- API client for the L15 versioned endpoints; frontend does not recalculate authoritative metrics.
- Habitation, site, capacity, optimization, allocation, methodology, and report views.
- Report export supports backend JSON retrieval, Markdown download, and browser Print / Save as PDF.
- Backend/API errors are surfaced instead of converted to fabricated values.
- L16 does not introduce new scoring formulas, thresholds, datasets, or ML.
- L16 frontend production verification requires `npm install` and `npm run build`.

## 4. Existing Real-Data Limitations

- Authoritative L04-L06 hazard inputs are absent from local data directories.
- No real combined-risk raster, red-zone raster, or real Chamoli vulnerability values are generated.
- L03-L16 verification relies on framework contracts and synthetic/unit fixtures where authoritative inputs are unavailable.
- Current outputs are decision-support artifacts, not legal orders or engineering-certified capacities.

## 5. Active Blockers & Decisions Log

- **Active Blockers**: Authoritative L04-L06 hazard inputs are absent from local data directories; no real combined-risk output can be generated.
- **Architectural Decisions**: `OD-01` through `OD-12` strictly respected.


## 6. L17 Implementation Summary

- Added committed Python runtime dependencies in `requirements.txt`.
- Corrected backend Docker entrypoint to the actual `src.api.app:app` FastAPI module.
- Removed silent Docker dependency-install fallbacks.
- Added backend health check and Docker build exclusions.
- Added frontend Docker build exclusions.
- Added GitHub Actions CI for backend tests, frontend production build, and Docker Compose configuration validation.
- Added L17 deployment-contract tests.
- Added the L17 testing/deployment/final-audit specification.
- Local evidence already available: `310 passed, 2 skipped, 1 warning` and successful `npm run build`.
- Remaining release verification: run Docker Compose configuration/build/up smoke tests on the user's machine.
