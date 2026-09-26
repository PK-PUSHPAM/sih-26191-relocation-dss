# Layer Specification: L03 — GIS Processing & Common Spatial Grid

**Layer ID**: `L03`  
**Layer Name**: GIS Processing & Common Spatial Grid  
**Status**: SPECIFICATION COMPLETE / FRAMEWORK IMPLEMENTATION (REAL DATA PENDING)  
**Blueprint Reference**: Section 2 (OD-01, OD-04), Section 4 (L03 Common Grid), Section 11 (Phase 3), Section 14 (Grid Resolution & CRS Decisions), Section 16 (Spatial & Grid Tests)  
**Parent Architecture**: [docs/ARCHITECTURE.md](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/docs/ARCHITECTURE.md)  
**Data Sources Manifest**: [config/sources.yaml](file:///c:/Users/pushp/OneDrive/Desktop/sih-26191-relocation-dss/config/sources.yaml)  

---

## A. Purpose and Scope

Layer L03 provides the unified geospatial foundation for the SIH 26191 Relocation Decision Support System.
Its primary objective is to eliminate spatial discrepancies, projection distortions, and resolution mismatches across disparate datasets before any hazard scoring, vulnerability assessment, or site allocation takes place.

Key responsibilities:
1. Establish the **canonical projected coordinate reference system** (`EPSG:32644` — WGS 84 / UTM Zone 44N) across all spatial vectors and rasters.
2. Formulate the **deterministic 30 m × 30 m canonical analysis grid** anchored to the study area extent.
3. Enforce **strict raster alignment contracts** (identical CRS, cell size, affine transform grid origin, dimensions, and nodata conventions).
4. Provide **explicit resampling policies** separating continuous terrain/surface variables from discrete/categorical thematic classifications.
5. Define the **terrain-processing pipeline** for digital elevation models (DEM) to compute slope (degrees) and aspect (degrees azimuth from North).
6. Implement **study-area clipping, masking, and boundary validation** preserving vector geometries.
7. Record end-to-end **geospatial processing provenance** linking output grids to raw data sources, transformations, and model runs.

---

## B. Inputs

L03 ingests validated vector and raster datasets promoted by Layer L01 (`data/curated/` or external verified sources):
1. **Administrative Boundaries** (`uttarakhand_ogd_admin` / Survey of India):
   - Polygon/MultiPolygon vector containing Chamoli district boundary and sub-district (tehsil/block/village) units.
2. **Digital Elevation Model (DEM)** (CartoDEM / Copernicus GLO-30 / SRTM 30m):
   - Single-band continuous raster representing topographic elevation above sea level (meters).
3. **Thematic Rasters** (e.g. Land Use / Land Cover 1:50k from Bhuvan/NRSC):
   - Categorical raster grids specifying land-use classifications and cover types.
4. **Vector Lifelines & Points** (`bhuvan_disaster_services`, Census 2011 locations, infrastructure points/lines).

*Data Status Note*: If authoritative production datasets are not yet present in local storage, L03 operates as a rigorous, verified processing framework using isolated synthetic fixtures for testing.

---

## C. Outputs

1. **Study Area Mask & Boundary**:
   - Curated, validated vector boundary and aligned 30 m binary boolean raster mask (`mask == 1` within Chamoli, `mask == 0` or nodata outside).
2. **Canonical 30 m Analysis Grid Definition**:
   - Deterministic affine transform `Affine(30.0, 0.0, x_min, 0.0, -30.0, y_max)`, grid width ($N_{cols}$), grid height ($N_{rows}$), and bounding envelope in `EPSG:32644`.
   - Grid cell geometry vector generation utility (mapping `cell_id` to bounding box `Polygon` in `EPSG:32644`).
3. **Aligned Base Rasters**:
   - Analysis rasters resampled, snapped, and clipped to the exact canonical grid extent.
4. **Primary Terrain Derivatives**:
   - `elevation.tif`: Aligned elevation raster in meters (`Float32`).
   - `slope.tif`: Aligned slope angle raster in degrees ($[0^\circ, 90^\circ]$) (`Float32`).
   - `aspect.tif`: Aligned aspect orientation raster in degrees azimuth ($[0^\circ, 360^\circ]$, with $-1$ or nodata for flat terrain) (`Float32`).
5. **Geospatial Processing Provenance Metadata**:
   - JSON manifest capturing input checksums, transformations, resampling algorithms, and spatial metrics.

---

## D. Study-Area Boundary Handling

1. **Source Geometry**: The study area boundary is derived strictly from authoritative administrative data (e.g. Survey of India / Uttarakhand OGD administrative boundaries).
2. **Boundary Validation**:
   - The boundary geometry must be valid according to OGC standards (`geom.is_valid == True`).
   - Self-intersecting rings, duplicate vertices, or bowtie polygons must be repaired (`shapely.validation.make_valid`) or rejected.
   - Multipart polygons are unified into a single validated `MultiPolygon`.
3. **Envelope Check**:
   - The geographic envelope must intersect the frozen Chamoli envelope sanity bounds:
     $\text{min\_lon} \ge 78.50^\circ\text{E}, \text{max\_lon} \le 80.50^\circ\text{E}, \text{min\_lat} \ge 29.50^\circ\text{N}, \text{max\_lat} \le 31.50^\circ\text{N}$.
4. **Strict Boundary Rule**: A bounding box must **never** be used as the actual study-area boundary. Bounding envelopes are used only as raster extents; spatial masks must use the exact vector boundary polygon.

---

## E. CRS Normalization

1. **Canonical Processing CRS**: `EPSG:32644` (WGS 84 / UTM Zone 44N) is non-negotiable for all distance, area, slope, and raster computations.
2. **Explicit Reprojection**:
   - No spatial operation may proceed on unprojected geographic coordinates (`EPSG:4326`) or non-UTM 44N projections.
   - Any input with missing CRS is immediately rejected with `MissingCRSError`.
   - Reprojection to `EPSG:32644` must be explicitly logged with source CRS, target CRS, and transformation method.

---

## F. Vector Processing Rules

1. Vector layers (points, linestrings, polygons) must be validated before processing.
2. Reprojection of vector features to `EPSG:32644` preserves topological validity.
3. Vector clipping to the study area boundary must use exact geometric intersection (`geopandas.clip`), discarding exterior features.
4. Attribute schemas are preserved during spatial processing; empty geometries resulting from spatial clipping are dropped.

---

## G. Raster Processing Rules

1. Every raster input must be inspected for:
   - CRS definition (must resolve to an authoritative EPSG).
   - Pixel dimensions ($dx, dy$) and transform.
   - Data type (`float32`, `int32`, `uint8`, etc.).
   - Explicit nodata value.
   - Spatial bounds.
2. Raster outputs must be written as standard Cloud-Optimized GeoTIFF (COG) or LZW-compressed GeoTIFF with explicit CRS `EPSG:32644` and defined nodata.

---

## H. DEM Requirements

1. **Target Grid**: 30 m horizontal resolution matching the canonical grid.
2. **Vertical Units**: Orthometric elevation in meters above sea level (`Float32`).
3. **Void / Nodata Treatment**: NoData pixels in the DEM (e.g., steep Himalayan shadow voids or glacier outliers) must not be silently replaced with 0 m (which represents sea level). Voids must remain explicitly marked with the nodata sentinel.
4. **Spatial Extent**: Must fully cover the Chamoli district boundary with a minimum 1000 m buffer to prevent edge-effect distortion during terrain derivative calculation.

---

## I. Terrain Derivative Requirements

1. **Slope Calculation**:
   - Calculated from the 30 m projected DEM using 3×3 finite-difference (Zevenbergen & Thorne or Horn’s method).
   - Horizontal distance $\Delta x, \Delta y = 30.0\text{ m}$.
   - Units: **Degrees** ($[0.0^\circ, 90.0^\circ]$).
   - Slopes exceeding $45^\circ$ represent the frozen hard-exclusion threshold for relocation safety (Section 2, OD-05).
2. **Aspect Calculation**:
   - Direction of maximum slope downward.
   - Units: **Degrees Azimuth** ($[0.0^\circ, 360.0^\circ]$ measured clockwise from True North: North = $0^\circ / 360^\circ$, East = $90^\circ$, South = $180^\circ$, West = $270^\circ$).
   - Flat terrain (slope $= 0^\circ$) is assigned $-1.0$ (or designated nodata).
3. **No Hazard Derivation**: L03 computes raw physical terrain slope and aspect. Converting slope into landslide susceptibility scores belongs strictly to Layer L04.

---

## J. Canonical 30 m Grid Definition

1. **Resolution**: Exactly $30.0\text{ m} \times 30.0\text{ m}$ per cell in `EPSG:32644`.
2. **Grid Origin & Snapping**:
   - The grid origin $(x_{min}, y_{max})$ is derived from the outer envelope of the study area, snapped outwards to the nearest integer multiple of 30 meters:
     $$x_{min}^{snapped} = \lfloor x_{min} / 30.0 \rfloor \times 30.0$$
     $$y_{max}^{snapped} = \lceil y_{max} / 30.0 \rceil \times 30.0$$
     $$x_{max}^{snapped} = \lceil x_{max} / 30.0 \rceil \times 30.0$$
     $$y_{min}^{snapped} = \lfloor y_{min} / 30.0 \rfloor \times 30.0$$
   - Affine transform: `Affine(30.0, 0.0, x_min_snapped, 0.0, -30.0, y_max_snapped)`.
3. **Dimensions**:
   - Width: $N_{cols} = \text{int}((x_{max}^{snapped} - x_{min}^{snapped}) / 30.0)$.
   - Height: $N_{rows} = \text{int}((y_{max}^{snapped} - y_{min}^{snapped}) / 30.0)$.

---

## K. Raster Alignment Verification

Two rasters are considered **strictly aligned** if and only if all the following conditions hold:
1. `crs.to_epsg() == 32644` (or exact CRS WKT match).
2. `abs(transform.a - 30.0) < 1e-6` and `abs(transform.e - (-30.0)) < 1e-6` (pixel size 30 m).
3. `abs(transform.b) < 1e-6` and `abs(transform.d) < 1e-6` (unrotated grid).
4. `abs(transform.c - target.transform.c) < 1e-6` (identical upper-left $X$ origin).
5. `abs(transform.f - target.transform.f) < 1e-6` (identical upper-left $Y$ origin).
6. `width == target.width` and `height == target.height`.

L03 provides an automated validator `validate_raster_alignment(raster_a, raster_b)` returning boolean status and diagnostic discrepancies.

---

## L. Resampling Policy

When resampling rasters to the canonical 30 m grid:
1. **Continuous Rasters (Elevation, Rainfall, Temperature, Distance Grids)**:
   - Must use **Bilinear** or **Cubic** interpolation.
   - Avoids step-like staircasing artifacts on smooth terrain surfaces.
2. **Categorical / Thematic Rasters (Land Cover, Soil Type, Admin Classes, Hazard Zones)**:
   - Must use **Nearest Neighbour** resampling.
   - **Prohibited**: Bilinear or cubic interpolation on categorical data (e.g. interpolating land-cover class 1 [Forest] and class 3 [Water] must never produce class 2 [Agriculture]).
3. Every resampling step must log the chosen algorithm in the provenance manifest.

---

## M. No-Data Handling

1. Nodata values are explicitly declared in the GeoTIFF header (e.g., `-9999.0` for `Float32`, `255` for `UInt8`).
2. Nodata pixels must never be converted to zero unless zero is explicitly defined in the data contract as valid data.
3. During raster arithmetic (e.g. slope, aspect, masks):
   - If any kernel input pixel is nodata, the derived pixel is assigned output nodata.
   - Masked pixels outside the Chamoli district boundary are assigned nodata.

---

## N. Clipping and Masking

1. **Bounding Box Crop**: Fast preliminary crop to the outer bounding box of the study area.
2. **Vector Polygon Mask**: Exact masking where pixels whose centers fall outside the district polygon boundary are assigned the nodata value.
3. All intermediate and curated rasters are clipped and masked consistently.

---

## O. Resolution Handling

Native data resolutions vary widely:
- Land Cover: 10 m to 30 m.
- Elevation: 30 m (CartoDEM / Copernicus).
- Daily Rainfall: 0.25° (~25 km gridded IMD).
- Flood hazard extents: 10 m to 30 m.

All datasets must be explicitly resampled and aligned to the canonical 30 m grid before downstream multi-hazard combination.

---

## P. Spatial Extent Validation

1. Any incoming layer must spatially intersect the Chamoli district boundary.
2. If an input layer has zero spatial overlap with Chamoli, ingestion/processing must fail with `ExtentMismatchError`.
3. If coverage is partial, a warning is raised and coverage percentage is recorded in provenance.

---

## Q. Cell and Grid Indexing

1. Each canonical 30 m cell is assigned a deterministic 64-bit integer identifier:
   $$\text{cell\_id} = \text{row} \times N_{cols} + \text{col}$$
   where $\text{row} \in [0, N_{rows}-1]$ and $\text{col} \in [0, N_{cols}-1]$.
2. Geographic center coordinates of cell $(\text{row}, \text{col})$:
   $$x_{center} = x_{min}^{snapped} + (\text{col} + 0.5) \times 30.0$$
   $$y_{center} = y_{max}^{snapped} - (\text{row} + 0.5) \times 30.0$$
3. This 1-to-1 mapping guarantees lossless roundtrip conversion between raster matrix indices and PostGIS `risk_cell.cell_id`.

---

## R. Processing Provenance

Every GIS transformation in L03 produces an audit record:
- `operation`: e.g., `REPROJECT`, `RESAMPLE`, `ALIGN_GRID`, `CLIP_MASK`, `CALCULATE_SLOPE`.
- `input_source_id`: Source identifier from `config/sources.yaml`.
- `input_checksum`: SHA-256 hash of source file.
- `parameters`: Method (e.g., `bilinear`), target resolution (30.0), target CRS (`EPSG:32644`).
- `output_path`: Relative path of generated GeoTIFF or GeoPackage.
- `timestamp`: UTC ISO timestamp.

---

## S. Reproducibility

Given identical raw inputs, parameter configurations, and software versions, L03 must generate bit-for-bit identical raster matrices, transforms, and cell IDs across platforms.

---

## T. Validation Rules

1. Vector geometries must be non-empty and topologically valid.
2. Raster bands must have finite numeric values inside the study area.
3. Slope output values must be bounded within $[0^\circ, 90^\circ]$.
4. Aspect output values must be bounded within $[0^\circ, 360^\circ] \cup \{-1.0\}$.
5. Grid transform must match canonical parameters to within $10^{-5}$ tolerance.

---

## U. Failure Behavior

1. **Missing CRS**: Immediate exception (`MissingCRSError`). Never guess or assume EPSG.
2. **Invalid Geometry**: If geometry cannot be healed with `make_valid`, fail with `InvalidGeometryError`.
3. **Unaligned Raster in Analysis**: If an operation receives unaligned rasters without explicit resampling, fail with `RasterAlignmentError`.
4. **No-Data Dominance**: If a processed layer has $>95\%$ nodata inside the study area, raise `DataDegradationWarning` and flag in provenance.

---

## V. Testing Requirements

The L03 test suite must verify:
1. Reprojection of vector features from `EPSG:4326` to `EPSG:32644`.
2. Rejection of layers with missing CRS.
3. Canonical 30 m grid origin snapping and transform calculation.
4. Deterministic cell ID computation and inverse coordinate mapping.
5. Detection of aligned vs misaligned rasters.
6. Nearest-neighbour vs bilinear resampling policies.
7. Slope and aspect mathematical correctness on synthetic planar/tilted DEM fixtures.
8. Vector clipping and raster masking behavior.
9. Nodata preservation and propagation.
10. Provenance record generation for GIS operations.

---

## W. Explicit Non-Goals (Reserved for L04+)

1. **No Hazard Scoring**: No landslide susceptibility modeling (L04), flood zone calculation (L05), or rainfall triggering (L06).
2. **No Multi-Hazard Combination**: No computation of $H = 0.45L + 0.35F + 0.20R$ (L07).
3. **No Red Zone Classification**: No red zone decision flag assignment (L08).
4. **No Vulnerability Assessment**: No social, economic, or infrastructure vulnerability scoring (L09).
5. **No Optimization or Allocation**: No site suitability (L10), carrying capacity (L11), or solver execution (L13).
6. **No Real Data Fabrication**: No synthetic DEMs or guessed boundaries represented as real Chamoli production data.
