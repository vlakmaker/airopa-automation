# AIropa Automation -- System Architecture Review

## 1. HIGH-LEVEL ARCHITECTURE (Grounded)

### System Overview

AIropa Automation is an automated European AI/tech news scraping, classification, and publishing pipeline. It ingests articles from 15 RSS feeds and 3 web sources, classifies them using LLM (with keyword fallback), generates summaries, scores quality, stores results in a database, and serves them via a REST API.

### Components

| Component | Responsibility | Key File(s) |
|---|---|---|
| **ScraperAgent** | Fetches articles from RSS feeds (feedparser) and web pages (newspaper3k, BeautifulSoup). Normalizes source names, filters stale articles, extracts images. | `airopa_automation/agents.py:59-333` -- class `ScraperAgent` |
| **CategoryClassifierAgent** | Classifies articles into 5 categories (startups, policy, research, industry, other) plus country/EU-relevance. Supports LLM, keyword fallback, and shadow mode. | `airopa_automation/agents.py:335-541` -- class `CategoryClassifierAgent` |
| **SummarizerAgent** | Generates 2-3 sentence editorial summaries via LLM. Respects feature flags and shadow mode. | `airopa_automation/agents.py:544-672` -- class `SummarizerAgent` |
| **QualityScoreAgent** | Computes a 0-1.0 quality score from 5 weighted signals: content depth (0.30), EU relevance (0.25), title quality (0.15), source credibility (0.15), metadata completeness (0.15). | `airopa_automation/agents.py:675-752` -- class `QualityScoreAgent` |
| **LLM Abstraction** | Dispatches to Groq or Mistral APIs. Returns structured dicts with telemetry. Never raises exceptions into calling code. | `airopa_automation/llm.py:17-64` -- function `llm_complete` |
| **LLM Schema Validation** | Parses and validates JSON from LLM responses. Enforces business rules (low-confidence demotion, irrelevance demotion). | `airopa_automation/llm_schemas.py:38-168` -- `parse_classification`, `validate_classification` |
| **Token Budget** | Per-run token cap (default 50,000). When exceeded, pipeline falls back to keyword classification. | `airopa_automation/budget.py:15-42` -- class `TokenBudget` |
| **PipelineService** | Orchestrates the full scrape→classify→summarize→score→store pipeline. Manages deduplication, telemetry persistence, source metrics, and job status. | `airopa_automation/api/services/pipeline.py:29-438` -- class `PipelineService` |
| **FastAPI Application** | REST API with CORS, rate limiting, API-key auth. Routes for articles, jobs, health. | `airopa_automation/api/main.py:12-89` -- `app = FastAPI(...)` |
| **SQLAlchemy Data Layer** | 4 tables: `articles`, `jobs`, `source_metrics`, `llm_telemetry`. SQLite (dev) / PostgreSQL (prod). | `airopa_automation/api/models/database.py:15-180` |
| **Configuration** | Pydantic-based config with env var overrides for feature flags, LLM keys, thresholds. | `airopa_automation/config.py:13-136` -- class `Config`, global `config` |
| **Scheduled Scrape** | GitHub Actions cron (every 6h) calls `POST /api/scrape/sync` on Railway. | `.github/workflows/scheduled-scrape.yml:6` |
| **Legacy CLI Pipeline** | Original pipeline runner generating markdown files and committing to git. Not used by the API. | `main.py:25-158` -- class `AutomationPipeline` |

### API Endpoints

| Method | Path | Auth | Rate Limit | Handler | File |
|---|---|---|---|---|---|
| `GET` | `/` | None | None | `root()` | `api/main.py:69` |
| `GET` | `/api/health` | None | 100/min | `health_check()` | `api/routes/health.py:17` |
| `GET` | `/api/articles` | None | 100/min | `list_articles()` | `api/routes/articles.py:30` |
| `GET` | `/api/articles/{id}` | None | 100/min | `get_article()` | `api/routes/articles.py:132` |
| `POST` | `/api/scrape` | API Key | 5/min | `trigger_scrape()` | `api/routes/jobs.py:25` |
| `POST` | `/api/scrape/sync` | API Key | 5/min | `trigger_scrape_sync()` | `api/routes/jobs.py:80` |
| `GET` | `/api/jobs/{job_id}` | None | 100/min | `get_job_status()` | `api/routes/jobs.py:161` |

### Database Tables

