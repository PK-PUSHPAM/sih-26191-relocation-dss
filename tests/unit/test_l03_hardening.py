import numpy as np
import rasterio
import pytest
from affine import Affine

from src.spatial.raster import (
    MissingRasterCRSError,
    MissingRasterNoDataError,
    resample_and_align_raster,
)
from src.spatial.grid import create_canonical_grid
from src.spatial.terrain import calculate_slope_and_aspect_arrays
from src.spatial.raster import mask_raster_with_vector
from shapely.geometry import box
import geopandas as gpd


def _write_raster(path, data, *, crs="EPSG:32644", nodata=-9999.0):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=Affine(30, 0, 700000, 0, -30, 3350300),
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def test_missing_raster_crs_is_rejected(tmp_path):
    path = tmp_path / "no_crs.tif"
    _write_raster(path, np.ones((3, 3), dtype=np.float32), crs=None)

    grid = create_canonical_grid((700000, 3350210, 700090, 3350300))
    with pytest.raises(MissingRasterCRSError):
        resample_and_align_raster(path, tmp_path / "out.tif", grid)


def test_missing_raster_nodata_is_rejected(tmp_path):
    path = tmp_path / "no_nodata.tif"
    _write_raster(path, np.ones((3, 3), dtype=np.float32), nodata=None)

    grid = create_canonical_grid((700000, 3350210, 700090, 3350300))
    with pytest.raises(MissingRasterNoDataError):
        resample_and_align_raster(path, tmp_path / "out.tif", grid)


@pytest.mark.parametrize(
    ("direction", "expected_aspect"),
    [
        ("north", 0.0),
        ("east", 90.0),
        ("south", 180.0),
        ("west", 270.0),
    ],
)
def test_aspect_cardinal_directions(direction, expected_aspect):
    rows, cols = 5, 5
    dem = np.zeros((rows, cols), dtype=np.float32)

    for r in range(rows):
        for c in range(cols):
            if direction == "north":
                dem[r, c] = 2000.0 + r * 15.0
            elif direction == "south":
                dem[r, c] = 2000.0 - r * 15.0
            elif direction == "east":
                dem[r, c] = 2000.0 - c * 15.0
            else:
                dem[r, c] = 2000.0 + c * 15.0

    slope, aspect = calculate_slope_and_aspect_arrays(dem, dx=30, dy=30)

    assert np.allclose(slope[1:-1, 1:-1], np.degrees(np.arctan(0.5)), atol=1e-3)
    assert np.allclose(aspect[1:-1, 1:-1], expected_aspect, atol=1e-3)


def test_terrain_rejects_non_2d_array():
    with pytest.raises(ValueError, match="2D"):
        calculate_slope_and_aspect_arrays(np.ones((2, 3, 4), dtype=np.float32))


def test_terrain_rejects_non_positive_cell_size():
    with pytest.raises(ValueError, match="positive"):
        calculate_slope_and_aspect_arrays(np.ones((3, 3), dtype=np.float32), dx=0)


def test_mask_requires_boundary_crs(tmp_path):
    path = tmp_path / "input.tif"
    _write_raster(path, np.ones((3, 3), dtype=np.float32))
    boundary = gpd.GeoDataFrame({"geometry": [box(700000, 3350210, 700090, 3350300)]}, crs=None)

    with pytest.raises(ValueError, match="Boundary CRS is missing"):
        mask_raster_with_vector(path, tmp_path / "masked.tif", boundary)
