"""
Unit Tests for Layer L02 — PostGIS Spatial Database Foundation.
Validates migration ordering, DDL integrity, table structures, geometry SRID 32644 constraints, GiST indexes, and ORM mappings.
"""
from pathlib import Path
import pytest
from sqlalchemy import inspect

from src.db.session import Base, get_database_url
from src.db.models import (
    DataSourceModel,
    ModelRunModel,
    HazardLayerModel,
    AdminUnitModel,
    HabitationModel,
    InfrastructureModel,
    RiskCellModel,
    VulnerabilityModel,
    CandidateSiteModel,
    CapacityModel,
    PriorityModel,
    AllocationModel,
)
from scripts.init_db import get_ordered_migrations, verify_migration_sql


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "db" / "migrations"


# ==============================================================================
# 1. Migration File Integrity & Ordering Tests
# ==============================================================================

def test_migration_files_exist_and_ordered():
    """Verify that migrations exist in db/migrations/ and follow sequential naming."""
    migrations = get_ordered_migrations(MIGRATIONS_DIR)
    assert len(migrations) == 5

    expected_names = [
        "001_extensions.sql",
        "002_provenance_and_metadata.sql",
        "003_core_entities.sql",
        "004_analytical_entities.sql",
        "005_indexes.sql",
    ]
    actual_names = [m.name for m in migrations]
    assert actual_names == expected_names


def test_migration_files_content_and_syntax():
    """Verify migration files are non-empty and have valid transaction blocks."""
    migrations = get_ordered_migrations(MIGRATIONS_DIR)
    assert verify_migration_sql(migrations) is True

    for m in migrations:
        sql = m.read_text(encoding="utf-8").upper()
        assert "BEGIN;" in sql
        assert "COMMIT;" in sql


# ==============================================================================
# 2. PostGIS Extension & DDL Geometry SRID Checks
# ==============================================================================

def test_migration_001_postgis_extension():
    sql = (MIGRATIONS_DIR / "001_extensions.sql").read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS postgis;" in sql
    assert "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" in sql


def test_migration_geometry_srid_32644():
    """Verify all spatial tables enforce SRID 32644 in DDL with correct geometry types."""
    core_sql = (MIGRATIONS_DIR / "003_core_entities.sql").read_text(encoding="utf-8")
    analytical_sql = (MIGRATIONS_DIR / "004_analytical_entities.sql").read_text(encoding="utf-8")

    # Core tables
    assert "GEOMETRY(MultiPolygon, 32644)" in core_sql  # admin_unit (concrete MultiPolygon)
    assert "GEOMETRY(Geometry, 32644)" in core_sql      # habitation / infrastructure (multi-type by spec)

    # Analytical tables
    assert "GEOMETRY(Polygon, 32644)" in analytical_sql # risk_cell (30m grid square)
    assert "GEOMETRY(Polygon, 32644)" in analytical_sql # candidate_site (site polygon footprint per data dictionary)


def test_migration_foreign_key_restrict_policy():
    """Verify migrations use ON DELETE RESTRICT to preserve provenance and audit records."""
    core_sql = (MIGRATIONS_DIR / "003_core_entities.sql").read_text(encoding="utf-8")
    analytical_sql = (MIGRATIONS_DIR / "004_analytical_entities.sql").read_text(encoding="utf-8")

    # Core table foreign keys
    assert "REFERENCES admin_unit(unit_id) ON DELETE RESTRICT" in core_sql
    assert "REFERENCES data_source(source_id) ON DELETE RESTRICT" in core_sql

    # Analytical foreign keys must be RESTRICT to preserve audit history
    assert "REFERENCES habitation(habitation_id) ON DELETE RESTRICT" in analytical_sql
    assert "REFERENCES candidate_site(site_id) ON DELETE RESTRICT" in analytical_sql
    assert "REFERENCES model_run(run_id) ON DELETE RESTRICT" in analytical_sql


def test_migration_spatial_gist_indexes():
    """Verify GiST spatial indexes are defined for all spatial geometry columns."""
    indexes_sql = (MIGRATIONS_DIR / "005_indexes.sql").read_text(encoding="utf-8")

    assert "CREATE INDEX IF NOT EXISTS idx_admin_unit_geom ON admin_unit USING GIST(geom);" in indexes_sql
    assert "CREATE INDEX IF NOT EXISTS idx_habitation_geom ON habitation USING GIST(geom);" in indexes_sql
    assert "CREATE INDEX IF NOT EXISTS idx_infrastructure_geom ON infrastructure USING GIST(geom);" in indexes_sql
    assert "CREATE INDEX IF NOT EXISTS idx_risk_cell_geom ON risk_cell USING GIST(geom);" in indexes_sql
    assert "CREATE INDEX IF NOT EXISTS idx_candidate_site_geom ON candidate_site USING GIST(geom);" in indexes_sql


# ==============================================================================
# 3. SQLAlchemy ORM Model Mapping Tests
# ==============================================================================

def test_orm_tables_match_data_dictionary():
    """Verify all 12 core tables from data dictionary exist in ORM metadata."""
    tables = Base.metadata.tables

    expected_tables = [
        "data_source",
        "model_run",
        "hazard_layer",
        "admin_unit",
        "habitation",
        "infrastructure",
        "risk_cell",
        "vulnerability",
        "candidate_site",
        "capacity",
        "priority",
        "allocation",
    ]

    for table_name in expected_tables:
        assert table_name in tables, f"Missing table in ORM: {table_name}"


def test_orm_primary_keys_and_foreign_keys():
    """Verify primary keys and foreign key relationships in ORM."""
    tables = Base.metadata.tables

    # Primary key checks
    assert tables["data_source"].primary_key.columns.keys() == ["source_id"]
    assert tables["habitation"].primary_key.columns.keys() == ["habitation_id"]
    assert tables["risk_cell"].primary_key.columns.keys() == ["cell_id"]
    assert tables["candidate_site"].primary_key.columns.keys() == ["site_id"]
    assert tables["allocation"].primary_key.columns.keys() == ["allocation_id"]

    # Foreign key checks
    habitation_fks = {fk.target_fullname for fk in tables["habitation"].foreign_keys}
    assert "admin_unit.unit_id" in habitation_fks
    assert "data_source.source_id" in habitation_fks

    allocation_fks = {fk.target_fullname for fk in tables["allocation"].foreign_keys}
    assert "model_run.run_id" in allocation_fks
    assert "habitation.habitation_id" in allocation_fks
    assert "candidate_site.site_id" in allocation_fks


def test_orm_geometry_columns_srid_and_types():
    """Verify ORM geometry columns enforce SRID 32644 and concrete types where specified."""
    tables = Base.metadata.tables

    admin_geom = tables["admin_unit"].columns["geom"].type
    assert getattr(admin_geom, "srid", None) == 32644
    assert admin_geom.geometry_type.upper() == "MULTIPOLYGON"

    hab_geom = tables["habitation"].columns["geom"].type
    assert getattr(hab_geom, "srid", None) == 32644

    risk_geom = tables["risk_cell"].columns["geom"].type
    assert getattr(risk_geom, "srid", None) == 32644
    assert risk_geom.geometry_type.upper() == "POLYGON"

    site_geom = tables["candidate_site"].columns["geom"].type
    assert getattr(site_geom, "srid", None) == 32644
    assert site_geom.geometry_type.upper() == "POLYGON"
