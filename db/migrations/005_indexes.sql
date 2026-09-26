-- Migration 005: Spatial and Relational Indexes
-- Purpose: Accelerate spatial queries with GiST indexes and relational lookups with B-tree indexes

BEGIN;

-- 1. Spatial GiST Indexes (SRID 32644)
CREATE INDEX IF NOT EXISTS idx_admin_unit_geom ON admin_unit USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_habitation_geom ON habitation USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_infrastructure_geom ON infrastructure USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_risk_cell_geom ON risk_cell USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_candidate_site_geom ON candidate_site USING GIST(geom);

-- 2. Foreign Key & Filter B-Tree Indexes
CREATE INDEX IF NOT EXISTS idx_admin_unit_parent ON admin_unit(parent_id);
CREATE INDEX IF NOT EXISTS idx_habitation_admin_unit ON habitation(admin_unit_id);
CREATE INDEX IF NOT EXISTS idx_habitation_source ON habitation(source_id);
CREATE INDEX IF NOT EXISTS idx_infrastructure_source ON infrastructure(source_id);
CREATE INDEX IF NOT EXISTS idx_hazard_layer_source ON hazard_layer(source_id);
CREATE INDEX IF NOT EXISTS idx_risk_cell_red_zone ON risk_cell(red_zone);
CREATE INDEX IF NOT EXISTS idx_risk_cell_tier ON risk_cell(risk_tier);
CREATE INDEX IF NOT EXISTS idx_candidate_site_status ON candidate_site(status);
CREATE INDEX IF NOT EXISTS idx_priority_tier ON priority(tier);
CREATE INDEX IF NOT EXISTS idx_allocation_run_id ON allocation(run_id);
CREATE INDEX IF NOT EXISTS idx_allocation_habitation ON allocation(habitation_id);
CREATE INDEX IF NOT EXISTS idx_allocation_site ON allocation(site_id);

COMMIT;
