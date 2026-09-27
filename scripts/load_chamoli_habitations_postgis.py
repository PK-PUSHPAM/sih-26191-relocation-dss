#!/usr/bin/env python3
"""
Load the verified Chamoli Census + Survey of India spatial habitation artifact
into the project's PostGIS core entities.

The loader is deliberately data-only: it does not calculate risk, vulnerability,
capacity, suitability, priority, or optimization outputs.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import date
from pathlib import Path
import sys

import geopandas as gpd
from sqlalchemy import text
from shapely import force_2d

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.config import get_source_by_id
from src.db.session import get_db


CENSUS_SOURCE_ID = "census_2011_basic_population_village"
SOI_SOURCE_ID = "survey_of_india_uttarakhand_village_boundaries"
TARGET_CRS = "EPSG:32644"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_2d_geometry(geometry):
    if geometry is None:
        return None
    # PostGIS core tables are 2D geometry columns. The verified SOI artifact
    # can carry a constant Z=0 ordinate, so strip Z explicitly rather than
    # relying on a database-side cast that may reject the insert.
    return force_2d(geometry)


def validate_artifact(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    required = {
        "location_code",
        "village_lgd",
        "village_name",
        "population_2011",
        "households_2011",
        "geometry",
    }
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(f"Spatial habitation artifact is missing columns: {sorted(missing)}")
    if gdf.crs is None:
        raise ValueError("Spatial habitation artifact CRS is missing.")
    if str(gdf.crs) != TARGET_CRS:
        raise ValueError(f"Expected artifact CRS {TARGET_CRS}, got {gdf.crs}.")
    if gdf.empty:
        raise ValueError("Spatial habitation artifact is empty.")
    if gdf["village_lgd"].isna().any():
        raise ValueError("Spatial habitation artifact contains NULL village_lgd values.")
    if gdf["village_lgd"].astype(str).str.fullmatch(r"\d{6}").eq(False).any():
        raise ValueError("Spatial habitation artifact contains invalid village_lgd values.")
    if gdf["village_lgd"].duplicated().any():
        raise ValueError("Spatial habitation artifact contains duplicate village_lgd values.")
    for column in ("population_2011", "households_2011"):
        if gdf[column].isna().any():
            raise ValueError(f"Spatial habitation artifact contains NULL {column} values.")
        if (gdf[column] < 0).any():
            raise ValueError(f"Spatial habitation artifact contains negative {column} values.")
    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        raise ValueError("Spatial habitation artifact contains NULL or empty geometries.")
    if (~gdf.geometry.is_valid).any():
        raise ValueError("Spatial habitation artifact contains invalid geometries.")
    return gdf


def _source_meta(source_id: str) -> dict:
    meta = get_source_by_id(source_id)
    if not meta:
        raise ValueError(f"Source is not registered in config/sources.yaml: {source_id}")
    return meta


def _upsert_source(session, source_id: str, checksum: str) -> None:
    meta = _source_meta(source_id)
    session.execute(
        text(
            """
            INSERT INTO data_source
                (source_id, agency, url, access_date, license, version, checksum)
            VALUES
                (:source_id, :agency, :url, :access_date, :license, :version, :checksum)
            ON CONFLICT (source_id) DO UPDATE SET
                agency = EXCLUDED.agency,
                url = EXCLUDED.url,
                access_date = EXCLUDED.access_date,
                license = EXCLUDED.license,
                version = EXCLUDED.version,
                checksum = EXCLUDED.checksum
            """
        ),
        {
            "source_id": source_id,
            "agency": meta["authority"],
            "url": meta.get("official_url"),
            "access_date": date.today(),
            "license": meta.get("license", "Government Open Publication"),
            "version": "2011" if source_id == CENSUS_SOURCE_ID else "official",
            "checksum": checksum,
        },
    )


def load_artifact(artifact: Path, census_checksum: str, soi_checksum: str) -> int:
    gdf = validate_artifact(gpd.read_file(artifact))

    with get_db() as session:
        _upsert_source(session, CENSUS_SOURCE_ID, census_checksum)
        _upsert_source(session, SOI_SOURCE_ID, soi_checksum)

        for row in gdf.itertuples(index=False):
            village_code = str(row.village_lgd)
            habitation_id = f"chamoli_village_{village_code}"
            admin_unit_id = habitation_id
            geometry_2d = _normalize_2d_geometry(row.geometry)
            wkt = geometry_2d.wkt

            session.execute(
                text(
                    """
                    INSERT INTO admin_unit
                        (unit_id, type, parent_id, name, code, geom)
                    VALUES
                        (:unit_id, 'village', NULL, :name, :code,
                         ST_Multi(ST_GeomFromText(:wkt, 32644)))
                    ON CONFLICT (unit_id) DO UPDATE SET
                        type = EXCLUDED.type,
                        name = EXCLUDED.name,
                        code = EXCLUDED.code,
                        geom = EXCLUDED.geom,
                        updated_at = NOW()
                    """
                ),
                {
                    "unit_id": admin_unit_id,
                    "name": str(row.village_name),
                    "code": village_code,
                    "wkt": wkt,
                },
            )

            session.execute(
                text(
                    """
                    INSERT INTO habitation
                        (habitation_id, admin_unit_id, name, population_year,
                         population, households, geom, source_id)
                    VALUES
                        (:habitation_id, :admin_unit_id, :name, 2011,
                         :population, :households,
                         ST_GeomFromText(:wkt, 32644), :source_id)
                    ON CONFLICT (habitation_id) DO UPDATE SET
                        admin_unit_id = EXCLUDED.admin_unit_id,
                        name = EXCLUDED.name,
                        population_year = EXCLUDED.population_year,
                        population = EXCLUDED.population,
                        households = EXCLUDED.households,
                        geom = EXCLUDED.geom,
                        source_id = EXCLUDED.source_id,
                        updated_at = NOW()
                    """
                ),
                {
                    "habitation_id": habitation_id,
                    "admin_unit_id": admin_unit_id,
                    "name": str(row.village_name),
                    "population": int(row.population_2011),
                    "households": int(row.households_2011),
                    "wkt": wkt,
                    "source_id": CENSUS_SOURCE_ID,
                },
            )

    return len(gdf)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        type=Path,
        default=REPO_ROOT / "data/curated/chamoli_habitations_spatial_2011.gpkg",
    )
    parser.add_argument(
        "--census-source-file",
        type=Path,
        default=REPO_ROOT / "data/curated/chamoli_villages_population_2011.csv",
    )
    parser.add_argument(
        "--soi-source-file",
        type=Path,
        default=REPO_ROOT / "data/raw/UTTARAKHAND.zip",
    )
    args = parser.parse_args()

    for path in (args.artifact, args.census_source_file, args.soi_source_file):
        if not path.is_file():
            raise FileNotFoundError(f"Required source file not found: {path}")

    count = load_artifact(
        args.artifact,
        sha256_file(args.census_source_file),
        sha256_file(args.soi_source_file),
    )
    print(f"Loaded verified Chamoli habitation records: {count}")
    print(f"Artifact: {args.artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
