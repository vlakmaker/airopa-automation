"""
Migration script: Add confidence column to articles table.

Idempotent — safe to run multiple times.

Usage:
    python scripts/add_confidence_column.py
"""

import os
import sys

from sqlalchemy import inspect, text


def migrate():
    """Add confidence column to articles table if it doesn't exist."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("articles")]

    if "confidence" in columns:
        print("Column 'confidence' already exists in articles table. Nothing to do.")
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE articles ADD COLUMN confidence FLOAT"))

    print("Successfully added 'confidence' column to articles table.")


if __name__ == "__main__":
    migrate()
