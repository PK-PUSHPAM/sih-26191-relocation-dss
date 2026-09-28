"""
Raster GIS Processing and Alignment Module for Layer L03.
Handles raster metadata extraction, strict alignment verification, explicit continuous/categorical resampling,
vector polygon masking, and GeoTIFF I/O.
"""
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any, Union
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask
from rasterio.warp import reproject
import geopandas as gpd

from src.common.crs import CANONICAL_PROJECTED_CRS_STR, CANONICAL_PROJECTED_CRS_EPSG
from src.spatial.grid import (
    CanonicalGridDefinition,
    CANONICAL_RESOLUTION_METERS,
    DEFAULT_NODATA_FLOAT,
    DEFAULT_NODATA_INT,
)


class RasterProcessingError(Exception):
    """Base exception for raster processing errors."""


class RasterAlignmentError(RasterProcessingError):
    """Raised when two rasters fail alignment checks."""


class MissingRasterCRSError(RasterProcessingError):
    """Raised when a raster has no CRS definition."""


class MissingRasterNoDataError(RasterProcessingError):
    """Raised when a raster has no explicit nodata value."""


RasterMetadata = Dict[str, Any]


def inspect_raster_metadata(raster_path: Union[str, Path]) -> Dict[str, Any]:
    p = Path(raster_path)
    if not p.exists():
        raise FileNotFoundError(f"Raster file not found: {p}")

    with rasterio.open(p) as src:
        crs_str = src.crs.to_string() if src.crs else None
        return {
            "file_path": str(p.as_posix()),
            "crs": crs_str,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtypes": src.dtypes,
            "nodata": src.nodata,
            "bounds": {
                "left": src.bounds.left,
                "bottom": src.bounds.bottom,
                "right": src.bounds.right,
                "top": src.bounds.top,
            },
            "resolution": (src.res[0], src.res[1]),
            "transform": [
                src.transform.a, src.transform.b, src.transform.c,
                src.transform.d, src.transform.e, src.transform.f,
            ],
            "is_tiled": src.profile.get("tiled", False),
        }


def _require_explicit_metadata(src) -> None:
    if src.crs is None:
        raise MissingRasterCRSError(
            "Raster CRS is missing; L03 will not guess or assume a CRS."
        )
    if src.nodata is None:
        raise MissingRasterNoDataError(
            "Raster nodata value is missing; L03 will not invent one."
        )


def validate_raster_alignment(
    raster_a_path: Union[str, Path],
    raster_b_path: Union[str, Path],
    tolerance: float = 1e-4,
) -> Tuple[bool, List[str]]:
    meta_a = inspect_raster_metadata(raster_a_path)
    meta_b = inspect_raster_metadata(raster_b_path)
    issues: List[str] = []

    if meta_a["crs"] != meta_b["crs"]:
        issues.append(f"CRS mismatch: {meta_a['crs']} vs {meta_b['crs']}")
    if meta_a["width"] != meta_b["width"] or meta_a["height"] != meta_b["height"]:
        issues.append(
            f"Dimension mismatch: ({meta_a['width']}x{meta_a['height']}) vs "
            f"({meta_b['width']}x{meta_b['height']})"
        )

    t_a = meta_a["transform"]
    t_b = meta_b["transform"]
    if abs(t_a[0] - t_b[0]) > tolerance or abs(t_a[4] - t_b[4]) > tolerance:
        issues.append(f"Pixel resolution mismatch: ({t_a[0]}, {t_a[4]}) vs ({t_b[0]}, {t_b[4]})")
    if abs(t_a[2] - t_b[2]) > tolerance or abs(t_a[5] - t_b[5]) > tolerance:
        issues.append(f"Origin (X, Y) mismatch: ({t_a[2]}, {t_a[5]}) vs ({t_b[2]}, {t_b[5]})")
    if abs(t_a[1]) > tolerance or abs(t_a[3]) > tolerance or abs(t_b[1]) > tolerance or abs(t_b[3]) > tolerance:
        issues.append("One or both rasters have non-zero rotation coefficients.")

    return len(issues) == 0, issues


