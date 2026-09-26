"""
CRS and Spatial Reference Definitions.
Chamoli DSS canonical projected CRS is EPSG:32644 (UTM Zone 44N).
API interchange and display CRS is EPSG:4326 (WGS 84).
"""
from dataclasses import dataclass
from typing import Tuple, Optional
import pyproj

# Frozen CRS Definitions
CANONICAL_PROJECTED_CRS_EPSG: int = 32644  # WGS 84 / UTM Zone 44N
CANONICAL_PROJECTED_CRS_STR: str = "EPSG:32644"

INTERCHANGE_CRS_EPSG: int = 4326  # WGS 84 Geographic
INTERCHANGE_CRS_STR: str = "EPSG:4326"

# Chamoli District Approximate Bounding Box (WGS84 Degrees)
# Latitude: ~29.98°N to ~31.07°N, Longitude: ~79.03°E to ~80.10°E
# Generous envelope for spatial sanity checks:
CHAMOLI_BBOX_WGS84 = {
    "min_lon": 78.50,
    "max_lon": 80.50,
    "min_lat": 29.50,
    "max_lat": 31.50
}

@dataclass(frozen=True)
class SpatialBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    crs: str

    def intersects(self, other: "SpatialBounds") -> bool:
        """Check if two bounding boxes intersect."""
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_y < other.min_y
            or self.min_y > other.max_y
        )

def validate_crs_string(crs_input: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and normalize a CRS definition string.
    Returns (is_valid, normalized_crs_str, error_message).
    """
    if not crs_input:
        return False, None, "CRS is missing or null"
    
    try:
        crs_obj = pyproj.CRS.from_user_input(crs_input)
        auth_name = crs_obj.to_authority()
        if auth_name:
            norm_str = f"{auth_name[0]}:{auth_name[1]}"
        else:
            norm_str = crs_obj.to_string()
        return True, norm_str, None
    except Exception as e:
        return False, None, f"Invalid CRS format '{crs_input}': {str(e)}"
