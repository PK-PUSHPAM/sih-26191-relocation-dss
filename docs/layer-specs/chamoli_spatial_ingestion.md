# Chamoli spatial habitation ingestion

## Sources

- Survey of India Village Boundary Database: official Uttarakhand village-boundary shapefile (`UTTARAKHAND.zip`).
- Census 2011 Chamoli village population table produced by `scripts/ingest_chamoli_census.py`.

## Matching contract

Spatial and population records are joined only by the authoritative village identifier:

`Census Town/Village code == Survey of India Vill_LGD`

Village-name matching is deliberately disabled. No coordinates, geometry, population, or household values are invented or imputed.

## SOI filtering

Only records satisfying all of the following are treated as rural habitation boundaries:

- `STATE_LGD = 05`
- `Dist_LGD = 057`
- `Vill_Cat = RURAL`
- `Vill_LGD` is a unique six-digit identifier

For the supplied official Uttarakhand file, the Chamoli subset contains 1,237 records overall, including 1,180 rural records. The non-rural categories are not used as rural habitation polygons.

## Output

Run:

```powershell
python scripts/ingest_chamoli_spatial.py
```

Inputs:

- `data/raw/UTTARAKHAND.zip`
- `data/curated/chamoli_villages_population_2011.csv`

Output:

- `data/curated/chamoli_habitations_spatial_2011.gpkg`
- `data/curated/chamoli_census_unmatched_to_soi.csv`
- `data/curated/chamoli_soi_unmatched_to_census.csv`
- `data/curated/chamoli_spatial_match_manifest.txt`

The GeoPackage is reprojected to the project's canonical analysis CRS, EPSG:32644.

Unmatched records are explicitly reported rather than silently discarded. A complete match is **not** assumed until the actual Census CSV is processed against the supplied SOI file.