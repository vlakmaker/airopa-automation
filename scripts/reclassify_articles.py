"""
One-time reclassification of existing articles using classification_v2 prompt.

Reads articles from the database, runs the new classifier + post-validation,
and updates category, country, eu_relevance, and confidence.

Safety features:
- Dry-run mode by default (set --apply to write changes)
- Rate limiting between LLM calls
- Budget cap (configurable)
- Logs all changes to CSV for audit

Usage:
    python scripts/reclassify_articles.py              # dry run
    python scripts/reclassify_articles.py --apply       # write changes
    python scripts/reclassify_articles.py --limit 10    # process 10 articles
"""

import argparse
import csv
import os
import sys
import time

from sqlalchemy import text


def _fetch_articles(engine, limit):
    """Fetch articles from DB for reclassification."""
    with engine.connect() as conn:
        query = (
            "SELECT id, title, url, source, content, "
            "category, country, eu_relevance "
            "FROM articles ORDER BY created_at DESC"
        )
        if limit > 0:
            query += f" LIMIT {limit}"
        return conn.execute(text(query)).fetchall()


def _apply_change(engine, article_id, new_cat, new_country, new_eu, new_conf):
    """Write full reclassification to DB."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE articles SET category = :cat, "
                "country = :country, eu_relevance = :eu, "
                "confidence = :conf WHERE id = :id"
            ),
            {
                "cat": new_cat,
                "country": new_country,
                "eu": new_eu,
                "conf": new_conf,
                "id": article_id,
            },
        )


def _apply_confidence_only(engine, article_id, conf):
    """Write only confidence score to DB."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE articles SET confidence = :conf WHERE id = :id"),
            {"conf": conf, "id": article_id},
        )


def _write_csv_log(log_path, changes):
    """Write change log to CSV."""
    with open(log_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=changes[0].keys())
        writer.writeheader()
        writer.writerows(changes)
    print(f"\nChange log written to: {log_path}")


def _classify_row(row, classifier, Article):
    """Classify a single article row. Returns (result, error_flag)."""
    article_id, title, url, source, content, _, _, _ = row

    article = Article(
        title=title or "",
        url=url or "",
        source=source or "",
        content=content or "",
    )

    try:
        llm_result = classifier._classify_with_llm(article)
    except Exception as e:
        print(f"  Error classifying '{title[:50]}': {e}")
        return None, True

    if not llm_result or not llm_result.valid:
        print(f"  Skip (no valid result): {title[:60]}")
        return None, False

    return llm_result, False


def _check_changed(llm_result, old_cat, old_country, old_eu):
    """Check if classification changed meaningfully."""
    return (
        (llm_result.category != old_cat)
        or (llm_result.country != old_country)
        or (abs(llm_result.eu_relevance - (old_eu or 0)) > 0.5)
    )


def _record_telemetry(classifier, budget):
    """Record token usage from last LLM call."""
    if classifier.last_telemetry:
        budget.record(
            classifier.last_telemetry.get("tokens_in", 0),
            classifier.last_telemetry.get("tokens_out", 0),
        )


def _persist_result(engine, apply, row, llm_result, changes):
    """Persist classification result and track changes."""
    article_id, title, _, _, _, old_cat, old_country, old_eu = row

    if _check_changed(llm_result, old_cat, old_country, old_eu):
        changes.append(
            {
                "id": article_id,
                "title": title[:80],
                "old_category": old_cat,
                "new_category": llm_result.category,
                "old_country": old_country,
                "new_country": llm_result.country,
                "old_eu_relevance": old_eu,
                "new_eu_relevance": llm_result.eu_relevance,
                "confidence": llm_result.confidence,
            }
        )
        print(
            f"  Change: '{title[:50]}' "
            f"{old_cat}->{llm_result.category} "
            f"eu:{old_eu}->{llm_result.eu_relevance} "
            f"conf:{llm_result.confidence:.2f}"
        )
        if apply:
            _apply_change(
                engine,
                article_id,
                llm_result.category,
                llm_result.country,
                llm_result.eu_relevance,
                llm_result.confidence,
            )
    elif apply:
        _apply_confidence_only(engine, article_id, llm_result.confidence)


def main():
    parser = argparse.ArgumentParser(description="Reclassify existing articles")
    parser.add_argument("--apply", action="store_true", help="Write changes to DB")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max articles to process (0=all)",
    )
    args = parser.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from airopa_automation.agents import Article, CategoryClassifierAgent  # noqa: E402
    from airopa_automation.api.models.database import engine  # noqa: E402
    from airopa_automation.budget import TokenBudget  # noqa: E402

    classifier = CategoryClassifierAgent()
    budget = TokenBudget()

    rows = _fetch_articles(engine, args.limit)
    mode = "DRY RUN - " if not args.apply else ""
    print(f"{mode}Reclassifying {len(rows)} articles...")

    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "data",
        "reclassify_log.csv",
    )
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    changes = []
    errors = 0

    for row in rows:
        if budget.exceeded:
            print(f"Budget exceeded ({budget.tokens_used}), stopping.")
            break

        llm_result, had_error = _classify_row(row, classifier, Article)
        if had_error:
            errors += 1
            continue
        if llm_result is None:
            continue

        _record_telemetry(classifier, budget)
        _persist_result(engine, args.apply, row, llm_result, changes)

        time.sleep(0.5)

    if changes:
        _write_csv_log(log_path, changes)

    print(
        f"\nSummary: {len(changes)} changes, "
        f"{errors} errors, {budget.tokens_used} tokens used"
    )
    if not args.apply and changes:
        print("Run with --apply to write changes to the database.")


if __name__ == "__main__":
    main()
