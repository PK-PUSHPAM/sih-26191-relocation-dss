# Project Context — SIH 26191 Relocation DSS

**Permanent Project Identity & Architecture Baseline**  
**Version**: 1.0 (Frozen Architecture Specification)  
**Single Source of Truth**: [docs/SIH_26191_Final_Blueprint_v1.0.pdf](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/SIH_26191_Final_Blueprint_v1.0.pdf)

---

## 1. Project Identity & Problem Statement
* **Event / ID**: Smart India Hackathon 2026 — Problem Statement 26191
* **Title**: Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations
* **Purpose**: A GIS-enabled decision-support system (DSS) for proactive, evidence-based relocation planning in high-risk mountainous habitations.
* **Prototype Geography**: Chamoli District, Uttarakhand, India (OD-01).
* **Core Hazards**: Landslide + Flood / Flash Flood + Extreme/Heavy Rainfall trigger (OD-02).

---

## 2. Frozen Open Decisions (OD-01 to OD-12)

| ID | Parameter | Frozen Choice | Implementation Summary |
| :--- | :--- | :--- | :--- |
| **OD-01** | Geography | Chamoli District, Uttarakhand | Study area bounding box $\approx [79.03^\circ\text{E}, 80.10^\circ\text{E}], [29.98^\circ\text{N}, 31.07^\circ\text{N}]$ |
| **OD-02** | Initial Hazards | Landslide + Flood + Rainfall | Primary multi-hazard baseline inputs |
| **OD-03** | Data Policy | Authoritative government first | Sourced exclusively from USDMA, Census 2011, Bhuvan/NRSC, NWIC |
| **OD-04** | Spatial Grid | Canonical 30 m (`EPSG:32644`) | Projected UTM Zone 44N; native source resolutions preserved |
| **OD-05** | Red Zone Rule | Hard exclusions OR $H \ge 0.70$ | Decision support layer, not a legal gazette notification |
| **OD-06** | Vulnerability | 35% P, 25% S, 20% A, 10% I, 10% D | Exposed population, social proxies, service deficit, infra, history |
| **OD-07** | Site Suitability | 30% $H_{safe}$, 15% Slope, 15% Road, 15% Water, 10% Health, 5% Edu, 5% LU, 5% Serv | Hard exclusions applied before scoring; normalized to $[0, 1]$ |
| **OD-08** | Carrying Capacity | Bottleneck effective capacity | $\lfloor \min(\text{land}, \text{water}, \text{sanitation}, \text{health}, \text{access}) \times 0.80 \rfloor$ |
| **OD-09** | Priority Tiers | 40% Risk, 25% Pop, 20% Vuln, 10% Resp, 5% Rec | Tiers: Immediate ($\ge 0.75$), Short ($0.55\text{--}0.75$), Med ($0.35\text{--}0.55$), Monitor ($< 0.35$) |
| **OD-10** | ML Role | Optional / assistive only | Supervised landslide susceptibility if data permits; deterministic baseline is authoritative |
| **OD-11** | Optimization | Constrained Linear / Integer | OR-Tools CP-SAT solver minimizing weighted distance and unmet demand |
| **OD-12** | Tech Stack | Python + FastAPI + PostGIS + React | GeoPandas, Rasterio, OR-Tools, MapLibre/Leaflet, Docker |

---

## 3. Core Decision Formulas

1. **Multi-Hazard Risk Score ($H$)**:
   $$H = 0.45 \cdot L + 0.35 \cdot F + 0.20 \cdot R \quad (L, F, R \in [0.0, 1.0])$$
2. **Red Zone Decision**:
   $$\text{Red\_Zone} = (\text{Hard\_Exclusions} == \text{True}) \lor (H \ge 0.70)$$
   *Hard Exclusions*: Very high landslide, flood zone, active river channel buffer, slope $>45^\circ$, reserve forest/restricted land, water bodies.
3. **Habitation Vulnerability Score ($V$)**:
   $$V = 0.35 \cdot P + 0.25 \cdot S + 0.20 \cdot A + 0.10 \cdot I + 0.10 \cdot D$$
4. **Relocation Site Suitability ($S$)**:
   $$S = 0.30 \cdot H_{safe} + 0.15 \cdot \text{Slope} + 0.15 \cdot \text{Road} + 0.15 \cdot \text{Water} + 0.10 \cdot \text{Health} + 0.05 \cdot \text{Education} + 0.05 \cdot \text{LandUse} + 0.05 \cdot \text{Services}$$
5. **Modeled Effective Carrying Capacity**:
   $$\text{Physical\_Capacity} = \min(\text{Cap}_{land}, \text{Cap}_{water}, \text{Cap}_{sanitation}, \text{Cap}_{health}, \text{Cap}_{access})$$
   $$\text{Effective\_Capacity} = \lfloor \text{Physical\_Capacity} \times 0.80 \rfloor$$
6. **Relocation Priority Score ($RP$) & Tiers**:
   $$RP = 0.40 \cdot \text{Risk} + 0.25 \cdot \text{Exposed\_Pop} + 0.20 \cdot V + 0.10 \cdot \text{Response\_Difficulty} + 0.05 \cdot \text{Recurrence}$$
   * **Immediate**: $RP \ge 0.75$ | **Short-term**: $0.55 \le RP < 0.75$ | **Medium-term**: $0.35 \le RP < 0.55$ | **Monitor**: $RP < 0.35$
7. **Optimization Objective**:
   $$\min \sum_{h, s} \left( \text{Distance}(h,s) \cdot x[h,s] \right) + \text{Penalties}(\text{unmet, hazard, capacity})$$

---

## 4. 17-Layer System Flow

```
L01: Data Ingestion & Validation
  │
L02: PostGIS Spatial Database (EPSG:32644)
  │
L03: GIS Common Spatial Grid (30 m)
  │
L04–L06: Hazard Stack (Landslide, Flood, Rainfall)
  │
L07: Multi-Hazard Risk (H = 0.45L + 0.35F + 0.20R)
  │
L08: Red-Zone Engine (Hard exclusions + H >= 0.70)
  │
L09: Exposure & Vulnerability Engine (V score)
  │
L10: Relocation Site Suitability Engine (S score)
  │
L11: Carrying Capacity Engine (Bottleneck effective capacity)
  │
L12: Relocation Priority Engine (RP score & Tiers)
  │
L13: Allocation Optimization Engine (OR-Tools CP-SAT)
  │
L14: Update / Recompute Engine
  │
L15: FastAPI Integration Layer (/api/v1/...)
  │
L16: Dashboard & Reports (10 screens)
  │
L17: Testing, Deployment & Audit
```

---

## 5. Non-Negotiable System & Engineering Boundaries

* **No Legal Claims**: The prototype produces modeled decision-support layers for planning review, not legal notifications or certified structural capacities.
* **CRS Authority**: `EPSG:32644` is the sole processing CRS. `EPSG:4326` is used strictly for API interchange / frontend maps.
* **Data Provenance**: Raw data in `data/raw/` is immutable. Every score carries data source, timestamps, and `model_version`/`config_version`.
* **Backend as Single Source of Truth**: The frontend never calculates authoritative scores or metrics.
