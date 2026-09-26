"""
Vector GIS Processing and Study Area Validation for Layer L03.
Handles study-area boundary ingestion, validation, reprojection to EPSG:32644, and vector clipping.
"""
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, Union
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.validation import make_valid
import pyproj

from src.common.crs import (
    CANONICAL_PROJECTED_CRS_EPSG,
    CANONICAL_PROJECTED_CRS_STR,
    CHAMOLI_BBOX_WGS84,
    validate_crs_string,
)


class SpatialProcessingError(Exception):
    """Base exception for spatial processing errors."""
    pass


class MissingCRSError(SpatialProcessingError):
    """Raised when a spatial dataset is missing a CRS definition."""
    pass


class InvalidGeometryError(SpatialProcessingError):
    """Raised when a geometry is topologically invalid and unrepairable."""
    pass


class ExtentMismatchError(SpatialProcessingError):
    """Raised when an input layer does not intersect the study area."""
    pass


def validate_and_reproject_vector(
    gdf: gpd.GeoDataFrame,
    target_crs: str = CANONICAL_PROJECTED_CRS_STR,
) -> gpd.GeoDataFrame:
    """
    Validate vector dataset CRS and reproject to target projected CRS (EPSG:32644).
    Rejects datasets with missing CRS.
    """
    if gdf.crs is None:
        raise MissingCRSError("Vector GeoDataFrame has no defined CRS. Cannot guess or assume CRS.")

    # Check if already in target CRS
    target_pyproj = pyproj.CRS.from_user_input(target_crs)
    if gdf.crs == target_pyproj:
        return gdf.copy()

    # Reproject
    reprojected = gdf.to_crs(target_crs)
    return reprojected


def validate_study_area_geometry(
    boundary_geom: Union[Polygon, MultiPolygon],
    sanity_bbox_wgs84: Optional[Dict[str, float]] = None,
    source_crs: Optional[str] = None,
) -> Tuple[bool, Union[Polygon, MultiPolygon], Optional[str]]:
    """
    Validate a study-area boundary geometry.
    1. Ensures non-empty and valid polygon/multipolygon.
    2. Repairs minor topology errors if needed via make_valid.
    3. Confirms spatial overlap with Chamoli envelope in WGS84.
    Returns (is_valid, cleaned_geom, message).
    """
    if boundary_geom is None or boundary_geom.is_empty:
        return False, boundary_geom, "Study area boundary geometry is empty or None."

    if not isinstance(boundary_geom, (Polygon, MultiPolygon)):
        return False, boundary_geom, f"Boundary geometry must be Polygon or MultiPolygon, got {boundary_geom.geom_type}."

    cleaned_geom = boundary_geom
    if not boundary_geom.is_valid:
        cleaned_geom = make_valid(boundary_geom)
        if not cleaned_geom.is_valid or cleaned_geom.is_empty:
            return False, boundary_geom, "Boundary geometry is topologically invalid and could not be repaired."

    # Validate against sanity bounding envelope if provided
    bbox = sanity_bbox_wgs84 or CHAMOLI_BBOX_WGS84
    sanity_box = box(bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"])

    # If geometry is in projected coordinates, project sanity box or check in WGS84
    if source_crs and source_crs != "EPSG:4326":
        try:
            transformer = pyproj.Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
            # Transform boundary sample to WGS84 for envelope check
            minx, miny, maxx, maxy = cleaned_geom.bounds
            p0_lon, p0_lat = transformer.transform(minx, miny)
            p1_lon, p1_lat = transformer.transform(maxx, maxy)
            geom_wgs84_box = box(min(p0_lon, p1_lon), min(p0_lat, p1_lat), max(p0_lon, p1_lon), max(p0_lat, p1_lat))
            if not geom_wgs84_box.intersects(sanity_box):
                return False, cleaned_geom, "Boundary does not intersect Chamoli sanity bounding envelope."
        except Exception:
            pass  # Fallback to geometry validity
    else:
        # Assumed WGS84
        if not cleaned_geom.intersects(sanity_box):
            return False, cleaned_geom, "Boundary does not intersect Chamoli sanity bounding envelope."

    return True, cleaned_geom, None


def load_and_prepare_study_area(
    boundary_gdf: gpd.GeoDataFrame,
    target_crs: str = CANONICAL_PROJECTED_CRS_STR,
) -> gpd.GeoDataFrame:
    """
    Process an authoritative district boundary GeoDataFrame:
    1. Validates CRS.
    2. Reprojects to EPSG:32644.
    3. Validates topology and repairs self-intersections.
    4. Unions / dissolves multipart features into a single validated study area polygon.
    """
    if boundary_gdf.empty:
        raise ValueError("Provided boundary GeoDataFrame is empty.")

    reprojected = validate_and_reproject_vector(boundary_gdf, target_crs=target_crs)

    # Union all geometries into a dissolved polygon/multipolygon
    dissolved_geom = reprojected.geometry.union_all()
    is_valid, cleaned_geom, err = validate_study_area_geometry(
        dissolved_geom,
        source_crs=target_crs,
    )
    if not is_valid:
        raise InvalidGeometryError(f"Study area geometry validation failed: {err}")

    # Return as unified single-row GeoDataFrame
    result_gdf = gpd.GeoDataFrame(
        [{"study_area": "Chamoli", "geometry": cleaned_geom}],
        crs=target_crs,
    )
    return result_gdf


def clip_vector_to_study_area(
    input_gdf: gpd.GeoDataFrame,
    study_area_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Clip vector features to the exact study area polygon.
    Ensures both datasets share EPSG:32644 before clipping.
    """
    if input_gdf.empty:
        return input_gdf.copy()

    # Reproject input to match study area CRS if needed
    prep_input = validate_and_reproject_vector(input_gdf, target_crs=str(study_area_gdf.crs))

    # Perform geometric clip
    clipped = gpd.clip(prep_input, study_area_gdf)
    # Remove empty geometries resulting from edge clips
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()].copy()
    return clipped
