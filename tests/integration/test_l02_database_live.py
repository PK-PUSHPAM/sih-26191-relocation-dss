"""
Integration Tests for Layer L02 — PostGIS Spatial Database.
Tests live PostgreSQL/PostGIS connectivity, extension verification, migration execution, and schema creation when DB is online.
"""
import pytest
from sqlalchemy import text
from src.db.session import get_engine, check_db_connection, get_database_url
from scripts.init_db import get_ordered_migrations, run_migrations


def test_database_url_configuration():
    """Verify database connection URL is properly configured with psycopg driver."""
    url = get_database_url()
    assert url is not None
    assert "postgresql" in url
    assert "psycopg" in url or "localhost" in url


def test_database_connectivity_and_postgis():
    """
    Test live database connectivity and PostGIS extension.
    If database server is not running on localhost, skips gracefully with informative notice.
    """
    if not check_db_connection():
        pytest.skip("Local PostgreSQL server is offline or unreachable on port 5432. Start Docker database to run live integration tests.")

    engine = get_engine()
    with engine.connect() as conn:
        # Check PostgreSQL version
        pg_ver = conn.execute(text("SELECT version()")).scalar()
        assert "PostgreSQL" in pg_ver

        # Check PostGIS extension
        postgis_ver = conn.execute(text("SELECT PostGIS_Version()")).scalar()
        assert postgis_ver is not None
        assert "3." in postgis_ver


def test_live_migrations_execution():
    """Test executing all 5 migrations in order on the live database."""
    if not check_db_connection():
        pytest.skip("Local PostgreSQL server is offline. Skipping live migration test.")

    engine = get_engine()
    migration_files = get_ordered_migrations()
    success, applied = run_migrations(engine, migration_files)

    assert success is True
    assert len(applied) == 5

    # Verify tables exist in information_schema
    with engine.connect() as conn:
        tables_res = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )).fetchall()
        table_names = {r[0] for r in tables_res}

        assert "data_source" in table_names
        assert "admin_unit" in table_names
        assert "habitation" in table_names
        assert "risk_cell" in table_names
        assert "candidate_site" in table_names
        assert "allocation" in table_names