| Table | Model Class | File | Purpose |
|---|---|---|---|
| `articles` | `Article` | `api/models/database.py:15-45` | Processed article storage |
| `jobs` | `Job` | `api/models/database.py:102-118` | Background job tracking |
| `source_metrics` | `SourceMetric` | `api/models/database.py:48-70` | Per-source stats per scrape run |
| `llm_telemetry` | `LLMTelemetry` | `api/models/database.py:73-99` | LLM call observability |

---

## 2. DATAFLOW WALKTHROUGH

### How a new article enters and flows through the system:

**Step 1: Trigger** -- A GitHub Actions cron job (`.github/workflows/scheduled-scrape.yml:6`, every 6 hours) calls `POST /api/scrape/sync`. The endpoint handler at `api/routes/jobs.py:80` (`trigger_scrape_sync`) creates a `Job` record with status `queued` and calls `pipeline_service.run_scrape_job(job_id)` synchronously.

**Step 2: Scrape** -- `PipelineService.run_scrape_job()` at `api/services/pipeline.py:44` calls `ScraperAgent.scrape_rss_feeds()` (`agents.py:93`) which iterates over 15 RSS feed URLs (configured in `config.py:14-34`). For each feed entry, `_extract_article_data()` (`agents.py:245`) uses newspaper3k to download and parse the article page. If newspaper3k returns < 200 chars, RSS `content:encoded` is used as fallback (`agents.py:129-139`). Articles older than `max_article_age_days` (default 30) are skipped (`agents.py:78-91`). The method also calls `scrape_web_sources()` (`agents.py:168`) for 3 additional HTML sources.

**Step 3: Deduplicate** -- `_remove_duplicates()` (`pipeline.py:379-410`) removes duplicates by URL and SHA-256 content hash (computed from `title + url + source` in `agents.py:53-56`).

**Step 4: Classify** -- Each article passes through `CategoryClassifierAgent.classify()` (`agents.py:399`). If `LLM_CLASSIFICATION_ENABLED=true` and token budget not exceeded, `_classify_with_llm()` (`agents.py:445`) sends a prompt to Groq/Mistral via `llm_complete()` (`llm.py:17`). The LLM response JSON is parsed by `parse_classification()` (`llm_schemas.py:38`) and validated by `validate_classification()` (`llm_schemas.py:126`) which applies business rules: articles with confidence < 0.5 or eu_relevance < 2.0 are demoted to category "other". If LLM is disabled or fails, `_classify_with_keywords()` (`agents.py:505`) applies simple keyword matching. Token usage is tracked by `TokenBudget` (`budget.py:15`); once exceeded, remaining articles use keyword fallback (`pipeline.py:80-91`).

**Step 5: Summarize** -- `SummarizerAgent.summarize()` (`agents.py:574`) generates LLM summaries if `LLM_SUMMARY_ENABLED=true`. Content is truncated to 2000 chars (`agents.py:631`). The response is validated by `parse_summary()` (`llm_schemas.py:188`) which rejects markdown, HTML, and summaries with > 5 sentences. Shares the same token budget.

**Step 6: Assess Quality** -- `QualityScoreAgent.assess_quality()` (`agents.py:690`) computes a weighted score from 5 signals. Only articles scoring >= 0.6 pass (`pipeline.py:173-175`).

**Step 7: Store** -- `_store_article()` (`pipeline.py:226`) generates a SHA-256 hash from `url|title` (`pipeline.py:412-424`), checks for duplicates by URL or hash against the DB (`pipeline.py:242-249`), and inserts a new `articles` row. Per-article commits (`pipeline.py:275`).

**Step 8: Record Metrics** -- `_record_telemetry()` (`pipeline.py:346`) persists LLM call telemetry to `llm_telemetry`. `_record_source_metrics()` (`pipeline.py:289`) aggregates and stores per-source counts, quality averages, and category distributions.

**Step 9: Serve** -- `GET /api/articles` (`api/routes/articles.py:30`) queries articles with filters: excludes `category='other'` (line 59), excludes `quality_score < 0.4` (line 70), excludes `eu_relevance < threshold` (default 3.0, lines 62-67, allowing NULL through). Orders by `coalesce(published_date, created_at) DESC` (lines 87-91).

---

## 3. DECISION RECORD

### DR-1: LLM Feature Flags with Shadow Mode

