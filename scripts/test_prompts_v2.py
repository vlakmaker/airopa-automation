"""
Test the v2 classification and summary prompts against sample articles.

Bypasses the scraper (no feedparser needed). Uses the LLM directly
with the updated prompts from agents.py.

Usage:
    python scripts/test_prompts_v2.py
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub out heavy deps so __init__.py doesn't fail
for mod_name in ("feedparser", "newspaper", "slugify", "git"):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# bs4 needs a BeautifulSoup attribute
bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = type("BeautifulSoup", (), {})
sys.modules["bs4"] = bs4_stub

# newspaper needs an Article class
newspaper_stub = sys.modules["newspaper"]
newspaper_stub.Article = type("Article", (), {})

# git needs Actor
git_stub = sys.modules["git"]
git_stub.Repo = type("Repo", (), {})
git_stub.Actor = type("Actor", (), {})

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from airopa_automation.llm import llm_complete  # noqa: E402
from airopa_automation.llm_schemas import parse_classification, parse_summary  # noqa: E402

# Borrow the prompt templates directly
CLASSIFICATION_PROMPT = """You are an editorial classifier for AIropa, a European AI and technology news platform.

Your job is to classify articles AND filter out irrelevant content.

STEP 1: RELEVANCE CHECK
Is this article about AI, technology, startups, tech policy, or digital innovation?
If NO → set eu_relevance to 0, category to "industry", country to "".
Do not try to force-fit non-tech content into a category.

STEP 2: EUROPEAN RELEVANCE (only if Step 1 passes)
Rate 0-10 how relevant this is to the European tech ecosystem:
- 8-10: European company, EU policy, European research lab, or European market focus
- 5-7: Global story with meaningful European angle (European office, EU impact mentioned)
- 2-4: Primarily US/global story with minor European mention
- 0-1: No European connection

STEP 3: CLASSIFY into exactly ONE category based on the PRIMARY focus:
- startups: Funding rounds, product launches, acquisitions, founder stories of startups
- policy: Regulation, government policy, AI ethics, governance, legal frameworks
- research: Academic papers, technical breakthroughs, new models, benchmarks
- industry: Enterprise adoption, corporate partnerships, market analysis, established companies

When in doubt: if the article is about a regulation affecting startups, classify as "policy" (the regulation is the news). If it's about a startup responding to regulation, classify as "startups" (the company is the news).

STEP 4: COUNTRY
Identify the primary European country. Use "Europe" only if genuinely pan-European (e.g., EU-wide policy). Use "" if not European.

Examples:

Title: "French AI startup Mistral raises €400M Series B"
{{"category": "startups", "country": "France", "eu_relevance": 10}}

Title: "EU AI Act enforcement timeline announced by Commission"
{{"category": "policy", "country": "Europe", "eu_relevance": 10}}

Title: "OpenAI launches new model with improved reasoning"
{{"category": "industry", "country": "", "eu_relevance": 1}}

Title: "Psychology says introverts have these 8 habits"
{{"category": "industry", "country": "", "eu_relevance": 0}}

Article:
Title: {title}
Content: {content}

Respond in JSON only:
{{"category": "...", "country": "...", "eu_relevance": ...}}"""

SUMMARY_PROMPT = """You are a news editor for AIropa, a European AI and technology platform.

Write a 2-3 sentence summary of this article for a news card.
The summary should help a reader decide whether to click through to the original article.

Rules:
- State what happened, who is involved, and why it matters
- If the article has a European angle, emphasize it
- If the article is not about AI or technology, write: "NOT_RELEVANT"
- Do NOT include any HTML tags, image URLs, or markup
- Do NOT invent facts not present in the article
- Do NOT repeat the title as the first sentence
- Write in plain text only

Title: {title}
Content: {content}

