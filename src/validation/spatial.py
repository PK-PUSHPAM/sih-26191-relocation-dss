"""
Spatial Data Validation Functions.
Validates GeoDataFrames, Shapely geometries, CRS validity, and spatial envelopes.
"""
from typing import List, Optional
import geopandas as gpd
from shapely.geometry.base import BaseGeometry
import pyproj

from src.common.crs import CHAMOLI_BBOX_WGS84, CANONICAL_PROJECTED_CRS_STR, validate_crs_string
from .models import (
    DatasetSchemaContract,
    ValidationIssue,
    ValidationSeverity,
)

def validate_crs_presence_and_validity(
    gdf: gpd.GeoDataFrame, contract: DatasetSchemaContract
) -> List[ValidationIssue]:
    """Check that the GeoDataFrame has a valid, non-null Coordinate Reference System."""
    issues = []
    if gdf.crs is None:
        issues.append(
            ValidationIssue(
                check_name="spatial_crs_presence",
                severity=ValidationSeverity.ERROR,
                message="Dataset has missing / undefined CRS (Coordinate Reference System).",
            )
        )
        return issues

    is_valid, crs_str, error_msg = validate_crs_string(str(gdf.crs))
    if not is_valid:
        issues.append(
            ValidationIssue(
                check_name="spatial_crs_validity",
                severity=ValidationSeverity.ERROR,
                message=f"CRS is invalid: {error_msg}",
            )
        )
    elif contract.expected_crs:
        _, exp_crs_str, _ = validate_crs_string(contract.expected_crs)
        if crs_str != exp_crs_str:
            issues.append(
                ValidationIssue(
                    check_name="spatial_crs_mismatch",
                    severity=ValidationSeverity.WARNING,
                    message=f"Dataset CRS '{crs_str}' differs from expected '{exp_crs_str}'. Reprojection will be required.",
                    details={"current_crs": crs_str, "expected_crs": exp_crs_str},
                )
            )
    return issues

def validate_geometry_integrity(gdf: gpd.GeoDataFrame) -> List[ValidationIssue]:
    """Check for null, empty, or topological invalidity in geometries."""
    issues = []
    if "geometry" not in gdf.columns:
        issues.append(
            ValidationIssue(
                check_name="spatial_geometry_column_presence",
                severity=ValidationSeverity.ERROR,
                message="GeoDataFrame lacks an active 'geometry' column.",
            )
        )
        return issues

    # Null geometries check
    null_geom_count = int(gdf.geometry.isna().sum())
    if null_geom_count > 0:
        issues.append(
            ValidationIssue(
                check_name="spatial_geometry_null_check",
                severity=ValidationSeverity.ERROR,
                message=f"Found {null_geom_count} rows with NULL geometry.",
                details={"null_geometry_count": null_geom_count},
            )
        )

    # Filter non-null geometries for validity and emptiness checks
    valid_geoms = gdf.geometry.dropna()
    if len(valid_geoms) == 0:
        return issues

    # Empty geometry check
    empty_mask = valid_geoms.is_empty
    empty_count = int(empty_mask.sum())
    if empty_count > 0:
        issues.append(
            ValidationIssue(
                check_name="spatial_geometry_empty_check",
                severity=ValidationSeverity.ERROR,
                message=f"Found {empty_count} empty geometry features.",
                details={"empty_geometry_count": empty_count},
            )
        )

    # Topology validity check (shapely.is_valid)
    invalid_mask = ~valid_geoms.is_valid
    invalid_count = int(invalid_mask.sum())
    if invalid_count > 0:
        invalid_sample = list(gdf.index[invalid_mask][:5])
        issues.append(
            ValidationIssue(
                check_name="spatial_geometry_validity",
                severity=ValidationSeverity.ERROR,
                message=f"Found {invalid_count} geometrically invalid features (self-intersections, bowties).",
                row_indices=invalid_sample,
                details={"invalid_count": invalid_count},
            )
        )

    return issues

def validate_geometry_types(
    gdf: gpd.GeoDataFrame, contract: DatasetSchemaContract
) -> List[ValidationIssue]:
    """Validate that geometry types match the expected contract."""
    issues = []
    if not contract.expected_geometry_type or "geometry" not in gdf.columns:
        return issues

    geom_types = set(gdf.geometry.dropna().geom_type.unique())
    expected = contract.expected_geometry_type

    # Allow Multi-variants (e.g. Polygon allows Polygon and MultiPolygon)
    compatible_types = {expected}
    if expected == "Polygon":
        compatible_types.add("MultiPolygon")
    elif expected == "LineString":
        compatible_types.add("MultiLineString")
    elif expected == "Point":
        compatible_types.add("MultiPoint")

    incompatible = geom_types - compatible_types
    if incompatible:
        issues.append(
            ValidationIssue(
                check_name="spatial_geometry_type_mismatch",
                severity=ValidationSeverity.ERROR,
                message=f"Incompatible geometry types found: {list(geom_types)}. Expected compatible with '{expected}'.",
                details={"found_types": list(geom_types), "expected_type": expected},
            )
        )
    return issues

def validate_spatial_bounding_box(gdf: gpd.GeoDataFrame) -> List[ValidationIssue]:
    """Ensure that the dataset bounding box intersects the Chamoli study area envelope."""
    issues = []
    if gdf.empty or "geometry" not in gdf.columns or gdf.crs is None:
        return issues

    try:
        # Reproject to WGS84 for envelope check if needed
        gdf_wgs84 = gdf.to_crs("EPSG:4326") if str(gdf.crs) != "EPSG:4326" else gdf
        total_bounds = gdf_wgs84.total_bounds  # (minx, miny, maxx, maxy) -> (min_lon, min_lat, max_lon, max_lat)
        min_lon, min_lat, max_lon, max_lat = total_bounds

        # Check for intersection with generous Chamoli envelope
        c_bbox = CHAMOLI_BBOX_WGS84
        intersects = not (
            max_lon < c_bbox["min_lon"]
            or min_lon > c_bbox["max_lon"]
            or max_lat < c_bbox["min_lat"]
            or min_lat > c_bbox["max_lat"]
        )

        if not intersects:
            issues.append(
                ValidationIssue(
                    check_name="spatial_extent_bounding_box",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Dataset bounding box [{min_lon:.3f}, {min_lat:.3f}, {max_lon:.3f}, {max_lat:.3f}] "
                        f"does not intersect the Chamoli District regional envelope."
                    ),
                    details={
                        "dataset_bounds": [min_lon, min_lat, max_lon, max_lat],
                        "chamoli_bounds": c_bbox,
                    },
                )
            )
    except Exception as e:
        issues.append(
            ValidationIssue(
                check_name="spatial_extent_check_error",
                severity=ValidationSeverity.WARNING,
                message=f"Could not compute spatial bounds for verification: {str(e)}",
            )
        )

    return issues
