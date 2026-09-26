# System Architecture Specification

**Project**: SIH Problem Statement 26191 — Relocation Decision Support System (DSS)  
**Study Region**: Chamoli District, Uttarakhand  
**Document Version**: 1.0 (Frozen Architecture Specification)  
**Single Source of Truth**: [SIH_26191_Final_Blueprint_v1.0.pdf](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/SIH_26191_Final_Blueprint_v1.0.pdf)

---

## 1. Executive Summary & Philosophy

The prototype is a GIS-enabled decision-support system designed to assist regional authorities with proactive relocation planning in Chamoli District. It replaces ad-hoc hazard maps with an auditable, end-to-end multi-criteria pipeline.

### Core Architectural Principles
1. **Separation of Concerns**: Deterministic GIS safety rules, machine learning models, and mathematical optimization are strictly isolated into independent modules.
2. **Data Provenance & Explainability**: Every score, polygon, and recommendation carries metadata linking it back to source datasets, timestamps, and model/config versions.
3. **No Unsubstantiated Claims**: Red zones are modeled decision layers, carrying capacities are effective estimates based on limiting bottlenecks, and ML models are optional assistive predictors.
4. **Backend as Single Source of Truth**: All formulas and rankings execute on the backend; the frontend never recalculates authoritative metrics.

---

## 2. 17-Layer System Architecture

