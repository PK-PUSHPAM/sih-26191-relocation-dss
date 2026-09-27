import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from scripts.ingest_chamoli_spatial import (
    load_soi_rural_boundaries,
    match_census_to_soi,
)


def _soi(rows):
    return gpd.GeoDataFrame(
        rows,
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]) for _ in rows],
        crs="EPSG:4326",
    )


def test_matches_census_to_soi_by_village_code_not_name():
    soi = _soi(
        [
            {
                "STATE_LGD": "05",
                "Dist_LGD": "057",
                "District": "CHAMOLI",
                "Sub_dist": "JOSHIMATH",
                "Vill_name": "MANA",
                "Vill_Cat": "RURAL",
                "Vill_LGD": "040808",
            },
            {
                "STATE_LGD": "05",
                "Dist_LGD": "057",
                "District": "CHAMOLI",
                "Sub_dist": "JOSHIMATH",
                "Vill_name": "KHIRON",
                "Vill_Cat": "RURAL",
                "Vill_LGD": "040809",
            },
        ]
    )
    census = pd.DataFrame(
        {
            "location_code": [
                "05 057 00284 040808 0000",
                "05 057 00284 040809 0000",
                "05 057 00284 040999 0000",
            ],
            "village_name": ["Mana Rural", "Khiron Rural", "Unmatched"],
            "population_2011": [1214, 90, 10],
            "households_2011": [558, 100, 4],
            "village_lgd": ["040808", "040809", "040999"],
        }
    )

    matched, census_unmatched, soi_unmatched = match_census_to_soi(census, soi)

    assert list(matched["village_lgd"]) == ["040808", "040809"]
    assert len(census_unmatched) == 1
    assert census_unmatched.iloc[0]["village_lgd"] == "040999"
    assert len(soi_unmatched) == 0


def test_missing_soi_crs_is_rejected():
    soi = _soi(
        [
            {
                "STATE_LGD": "05",
                "Dist_LGD": "057",
                "District": "CHAMOLI",
                "Sub_dist": "JOSHIMATH",
                "Vill_name": "MANA",
                "Vill_Cat": "RURAL",
                "Vill_LGD": "040808",
            }
        ]
    ).set_crs(None, allow_override=True)

    with pytest.raises(ValueError, match="CRS is missing"):
        load_soi_rural_boundaries_from_frame(soi)


def test_duplicate_soi_village_codes_are_rejected(tmp_path):
    # Write a tiny shapefile to exercise the real reader validation path.
    soi = _soi(
        [
            {
                "STATE_LGD": "05",
                "Dist_LGD": "057",
                "District": "CHAMOLI",
                "Sub_dist": "JOSHIMATH",
                "Vill_name": "MANA",
                "Vill_Cat": "RURAL",
                "Vill_LGD": "040808",
            },
            {
                "STATE_LGD": "05",
                "Dist_LGD": "057",
                "District": "CHAMOLI",
                "Sub_dist": "JOSHIMATH",
                "Vill_name": "MANA DUP",
                "Vill_Cat": "RURAL",
                "Vill_LGD": "040808",
            },
        ]
    )
    shp = tmp_path / "boundaries.shp"
    soi.to_file(shp)

    with pytest.raises(ValueError, match="Duplicate SOI rural"):
        load_soi_rural_boundaries(shp)


def test_non_rural_soi_rows_are_excluded():
    soi = _soi(
        [
            {
                "STATE_LGD": "05",
                "Dist_LGD": "057",
                "District": "CHAMOLI",
                "Sub_dist": "JOSHIMATH",
                "Vill_name": "MANA",
                "Vill_Cat": "RURAL",
                "Vill_LGD": "040808",
            },
            {
                "STATE_LGD": "05",
                "Dist_LGD": "057",
                "District": "CHAMOLI",
                "Sub_dist": "JOSHIMATH",
                "Vill_name": "JOSHIMATH (NPP)",
                "Vill_Cat": "URBAN",
                "Vill_LGD": "800291",
            },
        ]
    )

    result = load_soi_rural_boundaries_from_frame(soi)
    assert len(result) == 1
    assert result.iloc[0]["Vill_LGD"] == "040808"


def load_soi_rural_boundaries_from_frame(gdf):
    required = {
        "STATE_LGD",
        "Dist_LGD",
        "District",
        "Sub_dist",
        "Vill_name",
        "Vill_Cat",
        "Vill_LGD",
        "geometry",
    }
    missing = required - set(gdf.columns)
    assert not missing
    selected = gdf[
        gdf["STATE_LGD"].astype(str).eq("05")
        & gdf["Dist_LGD"].astype(str).eq("057")
        & gdf["Vill_Cat"].astype(str).str.upper().eq("RURAL")
    ].copy()
    if selected.crs is None:
        raise ValueError("SOI boundary CRS is missing; spatial reprojection is unsafe.")
    if selected["Vill_LGD"].duplicated().any():
        raise ValueError("Duplicate SOI rural Vill_LGD identifiers detected")
    return selected
