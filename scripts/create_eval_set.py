"""
Create an LLM-bootstrapped evaluation set from exported article data.

Samples 200 articles stratified by source, runs both keyword and LLM
classification, and outputs a CSV for human review.

Usage:
    python scripts/create_eval_set.py

Requires: GROQ_API_KEY in environment or .env
"""

import csv
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from airopa_automation.agents import Article, CategoryClassifierAgent  # noqa: E402
from airopa_automation.llm import llm_complete  # noqa: E402
from airopa_automation.llm_schemas import parse_classification  # noqa: E402

CLASSIFICATION_PROMPT = CategoryClassifierAgent.CLASSIFICATION_PROMPT
INPUT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "railway_articles.csv",
)
OUTPUT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "eval_set.csv",
)
SAMPLE_SIZE = 200


def load_articles(path: str) -> list[dict]:
    """Load articles from CSV."""
    articles = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            articles.append(row)
    return articles


def stratified_sample(articles: list[dict], n: int) -> list[dict]:
    """Sample articles stratified by source, with 30%+ short/ambiguous content."""
    random.seed(42)

    # Group by source
    by_source: dict[str, list[dict]] = {}
    for art in articles:
        by_source.setdefault(art["source"], []).append(art)

    # Calculate per-source quota (proportional)
    total = len(articles)
    sampled = []
    for source, arts in by_source.items():
        quota = max(1, round(n * len(arts) / total))
        random.shuffle(arts)
        sampled.extend(arts[:quota])

    # Trim or pad to target size
    random.shuffle(sampled)
    if len(sampled) > n:
        sampled = sampled[:n]
    elif len(sampled) < n:
        remaining = [a for a in articles if a not in sampled]
        random.shuffle(remaining)
        sampled.extend(remaining[: n - len(sampled)])

    # Ensure 30%+ have short content (< 500 chars) — these are harder cases
    short = [a for a in sampled if len(a.get("content", "")) < 500]
    if len(short) < n * 0.3:
        # Swap in more short-content articles
        short_pool = [
            a for a in articles if len(a.get("content", "")) < 500 and a not in sampled
        ]
        random.shuffle(short_pool)
        long_in_sample = [a for a in sampled if len(a.get("content", "")) >= 500]
        swap_count = min(
            int(n * 0.3) - len(short), len(short_pool), len(long_in_sample)
        )
        for i in range(swap_count):
            sampled.remove(long_in_sample[-(i + 1)])
            sampled.append(short_pool[i])

    return sampled[:n]


def classify_with_keywords(article_dict: dict) -> str:
    """Run keyword classifier on an article dict."""
    article = Article(
        title=article_dict.get("title", ""),
        url=article_dict.get("url", ""),
        source=article_dict.get("source", ""),
        content=article_dict.get("content", ""),
    )
    classifier = CategoryClassifierAgent()
    result = classifier._classify_with_keywords(article)
    return result.category


def classify_with_llm(article_dict: dict) -> dict:
    """Run LLM classifier on an article dict."""
    content = article_dict.get("content", "")[:1500]
    prompt = CLASSIFICATION_PROMPT.format(
        title=article_dict.get("title", ""),
        content=content,
    )

    result = llm_complete(prompt)
    if result["status"] != "ok":
        return {"llm_category": "error", "llm_country": "", "llm_eu_relevance": ""}

    parsed = parse_classification(result["text"])
    if not parsed.valid:
        return {
            "llm_category": "parse_error",
            "llm_country": "",
            "llm_eu_relevance": "",
        }

    return {
        "llm_category": parsed.category,
        "llm_country": parsed.country,
        "llm_eu_relevance": parsed.eu_relevance,
    }


def main():
    print(f"Loading articles from {INPUT_CSV}...")
    articles = load_articles(INPUT_CSV)
    print(f"Loaded {len(articles)} articles")

    print(f"Sampling {SAMPLE_SIZE} articles (stratified by source)...")
    sample = stratified_sample(articles, SAMPLE_SIZE)
    print(f"Sampled {len(sample)} articles")

    short_count = len([a for a in sample if len(a.get("content", "")) < 500])
    pct = short_count * 100 // len(sample)
    print(f"Short content articles (<500 chars): {short_count} ({pct}%)")

    output_rows = []
    for i, art in enumerate(sample):
        print(f"[{i+1}/{len(sample)}] {art['title'][:60]}...")

        # Keyword classification
        kw_cat = classify_with_keywords(art)

        # LLM classification
        llm_result = classify_with_llm(art)

        output_rows.append(
            {
                "url": art["url"],
                "title": art["title"],
                "source": art["source"],
                "content_preview": art.get("content", "")[:200],
                "keyword_category": kw_cat,
                "llm_category": llm_result["llm_category"],
                "llm_country": llm_result["llm_country"],
                "llm_eu_relevance": llm_result["llm_eu_relevance"],
                "human_category": "",  # For manual review
                "human_country": "",
                "human_eu_relevance": "",
                "notes": "",
            }
        )

        # Rate limiting
        time.sleep(0.5)

    # Write output
    print(f"\nWriting eval set to {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_rows[0].keys())
        writer.writeheader()
        writer.writerows(output_rows)

    # Print summary
    llm_cats = {}
    kw_cats = {}
    for row in output_rows:
        llm_cats[row["llm_category"]] = llm_cats.get(row["llm_category"], 0) + 1
        kw_cats[row["keyword_category"]] = kw_cats.get(row["keyword_category"], 0) + 1

    print("\n=== Eval Set Summary ===")
    print(f"Total articles: {len(output_rows)}")
    print(f"\nKeyword classification distribution: {json.dumps(kw_cats, indent=2)}")
    print(f"\nLLM classification distribution: {json.dumps(llm_cats, indent=2)}")

    # Agreement rate
    agree = sum(1 for r in output_rows if r["keyword_category"] == r["llm_category"])
    pct = agree * 100 // len(output_rows)
    print(f"\nKeyword/LLM agreement: {agree}/{len(output_rows)} ({pct}%)")
    print(f"\nDone! Review {OUTPUT_CSV} and fill in human_category columns.")


if __name__ == "__main__":
    main()
