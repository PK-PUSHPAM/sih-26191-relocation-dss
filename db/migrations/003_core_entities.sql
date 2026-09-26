-- Migration 003: Core Geographic and Settlement Entities
-- Purpose: Store administrative boundaries, habitations/villages, and critical infrastructure

BEGIN;

-- 1. Administrative Hierarchy (District, Block/Tehsil, Village)
CREATE TABLE IF NOT EXISTS admin_unit (
    unit_id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(32) NOT NULL,
    parent_id VARCHAR(64) REFERENCES admin_unit(unit_id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64),
    geom GEOMETRY(MultiPolygon, 32644) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_admin_unit_type CHECK (type IN ('district', 'block', 'tehsil', 'village'))
);

-- 2. Habitations / Settlements Decision Units
-- Note: geom is GEOMETRY(Geometry, 32644) to support both Point centroids and settlement area Polygons
CREATE TABLE IF NOT EXISTS habitation (
    habitation_id VARCHAR(64) PRIMARY KEY,
    admin_unit_id VARCHAR(64) NOT NULL REFERENCES admin_unit(unit_id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    population_year INT NOT NULL DEFAULT 2011,
    population INT NOT NULL,
    households INT NOT NULL,
    geom GEOMETRY(Geometry, 32644) NOT NULL,
    source_id VARCHAR(64) REFERENCES data_source(source_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_population_non_negative CHECK (population >= 0),
    CONSTRAINT chk_households_non_negative CHECK (households >= 0),
    CONSTRAINT chk_population_year_valid CHECK (population_year >= 1900 AND population_year <= 2100)
);

-- 3. Critical Infrastructure, Facilities & Amenities
-- Note: geom is GEOMETRY(Geometry, 32644) to support Points (hospitals, schools) and LineStrings (roads)
CREATE TABLE IF NOT EXISTS infrastructure (
    asset_id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(64) NOT NULL,
    name VARCHAR(255),
    capacity_or_proxy NUMERIC,
    is_proxy BOOLEAN NOT NULL DEFAULT TRUE,
    geom GEOMETRY(Geometry, 32644) NOT NULL,
    source_id VARCHAR(64) REFERENCES data_source(source_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
