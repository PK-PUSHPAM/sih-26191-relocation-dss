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
SOURCE_URL = (
    "https://censusindia.gov.in/nada/index.php/catalog/42559/"
    "download/46185/2011-IndiaStateDistSbDistTwn-0000.xlsx"
)
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
        cols = [norm(c) for c in df.columns]
        has_area = any("area_name" in c for c in cols)
        has_population = any("population_total" in c for c in cols)
        has_location = any("location_code" in c for c in cols)
        if has_area and has_population and has_location:
            candidates.append((sheet_name, df))

    if not candidates:
        raise ValueError(
            "Could not identify the Census village table. "
            "Inspect the downloaded workbook sheets before changing the parser."
        )

    candidates.sort(
        key=lambda item: (
            0 if any(x in item[0].lower() for x in ("village", "pca", "tv")) else 1,
            item[0],
        )
    )
    return candidates[0][1]


def normalize_chamoli_population(xlsx: Path) -> pd.DataFrame:
    sheets = pd.read_excel(xlsx, sheet_name=None, dtype=str)
    df = find_village_frame(sheets)

    location_col = find_column(df.columns, "location_code")
    area_col = find_column(df.columns, "area_name")
    population_col = find_column(df.columns, "population_total", "total_population_persons")
    households_col = find_column(df.columns, "number_of_households")

    if not all((location_col, area_col, population_col, households_col)):
        raise ValueError(
            "Required Census columns could not be resolved: "
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

    out = out[
        out["village_name"].notna()
        & ~out["village_name"].str.contains(
            r"\b(district|sub[- ]district|total|urban|rural|ward)\b",
            case=False,
            na=False,
        )
    ].copy()

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
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--curated-dir", type=Path, default=Path("data/curated"))
    args = parser.parse_args()

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.curated_dir.mkdir(parents=True, exist_ok=True)

    raw_path = args.raw_dir / "2011-IndiaStateDistSbDistTwn-0000.xlsx"
    print(f"Downloading official Census source: {args.url}")
    try:
        urllib.request.urlretrieve(args.url, raw_path)
    except Exception as exc:
        raise SystemExit(
            "Census download failed. Use --url with the current download link "
            "shown on the official Census catalog page."
        ) from exc

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
