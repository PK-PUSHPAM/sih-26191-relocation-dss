# L10 — Relocation-Site Suitability Engine

**Status:** Implemented framework; authoritative Chamoli site inputs pending.

## Purpose

Evaluate candidate relocation-site polygons under the frozen SIH 26191 suitability model. L10 applies hard eligibility exclusions first, then computes a normalized suitability score for candidates with complete required inputs.

L10 is deterministic and persistence-ready. It does not write to the database, create migrations, call APIs, fabricate source data, or perform ML/forecasting.

## Frozen rule

**S = 0.30 Hsafe + 0.15 Slope + 0.15 Road + 0.15 Water + 0.10 Health + 0.05 Education + 0.05 LandUse + 0.05 Services**

Where:

**Hsafe = 1.0 − H**

and H is the L07 combined multi-hazard risk for the candidate location.

Weights are frozen by config/weights.yaml and the architecture/project-context specifications.

## Hard eligibility constraints

A candidate is rejected before scoring when any of these conditions is true:

- candidate intersects/is flagged as a L08 red zone;
- candidate is a water body;
- candidate is protected/restricted land;
- contiguous candidate area is below **1.0 hectare (10,000 m²)**;
- slope is above **30°**;
- road distance is above **2,000 m**.

The boundary values themselves are allowed (area >= 10,000 m², slope <= 30°, road_distance <= 2,000 m).

These constraints come from the frozen architecture and config/thresholds.yaml; they are not newly invented by L10.

## Input contract

Each SiteCandidateInput contains:

- site ID;
- Polygon geometry in the canonical projected coordinate system;
- L07 combined risk H in [0,1];
- seven already-derived normalized suitability indicators in [0,1]:
  - slope;
  - road access;
  - water availability;
  - healthcare access;
  - education access;
  - land use;
  - service proximity;
- raw slope in degrees for the hard constraint;
- road distance in metres for the hard constraint;
- Boolean hard-exclusion flags for red zone, water body, and protected land.

L10 does not invent normalization functions for the seven component indicators. Their normalized values must be supplied by the upstream data/GIS pipeline.

## Candidate geometry

The persistence contract requires candidate_site.geom to be a Polygon in EPSG:32644. L10 therefore accepts valid non-empty Polygon candidates only and derives area_m2 from the geometry.

This implementation evaluates candidate polygons supplied to the engine. Construction of those polygons from authoritative DEM/LULC/forest/road layers remains dependent on real source data and is not fabricated by the prototype.

## Data-quality policy

### Complete

All required constraints and all scoring indicators are present and valid. The site receives a suitability score and eligible status.

### Non-evaluable

A candidate passes the hard checks but one or more required scoring/eligibility inputs are missing. Missing values are **not converted to zero**. The site receives:

- suitability = NoData;
- quality_flag = non_evaluable;
- status = conditional.

### Invalid

A supplied numeric input is NaN, infinite, non-numeric, or outside its allowed range. The site receives:

- suitability = NoData;
- quality_flag = invalid;
- status = rejected.

A hard exclusion takes precedence over missing scoring data: an excluded candidate is rejected before scoring.

## Output contract

Each persistence-ready record contains:

- site_id;
- geometry;
- area_m2;
- suitability;
- status: eligible, conditional, or rejected;
- quality_flag;
- explanation, including exclusion reasons or suitability components.

The database candidate_site schema remains unchanged and L10 performs no database write.

## Explainability

For scored candidates, the explanation includes:

- Hsafe;
- each normalized component;
- weighted contribution of each component;
- exclusion reasons (empty for eligible candidates).

## Provenance

The L10 result metadata records:

- layer and model version;
- formula version and exact formula;
- frozen weights;
- hard-constraint thresholds;
- execution timestamp;
- CRS;
- quality/status states;
- missing/invalid-data policies;
- optional source metadata.

## Non-goals

L10 does not:

- create or invent authoritative Chamoli datasets;
- derive L07 hazard values;
- generate normalized factor values from guessed formulas;
- perform interpolation/resampling;
- calculate carrying capacity (L11);
- calculate relocation priority (L12);
- allocate people (L13);
- write database rows or migrations;
- expose APIs;
- use ML or forecasting.

## Version

- Model: L10-site-suitability-1.0
- Formula: S-0.30-0.15-0.15-0.15-0.10-0.05-0.05-0.05
