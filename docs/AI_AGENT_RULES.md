# AI Coding Agent Rules & Execution Playbook

**Project**: SIH Problem Statement 26191 — Relocation Decision Support System (DSS)  
**Document Version**: 1.0  
**Blueprint Reference**: Section 11, Section 17, Section 18, Section 19

---

## 1. Context Loading Policy

Every AI coding agent working on this repository MUST adhere to the following sequence:

1. **Read `docs/PROJECT_CONTEXT.md` First**: Obtain the frozen problem statement, geography, CRS (`EPSG:32644`), formulas, and constraints.
2. **Read `docs/PROJECT_STATE.md` Second**: Determine current progress, active layer, and verified commit.
3. **Read Only the Specific Layer Spec**: Read only the specification file (e.g. `docs/layer-specs/L01_data_ingestion.md`) for the current layer being implemented.
4. **Inspect Only Relevant Code**: Limit repository inspection to files relevant to the current layer contract.
5. **Do Not Reread the Complete Blueprint** unless explicitly required to resolve a textual ambiguity.
6. **Do Not Redesign Architecture**: Follow frozen open decisions (`OD-01` to `OD-12`).
7. **Do Not Hallucinate**: Never invent data, APIs, credentials, government portals, or unverified capabilities.
8. **Stop and Escalate on Conflicts**: If a architectural or formula conflict is discovered, stop immediately and report it to the user.
9. **Update `docs/PROJECT_STATE.md`**: At the completion of each layer task, update `docs/PROJECT_STATE.md` with the new status, tests passed, and commit.
10. **Do Not Auto-Proceed**: Never start the next layer automatically without explicit user review and instruction.

---

## 2. Non-Negotiable AI Rules

1. **Architecture is Frozen**: Do NOT redesign the architecture, change frozen open decisions (OD-01 to OD-12), or substitute core technologies. If you think an architecture change is needed, STOP and inform the user.
2. **Single Layer Scope**: Do NOT attempt to implement multiple layers in a single prompt. **One layer = one implementation contract = one testable checkpoint/merge.**
3. **No Hallucinated Data / Integrations**: Do NOT invent APIs, credentials, datasets, thresholds, or fake government endpoints. Sourced inputs must match `docs/DATA_SOURCES.md` and `config/sources.yaml`.
4. **No Unsubstantiated Claims**: Never label the system as "predicting disasters with 100% accuracy", "legally approved red zones", or "engineering-certified capacity". The system produces modeled prototype decision-support layers.
5. **No Business Logic in the Frontend**: All scoring, spatial overlays, carrying capacity calculations, and optimization logic must live in the Python backend. The frontend is purely for visualization and user interaction.

---

## 3. The 7-Step AI Development Loop

For every layer (from L01 to L17), the AI workflow must follow this exact loop:

```
[1] Receive Layer Contract & Master Blueprint
                       │
                       ▼
[2] Receive Repository Tree & Permissible Target Files
                       │
                       ▼
[3] Receive Input / Output Schemas & Acceptance Criteria
                       │
                       ▼
[4] Inspect Existing Code & Identify Interface Conflicts (No Redesign!)
                       │
                       ▼
[5] Implement ONLY That Layer's Code & Unit/Spatial Tests
                       │
                       ▼
[6] Run Test Suite & Real-Data Smoke Test
                       │
                       ▼
[7] Checkpoint Merge & Advance to Next Layer Only When Tests Pass
```

---

## 4. Standard AI Master Prompt Template

When instructing an AI to implement any layer, use the following standardized prompt:

```text
You are implementing Layer {LAYER_ID} of SIH Problem Statement 26191.
Treat docs/SIH_26191_Final_Blueprint_v1.0.pdf as the single source of truth.

Do not redesign architecture, change frozen decisions, invent data, invent APIs, or add dependencies without explicit justification.
First inspect the repository and identify existing interfaces that this layer must respect.
Then implement only this layer. Use the exact input/output contracts and configuration keys defined in the layer specification.
Write production-quality modular code with logging, validation, error handling, and tests.
Never hard-code secrets or source URLs inside business logic.
Every derived result must carry source/version/model/config metadata where applicable.

After implementation, run the relevant tests and provide:
1) files changed,
2) schema/API changes,
3) commands run,
4) test results,
5) known limitations,
6) exact next dependency.
```

---

## 5. Layer Prompt Cheat Sheet (Section 18)

| Phase | Target Layer | Prompt Summary / Scope |
| :--- | :--- | :--- |
| **Phase 1** | **L01: Data Layer** | Build source manifests, download/import adapters, raw/staging/curated structure, schema validation, CRS checks, geometry checks, duplicate reports, and provenance. |
| **Phase 2** | **L02: PostGIS DB** | Create migrations for frozen schema, spatial indexes, geometry constraints (`EPSG:32644`), foreign keys, and seed scripts. |
| **Phase 3** | **L03: GIS Grid** | Establish canonical projected CRS (`EPSG:32644`), 30 m analysis grid, raster/vector reprojection utilities, slope/aspect derivation, and distance calculations. |
| **Phases 4–6** | **L04–L06: Hazards** | Implement landslide baseline (L04), flood/flash-flood baseline (L05), and rainfall trigger index (L06). Normalize outputs to $[0, 1]$ with clear metadata. |
| **Phases 7–9** | **L07–L09: Risk & Red Zone** | Implement multi-hazard risk ($H = 0.45L + 0.35F + 0.20R$), red-zone engine ($H \ge 0.70$ or hard exclusions), and habitation vulnerability ($V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D$). |
| **Phases 10–13**| **L10–L13: Site & Optimization** | Implement candidate site generation ($S$), carrying capacity bottleneck model, relocation priority tiers ($RP$), and OR-Tools CP-SAT integer optimization. |
| **Phases 14–17**| **L14–L17: API, UI & QA** | Implement update jobs (L14), FastAPI REST endpoints (L15), React + MapLibre 10-screen dashboard (L16), and end-to-end acceptance tests + Docker (L17). |

---

## 6. Division of Labor & Human Checkpoints (Section 19)

* **Architecture**: AI reviews consistency; Human approves frozen design.
* **Coding & Tests**: AI writes clean, typed Python/React code and tests; Human reviews diffs.
* **GIS & ML**: AI writes GeoPandas/Rasterio/PostGIS pipelines; Human visually verifies maps, CRS, and spatial sanity.
* **Optimization**: AI models constraints in OR-Tools; Human validates capacity and feasibility assumptions.

**Stop & Escalate**: If an AI agent encounters a blocking ambiguity, conflicting requirement, or test failure, it must pause and request human review rather than guessing or modifying frozen parameters.
