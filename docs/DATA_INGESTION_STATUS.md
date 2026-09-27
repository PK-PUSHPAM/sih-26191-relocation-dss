# Chamoli Data Ingestion Status

## Current verified source

The first production data source is the Census of India 2011 Primary Census Abstract (PCA TV) for Chamoli district.

Official catalog:
- Reference: PC11_PCA-TV-0502
- Producer: Office of the Registrar General & Census Commissioner, India
- Geographic granularity: district, sub-district, village, town and ward
- Relevant fields: village/location code, village name, households and population.

The source is listed in config/sources.yaml as census_2011_basic_population_village.

## Ingestion behavior

scripts/ingest_chamoli_census.py:
1. Downloads the official Census workbook.
2. Calculates SHA-256 for provenance.
3. Identifies the village-level PCA table.
4. Filters Chamoli administrative records.
5. Rejects missing population/household values.
6. Rejects invalid negative values.
7. Rejects duplicate location codes.
8. Writes a curated CSV and provenance manifest.

The script does not create coordinates. Census population tables do not provide the spatial geometry required by the habitation.geom PostGIS field. Therefore no coordinate is guessed from a village name.

## Why the dashboard can still be empty

The API habitation entity requires both Census population/household attributes and spatial geometry in canonical analysis CRS EPSG:32644.

The repository now has an executable Census ingestion path, but the authoritative settlement geometry dataset is still not checked into the repository. The next ingestion step is a spatial settlement layer from an approved source such as Bhuvan, with exact source/version/checksum recorded before database loading.

No vulnerability, hazard, priority, suitability or capacity values are fabricated merely to make the dashboard non-empty.

## Official references

- Census village population catalog: https://censusindia.gov.in/nada/index.php/catalog/42559
- Census Chamoli District Census Handbook: https://censusindia.gov.in/nada/index.php/catalog/1306
- Bhuvan developer documentation: https://bhuvan.nrsc.gov.in/wiki/index.php/Information_for_Developers