- **What:** LLM classification/summarization is gated by feature flags (`LLM_CLASSIFICATION_ENABLED`, `LLM_SHADOW_MODE`) with keyword fallback.
- **Why:** Evidence in `agents.py:400-409` comments: "classification_enabled=False: keywords only (current default) / shadow_mode=True: run both, log LLM result, apply keyword result". The `AGENTIC_UPGRADE_PLAN.md` documents a 5-phase rollout strategy.
- **Evidence:** `config.py:82-88` (flags default to `false`/`true`), `agents.py:399-443` (dispatch logic), `AGENTIC_UPGRADE_PLAN.md` (strategic plan).
- **Alternatives:** Ship LLM directly without gradual rollout; use A/B testing at the API layer.
- **Trade-offs:** Increases code complexity (three paths: keywords-only, shadow, live). Shadow mode doubles LLM cost during evaluation. However, it prevents LLM regressions from affecting production output.

### DR-2: Per-Run Token Budget

- **What:** A `TokenBudget` caps total LLM tokens per scrape run (default 50,000).
- **Why:** Evidence in `budget.py:1-6` docstring: "Prevents runaway costs by enforcing a per-run token cap. When the budget is exceeded, callers should fall back to non-LLM paths."
- **Evidence:** `budget.py:15-42`, `pipeline.py:74-99` (budget check before each classify call), `config.py:89-90` (`LLM_BUDGET_MAX_TOKENS`).
- **Alternatives:** Per-day budget, per-API-key rate limiting at the provider level, no budget (rely on provider billing alerts).
- **Trade-offs:** Simple to implement but coarse-grained. Later articles in a batch may get worse (keyword-only) classification. No cross-run tracking means a burst of manual triggers could still overspend.

### DR-3: SQLite (Dev) / PostgreSQL (Prod) with No Migration Framework

- **What:** Database uses SQLite locally and PostgreSQL on Railway. Migrations are hand-written scripts in `scripts/`.
- **Why:** INFERRED -- Likely chosen for simplicity during early development. No Alembic or similar framework is present.
- **Evidence:** `api/models/database.py:122-134` (engine config with SQLite fallback), `scripts/add_eu_relevance.py`, `scripts/add_confidence_column.py` etc. (manual ALTER TABLE scripts).
- **Alternatives:** Alembic (standard SQLAlchemy migration tool), Django-style migrations, raw SQL versioned files.
- **Trade-offs:** No migration versioning or rollback capability. Manual scripts risk being run out of order or forgotten. Schema drift between dev/prod is possible.

### DR-4: FastAPI BackgroundTasks Instead of a Task Queue

- **What:** The async scrape endpoint uses FastAPI's built-in `BackgroundTasks`, not Celery/RQ/etc.
- **Why:** INFERRED -- Simplicity for a single-worker deployment on Railway. The comment in `jobs.py:90-95` mentions "Designed for cron/CI callers that need to wait for completion anyway."
- **Evidence:** `api/routes/jobs.py:61` (`background_tasks.add_task(...)`), `Procfile` (single uvicorn process). No Redis/Celery/RQ in `requirements.txt`.
- **Alternatives:** Celery + Redis, RQ, Dramatiq, or AWS SQS/Lambda.
- **Trade-offs:** Background tasks run in the same process. If the worker crashes mid-job, the job is lost with no retry. No distributed scaling. Jobs cannot be monitored externally (no broker dashboard). However, this avoids infrastructure complexity for what is essentially a cron-triggered batch job.

### DR-5: Dual Hash Computation for Deduplication

- **What:** Two different hash algorithms exist: `Article.generate_hash()` in the pipeline model uses `sha256(title + url + source)` (`agents.py:55`), while `PipelineService._generate_hash()` uses `sha256(url + "|" + title)` (`pipeline.py:423`).
- **Why:** UNKNOWN -- No comments explain why two different hashing schemes exist.
- **Evidence:** `agents.py:53-56` (in-memory dedup), `pipeline.py:412-424` (DB-level dedup).
- **Alternatives:** Single hash computation shared between pipeline dedup and DB storage.
- **Trade-offs:** Two articles with the same URL and title but different sources would be considered different by the DB hash but the same by the pipeline hash. This is an inconsistency that could lead to missed deduplication or unexpected behavior.

### DR-6: API Key Authentication Without Rotation/Multi-Key

