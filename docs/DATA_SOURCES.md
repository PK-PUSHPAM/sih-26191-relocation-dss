# Data Sources & Acquisition Specification

**Project**: SIH Problem Statement 26191 — Relocation Decision Support System (DSS)  
**Study Region**: Chamoli District, Uttarakhand  
**Document Version**: 1.0  
**Blueprint Reference**: Section 3 (Data Strategy) & Section 24 (Verified Source Register)

---

## 1. Verified Public & Government Data Sources

All inputs for the Chamoli DSS are strictly grounded in verified government portals and open datasets. No synthetic or invented datasets are permitted.

| Domain | Preferred Source | Project Role | Required Ingestion Processing |
| :--- | :--- | :--- | :--- |
| **Administrative Boundaries** | Uttarakhand OGD / NWIC Admin Boundaries / LGD | District, block, tehsil, and village boundaries | Normalize names and codes; validate topology; reproject to `EPSG:32644` |
| **Population & Demographics** | Census India 2011 Chamoli PCA (DCHB Part B) | Population exposure and demographic vulnerability | Join on Census village codes; preserve Census baseline year (2011) |
| **Village Amenities & Services** | Census India 2011 Chamoli DCHB Part A | Proxies for water, healthcare, education, electricity, road access | Parse directory tables; convert categorical amenities into normalized numeric indicators |
| **Landslide Hazard / Inventory** | NRSC / Bhuvan Landslide Geoportal + GSI | Landslide susceptibility baseline, training labels, and validation | Reproject; deduplicate overlapping polygons; calculate centroid distance and density |
| **Terrain / Elevation (DEM)** | Survey of India (SOI) / Open DEM (CartoDEM / SRTM / Copernicus) | Elevation, slope, aspect, curvature, terrain constraints | Compute slope (degrees) and aspect; resample to canonical 30 m grid (`EPSG:32644`) |
| **Rainfall / Precipitation** | IMD Daily Rainfall via NWIC | Meteorological trigger index and temporal update features | Data quality checks; compute daily, 3-day rolling, and cumulative antecedent precipitation |
| **River Discharge & Hydrology** | CWC Telemetry via NWIC + Bhuvan Hydrology | Flash flood / inundation exposure and telemetry updates | Gauge station-to-river network mapping; peak discharge threshold tracking |
| **Land Use / Land Cover (LULC)** | Bhuvan Thematic Dashboard (LULC 1:50k) | Hard exclusions and candidate site suitability scoring | Reclassify into allowed, conditional, and strictly excluded classes |
| **Forest / Ecology Constraints** | Bhuvan Uttarakhand Forest Viewer | Hard safety masking for protected / reserve forest lands | Extract restricted reserve forest polygons for hard exclusion |
| **Roads & Critical Infrastructure** | Bhuvan + OpenStreetMap (OSM) / Geodata | Accessibility modeling, transport network, service proximity | Clean road network topology; calculate distance-to-road raster |
| **Historical Disasters** | USDMA Chamoli DDMP + NRSC 2013 Landslide Report | Historical recurrence score and empirical validation | Normalize event dates, coordinates, impact severity, and source references |
| **Candidate Relocation Sites** | Derived algorithmically via GIS pipeline | Identification of safe, buildable, accessible relocation parcels | Generate polygons after removing Red Zones, water bodies, protected lands, and slopes $>30^\circ$ |

---

## 2. Verified Source URLs & Provenance

1. **USDMA Chamoli District Disaster Management Plan**:  
   `https://usdma.uk.gov.in/document-category/district-disaster-management-plan/`
2. **Census India — Chamoli DCHB Part A (Village & Town Directory)**:  
   `https://censusindia.gov.in/nada/index.php/catalog/1306`
3. **Census India — Chamoli DCHB Part B (Primary Census Abstract)**:  
   `https://censusindia.gov.in/nada/index.php/catalog/1307/study-description`
4. **NWIC — IMD Daily Rainfall Dataset**:  
   `https://nwdp.nwic.gov.in/dataset/rainfall-daily-imd`
5. **NWIC — CWC Uttarakhand Hourly River Discharge Telemetry**:  
   `https://nwdp.nwic.gov.in/dataset/river-discharge-telemetry-hourly-central-water-commission-cwc`
6. **Bhuvan / NRSC Disaster Services**:  
   `https://bhuvan-app1.nrsc.gov.in/disaster/disaster.php`
7. **Bhuvan / NRSC Landslide Geoportal**:  
   `https://bhuvan-app1.nrsc.gov.in/disaster/usrtasks/landslide/landslide.php?uname=empty`
8. **Bhuvan / NRSC Uttarakhand 2013 Landslide Inventory Study**:  
   `https://bhuvan-app1.nrsc.gov.in/disaster/usrtasks/landslide/doc/Uttarkhand_Landslide_inventory_2013.pdf`
9. **Uttarakhand Open Government Data (OGD) — Admin Boundaries**:  
   `https://uttarakhand.data.gov.in/catalog/admin-boundaries`
10. **Bhuvan / NRSC Thematic Dashboard**:  
    `https://bhuvan-app1.nrsc.gov.in/thematic_dashboard/`
11. **Bhuvan Uttarakhand Forest Viewer**:  
    `https://bhuvan-app1.nrsc.gov.in/uk_forest/`

---

## 3. Data Freshness & Attribution Rules

1. **Census Baseline Rule**: Census 2011 is the baseline population dataset for the prototype. It must **never** be silently presented as current (2026) census data. When demographic data is shown in API responses or UI screens, the year `2011` must be clearly attached.
2. **Immutability of Raw Data**: Downloaded raw data files placed in `data/raw/` are write-once and immutable. Reprocessed or cleaned files must be placed in `data/staging/` or `data/curated/`.
3. **Dataset Manifest**: For every ingested dataset, the ingestion pipeline must record:
   - `source_id`: unique identifier matching `config/sources.yaml`
   - `access_date`: date of retrieval
   - `version`: source version or release date
   - `checksum`: SHA-256 hash of the raw ingested file
   - `license`: explicit usage/redistribution terms
4. **Missingness Handling**: Missing values in Census amenities or telemetry must never be silently converted to `0`. Missing data must be explicitly flagged and penalize the confidence score of the derived index.
