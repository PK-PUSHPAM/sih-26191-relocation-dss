-- Migration 002: Provenance and Metadata Tables
-- Purpose: Track ingested sources, hazard layers, and pipeline execution runs

BEGIN;

-- 1. Provenance Registry
CREATE TABLE IF NOT EXISTS data_source (
    source_id VARCHAR(64) PRIMARY KEY,
    agency VARCHAR(255) NOT NULL,
    url TEXT,
    access_date DATE NOT NULL,
    license VARCHAR(128) NOT NULL,
    version VARCHAR(64) NOT NULL,
    checksum VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Model & Pipeline Execution Run Trace
CREATE TABLE IF NOT EXISTS model_run (
    run_id VARCHAR(64) PRIMARY KEY,
    model_version VARCHAR(64) NOT NULL,
    config_version VARCHAR(64) NOT NULL,
    input_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    logs_or_error TEXT,
    CONSTRAINT chk_model_run_status CHECK (status IN ('running', 'completed', 'failed'))
);

-- 3. Hazard Layers Metadata Registry
CREATE TABLE IF NOT EXISTS hazard_layer (
    hazard_id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(32) NOT NULL,
    date_version VARCHAR(64) NOT NULL,
    source_id VARCHAR(64) REFERENCES data_source(source_id),
    model_version VARCHAR(64) NOT NULL,
    raster_vector_ref TEXT NOT NULL,
    is_normalized BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_hazard_type CHECK (type IN ('landslide', 'flood', 'rainfall'))
);

COMMIT;
