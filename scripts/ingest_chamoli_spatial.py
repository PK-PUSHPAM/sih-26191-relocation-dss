#!/usr/bin/env python3
"""
Build the Chamoli spatial habitation artifact from official SOI boundaries
and the already-curated Census 2011 village population table.

Matching is intentionally identifier-first:
  Census Town/Village code == Survey of India Vill_LGD

No village-name fuzzy matching, coordinate invention, or population imputation
is performed. Unmatched records are written to explicit CSV reports.
"""
from __future__ import annotations

import argparse
import re
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

STATE_LGD = "05"
DISTRICT_LGD = "057"
TARGET_CRS = "EPSG:32644"
REQUIRED_SOI_COLUMNS = {
    "STATE_LGD",
    "Dist_LGD",
    "District",
    "Sub_dist",
    "Vill_name",
    "Vill_Cat",
    "Vill_LGD",
    "geometry",
}
REQUIRED_CENSUS_COLUMNS = {
    "location_code",
    "village_name",
    "population_2011",
    "households_2011",
}


def _village_code(location_code: object) -> str:
    value = re.sub(r"\s+", " ", str(location_code).strip())
    match = re.fullmatch(r"05 057 \d{5} (\d{6}) \d{4}", value)
    if not match:
        raise ValueError(
            f"Unsupported Census location_code format: {location_code!r}. "
            "Expected '05 057 <5-digit-subdistrict> <6-digit-village> <4-digit-ward>'."
        )
    return match.group(1)


def load_soi_rural_boundaries(shapefile: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shapefile)

    missing = REQUIRED_SOI_COLUMNS - set(gdf.columns)
    if missing:
        raise ValueError(f"SOI boundary file is missing required columns: {sorted(missing)}")

    selected = gdf[
        gdf["STATE_LGD"].astype(str).str.strip().eq(STATE_LGD)
        & gdf["Dist_LGD"].astype(str).str.strip().eq(DISTRICT_LGD)
        & gdf["Vill_Cat"].astype(str).str.strip().str.upper().eq("RURAL")
    ].copy()

    if selected.empty:
        raise ValueError("SOI boundary file contains no Chamoli rural village polygons.")

    selected["Vill_LGD"] = selected["Vill_LGD"].astype(str).str.strip().str.zfill(6)
    if not selected["Vill_LGD"].str.fullmatch(r"\d{6}").all():
        raise ValueError("SOI rural village identifiers contain non-6-digit Vill_LGD values.")

    if selected["Vill_LGD"].duplicated().any():
        dupes = selected.loc[selected["Vill_LGD"].duplicated(), "Vill_LGD"].tolist()
        raise ValueError(f"Duplicate SOI rural Vill_LGD identifiers detected: {dupes[:10]}")

    if selected.crs is None:
        raise ValueError("SOI boundary CRS is missing; spatial reprojection is unsafe.")

    if selected.geometry.is_empty.any() or selected.geometry.isna().any():
        raise ValueError("SOI rural boundaries contain empty or NULL geometries.")

    if (~selected.geometry.is_valid).any():
        bad = selected.loc[~selected.geometry.is_valid, "Vill_LGD"].tolist()
        raise ValueError(
            f"SOI rural boundaries contain invalid geometries for Vill_LGD: {bad[:10]}"
        )

    return selected


