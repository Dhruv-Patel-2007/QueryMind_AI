"""Database Configuration, Engines, and Session Management for QueryMind AI 2.0.

Provides strict architectural separation between:
1. Write-enabled engine: Exclusively used during schema migration, initialization, and deterministic seeding.
2. Hardened read-only engine: Exclusively used during application runtime for natural language query execution.
Both engines strictly enforce SQLite foreign key constraints via connection listeners.
"""

import os
import sqlite3
import time
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Base directories (resolved dynamically with zero hardcoded absolute paths)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_FILE = DATA_DIR / "academic.db"


def get_db_path(custom_path: Path | str | None = None) -> Path:
    """Returns the resolved absolute path to the SQLite database file."""
    if custom_path:
        return Path(custom_path).resolve()
    return DEFAULT_DB_FILE


DB_PATH = get_db_path()
DB_URI_PATH = str(DB_PATH).replace("\\", "/")

# ---------------------------------------------------------------------------
# Declarative Base for ORM Models
# ---------------------------------------------------------------------------
Base = declarative_base()

# ---------------------------------------------------------------------------
# 1. WRITE-ENABLED ENGINE (Exclusively for Initialization & Seeding)
# ---------------------------------------------------------------------------
WRITE_DATABASE_URL = f"sqlite:///{DB_PATH}"

write_engine = create_engine(
    WRITE_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(write_engine, "connect")
def configure_write_connection(dbapi_connection, connection_record):
    """Enforces SQLite Foreign Key constraints and busy timeout on write connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.close()


WriteSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=write_engine,
)

# ---------------------------------------------------------------------------
# 2. HARDENED READ-ONLY ENGINE (Exclusively for Runtime Query Execution)
# ---------------------------------------------------------------------------
# Uses SQLite URI filename mode with mode=ro
READ_ONLY_DATABASE_URL = f"sqlite:///file:{DB_URI_PATH}?mode=ro&uri=true"

read_only_engine = create_engine(
    READ_ONLY_DATABASE_URL,
    connect_args={"check_same_thread": False, "uri": True},
    echo=False,
)


@event.listens_for(read_only_engine, "connect")
def configure_read_only_connection(dbapi_connection, connection_record):
    """Enforces SQLite foreign keys, hardware read-only mode, and busy timeout."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA query_only = ON;")
    cursor.execute("PRAGMA busy_timeout = 3000;")
    cursor.close()


@event.listens_for(read_only_engine, "before_cursor_execute")
def enforce_read_only_query_timeout(conn, cursor, statement, parameters, context, executemany):
    """Injects a native SQLite C-API progress handler to enforce a 3.0s hard query timeout."""
    dbapi_conn = conn.connection.dbapi_connection
    query_start = time.time()

    def timeout_progress_handler() -> int:
        # Non-zero return immediately aborts long-running queries inside SQLite
        if time.time() - query_start > 3.0:
            return 1
        return 0

    # Checks execution progress every 1,000 SQLite virtual machine opcodes
    dbapi_conn.set_progress_handler(timeout_progress_handler, 1000)


ReadOnlySessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=read_only_engine,
)


# ---------------------------------------------------------------------------
# Dependency Injections
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a hardened read-only database session for API endpoints."""
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_write_db() -> Generator[Session, None, None]:
    """Internal session generator used exclusively by initialization and seeding routines."""
    db = WriteSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine=write_engine, drop_existing: bool = False) -> None:
    """Creates all database tables and integrity triggers defined in the metadata.
    
    Args:
        engine: The SQLAlchemy engine to bind with (defaults to write_engine).
        drop_existing: If True, explicitly drops all existing tables before creating.
    """
    if drop_existing:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Ensure database-level triggers are active on the bound engine
    with engine.begin() as conn:
        from app.models.academic import (
            trg_student_marks_insert,
            trg_student_marks_update,
            trg_assessments_weightage_insert,
            trg_assessments_weightage_update,
            trg_assessments_max_marks_update,
            trg_assessments_offering_update,
            trg_enrollments_offering_update,
        )
        conn.execute(trg_student_marks_insert)
        conn.execute(trg_student_marks_update)
        conn.execute(trg_assessments_weightage_insert)
        conn.execute(trg_assessments_weightage_update)
        conn.execute(trg_assessments_max_marks_update)
        conn.execute(trg_assessments_offering_update)
        conn.execute(trg_enrollments_offering_update)

