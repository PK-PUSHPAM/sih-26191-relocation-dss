# Layer Specification: L03 — GIS Processing & Common Spatial Grid

**Layer ID**: `L03`  
**Layer Name**: GIS Processing & Common Spatial Grid  
**Status**: **FRAMEWORK HARDENED — REAL DEM/STUDY-AREA DATA PENDING**  
**Blueprint Reference**: Section 2 (OD-01, OD-04), Section 4 (L03 Common Grid), Section 11 (Phase 3), Section 14 (Grid Resolution & CRS Decisions), Section 16 (Spatial & Grid Tests)  
**Parent Architecture**: [docs/ARCHITECTURE.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/ARCHITECTURE.md)

---

## A. Implementation Status

The L03 processing framework is implemented for deterministic 30 m GIS processing in EPSG:32644.

Implemented and hardened:
- canonical 30 m grid construction and cell indexing
- vector CRS validation/reprojection
- study-area geometry validation and clipping
- strict raster alignment checks
- explicit continuous vs categorical resampling
- raster masking
- Horn 3x3 slope calculation
- cardinal-direction-correct aspect calculation
- NoData propagation
- raster CRS and NoData rejection when metadata is missing
- GeoTIFF terrain derivative output
- provenance test coverage

### Real-data boundary

The verified Chamoli village polygons now exist in PostGIS, but they are **not substituted for the authoritative Chamoli district boundary**. Likewise, no DEM is invented or treated as production data.

Therefore L03 does **not** generate a fake district grid, elevation raster, slope raster, or aspect raster until an authoritative DEM and authoritative study-area boundary are available.

---

## B. Canonical Processing Contract

- CRS: **EPSG:32644**
- Resolution: **30 m × 30 m**
- Grid origin: outward-snapped study-area envelope
- Cell ID: `row * N_cols + col`
- Continuous resampling: **bilinear**
- Categorical resampling: **nearest neighbour**
- Raster output compression: **LZW**
- Missing CRS: **hard failure**
- Missing raster NoData: **hard failure**
- NoData in any terrain 3×3 kernel: output NoData
- Flat terrain aspect: **-1.0**

---

## C. Terrain Aspect Convention

Aspect is calculated from the downslope vector:

```
East component  = -dz/dx
North component = -dz/dy
Azimuth         = atan2(East, North)
```

Therefore:
- North = 0°
- East = 90°
- South = 180°
- West = 270°

This is a directional convention only; L03 does not convert aspect into hazard susceptibility.

---

## D. Verification Contract

L03 tests cover:
1. Vector reprojection and missing vector CRS.
2. Study-area validation and clipping.
3. Canonical grid snapping and cell-ID roundtrip.
4. Raster metadata and alignment.
5. Continuous/categorical resampling policies.
6. Slope and aspect mathematical correctness.
7. Cardinal aspect directions.
8. NoData propagation.
9. Raster masking.
10. Provenance generation.
11. Missing raster CRS rejection.
12. Missing raster NoData rejection.
13. Terrain input shape and cell-size validation.

---

## E. Explicit Non-Goals

1. No landslide susceptibility scoring.
2. No flood hazard calculation.
3. No rainfall trigger index.
4. No multi-hazard combination.
5. No red-zone classification.
6. No vulnerability or relocation suitability scoring.
7. No synthetic production DEM.
8. No invented Chamoli district boundary.