def load_census_table(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype={"location_code": str})

    missing = REQUIRED_CENSUS_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Census table is missing required columns: {sorted(missing)}")

    out = df[list(REQUIRED_CENSUS_COLUMNS)].copy()
    out["location_code"] = out["location_code"].astype(str).str.strip()
    out["village_name"] = out["village_name"].astype(str).str.strip()
    out["village_lgd"] = out["location_code"].map(_village_code)

    for column in ("population_2011", "households_2011"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any():
            raise ValueError(f"Census {column} contains missing/non-numeric values.")
        if (out[column] < 0).any():
            raise ValueError(f"Census {column} contains negative values.")

    if out["location_code"].duplicated().any():
        raise ValueError("Duplicate Census location_code values detected.")

    if out["village_lgd"].duplicated().any():
        dupes = out.loc[out["village_lgd"].duplicated(), "village_lgd"].tolist()
        raise ValueError(
            "Multiple Census records map to the same Town/Village code: "
            f"{dupes[:10]}"
        )

    return out.sort_values("village_lgd").reset_index(drop=True)


def match_census_to_soi(
    census: pd.DataFrame, soi_rural: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame]:
    soi = soi_rural.copy()
    census_codes = set(census["village_lgd"])
    soi_codes = set(soi["Vill_LGD"])

    census_unmatched = census[~census["village_lgd"].isin(soi_codes)].copy()
    soi_unmatched = soi[~soi["Vill_LGD"].isin(census_codes)].copy()

    matched = soi.merge(
        census,
        left_on="Vill_LGD",
        right_on="village_lgd",
        how="inner",
        validate="one_to_one",
        suffixes=("_soi", "_census"),
    )

    matched = matched.rename(
        columns={
            "Vill_LGD": "village_lgd",
            "Vill_name": "soi_village_name",
            "Sub_dist": "soi_subdistrict",
        }
    )

    keep = [
        "location_code",
        "village_lgd",
        "village_name",
        "soi_village_name",
        "soi_subdistrict",
        "population_2011",
        "households_2011",
        "STATE_LGD",
        "Dist_LGD",
        "Vill_Cat",
        "geometry",
    ]
    matched = matched[keep].copy()

    if matched.empty:
        raise ValueError("No Census village records matched SOI rural boundaries by Vill_LGD.")

    return matched, census_unmatched, soi_unmatched


def build_artifact(
    soi_zip: Path, census_csv: Path, output_gpkg: Path
) -> tuple[int, int, int]:
    if not soi_zip.is_file():
        raise FileNotFoundError(f"SOI ZIP not found: {soi_zip}")
    if not census_csv.is_file():
        raise FileNotFoundError(f"Census CSV not found: {census_csv}")

    with tempfile.TemporaryDirectory(prefix="soi_uttarakhand_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(soi_zip) as archive:
            members = [m for m in archive.namelist() if m.lower().endswith(".shp")]
            if len(members) != 1:
                raise ValueError(
                    f"Expected exactly one shapefile in SOI ZIP; found {len(members)}: {members}"
                )
            archive.extractall(tmp_path)
            shapefile = tmp_path / members[0]

        soi = load_soi_rural_boundaries(shapefile)
        census = load_census_table(census_csv)
        matched, census_unmatched, soi_unmatched = match_census_to_soi(census, soi)

        matched = matched.to_crs(TARGET_CRS)
        output_gpkg.parent.mkdir(parents=True, exist_ok=True)
        matched.to_file(
            output_gpkg,
            layer="habitations",
            driver="GPKG",
        )

        report_dir = output_gpkg.parent
        census_unmatched.to_csv(
            report_dir / "chamoli_census_unmatched_to_soi.csv", index=False
        )
        soi_unmatched.drop(columns="geometry").to_csv(
            report_dir / "chamoli_soi_unmatched_to_census.csv", index=False
        )

        (report_dir / "chamoli_spatial_match_manifest.txt").write_text(
            "\n".join(
                [
                    "dataset_id=chamoli_habitations_spatial_2011",
                    "boundary_source=Survey of India Village Boundary Database",
                    "boundary_source_file=UTTARAKHAND.zip",
                    "population_source=census_2011_basic_population_village",
                    f"analysis_crs={TARGET_CRS}",
                    f"soi_chamoli_rural_rows={len(soi)}",
                    f"matched_rows={len(matched)}",
                    f"census_unmatched_rows={len(census_unmatched)}",
                    f"soi_unmatched_rows={len(soi_unmatched)}",
                    "match_key=Census Town/Village code == Survey of India Vill_LGD",
                    "name_matching=DISABLED",
                    "geometry_invented=FALSE",
                    "population_imputed=FALSE",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        return len(matched), len(census_unmatched), len(soi_unmatched)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--soi-zip", type=Path, default=Path("data/raw/UTTARAKHAND.zip")
    )
    parser.add_argument(
        "--census-csv",
        type=Path,
        default=Path("data/curated/chamoli_villages_population_2011.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/curated/chamoli_habitations_spatial_2011.gpkg"),
    )
    args = parser.parse_args()

    matched, census_unmatched, soi_unmatched = build_artifact(
        args.soi_zip, args.census_csv, args.output
    )

    print(f"Matched spatial habitation records: {matched}")
    print(f"Census records without SOI rural polygon: {census_unmatched}")
    print(f"SOI rural polygons without Census record: {soi_unmatched}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
