"""
Migration script: Reclassify articles with category='country'.

The 'country' category was a misclassification from the keyword-based
classifier confusing geographic metadata with article category.
This script reclassifies those articles using simple keyword heuristics.

Idempotent — safe to run multiple times (no-op if no 'country' articles exist).

Usage:
    python scripts/fix_country_categories.py
"""

import os
import sys

from sqlalchemy import text


def migrate():
    """Reclassify articles with category='country' to proper categories."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.api.models.database import engine  # noqa: E402

    with engine.begin() as conn:
        # Check how many articles have category='country'
        result = conn.execute(
            text("SELECT COUNT(*) FROM articles WHERE category = 'country'")
        )
        count = result.scalar()

        if count == 0:
            print("No articles with category='country'. Nothing to do.")
            return

        print(f"Found {count} articles with category='country'. Reclassifying...")

        # Reclassify based on keyword heuristics in title/content:
        # 1. Funding/investment/raises -> startups
        conn.execute(
            text(
                """
                UPDATE articles SET category = 'startups'
                WHERE category = 'country'
                AND (
                    LOWER(title) LIKE '%fund%'
                    OR LOWER(title) LIKE '%invest%'
                    OR LOWER(title) LIKE '%raises%'
                    OR LOWER(title) LIKE '%startup%'
                    OR LOWER(title) LIKE '%venture%'
                    OR LOWER(title) LIKE '%ipo%'
                )
                """
            )
        )

        # 2. Regulation/policy/law -> policy
        conn.execute(
            text(
                """
                UPDATE articles SET category = 'policy'
                WHERE category = 'country'
                AND (
                    LOWER(title) LIKE '%regulat%'
                    OR LOWER(title) LIKE '%policy%'
                    OR LOWER(title) LIKE '%law%'
                    OR LOWER(title) LIKE '%government%'
                )
                """
            )
        )

        # 3. Remaining 'country' articles -> industry (safe default)
        conn.execute(
            text(
                """
                UPDATE articles SET category = 'industry'
                WHERE category = 'country'
                """
            )
        )

        # Verify
        result = conn.execute(
            text("SELECT COUNT(*) FROM articles WHERE category = 'country'")
        )
        remaining = result.scalar()
        print(
            f"Reclassification complete. " f"Remaining 'country' articles: {remaining}"
        )


if __name__ == "__main__":
    migrate()