def is_aligned_to_canonical_grid(
    raster_path: Union[str, Path],
    grid_def: CanonicalGridDefinition,
    tolerance: float = 1e-4,
) -> Tuple[bool, List[str]]:
    meta = inspect_raster_metadata(raster_path)
    issues: List[str] = []

    if meta["crs"] not in [grid_def.crs, f"EPSG:{CANONICAL_PROJECTED_CRS_EPSG}"]:
        issues.append(f"CRS '{meta['crs']}' does not match canonical grid CRS '{grid_def.crs}'")
    if meta["width"] != grid_def.width or meta["height"] != grid_def.height:
        issues.append(f"Dimensions ({meta['width']}, {meta['height']}) do not match grid ({grid_def.width}, {grid_def.height})")

    t = meta["transform"]
    if abs(t[0] - grid_def.resolution) > tolerance or abs(t[4] - (-grid_def.resolution)) > tolerance:
        issues.append(f"Resolution ({t[0]}, {t[4]}) does not match canonical resolution {grid_def.resolution}m")
    if abs(t[2] - grid_def.x_min) > tolerance or abs(t[5] - grid_def.y_max) > tolerance:
        issues.append(f"Origin ({t[2]}, {t[5]}) does not match canonical origin ({grid_def.x_min}, {grid_def.y_max})")
    if abs(t[1]) > tolerance or abs(t[3]) > tolerance:
        issues.append("Raster has non-zero rotation coefficients.")

    return len(issues) == 0, issues


def resample_and_align_raster(
    input_raster_path: Union[str, Path],
    output_raster_path: Union[str, Path],
    grid_def: CanonicalGridDefinition,
    is_categorical: bool = False,
    output_nodata: Optional[float] = None,
) -> Path:
    in_p = Path(input_raster_path)
    out_p = Path(output_raster_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    resampling_method = Resampling.nearest if is_categorical else Resampling.bilinear

    with rasterio.open(in_p) as src:
        _require_explicit_metadata(src)

        if src.crs.to_epsg() is None:
            raise MissingRasterCRSError(f"Raster CRS cannot be resolved to an EPSG code: {src.crs}")

        target_nodata = output_nodata if output_nodata is not None else src.nodata
        destination = np.full(
            (grid_def.height, grid_def.width),
            target_nodata,
            dtype=np.float32 if not is_categorical else src.dtypes[0],
        )

        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=grid_def.transform,
            dst_crs=grid_def.crs,
            dst_nodata=target_nodata,
            resampling=resampling_method,
        )

        profile = src.profile.copy()
        profile.update({
            "driver": "GTiff",
            "crs": grid_def.crs,
            "transform": grid_def.transform,
            "width": grid_def.width,
            "height": grid_def.height,
            "count": 1,
            "dtype": destination.dtype,
            "nodata": target_nodata,
            "compress": "lzw",
        })

        with rasterio.open(out_p, "w", **profile) as dst:
            dst.write(destination, 1)

    return out_p


def mask_raster_with_vector(
    input_raster_path: Union[str, Path],
    output_raster_path: Union[str, Path],
    boundary_gdf: gpd.GeoDataFrame,
    nodata_value: Optional[float] = None,
) -> Path:
    in_p = Path(input_raster_path)
    out_p = Path(output_raster_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if boundary_gdf.crs is None:
        raise ValueError("Boundary CRS is missing; L03 will not guess or assume a CRS.")

    with rasterio.open(in_p) as src:
        _require_explicit_metadata(src)
        boundary_proj = boundary_gdf.to_crs(src.crs)
        shapes = [geom for geom in boundary_proj.geometry if not geom.is_empty]
        if not shapes:
            raise ValueError("Boundary contains no non-empty geometries.")

        out_nodata = nodata_value if nodata_value is not None else src.nodata

        masked_img, _ = mask(
            src,
            shapes,
            crop=False,
            nodata=out_nodata,
            filled=True,
        )

        profile = src.profile.copy()
        profile.update({
            "driver": "GTiff",
            "nodata": out_nodata,
            "compress": "lzw",
        })

        with rasterio.open(out_p, "w", **profile) as dst:
            dst.write(masked_img)

    return out_p
