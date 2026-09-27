import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from scripts.load_chamoli_habitations_postgis import validate_artifact


def _artifact(rows, crs="EPSG:32644"):
    return gpd.GeoDataFrame(
        rows,
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]) for _ in rows],
        crs=crs,
    )


def test_validate_artifact_accepts_verified_shape():
    gdf = _artifact(
        [{
            "location_code": "05 057 00284 040808 0000",
            "village_lgd": "040808",
            "village_name": "Mana Rural",
            "population_2011": 1214,
            "households_2011": 558,
        }]
    )
    assert len(validate_artifact(gdf)) == 1


def test_validate_artifact_rejects_missing_population():
    gdf = _artifact(
        [{
            "location_code": "05 057 00284 040808 0000",
            "village_lgd": "040808",
            "village_name": "Mana Rural",
            "population_2011": None,
            "households_2011": 558,
        }]
    )
    with pytest.raises(ValueError, match="NULL population_2011"):
        validate_artifact(gdf)


def test_validate_artifact_rejects_duplicate_village_code():
    gdf = _artifact(
        [
            {
                "location_code": "05 057 00284 040808 0000",
                "village_lgd": "040808",
                "village_name": "Mana Rural",
                "population_2011": 1214,
                "households_2011": 558,
            },
            {
                "location_code": "05 057 00284 040809 0000",
                "village_lgd": "040808",
                "village_name": "Duplicate",
                "population_2011": 90,
                "households_2011": 10,
            },
        ]
    )
    with pytest.raises(ValueError, match="duplicate village_lgd"):
        validate_artifact(gdf)


def test_validate_artifact_rejects_wrong_crs():
    gdf = _artifact(
        [{
            "location_code": "05 057 00284 040808 0000",
            "village_lgd": "040808",
            "village_name": "Mana Rural",
            "population_2011": 1214,
            "households_2011": 558,
        }],
        crs="EPSG:4326",
    )
    with pytest.raises(ValueError, match="Expected artifact CRS"):
        validate_artifact(gdf)
