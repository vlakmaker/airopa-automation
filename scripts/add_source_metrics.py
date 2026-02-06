"""
Migration script: Create source_metrics table.

Idempotent — safe to run multiple times.
Works with both PostgreSQL (Railway) and SQLite (local dev).

Usage:
    python scripts/add_source_metrics.py
"""

import os
import sys

from sqlalchemy import inspect, text


def migrate():
    """Create source_metrics table if it doesn't exist."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "source_metrics" in tables:
        print("Table 'source_metrics' already exists. Nothing to do.")
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE source_metrics (
                    id SERIAL PRIMARY KEY,
                    run_id VARCHAR NOT NULL,
                    source_name VARCHAR NOT NULL,
                    articles_fetched INTEGER NOT NULL DEFAULT 0,
                    articles_stored INTEGER NOT NULL DEFAULT 0,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text("CREATE INDEX ix_source_metrics_run_id ON source_metrics (run_id)")
        )
        conn.execute(
            text(
                "CREATE INDEX ix_source_metrics_source_name "
                "ON source_metrics (source_name)"
            )
        )

    print("Successfully created 'source_metrics' table.")


if __name__ == "__main__":
    migrate()
