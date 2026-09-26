-- Migration 001: PostGIS and Core Extensions
-- Purpose: Enable PostGIS spatial extensions and UUID generation

BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

COMMIT;
