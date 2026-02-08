"""
Migration script: Normalize source names in existing articles.

Uses the source_name_map from config to update historical source names
to their canonical forms (e.g., "https://sifted.eu" -> "Sifted").

Idempotent — safe to run multiple times.

Usage:
    python scripts/normalize_sources.py
"""

import os
import sys

from sqlalchemy import text


def migrate():
    """Normalize source names in existing articles."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402
    from airopa_automation.config import config  # noqa: E402

    print("Normalizing source names in articles table...")

    with engine.begin() as conn:
        for raw_name, canonical in config.scraper.source_name_map.items():
            if raw_name == canonical:
                continue
            result = conn.execute(
                text("UPDATE articles SET source = :canonical WHERE source = :raw"),
                {"canonical": canonical, "raw": raw_name},
            )
            if result.rowcount > 0:
                print(f"  {raw_name} -> {canonical}: {result.rowcount} rows")

        # Show distinct sources after normalization
        result = conn.execute(
            text(
                "SELECT DISTINCT source, COUNT(*) as cnt "
                "FROM articles GROUP BY source "
                "ORDER BY cnt DESC"
            )
        )
        rows = list(result)
        print(f"\nDistinct sources after normalization: {len(rows)}")
        for source, cnt in rows:
            print(f"  {source}: {cnt} articles")


if __name__ == "__main__":
    migrate()
