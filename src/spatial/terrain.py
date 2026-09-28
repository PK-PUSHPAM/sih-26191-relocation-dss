"""
Terrain Derivatives Processing Module for Layer L03.
Computes topographic slope (degrees) and aspect (degrees azimuth from North) from a 30m DEM
using Horn's 3x3 finite-difference algorithm.
"""
from pathlib import Path
from typing import Tuple, Union
import numpy as np
import rasterio

from src.spatial.grid import DEFAULT_NODATA_FLOAT


def calculate_slope_and_aspect_arrays(
    dem: np.ndarray,
    dx: float = 30.0,
    dy: float = 30.0,
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute slope (degrees) and aspect (degrees clockwise from North) from a 2D DEM.

    Uses Horn's 3x3 finite difference weighted kernel. NoData in any cell of
    the 3x3 window propagates to both derived outputs.

    Aspect is the downslope azimuth:
      atan2(-dz/dx, -dz/dy)
    where +x is East and +y is North. Thus North=0, East=90,
    South=180, West=270. Flat terrain receives -1.
    """
    if dem.ndim != 2:
        raise ValueError(f"DEM must be a 2D array, got {dem.ndim} dimensions.")
    if dx <= 0 or dy <= 0:
        raise ValueError(f"DEM cell sizes must be positive; got dx={dx}, dy={dy}.")

    rows, cols = dem.shape
    slope = np.full((rows, cols), nodata, dtype=np.float32)
    aspect = np.full((rows, cols), nodata, dtype=np.float32)

    if rows < 3 or cols < 3:
        return slope, aspect

    if np.isnan(nodata):
        valid = ~np.isnan(dem)
    else:
        valid = (dem != nodata) & (~np.isnan(dem))

    # 3x3 window:
    # a b c
    # d e f
    # g h i
    a = dem[0:-2, 0:-2]
    b = dem[0:-2, 1:-1]
    c = dem[0:-2, 2:]
    d = dem[1:-1, 0:-2]
    f = dem[1:-1, 2:]
    g = dem[2:, 0:-2]
    h = dem[2:, 1:-1]
    i = dem[2:, 2:]

    all_valid = (
        valid[0:-2, 0:-2]
        & valid[0:-2, 1:-1]
        & valid[0:-2, 2:]
        & valid[1:-1, 0:-2]
        & valid[1:-1, 2:]
        & valid[2:, 0:-2]
        & valid[2:, 1:-1]
        & valid[2:, 2:]
    )

    # Sentinel/invalid elevations must never enter the Horn arithmetic.
    # Compute derivatives only for windows whose complete 3x3 neighborhood is valid.
    dz_dx = np.zeros_like(a, dtype=np.float64)
    dz_dy = np.zeros_like(a, dtype=np.float64)

    if np.any(all_valid):
        dz_dx[all_valid] = (
            (c[all_valid] + 2.0 * f[all_valid] + i[all_valid])
            - (a[all_valid] + 2.0 * d[all_valid] + g[all_valid])
        ) / (8.0 * dx)
        dz_dy[all_valid] = (
            (g[all_valid] + 2.0 * h[all_valid] + i[all_valid])
            - (a[all_valid] + 2.0 * b[all_valid] + c[all_valid])
        ) / (8.0 * dy)

        gradient = np.sqrt(dz_dx[all_valid] ** 2 + dz_dy[all_valid] ** 2)
        slope_values = np.degrees(np.arctan(gradient))

        # Downslope vector = (-dz/dx East, -dz/dy North).
        # Azimuth clockwise from North = atan2(East, North).
        aspect_values = np.degrees(
            np.arctan2(-dz_dx[all_valid], -dz_dy[all_valid])
        ) % 360.0
        aspect_values = np.where(slope_values == 0.0, -1.0, aspect_values)

        slope_inner = slope[1:-1, 1:-1]
        aspect_inner = aspect[1:-1, 1:-1]
        slope_inner[all_valid] = slope_values.astype(np.float32)
        aspect_inner[all_valid] = aspect_values.astype(np.float32)

    return slope, aspect


def generate_terrain_derivatives_raster(
    dem_raster_path: Union[str, Path],
    output_slope_path: Union[str, Path],
    output_aspect_path: Union[str, Path],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> Tuple[Path, Path]:
    """
    Process an input DEM GeoTIFF and write aligned Slope and Aspect GeoTIFFs.

    The input DEM must have an explicit CRS and explicit nodata value.
    L03 requires canonical EPSG:32644 and projected positive cell sizes.
    """
    dem_p = Path(dem_raster_path)
    slope_p = Path(output_slope_path)
    aspect_p = Path(output_aspect_path)

    slope_p.parent.mkdir(parents=True, exist_ok=True)
    aspect_p.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(dem_p) as src:
        if src.crs is None:
            raise ValueError("DEM CRS is missing; L03 will not guess or assume a CRS.")
        if src.crs.to_epsg() != 32644:
            raise ValueError(f"DEM CRS must be EPSG:32644, got {src.crs}.")
        if src.nodata is None:
            raise ValueError("DEM nodata value is missing; L03 will not invent one.")
        if src.res[0] <= 0 or src.res[1] <= 0:
            raise ValueError(f"DEM resolution must be positive; got {src.res}.")
        if src.count < 1:
            raise ValueError("DEM contains no raster bands.")

        dem_data = src.read(1)
        dx, dy = src.res[0], src.res[1]

        slope_arr, aspect_arr = calculate_slope_and_aspect_arrays(
            dem_data,
            dx=dx,
            dy=dy,
            nodata=src.nodata,
        )

        profile = src.profile.copy()
        profile.update({
            "driver": "GTiff",
            "dtype": np.float32,
            "count": 1,
            "nodata": src.nodata,
            "compress": "lzw",
        })

        with rasterio.open(slope_p, "w", **profile) as dst_slope:
            dst_slope.write(slope_arr.astype(np.float32), 1)

        with rasterio.open(aspect_p, "w", **profile) as dst_aspect:
            dst_aspect.write(aspect_arr.astype(np.float32), 1)

    return slope_p, aspect_p
