"""
Migration script: Add image_url column to articles table.

Idempotent — safe to run multiple times.
Works with both PostgreSQL (Railway) and SQLite (local dev).

Usage:
    python scripts/add_image_url.py
"""

import os
import sys

from sqlalchemy import inspect, text


def migrate():
    """Add image_url column to articles table if it doesn't exist."""
    # Add project root to path so we can import the database module
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("articles")]

    if "image_url" in columns:
        print("Column 'image_url' already exists in articles table. Nothing to do.")
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE articles ADD COLUMN image_url VARCHAR"))

    print("Successfully added 'image_url' column to articles table.")


if __name__ == "__main__":
    migrate()
