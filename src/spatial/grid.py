"""
Spatial Grid and Coordinate Definitions for Layer L03.
Defines the canonical 30 m analysis grid for Chamoli District in EPSG:32644 (UTM Zone 44N).
"""
import math
from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict, Any
from affine import Affine
from shapely.geometry import Polygon, box
import geopandas as gpd

from src.common.crs import (
    CANONICAL_PROJECTED_CRS_EPSG,
    CANONICAL_PROJECTED_CRS_STR,
    CHAMOLI_BBOX_WGS84,
)

CANONICAL_RESOLUTION_METERS: float = 30.0
DEFAULT_NODATA_FLOAT: float = -9999.0
DEFAULT_NODATA_INT: int = -9999


@dataclass(frozen=True)
class CanonicalGridDefinition:
    """
    Defines the parameters of the deterministic 30 m analysis grid.
    All bounds are in EPSG:32644 coordinates (meters).
    """
    crs: str
    resolution: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    width: int   # Number of columns (nx)
    height: int  # Number of rows (ny)
    transform: Affine

    @property
    def total_cells(self) -> int:
        return self.width * self.height

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Return (minx, miny, maxx, maxy)."""
        return (self.x_min, self.y_min, self.x_max, self.y_max)

    def cell_id_from_row_col(self, row: int, col: int) -> int:
        """
        Compute deterministic 64-bit cell ID from row and column.
        Cell ID = row * width + col.
        """
        if not (0 <= row < self.height and 0 <= col < self.width):
            raise IndexError(f"Cell indices (row={row}, col={col}) out of grid bounds (h={self.height}, w={self.width})")
        return row * self.width + col

    def row_col_from_cell_id(self, cell_id: int) -> Tuple[int, int]:
        """Invert cell ID to (row, col)."""
        if not (0 <= cell_id < self.total_cells):
            raise IndexError(f"Cell ID {cell_id} out of bounds for grid with {self.total_cells} cells")
        row = cell_id // self.width
        col = cell_id % self.width
        return row, col

    def cell_center_coords(self, row: int, col: int) -> Tuple[float, float]:
        """Return projected (x, y) coordinates of the center of cell (row, col)."""
        x = self.x_min + (col + 0.5) * self.resolution
        y = self.y_max - (row + 0.5) * self.resolution
        return x, y

    def cell_polygon(self, row: int, col: int) -> Polygon:
        """Return Shapely Polygon bounding box for cell (row, col)."""
        x0 = self.x_min + col * self.resolution
        x1 = x0 + self.resolution
        y1 = self.y_max - row * self.resolution
        y0 = y1 - self.resolution
        return box(x0, y0, x1, y1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crs": self.crs,
            "resolution": self.resolution,
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
            "width": self.width,
            "height": self.height,
            "total_cells": self.total_cells,
            "transform": [
                self.transform.a, self.transform.b, self.transform.c,
                self.transform.d, self.transform.e, self.transform.f,
            ]
        }


def snap_coordinate_outward(val: float, resolution: float, mode: str) -> float:
    """
    Snap a coordinate outward to the nearest integer multiple of resolution.
    mode: 'floor' (for min_x, min_y) or 'ceil' (for max_x, max_y).
    """
    if mode == "floor":
        return math.floor(val / resolution) * resolution
    elif mode == "ceil":
        return math.ceil(val / resolution) * resolution
    else:
        raise ValueError(f"Unknown snapping mode '{mode}'. Must be 'floor' or 'ceil'.")


def create_canonical_grid(
    bounds: Tuple[float, float, float, float],
    resolution: float = CANONICAL_RESOLUTION_METERS,
    crs: str = CANONICAL_PROJECTED_CRS_STR,
) -> CanonicalGridDefinition:
    """
    Construct a deterministic canonical grid for a given bounding box in EPSG:32644.
    bounds: (min_x, min_y, max_x, max_y) in meters.
    Snaps bounds outward to ensure complete coverage.
    """
    raw_min_x, raw_min_y, raw_max_x, raw_max_y = bounds
    if raw_min_x >= raw_max_x or raw_min_y >= raw_max_y:
        raise ValueError(f"Invalid bounding box: {bounds}")

    snapped_min_x = snap_coordinate_outward(raw_min_x, resolution, "floor")
    snapped_min_y = snap_coordinate_outward(raw_min_y, resolution, "floor")
    snapped_max_x = snap_coordinate_outward(raw_max_x, resolution, "ceil")
    snapped_max_y = snap_coordinate_outward(raw_max_y, resolution, "ceil")

    width = int(round((snapped_max_x - snapped_min_x) / resolution))
    height = int(round((snapped_max_y - snapped_min_y) / resolution))

    # Affine transform: pixel size is +resolution in X, -resolution in Y (origin at top-left)
    transform = Affine(
        resolution, 0.0, snapped_min_x,
        0.0, -resolution, snapped_max_y
    )

    return CanonicalGridDefinition(
        crs=crs,
        resolution=resolution,
        x_min=snapped_min_x,
        y_min=snapped_min_y,
        x_max=snapped_max_x,
        y_max=snapped_max_y,
        width=width,
        height=height,
        transform=transform,
    )


def generate_grid_cells_gdf(
    grid_def: CanonicalGridDefinition,
    max_cells: Optional[int] = None,
) -> gpd.GeoDataFrame:
    """
    Generate a GeoDataFrame containing cell polygons and cell_ids for the grid.
    Useful for populating risk_cell spatial tables or vector overlays.
    """
    count = grid_def.total_cells if max_cells is None else min(grid_def.total_cells, max_cells)
    records = []

    for cell_id in range(count):
        row, col = grid_def.row_col_from_cell_id(cell_id)
        geom = grid_def.cell_polygon(row, col)
        records.append({
            "cell_id": cell_id,
            "row": row,
            "col": col,
            "geometry": geom,
        })

    gdf = gpd.GeoDataFrame(records, crs=grid_def.crs)
    return gdf
