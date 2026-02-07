"""
Migration script: Add missing columns to source_metrics table.

Adds: articles_passed_relevance, avg_eu_relevance, avg_quality_score,
      category_distribution.

Idempotent — safe to run multiple times.
Works with both PostgreSQL (Railway) and SQLite (local dev).

Usage:
    python scripts/enhance_source_metrics.py
"""

import os
import sys

from sqlalchemy import inspect, text


def migrate():
    """Add missing columns to source_metrics table."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402

    inspector = inspect(engine)

    if "source_metrics" not in inspector.get_table_names():
        print("Table 'source_metrics' does not exist. Run add_source_metrics.py first.")
        return

    columns = {col["name"] for col in inspector.get_columns("source_metrics")}

    new_columns = {
        "articles_passed_relevance": "INTEGER",
        "avg_eu_relevance": "FLOAT",
        "avg_quality_score": "FLOAT",
        "category_distribution": "TEXT",
    }

    added = 0
    with engine.begin() as conn:
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                conn.execute(
                    text(f"ALTER TABLE source_metrics ADD COLUMN {col_name} {col_type}")
                )
                print(f"  Added column '{col_name}' ({col_type})")
                added += 1
            else:
                print(f"  Column '{col_name}' already exists")

    if added:
        print(f"Successfully added {added} column(s) to source_metrics.")
    else:
        print("Nothing to do — all columns already exist.")


if __name__ == "__main__":
    migrate()
