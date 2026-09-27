#!/usr/bin/env python3
"""
Fetch and normalize the official Census 2011 Chamoli village population workbook.

This script stops at a validated tabular artifact. It does not invent geometry,
risk, vulnerability, or hazard values.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import urllib.request
from pathlib import Path

import pandas as pd

SOURCE_ID = "census_2011_basic_population_village"
SOURCE_URL = "https://censusindia.gov.in/nada/index.php/catalog/6248"
STATE_CODE = "05"
DISTRICT_CODE = "057"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def find_column(columns, *needles: str) -> str | None:
    normalized = {norm(c): c for c in columns}
    for needle in needles:
        target = norm(needle)
        for key, original in normalized.items():
            if target == key or target in key or key in target:
                return original
    return None


def find_village_frame(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    candidates = []

    for sheet_name, df in sheets.items():
        if df.empty:
            continue

        cols = {norm(c) for c in df.columns}

        # Dedicated PCA-TV exports: Location Code / Area Name / population / households.
        if (
            any("location_code" in c for c in cols)
            and any("area_name" in c for c in cols)
            and any("population_total" in c or "total_population" in c for c in cols)
            and any("number_of_households" in c for c in cols)
        ):
            candidates.append(("pca_tv", sheet_name, df))

        # The national Basic Population workbook has a Data sheet with
        # State/District/Subdistt/Town-Village/Level fields. It is not itself
        # a village-only export; village rows must be explicitly selected.
        elif (
            any(norm(c) == "state" for c in df.columns)
            and any(norm(c) == "district" for c in df.columns)
            and any(norm(c) == "subdistt" for c in df.columns)
            and any(norm(c) == "town_village" for c in df.columns)
            and any(norm(c) == "level" for c in df.columns)
            and any(norm(c) == "name" for c in df.columns)
            and any(norm(c) == "no_hh" for c in df.columns)
            and any(norm(c) == "tot_p" for c in df.columns)
        ):
            candidates.append(("basic_population", sheet_name, df))

    if not candidates:
        raise ValueError(
            "Could not identify a supported Census PCA-TV workbook structure. "
            "Expected either a PCA-TV export with Location Code/Area Name columns "
            "or the Basic Population Data sheet."
        )

    candidates.sort(key=lambda item: (0 if item[0] == "pca_tv" else 1, item[1]))
    kind, _, frame = candidates[0]
    frame = frame.copy()
    frame.attrs["source_structure"] = kind
    return frame


def normalize_chamoli_population(xlsx: Path) -> pd.DataFrame:
    sheets = pd.read_excel(xlsx, sheet_name=None, dtype=str)
    df = find_village_frame(sheets)
    structure = df.attrs.get("source_structure")

    if structure == "pca_tv":
        location_col = find_column(df.columns, "location_code")
        area_col = find_column(df.columns, "area_name")
        population_col = find_column(df.columns, "population_total", "total_population_persons")
        households_col = find_column(df.columns, "number_of_households")

        if not all((location_col, area_col, population_col, households_col)):
            raise ValueError(
                "Required PCA-TV columns could not be resolved: "
                f"location={location_col}, area={area_col}, "
                f"population={population_col}, households={households_col}"
            )

        out = pd.DataFrame(
            {
                "location_code": df[location_col].astype(str).str.strip(),
                "village_name": df[area_col].astype(str).str.strip(),
                "population_2011": pd.to_numeric(df[population_col], errors="coerce"),
                "households_2011": pd.to_numeric(df[households_col], errors="coerce"),
            }
        )

        compact_code = out["location_code"].str.replace(r"\s+", "", regex=True)
        out = out[
            compact_code.str.startswith(STATE_CODE + DISTRICT_CODE)
            & ~compact_code.str.endswith("0000000000")
        ].copy()

        # PCA-TV exports can contain district/sub-district/town aggregate rows.
        out = out[
            ~out["village_name"].str.contains(
                r"\b(district|sub[- ]district|total|urban|rural|ward)\b",
                case=False,
                na=False,
            )
        ].copy()

    else:
        def col(name: str) -> str:
            for candidate in df.columns:
                if norm(candidate) == name:
                    return candidate
            raise ValueError(f"Required Basic Population column missing: {name}")

        state = df[col("state")].astype(str).str.strip().str.zfill(2)
        district = df[col("district")].astype(str).str.strip().str.zfill(3)
        subdistt = df[col("subdistt")].astype(str).str.strip().str.zfill(5)
        town_village = df[col("town_village")].astype(str).str.strip().str.zfill(6)
        level = df[col("level")].astype(str).str.strip().str.upper()
        name = df[col("name")].astype(str).str.strip()
        tru = df[find_column(df.columns, "tru")].astype(str).str.strip().str.upper() if find_column(df.columns, "tru") else None

        village_mask = (
            state.eq(STATE_CODE)
            & district.eq(DISTRICT_CODE)
            & level.eq("VILLAGE")
            & town_village.ne("000000")
        )
        if tru is not None:
            total_mask = tru.eq("TOTAL")
            if total_mask.any():
                village_mask &= total_mask

        selected = df.loc[village_mask].copy()
        if selected.empty:
            raise ValueError(
                "The supplied Census Basic Population workbook contains no Chamoli "
                "village-level records. It is a district/sub-district/town extract "
                "for this release. Use the official Chamoli PCA-TV workbook from "
                "catalog 6248 instead."
            )

        out = pd.DataFrame(
            {
                "location_code": (
                    state.loc[selected.index]
                    + " "
                    + district.loc[selected.index]
                    + " "
                    + subdistt.loc[selected.index]
                    + " "
                    + town_village.loc[selected.index]
                    + " "
                    + selected[col("ward")].astype(str).str.strip().str.zfill(4)
                    if "ward" in {norm(c) for c in df.columns}
                    else state.loc[selected.index]
                    + " "
                    + district.loc[selected.index]
                    + " "
                    + subdistt.loc[selected.index]
                    + " "
                    + town_village.loc[selected.index]
                ),
                "village_name": name.loc[selected.index],
                "population_2011": pd.to_numeric(selected[col("tot_p")], errors="coerce"),
                "households_2011": pd.to_numeric(selected[col("no_hh")], errors="coerce"),
            }
        )

    if out.empty:
        raise ValueError("No Chamoli village records remained after filtering.")

    if out[["population_2011", "households_2011"]].isna().any().any():
        raise ValueError(
            "Census population/household values contain missing records. "
            "They are not silently converted to zero."
        )

    out["population_2011"] = out["population_2011"].astype("int64")
    out["households_2011"] = out["households_2011"].astype("int64")

    if (out["population_2011"] < 0).any() or (out["households_2011"] < 0).any():
        raise ValueError("Negative Census population/household values detected.")

    if out["location_code"].duplicated().any():
        raise ValueError("Duplicate Census location codes detected.")

    out.insert(0, "source_id", SOURCE_ID)
    out["source_year"] = 2011
    return out.sort_values("location_code").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=SOURCE_URL)
    parser.add_argument("--file", type=Path, help="Use an already-downloaded official Census Excel file.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--curated-dir", type=Path, default=Path("data/curated"))
    args = parser.parse_args()

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.curated_dir.mkdir(parents=True, exist_ok=True)

    raw_path = args.raw_dir / "chamoli_pca_tv_2011.xlsx"
    if args.file:
        if not args.file.is_file():
            raise SystemExit(f"Census Excel file not found: {args.file}")
        raw_path.write_bytes(args.file.read_bytes())
        print(f"Using downloaded Census source: {args.file}")
    else:
        print(f"Downloading official Census source: {args.url}")
        raise SystemExit(
            "Automatic download is not configured for this catalog page. "
            "Download the official Chamoli PCA-TV Excel file from catalog 6248 "
            "and rerun with --file."
        )

    checksum = sha256(raw_path)
    curated = normalize_chamoli_population(raw_path)
    output = args.curated_dir / "chamoli_villages_population_2011.csv"
    curated.to_csv(output, index=False)

    manifest = args.curated_dir / "chamoli_villages_population_2011_manifest.txt"
    manifest.write_text(
        "\n".join(
            [
                "dataset_id=chamoli_villages_population_2011",
                f"source_id={SOURCE_ID}",
                f"source_url={args.url}",
                "source_catalog=https://censusindia.gov.in/nada/index.php/catalog/6248",
                "source_year=2011",
                f"row_count={len(curated)}",
                f"raw_sha256={checksum}",
                "status=VALIDATED_TABULAR_ONLY",
                "geometry_status=NOT_PRESENT",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Curated rows: {len(curated)}")
    print(f"Output: {output}")
    print("Geometry was intentionally not invented; spatial loading remains separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
