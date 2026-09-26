-- Migration 004: Analytical Persistence Entities (Schema definitions for L07-L13)
-- Purpose: Schema definitions for risk cells, vulnerability, candidate sites, capacity, priority, and allocation
-- Note: All foreign keys use ON DELETE RESTRICT to guarantee audit preservation and prevent silent cascade deletion of analytical history.

BEGIN;

-- 1. Canonical 30m Grid Risk Cells
CREATE TABLE IF NOT EXISTS risk_cell (
    cell_id BIGINT PRIMARY KEY,
    h_landslide NUMERIC(5,4),
    h_flood NUMERIC(5,4),
    h_rain NUMERIC(5,4),
    combined_risk NUMERIC(5,4),
    red_zone BOOLEAN NOT NULL DEFAULT FALSE,
    risk_tier VARCHAR(32) NOT NULL DEFAULT 'lower_risk',
    quality_flag VARCHAR(64) NOT NULL DEFAULT 'UNVERIFIED',
    geom GEOMETRY(Polygon, 32644) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_h_landslide_range CHECK (h_landslide IS NULL OR (h_landslide >= 0.0 AND h_landslide <= 1.0)),
    CONSTRAINT chk_h_flood_range CHECK (h_flood IS NULL OR (h_flood >= 0.0 AND h_flood <= 1.0)),
    CONSTRAINT chk_h_rain_range CHECK (h_rain IS NULL OR (h_rain >= 0.0 AND h_rain <= 1.0)),
    CONSTRAINT chk_combined_risk_range CHECK (combined_risk IS NULL OR (combined_risk >= 0.0 AND combined_risk <= 1.0)),
    CONSTRAINT chk_risk_tier CHECK (risk_tier IN ('red', 'amber', 'lower_risk'))
);

-- 2. Habitation Vulnerability Scores
CREATE TABLE IF NOT EXISTS vulnerability (
    habitation_id VARCHAR(64) PRIMARY KEY REFERENCES habitation(habitation_id) ON DELETE RESTRICT,
    population_exposure NUMERIC(5,4),
    social_score NUMERIC(5,4),
    access_score NUMERIC(5,4),
    infra_score NUMERIC(5,4),
    recurrence_score NUMERIC(5,4),
    vulnerability NUMERIC(5,4),
    missing_data_penalty NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_vulnerability_range CHECK (vulnerability IS NULL OR (vulnerability >= 0.0 AND vulnerability <= 1.0))
);

-- 3. Candidate Relocation Sites
-- Note: geom is GEOMETRY(Polygon, 32644) per data-dictionary.md (site polygon footprint)
CREATE TABLE IF NOT EXISTS candidate_site (
    site_id VARCHAR(64) PRIMARY KEY,
    geom GEOMETRY(Polygon, 32644) NOT NULL,
    area NUMERIC NOT NULL,
    suitability NUMERIC(5,4),
    status VARCHAR(32) NOT NULL DEFAULT 'eligible',
    explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_site_area_positive CHECK (area > 0),
    CONSTRAINT chk_site_suitability_range CHECK (suitability IS NULL OR (suitability >= 0.0 AND suitability <= 1.0)),
    CONSTRAINT chk_site_status CHECK (status IN ('eligible', 'conditional', 'rejected'))
);

-- 4. Site Carrying Capacity and Bottleneck Analysis
CREATE TABLE IF NOT EXISTS capacity (
    site_id VARCHAR(64) PRIMARY KEY REFERENCES candidate_site(site_id) ON DELETE RESTRICT,
    land_cap INT NOT NULL DEFAULT 0,
    water_cap INT NOT NULL DEFAULT 0,
    sanitation_cap INT NOT NULL DEFAULT 0,
    health_cap INT NOT NULL DEFAULT 0,
    access_cap INT NOT NULL DEFAULT 0,
    binding_bottleneck VARCHAR(64) NOT NULL DEFAULT 'uncalculated',
    effective_cap INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_effective_cap_non_negative CHECK (effective_cap >= 0)
);

-- 5. Habitation Relocation Urgency & Priority Tiers
CREATE TABLE IF NOT EXISTS priority (
    habitation_id VARCHAR(64) PRIMARY KEY REFERENCES habitation(habitation_id) ON DELETE RESTRICT,
    risk NUMERIC(5,4),
    exposed_pop INT NOT NULL DEFAULT 0,
    vulnerability NUMERIC(5,4),
    response_difficulty NUMERIC(5,4),
    recurrence NUMERIC(5,4),
    priority_score NUMERIC(5,4),
    tier VARCHAR(32) NOT NULL DEFAULT 'Monitor',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_priority_score_range CHECK (priority_score IS NULL OR (priority_score >= 0.0 AND priority_score <= 1.0)),
    CONSTRAINT chk_priority_tier CHECK (tier IN ('Immediate', 'Short-term', 'Medium-term', 'Monitor'))
);

-- 6. Allocation Optimization Scenario Results
CREATE TABLE IF NOT EXISTS allocation (
    allocation_id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES model_run(run_id) ON DELETE RESTRICT,
    habitation_id VARCHAR(64) NOT NULL REFERENCES habitation(habitation_id) ON DELETE RESTRICT,
    site_id VARCHAR(64) NOT NULL REFERENCES candidate_site(site_id) ON DELETE RESTRICT,
    allocated_population INT NOT NULL,
    distance NUMERIC NOT NULL,
    constraint_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_allocated_population_non_negative CHECK (allocated_population >= 0),
    CONSTRAINT chk_distance_non_negative CHECK (distance >= 0.0)
);

COMMIT;
