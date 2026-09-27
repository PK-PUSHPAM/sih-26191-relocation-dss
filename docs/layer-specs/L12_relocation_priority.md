# L12 — Relocation Priority Engine

Status: IMPLEMENTED — verification pending local full-suite verification
Model: L12-relocation-priority-1.0
Formula: RP-0.40-0.25-0.20-0.10-0.05

## Frozen rule

RP = 0.40 Risk + 0.25 Exposed_Pop + 0.20 Vulnerability + 0.10 Response_Difficulty + 0.05 Recurrence

All five formula components are normalized to [0,1].

## Schema alignment

The existing priority.exposed_pop field stores raw exposed population as INT, while the frozen formula requires a normalized population component. The repository does not define a scientifically justified normalization function. Therefore L12 requires both exposed_pop (raw persistence count) and exposed_pop_score (already-derived normalized [0,1] population indicator). L12 does not invent a population normalization rule.

## Inputs

Each habitation requires habitation_id, risk [0,1], exposed_pop >= 0, exposed_pop_score [0,1], vulnerability [0,1], response_difficulty [0,1], and recurrence [0,1].

Missing values produce non_evaluable and never become zero. Invalid values produce invalid and never yield a score.

## Tiers

- Immediate: RP >= 0.75
- Short-term: 0.55 <= RP < 0.75
- Medium-term: 0.35 <= RP < 0.55
- Monitor: RP < 0.35

## Output

Persistence-ready fields match the priority table: habitation_id, risk, exposed_pop, vulnerability, response_difficulty, recurrence, priority_score, tier.

Application records also carry quality state and explanation/provenance.

## Boundaries

L09 supplies vulnerability. L08/L07-derived processing supplies habitation risk. Exposed-population raw count and normalized score must be sourced or derived upstream. Response difficulty and recurrence must already be normalized. L12 performs no database writes, migrations, ML, forecasting, interpolation, or optimization.

## Acceptance criteria

1. Frozen weights applied exactly.
2. All formula components normalized to [0,1].
3. Missing inputs remain non-evaluable.
4. Invalid inputs never yield a valid score.
5. Tier boundaries are exact.
6. Persistence names remain compatible with the existing priority schema.
7. Provenance is carried.
8. No unsupported population normalization formula is invented.