```
                               ┌────────────────────────────────┐
                               │       SOURCE DATASETS          │
                               │ (USDMA, Census, Bhuvan, NWIC)  │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ L01: Data Ingestion & Validation  ──> Adapters, schema checks, CRS validation, provenance    │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L02: PostGIS Spatial Database     ──> EPSG:32644, spatial indexing, relational constraints    │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L03: GIS Processing & Spatial Grid──> Canonical 30m grid, slope/aspect derivatives, clipping  │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                     HAZARD STACK                                             │
│ ┌─────────────────────────────┬─────────────────────────────┬──────────────────────────────┐ │
│ │ L04: Landslide Baseline     │ L05: Flood Baseline         │ L06: Rainfall Trigger Index  │ │
│ └─────────────────────────────┴─────────────────────────────┴──────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L07: Multi-Hazard Risk            ──> Normalized score H = 0.45L + 0.35F + 0.20R             │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L08: Red-Zone Engine              ──> Hard exclusions + H >= 0.70 threshold evaluation       │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L09: Exposure & Vulnerability     ──> V = 0.35P + 0.25S + 0.20A + 0.10I + 0.10D              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L10: Relocation-Site Suitability  ──> S = 0.30Hsafe + 0.15Slope + 0.15Road + 0.15Water + ...  │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L11: Carrying Capacity Engine     ──> Bottleneck: floor(min(land, water, ...) * safety_factor) │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L12: Relocation Priority Engine   ──> Priority score RP & Tiers (Immediate, Short, Med, Mon) │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L13: Allocation Optimization      ──> OR-Tools CP-SAT integer programming solver             │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L14: Update / Recompute Engine    ──> Triggered recomputation upon dataset updates           │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L15: FastAPI Integration Layer    ──> REST API endpoints serving GeoJSON and analytics       │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L16: Interactive UI & Dashboard   ──> React + MapLibre/Leaflet 10-screen interface           │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ L17: Testing, Deployment & Audit  ──> Unit/Spatial/Acceptance test suite + Docker            │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Models & Decision Formulas

### 3.1 Multi-Hazard Normalized Risk Score (L07)
Each hazard component is normalized to the $[0.0, 1.0]$ interval:
$$H = 0.45 \cdot L + 0.35 \cdot F + 0.20 \cdot R$$
* $L$: Landslide hazard / susceptibility class
* $F$: Flood / flash-flood exposure
* $R$: Rainfall trigger index

### 3.2 Red-Zone Decision Logic (L08)
A grid cell or zone is classified as **Red Zone** if:
$$\text{Is\_Red\_Zone} = (\text{Hard\_Exclusion} == \text{True}) \lor (H \ge 0.70)$$

**Hard Exclusion Rules**:
1. Very High Landslide Susceptibility class.
2. Active flood / flash flood inundation zones.
3. Active river channel buffer (e.g. 50 m buffer).
4. Extreme slope ($> 45^\circ$).
5. Protected / restricted reserve forest or ecological zones.
6. Existing infrastructure or permanent water body footprints.

**Risk Tiers**:
* **Red Zone**: Hard Exclusion OR $H \ge 0.70$
* **Amber / High-Risk**: $0.55 \le H < 0.70$
* **Lower-Risk**: $H < 0.55$

### 3.3 Habitation Exposure & Vulnerability (L09)
* **Exposed Population**: $\text{Exposed\_Pop}(h) = \text{Population}(h) \times \text{Affected\_Fraction}(h)$
* **Composite Vulnerability Score**:
$$V = 0.35 \cdot P + 0.25 \cdot S + 0.20 \cdot A + 0.10 \cdot I + 0.10 \cdot D$$
  * $P$: Population exposure share
  * $S$: Social vulnerability proxy (demographics from Census 2011)
  * $A$: Essential service access deficit (distance to health, drinking water, roads)
  * $I$: Critical infrastructure dependency
  * $D$: Historical disaster recurrence count

### 3.4 Relocation Site Suitability (L10)
Candidate sites are generated algorithmically by excluding Red Zones, water bodies, protected lands, and slopes $> 30^\circ$, requiring contiguous area $\ge 1.0\text{ ha}$:
$$S = 0.30 \cdot H_{safe} + 0.15 \cdot \text{Slope} + 0.15 \cdot \text{Road} + 0.15 \cdot \text{Water} + 0.10 \cdot \text{Health} + 0.05 \cdot \text{Education} + 0.05 \cdot \text{LandUse} + 0.05 \cdot \text{Services}$$
Where $H_{safe} = 1.0 - H$ after hard exclusions.

### 3.5 Modeled Effective Carrying Capacity (L11)
$$\text{Physical\_Capacity} = \min(\text{Cap}_{land}, \text{Cap}_{water}, \text{Cap}_{sanitation}, \text{Cap}_{health}, \text{Cap}_{access})$$
$$\text{Effective\_Capacity} = \lfloor \text{Physical\_Capacity} \times \text{Safety\_Factor} \rfloor$$
* Default prototype $\text{Safety\_Factor} = 0.80$.
* The limiting binding component is always surfaced to reviewers.

### 3.6 Relocation Priority & Tiers (L12)
$$RP = 0.40 \cdot \text{Risk} + 0.25 \cdot \text{Exposed\_Pop} + 0.20 \cdot V + 0.10 \cdot \text{Response\_Difficulty} + 0.05 \cdot \text{Recurrence}$$
* **Immediate**: $RP \ge 0.75$
* **Short-Term**: $0.55 \le RP < 0.75$
* **Medium-Term**: $0.35 \le RP < 0.55$
* **Monitor**: $RP < 0.35$

### 3.7 Relocation Allocation Optimization (L13)
* **Decision Variable**: $x[h, s] \ge 0$, integer number of persons relocated from habitation $h$ to candidate site $s$.
* **Objective Function**:
$$\min \sum_{h, s} \left( \text{Distance}(h,s) \cdot x[h,s] \right) + \text{Penalty}_{unmet} \sum_h \text{Unmet}(h) + \text{Penalty}_{hazard} \sum_{h, s} (H(s) \cdot x[h,s])$$
* **Subject to Constraints**:
  1. $\sum_s x[h, s] \le \text{Exposed\_Population}(h) \quad \forall h$
  2. $\sum_h x[h, s] \le \text{Effective\_Capacity}(s) \quad \forall s$
  3. $x[h, s] = 0 \quad \text{if site } s \text{ is infeasible for } h$
  4. Non-negativity and integer constraints: $x[h, s] \in \mathbb{Z}_{\ge 0}$

---

## 4. AI & ML Integration Strategy (Section 10)

1. **Deterministic Primary Pipeline**: Safety, red zones, capacity bottlenecks, and priority rankings are computed via explicit, deterministic mathematical rules.
2. **Optional ML Susceptibility Classifier**:
   * Evaluates probability of slope instability based on terrain slope, aspect, elevation, rainfall features, land cover, distance to faults/roads.
   * Algorithms: Random Forest baseline, XGBoost comparison, Logistic Regression baseline.
   * Spatial Cross-Validation: Spatial blocking to prevent spatial autocorrelation leakage.
   * Evaluation Metrics: ROC-AUC, PR-AUC, calibration curve, and threshold confusion matrix.
   * Safety Fallback: If inventory data is sparse or uncalibrated, deterministic baseline susceptibility remains authoritative.
3. **LLM Usage Policy**:
   * LLMs generate plain-language narrative explanations and summary reports from structured database outputs.
   * LLMs are strictly forbidden from modifying hazard scores, capacity limits, red zones, or optimization assignments.

---

## 5. API and Dashboard Architecture

### API Architecture (L15)
Built with FastAPI, exposing version-controlled REST endpoints:
* `/api/v1/admin-units`: GeoJSON administrative boundaries
* `/api/v1/habitations`: Habitation listing and filtering
* `/api/v1/habitations/{id}`: Detailed vulnerability breakdown and explanation JSON
* `/api/v1/hazards`: Metadata of active hazard layers
* `/api/v1/risk/map`: Vector tiles / GeoJSON of risk cells and red zones
* `/api/v1/sites`: Candidate relocation sites with suitability scores
* `/api/v1/sites/{id}/capacity`: Bottleneck breakdown and capacity
* `/api/v1/priorities`: Relocation priority rankings and tiers
* `/api/v1/optimize`: Execute allocation scenario with custom parameters
* `/api/v1/runs/{id}`: Provenance and run status
* `/api/v1/reports/{id}`: Decision report export

### Dashboard Interface (L16 - 10 Core Screens)
1. **Overview**: Study area summary, latest processing run, key metrics.
2. **Hazard Map**: Multi-layer GIS visualizer for landslide, flood, and rainfall.
3. **Red Zone Map**: Hard exclusions, risk overlays, clickable cell explanation drawer.
4. **Habitation Risk**: Searchable table & map of habitations, vulnerability scores, and priority tiers.
5. **Site Explorer**: Interactive candidate relocation sites with suitability breakdowns.
6. **Capacity Dashboard**: Visual site carrying capacity with highlighted binding bottlenecks.
7. **Relocation Planner**: Scenario sandbox to select habitations, sites, and constraints.
8. **Allocation Results**: Visual flow of relocated populations, travel distances, and site loads.
9. **Methodology Screen**: Transparent display of weights, thresholds, formulas, and data sources.
10. **Reports Export**: Automated PDF/Markdown export of relocation decision packages.
