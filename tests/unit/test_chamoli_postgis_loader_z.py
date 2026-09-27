import geopandas as gpd
from shapely.geometry import Polygon
from shapely.geometry import Point

from scripts.load_chamoli_habitations_postgis import _normalize_2d_geometry


def test_normalize_2d_geometry_strips_z_dimension():
    geometry = Point(10, 20, 30)
    normalized = _normalize_2d_geometry(geometry)
    assert normalized.has_z is False
    assert normalized.wkt == "POINT (10 20)"


def test_normalize_2d_geometry_preserves_polygon_shape():
    geometry = Polygon(
        [
            (0, 0, 5),
            (1, 0, 5),
            (1, 1, 5),
            (0, 0, 5),
        ]
    )
    normalized = _normalize_2d_geometry(geometry)
    assert normalized.has_z is False
    assert normalized.geom_type == "Polygon"
