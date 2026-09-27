# Project State — SIH 26191 Relocation DSS

**Current Development & Execution Status**

---

## 1. Current Status Summary

- **Current Layer**: `L14` (Update & Recompute Engine)
- **Current Status**: `IMPLEMENTED — VERIFICATION PENDING LOCAL RE-RUN`
- **Next Task**: L14 full-suite verification, then L15 (FastAPI Integration Layer)
- **Last Verified Commit**: `0d1a7cd` (L13 local full-suite verification)
- **Active Blockers**: `Authoritative L04-L06 hazard inputs are absent from local data directories`

---

## 2. Layer Implementation Progress

| Layer ID | Name                             | Status                                            | Specification                                                                                                          | Tests                              | Verified Commit |
| :------- | :------------------------------- | :------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------- | :--------------------------------- | :-------------- |
| **L01**  | Data Ingestion & Validation      | **FOUNDATION VERIFIED**                           | [L01 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L01_data_ingestion.md)    | 14/14 Passed                       | `49a204a`       |
| **L02**  | PostGIS Spatial Database         | **OFFLINE / DDL VERIFIED**<br>_(Live DB Pending)_ | [L02 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L02_spatial_database.md)  | 10/10 Passed<br>_(2 live-skipped)_ | `7ba343f`       |
| **L03**  | GIS Processing & Common Grid     | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L03 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L03_gis_processing.md)    | 20/20 Passed                       | In progress     |
| **L04**  | Landslide Baseline               | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L04 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L04_landslide_hazard.md)  | 22/22 Passed                       | In progress     |
| **L05**  | Flood / Flash Flood Baseline     | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L05 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L05_flood_hazard.md)      | 10/10 Passed                       | In progress     |
| **L06**  | Rainfall Trigger Index           | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L06 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L06_rainfall_trigger.md)  | 18/18 Passed                       | In progress     |
| **L07**  | Multi-Hazard Risk Engine         | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L07 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L07_multi_hazard_risk.md) | 29/29 Passed                       | In progress     |
| **L08**  | Red-Zone Engine                  | **FRAMEWORK VERIFIED**<br>_(Real Data Pending)_   | [L08 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L08_red_zone.md)    | 42/42 Passed                       | `aacf149`       |
| **L09**  | Exposure & Vulnerability Engine  | **VERIFIED** | [L09 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L09_vulnerability.md) | 25/25 Passed; full suite 190/190 | `3ff399e` |
| **L10**  | Relocation Site Suitability      | **VERIFIED** | [L10 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L10_site_suitability.md) | 37/37 L10 tests; full suite 227/227 passed, 2 skipped | `cdae582` |
| **L11**  | Carrying Capacity Engine         | **VERIFIED** | [L11 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L11_carrying_capacity.md) | 17 unit tests; local full suite **251 passed, 2 skipped** | `66aafd5` |
| **L12**  | Relocation Priority Engine       | **VERIFIED** | [L12 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L12_relocation_priority.md) | 18 focused tests; local full suite **279 passed, 2 skipped** | `5aaa695` |
| **L13**  | Allocation Optimization (CP-SAT) | **VERIFIED** | [L13 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L13_optimization.md) | local full suite **289 passed, 2 skipped** | `0d1a7cd` |
| **L14**  | Update & Recompute Engine        | **IMPLEMENTED — VERIFICATION PENDING** | [L14 Spec](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/layer-specs/L14_recompute_engine.md) | 11 focused tests added; full-suite verification pending | `a9ae06f` |
| **L15**  | FastAPI Integration Layer        | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L16**  | Dashboard & Decision Reports     | Queued                                            | Pending                                                                                                                | Pending                            | -               |
| **L17**  | Testing, Docker & Final Audit    | Queued                                            | Pending                                                                                                                | Pending                            | -               |

---

## 3. L14 Implementation Summary

- L14 is a deterministic invalidation/planning layer for the frozen L01-L13 pipeline.
- Dataset updates are represented by dataset ID, previous version, new version, and explicit dataset type.
- Changed inputs invalidate their consuming layer and all downstream layers.
- Model/config changes can explicitly identify affected layer IDs; L14 then invalidates that layer and all downstream layers.
- Duplicate updates, unchanged versions, unsupported dataset types, and unknown layer IDs are rejected.
- Execution order is deterministic and follows the frozen pipeline order.
- L14 does **not** execute downstream layers, write to PostgreSQL/PostGIS, run migrations, or expose API endpoints.
- No input is silently converted to zero or ignored.

---

## 4. Existing Real-Data Limitations

- Authoritative L04-L06 hazard inputs are absent from local data directories.
- No real combined-risk raster, red-zone raster, or real Chamoli vulnerability values are generated.
- L03-L14 verification relies on framework contracts and synthetic/unit fixtures where authoritative inputs are unavailable.
- Current outputs are decision-support artifacts, not legal orders or engineering-certified capacities.

## 5. Active Blockers & Decisions Log

- **Active Blockers**: Authoritative L04-L06 hazard inputs are absent from local data directories; no real combined-risk output can be generated.
- **Architectural Decisions**: `OD-01` through `OD-12` strictly respected.
