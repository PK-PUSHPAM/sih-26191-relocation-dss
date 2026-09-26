"""
Terrain Derivatives Processing Module for Layer L03.
Computes topographic slope (degrees) and aspect (degrees azimuth from North) from a 30m DEM
using Horn's 3x3 finite-difference algorithm.
"""
from pathlib import Path
from typing import Tuple, Optional, Union
import numpy as np
import rasterio
from rasterio.transform import Affine

from src.spatial.grid import DEFAULT_NODATA_FLOAT


def calculate_slope_and_aspect_arrays(
    dem: np.ndarray,
    dx: float = 30.0,
    dy: float = 30.0,
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute slope (degrees) and aspect (degrees clockwise from North) from a 2D DEM elevation grid.
    Uses Horn's 3x3 finite difference weighted kernel:
      dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * dx)
      dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * dy)
    
    Returns:
      slope_deg: array of slope in degrees in range [0.0, 90.0].
      aspect_deg: array of aspect in degrees in range [0.0, 360.0], with flat (-1.0) and nodata preserved.
    """
    rows, cols = dem.shape
    slope = np.full((rows, cols), nodata, dtype=np.float32)
    aspect = np.full((rows, cols), nodata, dtype=np.float32)

    if rows < 3 or cols < 3:
        return slope, aspect

    # Valid mask for nodata handling
    if np.isnan(nodata):
        valid = ~np.isnan(dem)
    else:
        valid = (dem != nodata) & (~np.isnan(dem))

    # Extract 3x3 window slices
    # a b c
    # d e f
    # g h i
    a = dem[0:-2, 0:-2]
    b = dem[0:-2, 1:-1]
    c = dem[0:-2, 2:]
    d = dem[1:-1, 0:-2]
    e = dem[1:-1, 1:-1]
    f = dem[1:-1, 2:]
    g = dem[2:, 0:-2]
    h = dem[2:, 1:-1]
    i = dem[2:, 2:]

    # Window validity: center and all 8 neighbors must be valid
    va = valid[0:-2, 0:-2]
    vb = valid[0:-2, 1:-1]
    vc = valid[0:-2, 2:]
    vd = valid[1:-1, 0:-2]
    ve = valid[1:-1, 1:-1]
    vf = valid[1:-1, 2:]
    vg = valid[2:, 0:-2]
    vh = valid[2:, 1:-1]
    vi = valid[2:, 2:]

    all_valid = va & vb & vc & vd & ve & vf & vg & vh & vi

    # Finite difference calculation
    dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * dx)
    dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * dy)

    # Slope in radians and degrees
    gradient = np.sqrt(dz_dx**2 + dz_dy**2)
    slope_rad = np.arctan(gradient)
    slope_sub = np.degrees(slope_rad)

    # Aspect in degrees azimuth (0 to 360 clockwise from North)
    # Downslope vector components: -dz/dx (East), -dz/dy (North)
    # aspect_rad = atan2(-dz/dy, -dz/dx) gives angle from East counter-clockwise
    # Standard geographic convention: 90 - atan2(dz/dy, -dz/dx) in degrees
    aspect_rad = np.arctan2(dz_dy, -dz_dx)
    aspect_sub = 90.0 - np.degrees(aspect_rad)
    aspect_sub = np.where(aspect_sub < 0.0, aspect_sub + 360.0, aspect_sub)
    aspect_sub = np.where(aspect_sub >= 360.0, aspect_sub - 360.0, aspect_sub)

    # Flat areas where slope is 0 have undefined aspect (conventionally -1.0)
    aspect_sub = np.where(slope_sub == 0.0, -1.0, aspect_sub)

    # Assign only where all 9 cells are valid
    interior_slope = slope[1:-1, 1:-1]
    interior_aspect = aspect[1:-1, 1:-1]

    interior_slope[all_valid] = slope_sub[all_valid]
    interior_aspect[all_valid] = aspect_sub[all_valid]

    slope[1:-1, 1:-1] = interior_slope
    aspect[1:-1, 1:-1] = interior_aspect

    return slope, aspect


def generate_terrain_derivatives_raster(
    dem_raster_path: Union[str, Path],
    output_slope_path: Union[str, Path],
    output_aspect_path: Union[str, Path],
    nodata: float = DEFAULT_NODATA_FLOAT,
) -> Tuple[Path, Path]:
    """
    Process an input DEM GeoTIFF and write aligned Slope and Aspect GeoTIFFs.
    Slope is in degrees [0, 90].
    Aspect is in degrees [0, 360], flat=-1.0.
    """
    dem_p = Path(dem_raster_path)
    slope_p = Path(output_slope_path)
    aspect_p = Path(output_aspect_path)

    slope_p.parent.mkdir(parents=True, exist_ok=True)
    aspect_p.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(dem_p) as src:
        dem_data = src.read(1)
        src_nodata = src.nodata if src.nodata is not None else nodata
        dx, dy = src.res[0], src.res[1]

        slope_arr, aspect_arr = calculate_slope_and_aspect_arrays(
            dem_data,
            dx=dx,
            dy=dy,
            nodata=src_nodata,
        )

        profile = src.profile.copy()
        profile.update({
            "driver": "GTiff",
            "dtype": np.float32,
            "count": 1,
            "nodata": nodata,
            "compress": "deflate",
        })

        with rasterio.open(slope_p, "w", **profile) as dst_slope:
            dst_slope.write(slope_arr.astype(np.float32), 1)

        with rasterio.open(aspect_p, "w", **profile) as dst_aspect:
            dst_aspect.write(aspect_arr.astype(np.float32), 1)

    return slope_p, aspect_p
