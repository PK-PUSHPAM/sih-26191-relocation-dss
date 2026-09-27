"""
Database Engine and Session Management.
"""
import os
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

DEFAULT_DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/sih_chamoli_dss"

def get_database_url() -> str:
    """Get database URL from environment or default local PostGIS instance."""
    url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
    # Use the psycopg2 driver bundled in the project runtime dependencies.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    return url

_engine: Optional[Engine] = None

def get_engine(echo: bool = False) -> Engine:
    """Obtain or initialize SQLAlchemy Engine."""
    global _engine
    if _engine is None:
        db_url = get_database_url()
        _engine = create_engine(db_url, echo=echo, future=True, pool_pre_ping=True)
    return _engine

def get_session_factory(engine: Optional[Engine] = None) -> sessionmaker:
    eng = engine or get_engine()
    return sessionmaker(bind=eng, autoflush=False, autocommit=False, expire_on_commit=False)

@contextmanager
def get_db(engine: Optional[Engine] = None) -> Generator[Session, None, None]:
    """Context manager for transactional database sessions."""
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def check_db_connection(engine: Optional[Engine] = None, timeout_seconds: float = 1.0) -> bool:
    """Check if database server is reachable and responsive using quick socket check and probe."""
    import socket
    from urllib.parse import urlparse

    db_url = get_database_url()
    try:
        # Extract host and port
        parsed = urlparse(db_url.replace("postgresql+psycopg2://", "http://"))
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432

        # Fast TCP socket check with tight timeout
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_seconds)
            result = sock.connect_ex((host, port))
            if result != 0:
                return False

        # If port is open, test SQLAlchemy connection
        eng = engine or get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

