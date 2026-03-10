# AIropa Agentic System Upgrade Plan

## Overview

Transform the keyword-based automation pipeline into an LLM-powered agentic system using Groq, with an iterative approach to keep costs low and manageable.

## Current State

- **Pipeline**: ScraperAgent → ClassifierAgent → QualityScoreAgent → ContentGenerator → GitCommit
- **Classification**: Keyword-based (hardcoded word lists)
- **Quality Scoring**: Rule-based (content length, title length, source)
- **Summaries**: Not generated (field exists but empty)
- **Groq**: Config exists but disabled (`groq==1.0.0` commented out)

## User Requirements

- Iterative approach (start small, expand over time)
- Keep costs low and realistic
- Use Groq as LLM provider (fast, cheap, already in codebase)

---

## Implementation Phases

### Phase 1: Re-enable Groq Foundation
**Goal**: Get Groq working with minimal changes

**Files to modify**:
- `requirements.txt` - Uncomment groq
- `airopa_automation/config.py` - Verify AI config
- Add `GROQ_API_KEY` to Railway environment variables

**Tasks**:
1. Uncomment `groq==1.0.0` in requirements.txt
2. Test Groq import locally
3. Add GROQ_API_KEY to Railway
4. Create simple test script to verify API connectivity

**Cost**: $0 (just setup)

---

### Phase 2: LLM-Powered Classification
**Goal**: Replace keyword matching with intelligent categorization

**File to modify**: `airopa_automation/agents.py`

**Changes to CategoryClassifierAgent**:
```python
class CategoryClassifierAgent:
    def __init__(self):
        self.client = Groq(api_key=config.ai.api_key) if config.ai.api_key else None

    def classify(self, article: Article) -> Article:
        if self.client:
            return self._classify_with_llm(article)
        return self._classify_with_keywords(article)  # Fallback
```

**Prompt design**:
- Input: Title + first 1500 chars of content
- Output: JSON with category + country
- Model: `llama-3.1-8b-instant` (cheapest, fastest)

**Fallback**: Keep keyword-based classification if API fails

**Estimated cost**: ~$0.01 per 100 articles (8B model is very cheap)

---

### Phase 3: Content Summarization
**Goal**: Generate article summaries for better UX

**File to modify**: `airopa_automation/agents.py`

**New SummarizerAgent class**:
```python
class SummarizerAgent:
    def summarize(self, article: Article) -> Article:
        # Generate 2-3 sentence summary
        article.summary = self._generate_summary(article.content)
        return article
```

**Integration points**:
- `airopa_automation/api/services/pipeline.py` (line ~75)
- Add after classification, before quality scoring

**Database**: `summary` field already exists in Article model

**Estimated cost**: ~$0.02 per 100 articles

---

### Phase 4: Smart Quality Scoring
**Goal**: AI-enhanced relevance and quality assessment

**File to modify**: `airopa_automation/agents.py`

**Changes to QualityScoreAgent**:
- Keep rule-based baseline (60% weight)
- Add LLM evaluation (40% weight)
- LLM scores: relevance, clarity, depth

**Blended approach**:
```python
final_score = 0.6 * rule_based_score + 0.4 * llm_score
```

**Estimated cost**: ~$0.01 per 100 articles

---

### Phase 5: Add More RSS Feeds
**Goal**: Expand content sources

**File to modify**: `airopa_automation/config.py`

**New feeds to add**:
```python
rss_feeds = [
    # Existing
    "https://sifted.eu/feed/",
    "https://tech.eu/category/deep-tech/feed",
    "https://tech.eu/category/robotics/feed",
    "https://european-champions.org/feed",
    # New
    "https://www.eu-startups.com/feed/",
    "https://thenextweb.com/feed/",
    "https://siliconcanals.com/feed/",
    "https://tech.eu/category/fintech/feed",
    "https://tech.eu/category/healthtech/feed",
]
```

**Cost**: $0 (more content to classify, but marginal)

---

## Cost Estimation (Monthly)

| Phase | Per 100 Articles | 4x Daily Scrapes | Monthly |
|-------|------------------|------------------|---------|
| Classification | $0.01 | $0.04 | ~$1.20 |
| Summarization | $0.02 | $0.08 | ~$2.40 |
| Quality Scoring | $0.01 | $0.04 | ~$1.20 |
| **Total** | **$0.04** | **$0.16** | **~$4.80** |

Using `llama-3.1-8b-instant` keeps costs minimal.

---

## Files to Modify Summary

| File | Changes |
|------|---------|
| `requirements.txt` | Uncomment groq |
| `airopa_automation/config.py` | Add new RSS feeds |
| `airopa_automation/agents.py` | Update ClassifierAgent, QualityScoreAgent, add SummarizerAgent |
| `airopa_automation/api/services/pipeline.py` | Integrate SummarizerAgent |
| `tests/test_agents.py` | Add tests with mocked Groq |
| Railway env vars | Add GROQ_API_KEY |

---

## Future Phases (After MVP)

- **Phase 6**: Autonomous scheduling (agents decide when to scrape based on source activity)
- **Phase 7**: Feedback learning (improve scoring based on user engagement)
- **Phase 8**: Multi-agent coordination (parallel processing, agent negotiation)
- **Phase 9**: Content enrichment (related articles, topic clustering)

---

## Success Criteria

1. Classification accuracy improves (measure against manual review)
2. Summaries are coherent and useful
3. Quality scores better reflect article value
4. Monthly Groq costs stay under $10
5. No increase in scrape job failures

---

## Rollback Plan

Each phase has fallback to previous behavior:
- Classification: Falls back to keyword matching
- Summarization: Article stored without summary (existing behavior)
- Quality scoring: Falls back to rule-based only

All changes are backward-compatible.
