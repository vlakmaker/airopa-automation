# AIropa Agentic System Upgrade — Implementation Plan

**Full spec:** `vibelore-knowledge/projects/airopa/specs/agentic-upgrade-v2.md`

## Context

AIropa's automation is MVP-grade. Baseline analysis of 56 articles revealed:
- **48% source concentration** — Sifted duplicated under two names
- **11% misclassification** — keyword system confuses "country" category with metadata
- **57% missing country** — undermines European relevance scoring
- **Quality scores cluster 0.6-0.9** — no real discrimination (content-length proxy)
- **98% missing images** — image pipeline needs more scrape cycles

---

## Strategic Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM Provider | Groq with llama-3.3-70b-versatile | Best quality/cost. 70B much better than 8B for nuanced European context. |
| Categories | `startups`, `policy`, `research`, `industry` | Replaces MVP categories. `country` stays as metadata field. |
| European relevance score | Internal only (0-10) | Used for ranking/scoring, not shown in UI. |
| LLM abstraction | Simple wrapper function | `llm_complete(prompt, model)` wrapping Groq. Easy to swap later. |
| Fallback strategy | Keyword classification when Groq unavailable | Backward compatible, no pipeline failures. |
| Rollout strategy | Feature flags + shadow mode before cutover | Reduces production risk. |
| Output contract | Strict JSON schema validation + safe defaults | Prevents malformed LLM output from breaking pipeline. |

---

## Pre-Phase 0: Pipeline Fixes — COMPLETE (2026-02-06)

Fix data issues before adding LLM capabilities.

1. ~~**Source name normalization**~~ — `_normalize_source_name()` + `source_name_map` config
2. ~~**Published date filter**~~ — `_is_article_too_old()`, configurable `MAX_ARTICLE_AGE_DAYS=30`
3. ~~**Clean "country" categories**~~ — `scripts/fix_country_categories.py` migration
4. ~~**Source metrics table**~~ — `SourceMetric` model + pipeline tracking + migration

**Files changed:** `agents.py`, `config.py`, `database.py`, `pipeline.py`, `scripts/fix_country_categories.py`, `scripts/add_source_metrics.py`, `tests/test_agents.py`
**Tests:** 9 new (35 total), all linters clean

---

## Phase 0: Evaluation + Reliability Foundation

1. **Feature flags** — `LLM_CLASSIFICATION_ENABLED`, `LLM_SHADOW_MODE`, etc.
2. **LLM wrapper** — `airopa_automation/llm.py` with structured status/telemetry
3. **Schema validation** — `airopa_automation/llm_schemas.py` with typed parsing + clamping
4. **Budget guardrails** — Per-run token/cost cap with circuit breaker
5. **Enable Groq** — Uncomment in `requirements.txt`

**Files:** `config.py`, `llm.py` (new), `llm_schemas.py` (new), `requirements.txt`, `tests/test_llm.py` (new)

---

## Phase 1: LLM Classification

1. **Update `CategoryClassifierAgent`** — Add `_classify_with_llm()` + rename existing to `_classify_with_keywords()` fallback
2. **Shadow mode support** — Run both classifiers, log LLM result, keep keyword output until gates pass
3. **`eu_relevance` field** — Pydantic model + DB column + migration script
4. **Config** — Default model to `llama-3.3-70b-versatile`

**Files:** `agents.py`, `database.py`, `schemas.py`, `scripts/add_eu_relevance.py`, `tests/test_agents.py`

### Verification
1. `pytest tests/ -v` — all pass
2. Linters clean (`flake8`, `black`, `isort`, `mypy`)
3. Run migration on Railway
4. Deploy with `LLM_SHADOW_MODE=true`
5. Compare LLM vs keyword on live articles
6. Promote `LLM_CLASSIFICATION_ENABLED=true` when rollout gates pass

---

## Future Phases

- **Phase 2:** Content Summarization (2-3 sentence editorial summaries)
- **Phase 3:** Frontend Compatibility + Summary UX
- **Phase 4:** Smart Quality Scoring (hybrid 60% rules + 40% LLM)
- **Phase 5:** RSS Source Expansion (10-15 new feeds in batches)
- **Later:** Story dedup, trending topics, source quality learning, newsletter generation
