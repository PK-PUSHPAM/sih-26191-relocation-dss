"""
Unit Tests for Layer L03 — GIS Processing & Common Spatial Grid.
Validates CRS handling, study-area geometry, vector clipping, canonical 30m grid generation,
raster alignment, continuous/categorical resampling, DEM slope/aspect calculation, nodata propagation,
and provenance tracking using isolated synthetic test fixtures.

NOTE: All test fixtures generated in this suite are STRICTLY SYNTHETIC TEST FIXTURES.
They do NOT represent real Chamoli terrain, official boundaries, or government data.
"""
from pathlib import Path
import math
import numpy as np
import pytest
import geopandas as gpd
import rasterio
from rasterio.transform import Affine
from shapely.geometry import Polygon, Point, box

from src.common.crs import (
    CANONICAL_PROJECTED_CRS_EPSG,
    CANONICAL_PROJECTED_CRS_STR,
    INTERCHANGE_CRS_STR,
)
from src.spatial.grid import (
    CanonicalGridDefinition,
    CANONICAL_RESOLUTION_METERS,
    DEFAULT_NODATA_FLOAT,
    create_canonical_grid,
    generate_grid_cells_gdf,
    snap_coordinate_outward,
)
from src.spatial.vector import (
    MissingCRSError,
    InvalidGeometryError,
    ExtentMismatchError,
    validate_and_reproject_vector,
    validate_study_area_geometry,
    load_and_prepare_study_area,
    clip_vector_to_study_area,
)
from src.spatial.raster import (
    inspect_raster_metadata,
    validate_raster_alignment,
    is_aligned_to_canonical_grid,
    resample_and_align_raster,
    mask_raster_with_vector,
)
from src.spatial.terrain import (
    calculate_slope_and_aspect_arrays,
    generate_terrain_derivatives_raster,
)
from src.common.provenance import ProvenanceRecord


# ==============================================================================
# Helpers to generate SYNTHETIC GeoTIFF fixtures for unit tests
# ==============================================================================