- **What:** A single API key via `API_KEY` env var, checked against `X-API-Key` header. If unset, all requests pass.
- **Why:** Evidence in `auth.py:43-50` comment: "If no API key is configured, allow access (for development). In production, always set the API_KEY environment variable."
- **Evidence:** `api/auth.py:20-66`, `api/routes/jobs.py:31` (Depends on `verify_api_key`).
- **Alternatives:** JWT, OAuth2, multi-key support, API key rotation mechanism.
- **Trade-offs:** Simple but fragile. No key rotation without downtime. Dev-mode bypass is a security risk if `API_KEY` is accidentally unset in production. Single key is shared between GitHub Actions and any other client.

### DR-7: No Foreign Key Constraints in Database

- **What:** `source_metrics.run_id` and `llm_telemetry.run_id` reference `jobs.id` but no `ForeignKey` is declared.
- **Why:** UNKNOWN -- No comments explain the absence.
- **Evidence:** `api/models/database.py:56` (`run_id = Column(String, nullable=False, index=True)` -- no FK), `pipeline.py:322-323` (application code manually links run_id to job_id).
- **Alternatives:** Declare `ForeignKey("jobs.id")` with `ON DELETE CASCADE`.
- **Trade-offs:** Allows orphaned telemetry/metrics rows if a job is deleted. Trades referential integrity for simpler table creation (no FK ordering issues).

### DR-8: Content Truncation Before LLM

- **What:** Article content is truncated to 1500 chars for classification (`agents.py:458`) and 2000 chars for summarization (`agents.py:631`).
- **Why:** INFERRED -- Likely to stay within token limits and reduce cost, given `max_tokens: 1024` for responses (`config.py:75`).
- **Evidence:** `agents.py:458` (1500 char truncation), `agents.py:631` (2000 char truncation), `config.py:75` (`max_tokens: int = 1024`).
- **Alternatives:** Token-based truncation (more accurate), sliding window, or chunked processing.
- **Trade-offs:** Character-based truncation is imprecise (different token:char ratios per language/model). Long articles may lose context-critical information in the middle/end.

---

## 4. ISSUES AND RISKS

### I-1: Exposed API Key in `.env` File (S1)
- **Symptom:** A live Groq API key (`gsk_9ekJ...`) is present in the `.env` file.
- **Location:** `/home/vlakmaker/airopa-automation/.env`
- **Impact:** If this file was ever committed to git or the workspace is shared, the key is compromised. Attacker could consume LLM quota or exfiltrate data.
- **Severity:** S1 (production-breaking if key is still active)
- **Fix sketch:** Rotate the Groq API key immediately. Verify `.env` was never committed (`git log --all --diff-filter=A -- .env`). Ensure `.gitignore` entry is working.

### I-2: `PipelineService` Instantiated at Module Import Time (S2)
- **Symptom:** `pipeline_service = PipelineService()` at `pipeline.py:428` runs at import time, which calls `ensure_directories()` and creates agent instances. This creates a global singleton that cannot be dependency-injected and makes testing harder.
- **Location:** `airopa_automation/api/services/pipeline.py:428`
- **Impact:** If `ensure_directories()` fails (e.g., filesystem permissions), the entire module fails to import, crashing the API. Also, the singleton's `ScraperAgent` holds a persistent `requests.Session`, which may not be thread-safe under concurrent uvicorn workers.
- **Severity:** S2 (significant risk in multi-worker deployment)
- **Fix sketch:** Use FastAPI dependency injection or lazy initialization. Create `PipelineService` instances per-request or use a factory pattern.

### I-3: Inconsistent Hash Functions Between Pipeline and DB (S3)
- **Symptom:** `Article.generate_hash()` hashes `title + url + source` (`agents.py:55`), while `_generate_hash()` hashes `url + "|" + title` (`pipeline.py:423`). Different input → different hashes.
- **Location:** `agents.py:53-56` vs `pipeline.py:412-424`
- **Impact:** An article deduplicated in the pipeline phase could still be flagged as duplicate (or not) at the DB storage phase, or vice versa. In practice the URL uniqueness constraint likely catches most cases, but edge cases exist.
- **Severity:** S3 (minor/cleanup)
- **Fix sketch:** Consolidate to a single hash function. Use the `Article.generate_hash()` method everywhere, or standardize on `url|title`.

