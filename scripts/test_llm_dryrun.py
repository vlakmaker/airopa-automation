"""
Dry-run: compare keyword vs LLM classification on live articles.

Scrapes a few articles from RSS feeds, classifies with both methods,
prints a side-by-side comparison. No database writes.

Usage:
    LLM_PROVIDER=mistral python scripts/test_llm_dryrun.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airopa_automation.agents import CategoryClassifierAgent, ScraperAgent  # noqa: E402
from airopa_automation.llm import llm_complete  # noqa: E402

MAX_ARTICLES = 5


def test_connectivity():
    """Quick smoke test: can we reach the LLM API?"""
    print("=" * 70)
    print("Step 1: LLM connectivity test")
    print("=" * 70)

    provider = os.getenv("LLM_PROVIDER", "groq")
    print(f"Provider: {provider}")

    result = llm_complete('Respond with only: {"status": "ok"}')
    print(f"Status:   {result['status']}")

    if result["status"] == "ok":
        print(f"Response: {result['text'][:100]}")
        print(f"Latency:  {result['latency_ms']}ms")
        print(f"Tokens:   {result['tokens_in']} in / {result['tokens_out']} out")
        print("PASS\n")
        return True
    else:
        print(f"Error:    {result['error']}")
        print("FAIL - fix your API key before continuing\n")
        return False


def scrape_articles():
    """Scrape a few real articles from RSS feeds."""
    print("=" * 70)
    print(f"Step 2: Scraping up to {MAX_ARTICLES} articles from RSS feeds")
    print("=" * 70)

    scraper = ScraperAgent()
    articles = scraper.scrape_rss_feeds()

    if not articles:
        print("No articles scraped. Check your RSS feeds.\n")
        return []

    articles = articles[:MAX_ARTICLES]
    print(f"Scraped {len(articles)} articles\n")

    for i, a in enumerate(articles, 1):
        print(f"  {i}. [{a.source}] {a.title[:65]}")
    print()

    return articles


def compare_classification(articles):
    """Classify with keywords and LLM, print comparison."""
    print("=" * 70)
    print("Step 3: Classification comparison (keyword vs LLM)")
    print("=" * 70)

    classifier = CategoryClassifierAgent()
    results = []

    for article in articles:
        # Keyword classification
        kw_article = article.model_copy()
        kw_article = classifier._classify_with_keywords(kw_article)

        # LLM classification
        llm_result = classifier._classify_with_llm(article)

        results.append(
            {
                "title": article.title[:45],
                "source": article.source[:12],
                "kw_cat": kw_article.category,
                "kw_country": kw_article.country or "-",
                "llm_cat": llm_result.category if llm_result else "FAIL",
                "llm_country": llm_result.country if llm_result else "-",
                "llm_eu": f"{llm_result.eu_relevance:.0f}" if llm_result else "-",
                "match": (
                    "Y"
                    if llm_result and llm_result.category == kw_article.category
                    else "N"
                ),
            }
        )

    # Print table
    header = (
        f"{'Title':<47} {'Source':<13} "
        f"{'KW Cat':<10} {'LLM Cat':<10} "
        f"{'KW Ctry':<10} {'LLM Ctry':<10} "
        f"{'EU':>3} {'Match':>5}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        print(
            f"{r['title']:<47} {r['source']:<13} "
            f"{r['kw_cat']:<10} {r['llm_cat']:<10} "
            f"{r['kw_country']:<10} {r['llm_country']:<10} "
            f"{r['llm_eu']:>3} {r['match']:>5}"
        )

    # Summary
    total = len(results)
    matches = sum(1 for r in results if r["match"] == "Y")
    llm_ok = sum(1 for r in results if r["llm_cat"] != "FAIL")
    print(
        f"\nResults: {llm_ok}/{total} LLM succeeded, "
        f"{matches}/{total} category match with keywords"
    )


def main():
    print("\nAIropa LLM Classification Dry Run")
    print("=" * 70 + "\n")

    if not test_connectivity():
        sys.exit(1)

    articles = scrape_articles()
    if not articles:
        sys.exit(1)

    compare_classification(articles)

    print("\nDone. No data was written to the database.\n")


if __name__ == "__main__":
    main()
