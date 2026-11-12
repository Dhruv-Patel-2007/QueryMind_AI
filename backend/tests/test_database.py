"""Unit tests for SQLite Database Engine, Read-Only Enforcement, and Pragmas."""

import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.database import (
    Base,
    ReadOnlySessionLocal,
    WriteSessionLocal,
    init_db,
    write_engine,
    read_only_engine,
)
from app.models.academic import Department


def test_database_tables_exist():
    """Verify that all 9 academic domain tables are recognized in SQLAlchemy metadata."""
    expected_tables = {
        "departments",
        "students",
        "instructors",
        "courses",
        "terms",
        "course_offerings",
        "enrollments",
        "assessments",
        "student_marks",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), (
        f"Missing tables: {expected_tables - actual_tables}"
    )


def test_init_db_creates_all_tables_on_temporary_database(tmp_path: Path):
    """Verify init_db creates all tables on an isolated temporary database."""
    test_db_file = tmp_path / "init_test.db"
    test_engine = create_engine(f"sqlite:///{test_db_file}")

    init_db(engine=test_engine, drop_existing=True)

    inspector = inspect(test_engine)
    created_tables = set(inspector.get_table_names())

    expected_tables = {
        "departments",
        "students",
        "instructors",
        "courses",
        "terms",
        "course_offerings",
        "enrollments",
        "assessments",
        "student_marks",
    }
    assert expected_tables == created_tables


def test_foreign_keys_pragma_enabled_on_write_engine():
    """Verify that write_engine connection listener enables foreign_keys pragma."""
    with write_engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert result == 1, "Foreign keys pragma must be enabled (1) on write engine"


def test_read_only_engine_pragmas_and_restrictions():
    """Verify that read_only_engine enforces query_only, foreign_keys, and blocks writes."""
    with read_only_engine.connect() as conn:
        fk_result = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert fk_result == 1, "Foreign keys pragma must be enabled (1) on read-only engine"

        qo_result = conn.execute(text("PRAGMA query_only;")).scalar()
        assert qo_result == 1, "query_only pragma must be ON (1) on read-only engine"


def test_read_only_session_allows_select_queries():
    """Verify read-only session allows SELECT queries without errors."""
    session = ReadOnlySessionLocal()
    try:
        count = session.query(Department).count()
        assert count >= 0
    finally:
        session.close()


def test_read_only_session_strictly_blocks_insert():
    """Verify attempting an INSERT on ReadOnlySessionLocal raises OperationalError."""
    session = ReadOnlySessionLocal()
    try:
        test_dept = Department(
            name="Blocked Department",
            code="BLOCK",
            established_year=2024,
            building="Denial Hall",
        )
        session.add(test_dept)
        with pytest.raises((OperationalError, DBAPIError)) as exc_info:
            session.commit()
        assert "readonly" in str(exc_info.value).lower() or "query_only" in str(exc_info.value).lower()
    finally:
        session.rollback()
        session.close()


def test_read_only_session_strictly_blocks_drop_table():
    """Verify attempting a DROP TABLE on read-only engine raises OperationalError."""
    with read_only_engine.connect() as conn:
        with pytest.raises((OperationalError, DBAPIError)):
            conn.execute(text("DROP TABLE IF EXISTS departments;"))