### I-4: Per-Article DB Commits in `_store_article()` (S2)
- **Symptom:** Each article is committed individually (`pipeline.py:275`, `db.commit()` inside the loop at `pipeline.py:181-186`).
- **Location:** `airopa_automation/api/services/pipeline.py:226-287` (`_store_article`)
- **Impact:** For a batch of ~150 articles (15 feeds x 10 articles), this means ~150 individual transactions. On PostgreSQL this is significantly slower than a single batch commit. If the process crashes mid-batch, partial results are committed with no way to roll back the entire run.
- **Severity:** S2 (significant performance risk)
- **Fix sketch:** Accumulate all articles in the session and commit once at the end of the batch, with a single rollback on failure.

### I-5: `datetime.utcnow()` Deprecated in Python 3.12+ (S3)
- **Symptom:** `datetime.utcnow()` is used throughout as default values and in pipeline logic. This function is deprecated since Python 3.12 and returns naive datetimes.
- **Location:** `api/models/database.py:36-38` (column defaults), `pipeline.py:200,270-271`, `agents.py:45` (`scraped_date`).
- **Impact:** Naive datetimes can cause timezone-related bugs when comparing with timezone-aware dates from RSS feeds (which `_is_article_too_old` at `agents.py:87-91` does handle correctly by forcing UTC). Deprecation warnings in Python 3.12+.
- **Severity:** S3 (minor, but project targets Python 3.12)
- **Fix sketch:** Replace with `datetime.now(timezone.utc)` throughout. Use `timezone.utc` in SQLAlchemy column defaults via `server_default` or `default=lambda: datetime.now(timezone.utc)`.

### I-6: Keyword Classifier Never Assigns "other" or EU Relevance (S2)
- **Symptom:** `_classify_with_keywords()` (`agents.py:505-541`) assigns one of {startups, policy, research, industry} but never "other". It also never sets `eu_relevance` or `confidence`, leaving them at their Pydantic defaults (0.0).
- **Location:** `airopa_automation/agents.py:505-541`
- **Impact:** When LLM is disabled (default), all articles pass through with `eu_relevance=0.0`. The API's EU relevance filter (`articles.py:64-67`) allows NULL eu_relevance through but blocks `eu_relevance < 3.0`. Since keyword-classified articles have `eu_relevance=0.0` (not NULL), they are **filtered out** by the API unless `eu_relevance_threshold` is set to 0. This means keyword-only mode produces articles that the API hides.
- **Severity:** S2 (significant -- keyword-only articles may be invisible to API consumers depending on threshold config)
- **Fix sketch:** Either: (a) set `eu_relevance=None` in keyword mode so the NULL-passthrough works, or (b) add keyword-based EU relevance scoring, or (c) set a default `eu_relevance` > threshold for keyword-classified articles.

### I-7: Auth Bypass When `API_KEY` Env Var Unset (S2)
- **Symptom:** `verify_api_key()` returns `"no_key_configured"` and allows access when `API_KEY` is not set (`auth.py:45-50`).
- **Location:** `airopa_automation/api/auth.py:45-50`
- **Impact:** If Railway deployment accidentally loses the `API_KEY` env var, scrape endpoints become fully unauthenticated. Any internet client could trigger scrape jobs.
- **Severity:** S2 (significant -- deployment misconfiguration risk)
- **Fix sketch:** Make `API_KEY` required in production. Check `os.getenv("RAILWAY_ENVIRONMENT")` or similar to distinguish dev from prod, and fail hard if unset in prod.

### I-8: `source_metrics` Not Committed in Same Transaction as Job (S3)
- **Symptom:** `_record_source_metrics()` calls `db.flush()` (`pipeline.py:342`) but not `db.commit()`. The commit only happens later when the job status is updated (`pipeline.py:202`). If the job status commit fails, source metrics are also lost.
- **Location:** `airopa_automation/api/services/pipeline.py:342` (flush only)
- **Impact:** Minor data loss risk. However, `flush()` without `commit()` means the data is in the session but not persisted until the next `commit()`. If the session is rolled back (exception handler at line 221), both metrics and telemetry are lost.
- **Severity:** S3 (minor -- the rollback scenario is already an error case)
- **Fix sketch:** This is acceptable if the intent is transactional consistency. Document the intent.