def write_synthetic_raster(
    file_path: Path,
    data: np.ndarray,
    transform: Affine,
    crs: str = CANONICAL_PROJECTED_CRS_STR,
    nodata: float = DEFAULT_NODATA_FLOAT,
    dtype: str = "float32",
) -> Path:
    """Helper to write a small synthetic GeoTIFF fixture for unit testing."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    height, width = data.shape
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
    }
    with rasterio.open(file_path, "w", **profile) as dst:
        dst.write(data.astype(dtype), 1)
    return file_path


# ==============================================================================
# 1. CRS Transformation & Missing CRS Handling Tests
# ==============================================================================

def test_vector_reprojection_success():
    """Verify vector reprojection from EPSG:4326 to EPSG:32644."""
    # Chamoli sample centroid point in WGS84
    pt = Point(79.35, 30.40)
    gdf_4326 = gpd.GeoDataFrame([{"name": "test_village", "geometry": pt}], crs=INTERCHANGE_CRS_STR)

    reprojected = validate_and_reproject_vector(gdf_4326, target_crs=CANONICAL_PROJECTED_CRS_STR)
    assert reprojected.crs.to_epsg() == CANONICAL_PROJECTED_CRS_EPSG
    # In UTM Zone 44N, X for Chamoli (~79.35°E) is ~341,000 m, Y is ~3,364,000 m
    geom = reprojected.geometry.iloc[0]
    assert 200000 < geom.x < 500000
    assert 3000000 < geom.y < 3600000


def test_vector_missing_crs_raises_error():
    """Verify that vector datasets missing a CRS raise MissingCRSError."""
    pt = Point(79.35, 30.40)
    gdf_no_crs = gpd.GeoDataFrame([{"name": "test", "geometry": pt}], crs=None)

    with pytest.raises(MissingCRSError, match="Vector GeoDataFrame has no defined CRS"):
        validate_and_reproject_vector(gdf_no_crs)


# ==============================================================================
# 2. Study-Area Geometry Validation & Clipping Tests
# ==============================================================================

def test_study_area_geometry_validation():
    """Verify study-area polygon validation and sanity envelope checking."""
    # Synthetic polygon well inside Chamoli bounds
    poly_valid = Polygon([(79.2, 30.1), (79.8, 30.1), (79.8, 30.8), (79.2, 30.8), (79.2, 30.1)])
    is_valid, cleaned, err = validate_study_area_geometry(poly_valid)
    assert is_valid is True
    assert err is None

    # Empty geometry
    is_valid, _, err = validate_study_area_geometry(Polygon())
    assert is_valid is False
    assert "empty" in err.lower()

    # Geometry outside Chamoli sanity envelope (e.g. South India)
    poly_far = Polygon([(77.0, 12.0), (77.5, 12.0), (77.5, 12.5), (77.0, 12.5), (77.0, 12.0)])
    is_valid, _, err = validate_study_area_geometry(poly_far)
    assert is_valid is False
    assert "does not intersect" in err.lower()


def test_study_area_preparation_and_dissolve():
    """Verify load_and_prepare_study_area unions multipart polygons and sets EPSG:32644."""
    p1 = Polygon([(79.2, 30.1), (79.5, 30.1), (79.5, 30.5), (79.2, 30.5), (79.2, 30.1)])
    p2 = Polygon([(79.5, 30.1), (79.8, 30.1), (79.8, 30.5), (79.5, 30.5), (79.5, 30.1)])
    gdf_parts = gpd.GeoDataFrame([{"id": 1, "geometry": p1}, {"id": 2, "geometry": p2}], crs=INTERCHANGE_CRS_STR)

    study_area = load_and_prepare_study_area(gdf_parts)
    assert len(study_area) == 1
    assert study_area.crs.to_epsg() == CANONICAL_PROJECTED_CRS_EPSG
    assert study_area.geometry.iloc[0].is_valid


def test_clip_vector_to_study_area():
    """Verify clipping points to study area boundary drops points outside."""
    boundary = Polygon([(700000, 3350000), (750000, 3350000), (750000, 3400000), (700000, 3400000)])
    study_gdf = gpd.GeoDataFrame([{"geometry": boundary}], crs=CANONICAL_PROJECTED_CRS_STR)

    pts = [
        Point(720000, 3360000),  # Inside
        Point(740000, 3380000),  # Inside
        Point(650000, 3300000),  # Outside
    ]
    pts_gdf = gpd.GeoDataFrame([{"id": i, "geometry": p} for i, p in enumerate(pts)], crs=CANONICAL_PROJECTED_CRS_STR)

    clipped = clip_vector_to_study_area(pts_gdf, study_gdf)
    assert len(clipped) == 2
    assert set(clipped["id"]) == {0, 1}


# ==============================================================================
# 3. Canonical 30 m Grid Definition & Indexing Tests
# ==============================================================================

def test_canonical_grid_snapping_and_transform():
    """Verify 30m grid snapping and affine transform construction."""
    # Raw bounds: minx=700012.3, miny=3350007.8, maxx=700145.2, maxy=3350221.1
    raw_bounds = (700012.3, 3350007.8, 700145.2, 3350221.1)
    grid = create_canonical_grid(raw_bounds, resolution=30.0)

    # Snapping floor for min, ceil for max:
    assert grid.x_min == 699990.0  # floor(700012.3/30)*30 = 699990.0
    assert grid.y_min == 3349980.0  # floor(3350007.8/30)*30 = 3349980.0
    assert grid.x_max == 700170.0  # ceil(700145.2/30)*30 = 700170.0
    assert grid.y_max == 3350250.0  # ceil(3350221.1/30)*30 = 3350250.0

    assert grid.width == int((700170.0 - 699990.0) / 30.0)  # 6 columns
    assert grid.height == int((3350250.0 - 3349980.0) / 30.0)  # 9 rows
    assert grid.total_cells == 54

    # Transform: resolution 30, top-left origin
    assert grid.transform.a == 30.0
    assert grid.transform.e == -30.0
    assert grid.transform.c == grid.x_min
    assert grid.transform.f == grid.y_max


def test_canonical_grid_cell_id_indexing_roundtrip():
    """Verify deterministic 1-to-1 bijection between (row, col) and cell_id."""
    raw_bounds = (699990.0, 3349980.0, 700290.0, 3350280.0)
    grid = create_canonical_grid(raw_bounds, resolution=30.0)  # 10x10 = 100 cells

    for r in range(grid.height):
        for c in range(grid.width):
            cell_id = grid.cell_id_from_row_col(r, c)
            inv_r, inv_c = grid.row_col_from_cell_id(cell_id)
            assert (inv_r, inv_c) == (r, c)

    # Out of range checks
    with pytest.raises(IndexError):
        grid.cell_id_from_row_col(grid.height, 0)
    with pytest.raises(IndexError):
        grid.row_col_from_cell_id(grid.total_cells)


def test_generate_grid_cells_gdf():
    """Verify GeoDataFrame generation of cell bounding polygons."""
    raw_bounds = (699990.0, 3349980.0, 700080.0, 3350040.0)
    grid = create_canonical_grid(raw_bounds, resolution=30.0)  # 3 cols x 2 rows = 6 cells

    gdf = generate_grid_cells_gdf(grid)
    assert len(gdf) == 6
    assert list(gdf.columns) == ["cell_id", "row", "col", "geometry"]
    assert gdf.crs.to_epsg() == CANONICAL_PROJECTED_CRS_EPSG
    # Cell 0 polygon area should be exactly 30 * 30 = 900 m2
    assert math.isclose(gdf.geometry.iloc[0].area, 900.0, rel_tol=1e-5)


# ==============================================================================
# 4. Raster Metadata & Alignment Detection Tests
# ==============================================================================

def test_raster_metadata_inspection(tmp_path):
    """Verify inspect_raster_metadata correctly extracts properties."""
    arr = np.zeros((10, 10), dtype=np.float32)
    t = Affine(30.0, 0.0, 700000.0, 0.0, -30.0, 3350300.0)
    r_path = write_synthetic_raster(tmp_path / "test.tif", arr, t)

    meta = inspect_raster_metadata(r_path)
    assert meta["width"] == 10
    assert meta["height"] == 10
    assert meta["resolution"] == (30.0, 30.0)
    assert meta["nodata"] == DEFAULT_NODATA_FLOAT
    assert CANONICAL_PROJECTED_CRS_STR in meta["crs"] or "32644" in meta["crs"]


def test_two_rasters_aligned_detection(tmp_path):
    """Verify validate_raster_alignment correctly identifies matching grids."""
    arr1 = np.ones((10, 10), dtype=np.float32)
    arr2 = np.full((10, 10), 2.0, dtype=np.float32)
    t = Affine(30.0, 0.0, 700000.0, 0.0, -30.0, 3350300.0)

    p1 = write_synthetic_raster(tmp_path / "r1.tif", arr1, t)
    p2 = write_synthetic_raster(tmp_path / "r2.tif", arr2, t)

    is_aligned, issues = validate_raster_alignment(p1, p2)
    assert is_aligned is True
    assert len(issues) == 0


def test_two_rasters_misaligned_detection(tmp_path):
    """Verify validate_raster_alignment detects shift, dimension, and resolution mismatches."""
    arr1 = np.ones((10, 10), dtype=np.float32)
    t1 = Affine(30.0, 0.0, 700000.0, 0.0, -30.0, 3350300.0)
    p1 = write_synthetic_raster(tmp_path / "r1.tif", arr1, t1)

    # Shifted origin
    t2 = Affine(30.0, 0.0, 700015.0, 0.0, -30.0, 3350300.0)
    p2 = write_synthetic_raster(tmp_path / "r2_shifted.tif", arr1, t2)

    is_aligned, issues = validate_raster_alignment(p1, p2)
    assert is_aligned is False
    assert any("Origin" in issue for issue in issues)

    # Dimension mismatch
    arr3 = np.ones((15, 10), dtype=np.float32)
    p3 = write_synthetic_raster(tmp_path / "r3_diff_dim.tif", arr3, t1)
    is_aligned, issues = validate_raster_alignment(p1, p3)
    assert is_aligned is False
    assert any("Dimension" in issue for issue in issues)


def test_is_aligned_to_canonical_grid(tmp_path):
    """Verify check against CanonicalGridDefinition."""
    grid = create_canonical_grid((700000.0, 3350000.0, 700300.0, 3350300.0), resolution=30.0)
    arr = np.ones((grid.height, grid.width), dtype=np.float32)
    p = write_synthetic_raster(tmp_path / "canonical.tif", arr, grid.transform)

    is_aligned, issues = is_aligned_to_canonical_grid(p, grid)
    assert is_aligned is True
    assert len(issues) == 0


# ==============================================================================
# 5. Resampling Policy: Categorical vs Continuous Tests
# ==============================================================================

def test_continuous_resampling_bilinear(tmp_path):
    """Verify continuous variables (e.g. elevation, rain) use bilinear interpolation."""
    # Create coarse 60m raster
    t_coarse = Affine(60.0, 0.0, 699960.0, 0.0, -60.0, 3350640.0)
    data_coarse = np.array([
        [100.0, 200.0],
        [300.0, 400.0]
    ], dtype=np.float32)
    coarse_p = write_synthetic_raster(tmp_path / "coarse_dem.tif", data_coarse, t_coarse)

    # Target 30m canonical grid (4x4 cells over same 120m x 120m area)
    grid = create_canonical_grid((699960.0, 3350520.0, 700080.0, 3350640.0), resolution=30.0)
    out_p = tmp_path / "aligned_dem.tif"

    resample_and_align_raster(coarse_p, out_p, grid, is_categorical=False)

    with rasterio.open(out_p) as src:
        aligned_data = src.read(1)
        assert aligned_data.shape == (grid.height, grid.width)
        valid_data = aligned_data[aligned_data != DEFAULT_NODATA_FLOAT]
        assert 100.0 <= valid_data.min() <= valid_data.max() <= 400.0
        # Check an interior interpolated value
        assert not np.all(np.isin(valid_data, [100.0, 200.0, 300.0, 400.0]))


def test_categorical_resampling_nearest(tmp_path):
    """Verify categorical variables (e.g. Land Cover classes) strictly use nearest neighbour."""
    # Land-cover classes: 1 (Forest), 3 (Water)
    t_coarse = Affine(60.0, 0.0, 699960.0, 0.0, -60.0, 3350640.0)
    data_cat = np.array([
        [1, 3],
        [3, 1]
    ], dtype=np.uint8)
    cat_p = write_synthetic_raster(tmp_path / "land_cover_coarse.tif", data_cat, t_coarse, dtype="uint8", nodata=255)

    grid = create_canonical_grid((699960.0, 3350520.0, 700080.0, 3350640.0), resolution=30.0)
    out_p = tmp_path / "land_cover_aligned.tif"

    resample_and_align_raster(cat_p, out_p, grid, is_categorical=True, output_nodata=255)

    with rasterio.open(out_p) as src:
        aligned_data = src.read(1)
        # All resampled pixels MUST strictly be either 1 or 3 (no class 2 created by averaging!)
        valid_cat = aligned_data[aligned_data != 255]
        unique_vals = set(np.unique(valid_cat))
        assert unique_vals.issubset({1, 3})


# ==============================================================================
# 6. DEM Slope, Aspect, and Nodata Propagation Tests
# ==============================================================================

def test_dem_slope_horizontal_plane():
    """Verify slope on a flat horizontal plane is exactly 0.0 degrees and aspect is -1.0."""
    # 5x5 flat DEM of elevation 2000 m
    flat_dem = np.full((5, 5), 2000.0, dtype=np.float32)
    slope, aspect = calculate_slope_and_aspect_arrays(flat_dem, dx=30.0, dy=30.0)

    # Interior cells (1:4, 1:4) should be 0 slope and -1 aspect
    interior_slope = slope[1:-1, 1:-1]
    interior_aspect = aspect[1:-1, 1:-1]
    assert np.allclose(interior_slope, 0.0, atol=1e-5)
    assert np.allclose(interior_aspect, -1.0, atol=1e-5)


def test_dem_slope_and_aspect_tilted_plane():
    """
    Verify slope and aspect on an inclined plane dipping toward East.
    Plane: elevation = 2000.0 - 0.5 * x (dz/dx = -0.5, dz/dy = 0.0)
    Expected slope: arctan(0.5) in degrees ≈ 26.565°
    Expected aspect: dipping East (downhill is +x / East) = 90.0°
    """
    # 5x5 grid with cols x = 0, 30, 60, 90, 120
    # Elevation drops 15m every 30m cell: dz/dx = -15/30 = -0.5
    rows, cols = 5, 5
    dem = np.zeros((rows, cols), dtype=np.float32)
    for c in range(cols):
        dem[:, c] = 2000.0 - c * 15.0

    slope, aspect = calculate_slope_and_aspect_arrays(dem, dx=30.0, dy=30.0)

    expected_slope = np.degrees(np.arctan(0.5))  # ~26.565°
    interior_slope = slope[1:-1, 1:-1]
    interior_aspect = aspect[1:-1, 1:-1]

    assert np.allclose(interior_slope, expected_slope, atol=1e-3)
    assert np.allclose(interior_aspect, 90.0, atol=1e-3)


def test_dem_nodata_propagation():
    """Verify that a NoData pixel in a 3x3 window causes the output slope/aspect to be NoData."""
    dem = np.full((5, 5), 2000.0, dtype=np.float32)
    # Inject a nodata void at cell (2, 2)
    dem[2, 2] = DEFAULT_NODATA_FLOAT

    slope, aspect = calculate_slope_and_aspect_arrays(dem, dx=30.0, dy=30.0, nodata=DEFAULT_NODATA_FLOAT)

    # Center cell (2, 2) and all its 8 immediate neighbors must be NoData in output
    for r in range(1, 4):
        for c in range(1, 4):
            assert slope[r, c] == DEFAULT_NODATA_FLOAT
            assert aspect[r, c] == DEFAULT_NODATA_FLOAT


def test_generate_terrain_derivatives_raster(tmp_path):
    """Verify end-to-end GeoTIFF slope and aspect generation from synthetic DEM."""
    rows, cols = 10, 10
    dem_arr = np.zeros((rows, cols), dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            dem_arr[r, c] = 2000.0 + r * 10.0 + c * 5.0

    t = Affine(30.0, 0.0, 700000.0, 0.0, -30.0, 3350300.0)
    dem_path = write_synthetic_raster(tmp_path / "synthetic_dem.tif", dem_arr, t)

    slope_path = tmp_path / "slope.tif"
    aspect_path = tmp_path / "aspect.tif"

    generate_terrain_derivatives_raster(dem_path, slope_path, aspect_path)

    assert slope_path.exists()
    assert aspect_path.exists()

    with rasterio.open(slope_path) as s_src, rasterio.open(aspect_path) as a_src:
        assert s_src.shape == (10, 10)
        assert a_src.shape == (10, 10)
        assert s_src.nodata == DEFAULT_NODATA_FLOAT
        s_data = s_src.read(1)
        # Valid slope angles must be within [0, 90]
        valid_slopes = s_data[s_data != DEFAULT_NODATA_FLOAT]
        assert np.all((valid_slopes >= 0.0) & (valid_slopes <= 90.0))


# ==============================================================================
# 7. Raster Vector Masking & Clipping Tests
# ==============================================================================

def test_mask_raster_with_vector(tmp_path):
    """Verify raster masking exterior to polygon sets nodata while preserving transform."""
    arr = np.full((10, 10), 50.0, dtype=np.float32)
    t = Affine(30.0, 0.0, 700000.0, 0.0, -30.0, 3350300.0)
    r_path = write_synthetic_raster(tmp_path / "to_mask.tif", arr, t)

    # Create polygon covering only the left half of the raster (x from 700000 to 700150)
    mask_poly = Polygon([(700000, 3350000), (700150, 3350000), (700150, 3350300), (700000, 3350300)])
    mask_gdf = gpd.GeoDataFrame([{"geometry": mask_poly}], crs=CANONICAL_PROJECTED_CRS_STR)

    masked_path = tmp_path / "masked.tif"
    mask_raster_with_vector(r_path, masked_path, mask_gdf, nodata_value=DEFAULT_NODATA_FLOAT)

    with rasterio.open(masked_path) as src:
        masked_data = src.read(1)
        # Dimensions and transform must remain identical
        assert src.shape == (10, 10)
        assert src.transform == t
        # Left columns (0..4) should have valid data (50.0)
        assert np.all(masked_data[:, 0:4] == 50.0)
        # Far right columns (6..9) outside polygon must be nodata
        assert np.all(masked_data[:, 6:10] == DEFAULT_NODATA_FLOAT)


# ==============================================================================
# 8. Provenance Manifest Test
# ==============================================================================

def test_gis_processing_provenance(tmp_path):
    """Verify generation of provenance manifest for GIS operations."""
    dummy_raster = tmp_path / "input.tif"
    dummy_raster.write_bytes(b"SYNTHETIC_RASTER_DATA_CONTENT")

    record = ProvenanceRecord(
        dataset_id="synthetic_dem_30m",
        source_id="test_synthetic_fixture",
        local_raw_path=str(dummy_raster.as_posix()),
        file_format="GEOTIFF",
        file_size_bytes=dummy_raster.stat().st_size,
        checksum_sha256="dummy_sha256_hash",
        original_crs=CANONICAL_PROJECTED_CRS_STR,
        target_crs=CANONICAL_PROJECTED_CRS_STR,
        validation_status="PASSED",
    )

    manifest_path = tmp_path / "provenance.json"
    record.save_json(manifest_path)

    assert manifest_path.exists()
    content = manifest_path.read_text(encoding="utf-8")
    assert "synthetic_dem_30m" in content
    assert "EPSG:32644" in content
