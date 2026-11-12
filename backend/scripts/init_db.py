"""Database Schema Initialization Utility for QueryMind AI 2.0.

Provides programmatic and CLI facilities to create the academic database schema.
Enforces explicit safety: existing tables are NEVER dropped unless explicitly requested via --reset.
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path for direct script execution
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import inspect
from app.core.database import Base, write_engine, get_db_path, init_db
# Import models to ensure they are registered with Base.metadata
import app.models  # noqa: F401


def initialize_database(engine=write_engine, drop_existing: bool = False) -> list[str]:
    """Initializes the database schema using the bound engine.

    Args:
        engine: SQLAlchemy Engine instance to use for DDL operations.
        drop_existing: If True, drops all existing tables before recreating.

    Returns:
        List of table names created.
    """
    db_file = get_db_path()
    action = "Rebuilding (drop + recreate)" if drop_existing else "Creating"
    print(f"--> [init_db] {action} academic database schema at: {db_file}")

    init_db(engine=engine, drop_existing=drop_existing)

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"--> [init_db] Verified {len(tables)} tables created:")
    for tbl in sorted(tables):
        print(f"    - {tbl}")

    return tables


def main() -> None:
    """CLI entry point for database initialization."""
    parser = argparse.ArgumentParser(
        description="Initialize QueryMind AI 2.0 Academic Database Schema."
    )
    parser.add_argument(
        "--reset",
        "--drop",
        action="store_true",
        dest="reset",
        help="Explicitly drop and rebuild all tables. CAUTION: Destroys existing data.",
    )
    args = parser.parse_args()

    try:
        tables = initialize_database(drop_existing=args.reset)
        print(f"==> [init_db] Schema initialization complete ({len(tables)} tables ready).")
    except Exception as exc:
        print(f"ERROR: [init_db] Schema initialization failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