Summary:"""

# Sample articles covering different categories and edge cases
SAMPLE_ARTICLES = [
    {
        "title": "French AI startup Mistral raises €600M in new funding round",
        "content": (
            "Paris-based AI startup Mistral has closed a €600 million Series B "
            "funding round led by General Catalyst and Lightspeed Venture Partners. "
            "The company, founded by former DeepMind and Meta researchers, builds "
            "open-weight large language models. Mistral now has a valuation of $6 "
            "billion and plans to expand its enterprise offerings across Europe."
        ),
        "expected_category": "startups",
        "expected_country": "France",
    },
    {
        "title": "EU AI Act enforcement timeline announced by Commission",
        "content": (
            "The European Commission has published the official enforcement "
            "timeline for the AI Act. High-risk AI systems must comply by August "
            "2026, while general-purpose AI models face requirements starting "
            "February 2025. Member states must designate national authorities by "
            "August 2025. The regulation affects thousands of companies operating "
            "in the European market."
        ),
        "expected_category": "policy",
        "expected_country": "Europe",
    },
    {
        "title": "DeepMind researchers publish breakthrough in protein folding",
        "content": (
            "Scientists at Google DeepMind's London lab have published a new "
            "paper in Nature showing a significant advance in protein structure "
            "prediction. The updated AlphaFold model can now predict protein "
            "interactions with near-experimental accuracy. The research was led "
            "by a team based in the UK and has implications for drug discovery "
            "across Europe."
        ),
        "expected_category": "research",
        "expected_country": "United Kingdom",
    },
    {
        "title": "SAP integrates generative AI across its enterprise suite",
        "content": (
            "German enterprise software giant SAP has announced the integration "
            "of generative AI capabilities into its core business suite. The "
            "Walldorf-based company is using large language models to automate "
            "business processes for its 400,000 enterprise customers worldwide. "
            "CEO Christian Klein said the AI features will be available to "
            "European customers first."
        ),
        "expected_category": "industry",
        "expected_country": "Germany",
    },
    {
        "title": "OpenAI launches GPT-5 with improved reasoning capabilities",
        "content": (
            "San Francisco-based OpenAI has released GPT-5, its latest large "
            "language model. The new model shows significant improvements in "
            "mathematical reasoning and code generation. CEO Sam Altman said "
            "the model was trained on more data and with new techniques. The "
            "company plans to roll it out to enterprise customers globally."
        ),
        "expected_category": "industry",
        "expected_country": "",
    },
    {
        "title": "Psychology says introverts have these 8 surprising habits",
        "content": (
            "New research from psychology departments reveals that introverted "
            "people share common behavioral patterns. These include preferring "
            "small groups, needing alone time to recharge, and being highly "
            "observant. The study surveyed 2,000 participants across multiple "
            "countries and was published in a psychology journal."
        ),
        "expected_category": "industry",
        "expected_country": "",
    },
    {
        "title": "EU proposes new rules for AI startups to ease compliance burden",
        "content": (
            "The European Commission has proposed a regulatory sandbox framework "
            "to help AI startups comply with the AI Act without excessive costs. "
            "The proposal includes simplified reporting for companies with fewer "
            "than 250 employees. European startup associations have welcomed the "
            "move, saying it will help level the playing field with US competitors."
        ),
        "expected_category": "policy",
        "expected_country": "Europe",
    },
]


def test_connectivity():
    """Quick check that the LLM API is reachable."""
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
        print("PASS\n")
        return True
    else:
        print(f"Error:    {result['error']}")
        print("FAIL - check your API key\n")
        return False


def test_classification():
    """Run classification prompt against sample articles."""
    print("=" * 70)
    print("Step 2: Classification (v2 prompt)")
    print("=" * 70)

    results = []
    for article in SAMPLE_ARTICLES:
        prompt = CLASSIFICATION_PROMPT.format(
            title=article["title"],
            content=article["content"][:1500],
        )
        result = llm_complete(prompt)

        if result["status"] != "ok":
            print(f"  FAIL [{result['status']}]: {article['title'][:50]}")
            results.append({"title": article["title"], "status": "FAIL"})
            continue

        parsed = parse_classification(result["text"])

        cat_match = parsed.category == article["expected_category"] if parsed.valid else False
        country_match = parsed.country == article["expected_country"] if parsed.valid else False

        results.append({
            "title": article["title"][:50],
            "expected_cat": article["expected_category"],
            "got_cat": parsed.category if parsed.valid else "PARSE_FAIL",
            "cat_ok": cat_match,
            "expected_country": article["expected_country"] or "(none)",
            "got_country": parsed.country if parsed.valid else "PARSE_FAIL",
            "country_ok": country_match,
            "eu_relevance": f"{parsed.eu_relevance:.0f}" if parsed.valid else "-",
            "latency": result["latency_ms"],
        })

    # Print table
    print()
    header = f"{'Title':<52} {'Exp Cat':<10} {'Got Cat':<10} {'OK':>3}  {'Exp Ctry':<12} {'Got Ctry':<12} {'OK':>3}  {'EU':>3}  {'ms':>5}"
    print(header)
    print("-" * len(header))

    for r in results:
        if r.get("status") == "FAIL":
            print(f"  {r['title']:<50} FAIL")
            continue
        print(
            f"{r['title']:<52} {r['expected_cat']:<10} {r['got_cat']:<10} "
            f"{'Y' if r['cat_ok'] else 'N':>3}  "
            f"{r['expected_country']:<12} {r['got_country']:<12} "
            f"{'Y' if r['country_ok'] else 'N':>3}  "
            f"{r['eu_relevance']:>3}  {r['latency']:>5}"
        )

    cat_correct = sum(1 for r in results if r.get("cat_ok"))
    total = len(results)
    print(f"\nCategory accuracy: {cat_correct}/{total}")


def test_summary():
    """Run summary prompt against a couple sample articles."""
    print("\n" + "=" * 70)
    print("Step 3: Summary (v2 prompt)")
    print("=" * 70)

    # Test with a relevant and an irrelevant article
    test_articles = [SAMPLE_ARTICLES[0], SAMPLE_ARTICLES[5]]

    for article in test_articles:
        prompt = SUMMARY_PROMPT.format(
            title=article["title"],
            content=article["content"][:2000],
        )
        result = llm_complete(prompt)

        if result["status"] != "ok":
            print(f"\n  FAIL [{result['status']}]: {article['title'][:50]}")
            continue

        parsed = parse_summary(result["text"])
        print(f"\nTitle:   {article['title']}")
        print(f"Valid:   {parsed.valid}")
        print(f"Summary: {parsed.text if parsed.valid else parsed.fallback_reason}")
        print(f"Latency: {result['latency_ms']}ms")


def main():
    print("\nAIropa v2 Prompt Test")
    print("=" * 70 + "\n")

    if not test_connectivity():
        sys.exit(1)

    test_classification()
    test_summary()

    print("\n" + "=" * 70)
    print("Done. No data was written to the database.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
