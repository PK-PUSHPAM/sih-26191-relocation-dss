"""
Layer 03: Spatial Grid & GIS Processing Module.
Canonical projected CRS (EPSG:32644), 30 m grid, resampling, vector/raster alignment, and terrain derivatives.
"""
from .grid import (
    CanonicalGridDefinition,
    CANONICAL_RESOLUTION_METERS,
    DEFAULT_NODATA_FLOAT,
    DEFAULT_NODATA_INT,
    create_canonical_grid,
    generate_grid_cells_gdf,
    snap_coordinate_outward,
)
from .vector import (
    SpatialProcessingError,
    MissingCRSError,
    InvalidGeometryError,
    ExtentMismatchError,
    validate_and_reproject_vector,
    validate_study_area_geometry,
    load_and_prepare_study_area,
    clip_vector_to_study_area,
)
from .raster import (
    RasterProcessingError,
    RasterAlignmentError,
    inspect_raster_metadata,
    validate_raster_alignment,
    is_aligned_to_canonical_grid,
    resample_and_align_raster,
    mask_raster_with_vector,
)
from .terrain import (
    calculate_slope_and_aspect_arrays,
    generate_terrain_derivatives_raster,
)

__all__ = [
    "CanonicalGridDefinition",
    "CANONICAL_RESOLUTION_METERS",
    "DEFAULT_NODATA_FLOAT",
    "DEFAULT_NODATA_INT",
    "create_canonical_grid",
    "generate_grid_cells_gdf",
    "snap_coordinate_outward",
    "SpatialProcessingError",
    "MissingCRSError",
    "InvalidGeometryError",
    "ExtentMismatchError",
    "validate_and_reproject_vector",
    "validate_study_area_geometry",
    "load_and_prepare_study_area",
    "clip_vector_to_study_area",
    "RasterProcessingError",
    "RasterAlignmentError",
    "inspect_raster_metadata",
    "validate_raster_alignment",
    "is_aligned_to_canonical_grid",
    "resample_and_align_raster",
    "mask_raster_with_vector",
    "calculate_slope_and_aspect_arrays",
    "generate_terrain_derivatives_raster",
]
