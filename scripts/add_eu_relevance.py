"""
Migration script: Add eu_relevance column to articles table.

Idempotent — safe to run multiple times.
Works with both PostgreSQL (Railway) and SQLite (local dev).

Usage:
    python scripts/add_eu_relevance.py
"""

import os
import sys

from sqlalchemy import inspect, text


def migrate():
    """Add eu_relevance column to articles table if it doesn't exist."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("articles")]

    if "eu_relevance" in columns:
        print("Column 'eu_relevance' already exists in articles table. Nothing to do.")
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE articles ADD COLUMN eu_relevance FLOAT"))

    print("Successfully added 'eu_relevance' column to articles table.")


if __name__ == "__main__":
    migrate()
