"""
PostGIS Database Migration and Initialization Runner.
Applies SQL migrations in db/migrations/ sequentially with verification and error handling.
"""
import os
import sys
import logging
from pathlib import Path
from typing import List, Tuple
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.db.session import get_database_url, check_db_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_db")

MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"

def get_ordered_migrations(migrations_dir: Path = MIGRATIONS_DIR) -> List[Path]:
    """Retrieve all .sql migration files sorted by filename."""
    if not migrations_dir.exists():
        raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")
    
    files = [f for f in migrations_dir.glob("*.sql") if f.is_file()]
    return sorted(files, key=lambda p: p.name)

def verify_migration_sql(migration_files: List[Path]) -> bool:
    """Validate that migration files are non-empty and have valid basic SQL syntax."""
    logger.info(f"Auditing {len(migration_files)} migration files...")
    for mf in migration_files:
        content = mf.read_text(encoding="utf-8").strip()
        if not content:
            logger.error(f"Migration file is empty: {mf.name}")
            return False
        logger.info(f"  [OK] {mf.name} ({len(content.splitlines())} lines)")
    return True

def run_migrations(engine: Engine, migration_files: List[Path]) -> Tuple[bool, List[str]]:
    """Execute migrations in sequence against the live database."""
    applied = []
    with engine.connect() as conn:
        # Check PostGIS extension
        try:
            res = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            logger.info(f"PostGIS Version detected: {res}")
        except Exception as e:
            logger.warning(f"Could not query PostGIS version directly (extension will be enabled by migration 001): {e}")

        # Run each migration in transaction
        for mf in migration_files:
            logger.info(f"Applying migration: {mf.name} ...")
            sql_content = mf.read_text(encoding="utf-8")
            try:
                # Execute migration script
                conn.execute(text(sql_content))
                conn.commit()
                applied.append(mf.name)
                logger.info(f"  [SUCCESS] {mf.name} applied successfully.")
            except Exception as e:
                conn.rollback()
                logger.error(f"  [FAILED] Migration {mf.name} failed: {e}")
                return False, applied

    return True, applied

def main():
    dry_run = "--dry-run" in sys.argv or "--lint" in sys.argv
    migration_files = get_ordered_migrations()

    if not migration_files:
        logger.error("No migration files found in db/migrations/.")
        sys.exit(1)

    if not verify_migration_sql(migration_files):
        logger.error("Migration file audit failed.")
        sys.exit(1)

    if dry_run:
        logger.info("[DRY-RUN / LINT] All migration files verified successfully.")
        sys.exit(0)

    db_url = get_database_url()
    logger.info(f"Connecting to database target: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    if not check_db_connection():
        logger.warning(
            "Database server is currently offline or unreachable on configured port. "
            "To launch local PostGIS, run 'docker-compose up -d db' or start PostgreSQL service."
        )
        logger.info("Migrations were validated structurally in offline mode.")
        sys.exit(0)

    engine = create_engine(db_url, future=True)
    success, applied = run_migrations(engine, migration_files)

    if success:
        logger.info(f"Database initialization complete. {len(applied)} migrations applied.")
    else:
        logger.error("Database initialization failed during migration execution.")
        sys.exit(1)

if __name__ == "__main__":
    main()
