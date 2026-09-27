# Project State — SIH 26191 Relocation DSS

**Current Development & Execution Status**

---

## 1. Current Status Summary

- **Current Layer**: `L15` (FastAPI Integration Layer)
- **Current Status**: `IMPLEMENTED — VERIFICATION PENDING LOCAL RE-RUN`
- **Next Task**: L15 full-suite verification, then L16 (Dashboard & Decision Reports)
- **Last Verified Commit**: `2b5ab535` (L14 local full-suite verification)
- **Active Blockers**: `Authoritative L04-L06 hazard inputs are absent from local data directories`

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
| **L15** | FastAPI Integration Layer | **IMPLEMENTED — VERIFICATION PENDING** | 3 focused tests added; full-suite verification pending | `025b7fb` |
| **L16** | Dashboard & Decision Reports | Queued | Pending | - |
| **L17** | Testing, Docker & Final Audit | Queued | Pending | - |

---

## 3. L15 Implementation Summary

- FastAPI application with versioned `/api/v1` routes.
- API contract follows the frozen L15 architecture in `docs/ARCHITECTURE.md`.
- Administrative boundaries and spatial resources are delivered as GeoJSON in EPSG:4326.
- Habitation, vulnerability, capacity, priority, run, and allocation data are read from existing PostGIS/SQLAlchemy persistence.
- `POST /api/v1/optimize` invokes the frozen L13 CP-SAT engine using caller-supplied scenario inputs and objective weights.
- L15 does not implement or duplicate L04-L12 mathematical formulas.
- L15 does not perform database migrations or persist optimization results.
- Report endpoint exposes JSON report data; document/PDF rendering remains L16.
- Invalid optimization payloads return HTTP 422; missing individual resources return HTTP 404.
- Database failures are not converted into fabricated empty results.

## 4. Existing Real-Data Limitations

- Authoritative L04-L06 hazard inputs are absent from local data directories.
- No real combined-risk raster, red-zone raster, or real Chamoli vulnerability values are generated.
- L03-L15 verification relies on framework contracts and synthetic/unit fixtures where authoritative inputs are unavailable.
- Current outputs are decision-support artifacts, not legal orders or engineering-certified capacities.

## 5. Active Blockers & Decisions Log

- **Active Blockers**: Authoritative L04-L06 hazard inputs are absent from local data directories; no real combined-risk output can be generated.
- **Architectural Decisions**: `OD-01` through `OD-12` strictly respected.