### I-9: `scraped_date` Uses `datetime.now()` Without Timezone (S3)
- **Symptom:** `Article` model defaults `scraped_date` to `datetime.now()` (`agents.py:45`) which returns local time, not UTC.
- **Location:** `airopa_automation/agents.py:45`
- **Impact:** If the server timezone is not UTC (unlikely on Railway, but possible in dev), scraped_date will be in a different timezone than `published_date` and DB timestamps.
- **Severity:** S3 (minor inconsistency)
- **Fix sketch:** Use `datetime.now(timezone.utc)` or `default_factory=lambda: datetime.now(timezone.utc)`.

### I-10: Rate Limiter Uses In-Memory Storage (S2)
- **Symptom:** `slowapi` uses the default in-memory storage (`api/rate_limit.py:14-18`). No persistent backend (Redis, etc.) is configured.
- **Location:** `airopa_automation/api/rate_limit.py`
- **Impact:** Rate limits reset on every server restart. With multiple uvicorn workers (if scaled), each worker has independent counters, effectively multiplying the rate limit. Currently a single-worker deployment, but this becomes a problem at scale.
- **Severity:** S2 (significant if scaling; minor currently)
- **Fix sketch:** Accept for single-worker. If scaling, switch to Redis-backed storage for slowapi.

---

## 5. OPEN QUESTIONS

1. **Is the legacy CLI pipeline (`main.py`) still used?** It generates markdown files and commits to a separate git repo (`../airopa/src/content/post`). Is there still a frontend consuming these markdown files, or has the API fully replaced this workflow?

2. **What is the production value of `LLM_CLASSIFICATION_ENABLED` and `LLM_SHADOW_MODE` on Railway?** The `.env` file shows `LLM_CLASSIFICATION_ENABLED=true` and `LLM_SHADOW_MODE=false`, but Railway env vars may differ. This determines whether articles are LLM-classified or keyword-classified in production.

3. **Is the `eu_relevance=0.0` vs NULL interaction in keyword mode intentional?** (See I-6.) Are keyword-classified articles meant to be hidden from the API, or is this a bug?

4. **How is the Groq API key budget managed externally?** The token budget is per-run, but there's no cross-run or monthly cap. Is there a billing alert on the Groq account?

5. **Is the `Database` class in `airopa_automation/database.py` still used?** It's a raw SQLite wrapper that appears to be from the original implementation, now superseded by the SQLAlchemy layer. Is anything referencing it?

6. **What frontend consumes the API?** CORS allows `localhost:5173` and `localhost:3000`, suggesting a local frontend dev server. Is there a separate frontend repo?

7. **Are the manual migration scripts (`scripts/add_*.py`) still needed going forward?** Would adopting Alembic be worthwhile at this stage?

8. **How many articles are typically processed per run?** This affects whether the per-article commit pattern (I-4) is a real performance concern.

---

## 6. CONFIDENCE REPORT

| # | Claim | Confidence | Reasoning |
|---|---|---|---|
| 1 | **The pipeline flow is: scrape → classify → summarize → quality score → store → serve.** | HIGH | Directly verified in `pipeline.py:44-204` (run_scrape_job method) with clear sequential steps, each calling the corresponding agent. |
| 2 | **Keyword-classified articles with `eu_relevance=0.0` are filtered out by the API when `eu_relevance_threshold > 0`.** | HIGH | The keyword classifier never sets `eu_relevance` (stays at Pydantic default `0.0` per `agents.py:49`). The API filter at `articles.py:64-67` allows NULL but blocks values below threshold. `0.0 < 3.0` → filtered. Confirmed by reading both code paths. |
| 3 | **There are two inconsistent hash functions for deduplication.** | HIGH | `agents.py:55` hashes `f"{self.title}{self.url}{self.source}"` while `pipeline.py:423` hashes `f"{url}|{title}"`. Different inputs produce different SHA-256 outputs. Verified by reading both functions directly. |
| 4 | **The auth system allows unauthenticated access to scrape endpoints when `API_KEY` is unset.** | HIGH | `auth.py:45-50`: `if not expected_key: ... return "no_key_configured"` -- explicitly returns success, does not raise. Verified by reading the function. |
| 5 | **The system uses Groq's `llama-3.3-70b-versatile` as the default LLM, with Mistral as a secondary provider.** | MEDIUM | `config.py:73-81` shows `provider` defaults to `"groq"` and `groq_model` is `"llama-3.3-70b-versatile"`. However, the actual production env vars on Railway could override this. The `.env` file shows `GROQ_API_KEY` is set but Railway-side config is not visible from the repo. |
