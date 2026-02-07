"""
Migration script: Create llm_telemetry table.

Idempotent — safe to run multiple times.
Works with both PostgreSQL (Railway) and SQLite (local dev).

Usage:
    python scripts/add_llm_telemetry.py
"""

import os
import sys

from sqlalchemy import inspect, text


def migrate():
    """Create llm_telemetry table if it doesn't exist."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402

    inspector = inspect(engine)
    if "llm_telemetry" in inspector.get_table_names():
        print("Table 'llm_telemetry' already exists. Nothing to do.")
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE llm_telemetry (
                    id INTEGER PRIMARY KEY,
                    run_id VARCHAR NOT NULL,
                    article_url VARCHAR NOT NULL,
                    llm_model VARCHAR NOT NULL,
                    prompt_version VARCHAR NOT NULL,
                    llm_latency_ms INTEGER NOT NULL DEFAULT 0,
                    tokens_in INTEGER NOT NULL DEFAULT 0,
                    tokens_out INTEGER NOT NULL DEFAULT 0,
                    llm_status VARCHAR NOT NULL,
                    fallback_reason VARCHAR,
                    timestamp DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text("CREATE INDEX ix_llm_telemetry_run_id ON llm_telemetry (run_id)")
        )

    print("Successfully created 'llm_telemetry' table.")


if __name__ == "__main__":
    migrate()
