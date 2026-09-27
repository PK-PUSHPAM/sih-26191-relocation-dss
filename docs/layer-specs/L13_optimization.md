# L13 — Allocation Optimization

**Status:** IMPLEMENTED — verification pending local full-suite re-run  \
**Model:** `L13-allocation-optimization-1.0`

## Frozen architecture

Decision variable: integer `x[h,s] >= 0`, persons allocated from habitation h to site s.

Objective:

`distance_weight * sum(distance[h,s] * x[h,s]) + unmet_penalty * sum(unmet[h]) + hazard_weight * sum(site_hazard[s] * x[h,s])`

Constraints:
1. allocation from a habitation cannot exceed its exposed population;
2. site allocation cannot exceed L11 effective carrying capacity;
3. only explicitly feasible habitation-site pairs may receive allocation;
4. allocation is integer and non-negative;
5. missing distance for a declared feasible pair is an error, never zero.

The architecture specification does not freeze numerical objective weights for distance, unmet demand, or hazard exposure. Therefore these are **required caller parameters**, recorded in provenance, rather than invented defaults.

## Inputs

- habitation ID + exposed population
- candidate site ID + L11 effective capacity
- site hazard in [0,1]
- explicit feasible habitation IDs per site
- distance for every feasible pair
- positive distance and unmet-demand weights; non-negative hazard weight

## Outputs

Persistence-ready allocation fields:
- habitation_id
- site_id
- allocated_population
- distance
- constraint_flags

Also returns unmet demand, solver status, objective value, and provenance metadata.

## Missing-data policy

Missing distance for a declared feasible pair is an error. It is never interpreted as zero distance.

A pair absent from the site's feasible-habitation list is infeasible and receives zero allocation.

Unknown habitation IDs listed in `feasible_habitations` are rejected.

Non-finite distance or objective-weight values are rejected.

No input is silently converted to zero.

## Solver

OR-Tools CP-SAT. The solver does not write to PostgreSQL/PostGIS; persistence is deferred to later integration.

Solver limits must be positive and finite; worker count must be a positive integer.

## Acceptance criteria

- capacity and demand constraints always hold;
- infeasible pairs receive zero allocation;
- unmet demand is explicit;
- objective components are auditable;
- solver status is preserved;
- no DB/API writes;
- deterministic model construction for fixed inputs and solver parameters;
- invalid/non-finite validation inputs are rejected explicitly.
