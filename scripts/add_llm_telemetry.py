"""
Migration script: Create llm_telemetry table.

Idempotent — safe to run multiple times.
Works with both PostgreSQL (Railway) and SQLite (local dev).

Usage:
    python scripts/add_llm_telemetry.py
"""

import os
import sys

from sqlalchemy import inspect


def migrate():
    """Create llm_telemetry table if it doesn't exist."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import LLMTelemetry  # noqa: F401
    from airopa_automation.api.models.database import Base, engine  # noqa: E402

    inspector = inspect(engine)
    if "llm_telemetry" in inspector.get_table_names():
        print("Table 'llm_telemetry' already exists. Nothing to do.")
        return

    # Create only the llm_telemetry table
    Base.metadata.tables["llm_telemetry"].create(bind=engine)
    print("Successfully created 'llm_telemetry' table.")


if __name__ == "__main__":
    migrate()
