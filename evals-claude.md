# AIropa Automation — Architecture Review for New Maintainers

---

## 1. HIGH-LEVEL ARCHITECTURE (Grounded)

### Components

| Component | Responsibility | Key Files |
|-----------|---------------|-----------|
| **FastAPI API** | HTTP interface for articles, scrape triggers, health checks | `airopa_automation/api/main.py`, `api/routes/articles.py`, `api/routes/jobs.py`, `api/routes/health.py` |
| **ScraperAgent** | Fetches articles from 14 RSS feeds + 3 web sources via feedparser/newspaper3k | `airopa_automation/agents.py:59–332` |
| **CategoryClassifierAgent** | Classifies articles into 4 categories + EU relevance score (LLM or keywords) | `airopa_automation/agents.py:335–541` |
| **SummarizerAgent** | Generates 2–3 sentence editorial summaries via LLM | `airopa_automation/agents.py:544–672` |
| **QualityScoreAgent** | Calculates quality score from 5 weighted signals | `airopa_automation/agents.py:675–752` |
| **PipelineService** | Orchestrates scrape→classify→summarize→score→store flow | `airopa_automation/api/services/pipeline.py:29–438` |
| **LLM Wrapper** | Abstracts Groq/Mistral API calls with structured error handling | `airopa_automation/llm.py` |
| **Token Budget** | Per-run LLM cost guardrail with circuit breaker | `airopa_automation/budget.py` |
| **Database Layer** | SQLAlchemy ORM: Article, Job, SourceMetric, LLMTelemetry tables | `airopa_automation/api/models/database.py` |
| **Config** | Pydantic-based config with env var overrides and feature flags | `airopa_automation/config.py` |
| **Auth & Rate Limiting** | X-API-Key header auth, slowapi per-IP rate limits | `airopa_automation/api/auth.py`, `api/rate_limit.py` |
| **Scheduled Scrape** | GitHub Actions cron every 6h, calls sync scrape endpoint | `.github/workflows/scheduled-scrape.yml` |
| **CI/CD** | Linting (flake8, black, isort, mypy) + tests on push/PR to main | `.github/workflows/ci_cd.yml` |

### API Endpoints

| Method | Path | Auth | Rate Limit | Handler |
|--------|------|------|------------|---------|
| GET | `/api/health` | None | 100/min | `health.py:health_check` |
| GET | `/api/articles` | None | 100/min | `articles.py:list_articles` |
| GET | `/api/articles/{id}` | None | 100/min | `articles.py:get_article` |
| POST | `/api/scrape` | X-API-Key | 5/min | `jobs.py:trigger_scrape` (async) |
| POST | `/api/scrape/sync` | X-API-Key | 5/min | `jobs.py:trigger_scrape_sync` (blocking) |
| GET | `/api/jobs/{id}` | None | 100/min | `jobs.py:get_job_status` |

### Database Tables

| Table | Purpose | Evidence |
|-------|---------|----------|
| `articles` | Stores processed articles with content, metadata, scores | `database.py:15–45` |
| `jobs` | Tracks scrape job lifecycle (queued→running→completed/failed) | `database.py:102–118` |
| `source_metrics` | Per-source stats per scrape run | `database.py:48–70` |
| `llm_telemetry` | Per-article LLM call metrics (latency, tokens, status) | `database.py:73–99` |

---

## 2. DATAFLOW WALKTHROUGH

### Trigger: Scrape initiated

**Step 1 — Job creation** (`jobs.py:trigger_scrape_sync`)
A POST to `/api/scrape/sync` with valid `X-API-Key` creates a `Job` record (status="queued"), then calls `pipeline_service.run_scrape_job(job_id)` synchronously.

**Step 2 — RSS scraping** (`pipeline.py:run_scrape_job` → `agents.py:ScraperAgent.scrape_rss_feeds`)
PipelineService sets job status to "running", then ScraperAgent iterates 14 RSS feeds via `feedparser`. For each entry:
- Extracts URL, title
- Fetches full text via `newspaper3k` (`agents.py:_extract_article_data`)
- Falls back to RSS `content:encoded` or `summary` if newspaper3k returns <200 chars (`agents.py:_extract_rss_content`)
- Extracts images from newspaper3k `.top_image`, RSS `media_content`, or `enclosures` (`agents.py:_extract_rss_image`)
- Skips articles older than `max_article_age_days` (default 30) (`agents.py:_is_article_too_old`)
- Normalizes source name via `config.scraper.source_name_map` (`agents.py:_normalize_source_name`)
- Creates `Article` Pydantic object

**Step 3 — Deduplication** (`pipeline.py:_remove_duplicates`)
Removes duplicates by URL and SHA-256 hash of `title+url+source` (`agents.py:Article.generate_hash`).

**Step 4 — Classification** (`pipeline.py:run_scrape_job` → `agents.py:CategoryClassifierAgent.classify`)
For each article, if `config.ai.classification_enabled` and `TokenBudget` not exceeded:
- Sends content to Groq LLM with `CLASSIFICATION_PROMPT` (`agents.py:336–392`)
- LLM returns JSON: `{category, country, eu_relevance, confidence}`
- Response parsed via `parse_classification()` and validated via `validate_classification()` (`llm_schemas.py`)
- Validation rules: confidence <0.5 → demote to "other"; eu_relevance <2.0 → demote to "other"
- On failure: falls back to `_classify_with_keywords()` (`agents.py:505–541`)
- Telemetry recorded per article
- Budget tracked via `budget.record(tokens_in, tokens_out)` (`budget.py:TokenBudget.record`)

**Step 5 — Summarization** (`pipeline.py:run_scrape_job` → `agents.py:SummarizerAgent.summarize`)
If `config.ai.summary_enabled` and budget not exceeded:
- Sends content to Groq LLM with `SUMMARY_PROMPT` (`agents.py:547–566`)
- Response validated via `parse_summary()` (`llm_schemas.py`) — rejects HTML, markdown, >5 sentences
- Sets `article.summary`; skips if "NOT_RELEVANT" returned

**Step 6 — Telemetry persistence** (`pipeline.py:_record_telemetry`)
All LLM telemetry rows written to `llm_telemetry` table.

**Step 7 — Quality scoring** (`agents.py:QualityScoreAgent.assess_quality`)
Five weighted signals calculated:
- Content depth (0.30): word count thresholds
- EU relevance (0.25): eu_relevance score thresholds
- Title quality (0.15): word count range
- Source credibility (0.15): Tier 1/2/other classification
- Metadata completeness (0.15): presence of category, country, summary

**Step 8 — Storage** (`pipeline.py:_store_article`)
Articles with `quality_score >= 0.6` are stored. Deduplication check by URL and content_hash. Creates `Article` DB record.

**Step 9 — Source metrics** (`pipeline.py:_record_source_metrics`)
Per-source aggregates written: articles fetched/stored, avg EU relevance, avg quality, category distribution.

**Step 10 — Job completion** (`pipeline.py:run_scrape_job`)
Job status set to "completed" with `result_count`. On error: status="failed" with `error_message`.

### Serving: Article retrieval

**`GET /api/articles`** (`articles.py:list_articles`)
- Filters: `category != "other"`, `eu_relevance >= threshold (3.0)`, `quality_score >= 0.4`
- Optional query params: category, country, min_quality
- Ordered by `coalesce(published_date, created_at) DESC`
- Paginated with limit/offset

---

## 3. DECISION RECORD

### Decision 1: Sync scrape endpoint instead of async background tasks

- **What:** Added `POST /api/scrape/sync` that runs the pipeline within the HTTP request lifecycle
- **Why:** FastAPI BackgroundTasks get silently killed on Railway deploys/restarts. Evidence: `jobs.py:trigger_scrape_sync`, Procfile `--timeout-keep-alive 600`
- **Alternatives:** Celery/Redis task queue, dedicated worker process, Railway cron service
- **Trade-offs:** Requires long HTTP timeouts (600s); ties pipeline execution to request lifetime; simpler ops (no message broker)

### Decision 2: Feature flags for LLM rollout

- **What:** Three boolean flags control LLM behavior: `classification_enabled`, `summary_enabled`, `shadow_mode`
- **Why:** INFERRED — Gradual rollout strategy; shadow mode allows comparison without affecting production data
- **Evidence:** `config.py:AIConfig` (lines 84–98), `agents.py:classify` (lines 399–443)
- **Alternatives:** A/B testing framework, percentage-based rollout
- **Trade-offs:** Manual flag management; requires env var changes per Railway service

### Decision 3: Token budget with keyword fallback

- **What:** Per-run token cap (default 50k); when exceeded, classifier falls back to keyword matching
- **Why:** INFERRED — Cost control for LLM API calls; ensures pipeline completes even if budget exhausted
- **Evidence:** `budget.py:TokenBudget`, `pipeline.py:run_scrape_job` (budget check in classification loop)
- **Alternatives:** Per-article token limit, monetary budget cap, rate limiting LLM calls
- **Trade-offs:** Later articles in a run may get lower-quality keyword classification; budget applies to both classification and summarization combined

### Decision 4: No ORM migration tool (no Alembic)

- **What:** Uses `Base.metadata.create_all()` instead of migration framework
- **Why:** UNKNOWN — No comment or documentation explaining this choice
- **Evidence:** `database.py:init_db()` calls `create_all()`; no `alembic/` directory or `alembic.ini`
- **Alternatives:** Alembic, manual SQL migrations checked into repo
- **Trade-offs:** New columns require manual `ALTER TABLE`; no migration history; schema drift risk between environments

### Decision 5: Dual hash-based deduplication

- **What:** Articles deduplicated by both URL uniqueness and SHA-256 content hash
- **Why:** INFERRED — URL catches exact duplicates; hash catches same-content-different-URL cases
- **Evidence:** `agents.py:Article.generate_hash` (SHA-256 of `title+url+source`), `pipeline.py:_store_article` checks both, `database.py:Article` has `url` unique + `content_hash` unique
- **Alternatives:** URL-only dedup, content similarity (fuzzy matching)
- **Trade-offs:** Hash includes URL, so it doesn't actually catch same-content-different-URL. Two articles with same title from different sources would have different hashes.

### Decision 6: Quality score as storage gate

- **What:** Only articles with `quality_score >= 0.6` are stored; API further filters to `>= 0.4`
- **Why:** INFERRED — Two-tier filtering: pipeline keeps higher-quality, API shows even stored low-scorers
- **Evidence:** `pipeline.py:run_scrape_job` (stores if >=0.6), `articles.py:list_articles` (filters >=0.4)
- **Alternatives:** Store everything, filter at API layer only; configurable threshold
- **Trade-offs:** Lost data — articles below 0.6 are discarded permanently; the 0.4 API filter is effectively redundant since nothing below 0.6 is stored

### Decision 7: Groq as primary LLM provider

- **What:** Uses Groq (llama-3.3-70b-versatile) as primary, Mistral as configurable alternative
- **Why:** INFERRED — Groq offers fast inference for open models; free tier availability
- **Evidence:** `config.py:AIConfig` (provider default "groq"), `llm.py:llm_complete`
- **Alternatives:** OpenAI, Anthropic, self-hosted models
- **Trade-offs:** Vendor dependency; Groq rate limits; model quality depends on open-source llama

### Decision 8: Single-process deployment

- **What:** One uvicorn worker serves both API requests and runs pipeline in-band
- **Why:** INFERRED — Railway's simple container model; minimal infrastructure
- **Evidence:** `Procfile` — single `web:` process, no workers flag
- **Alternatives:** Multiple workers (gunicorn+uvicorn), separate API and worker services
- **Trade-offs:** Long-running sync scrape blocks the single worker; no concurrent scrape+API serving during pipeline execution

### Decision 9: IP-based rate limiting

- **What:** slowapi with `get_remote_address` as key function
- **Why:** INFERRED — Simple protection against abuse without requiring auth for read endpoints
- **Evidence:** `rate_limit.py:limiter`, all route decorators
- **Alternatives:** Token-bucket, user-based limiting, API gateway rate limiting
- **Trade-offs:** Behind a reverse proxy, all clients may share one IP; easily bypassed with multiple IPs

### Decision 10: Separate Pydantic models for pipeline and API

- **What:** `Article` (agents.py) for pipeline processing; `ArticleResponse` (schemas.py) for API responses; manual mapping in routes
- **Why:** INFERRED — Decouples internal processing model from public API contract
- **Evidence:** `agents.py:Article`, `schemas.py:ArticleResponse`, route handlers manually construct responses
- **Alternatives:** Single model with `from_attributes=True` auto-mapping
- **Trade-offs:** Manual mapping code; risk of field drift between models; more boilerplate

---

## 4. ISSUES AND RISKS

### Issue 1: Auth bypass in development mode

- **Symptom:** When `API_KEY` env var is not set, `verify_api_key` logs a warning but returns `"no_key_configured"`, allowing unauthenticated access to scrape endpoints
- **Location:** `airopa_automation/api/auth.py:verify_api_key`
- **Impact:** Anyone can trigger scrapes if API_KEY accidentally unset in production
- **Severity:** S2
- **Fix sketch:** Reject requests when API_KEY is unset in non-development environments; check for a `ENVIRONMENT` or `RAILWAY_ENVIRONMENT` var

### Issue 2: Single uvicorn worker blocks during sync scrape

- **Symptom:** The sync scrape endpoint runs up to 10 minutes, during which the single uvicorn worker cannot serve other requests (health checks, article reads)
- **Location:** `Procfile` (no `--workers` flag), `jobs.py:trigger_scrape_sync`
- **Impact:** API is effectively unavailable during scrape runs; health checks from monitoring may fail
- **Severity:** S2
- **Fix sketch:** Add `--workers 2` to Procfile, or move pipeline to a background thread with proper locking

### Issue 3: Pipeline creates its own DB session, bypassing FastAPI dependency injection

- **Symptom:** `PipelineService.run_scrape_job` creates `SessionLocal()` directly instead of using `get_db()`. The sync endpoint must call `db.expire()` + `db.refresh()` to see pipeline's writes.
- **Location:** `pipeline.py:run_scrape_job` (line ~48), `jobs.py:trigger_scrape_sync`
- **Impact:** Session management inconsistency; potential for stale reads or uncommitted data if pipeline crashes mid-transaction
- **Severity:** S3
- **Fix sketch:** Pass the route's DB session into the pipeline, or accept the dual-session pattern but document it clearly

### Issue 4: Content hash doesn't actually catch cross-source duplicates

- **Symptom:** `Article.generate_hash()` uses `title+url+source`, meaning the same article syndicated with a different URL produces a different hash
- **Location:** `agents.py:Article.generate_hash`
- **Impact:** Duplicate content from syndication partners stored multiple times
- **Severity:** S3
- **Fix sketch:** Hash on `title` only (or normalized title), or use content similarity

### Issue 5: Quality score 0.6 gate discards data permanently

- **Symptom:** Articles below 0.6 quality score are never stored. The API then has a redundant >=0.4 filter.
- **Location:** `pipeline.py:run_scrape_job` (~line 185), `articles.py:list_articles`
- **Impact:** Potentially useful articles lost permanently; no way to retroactively lower the threshold
- **Severity:** S3
- **Fix sketch:** Store all articles, use the API-layer filter for display; or make the storage threshold configurable via env var

### Issue 6: `datetime.utcnow()` used for defaults (deprecated in Python 3.12+)

- **Symptom:** SQLAlchemy column defaults use `datetime.utcnow` which is deprecated and returns naive datetimes
- **Location:** `database.py` — `created_at`, `updated_at`, `timestamp` columns across all models
- **Impact:** Timezone-naive timestamps; potential issues when comparing with timezone-aware dates from RSS feeds
- **Severity:** S3
- **Fix sketch:** Use `datetime.now(timezone.utc)` or `func.now()` for server-side defaults

### Issue 7: No pagination guard on total count query

- **Symptom:** `list_articles` runs a `count()` query on the full filtered result set on every request
- **Location:** `articles.py:list_articles`
- **Impact:** Performance degradation as article count grows (currently ~2500 rows, acceptable; at scale could be slow)
- **Severity:** S3
- **Fix sketch:** Cache count, or use approximate counts, or paginate with cursor-based pagination

### Issue 8: CORS origins configuration

- **Symptom:** `DEFAULT_ORIGINS` must include the production frontend domain
- **Location:** `api/main.py` CORS configuration
- **Impact:** Frontend requests blocked if origin not listed
- **Severity:** S3
- **Fix sketch:** Ensure `https://airopa.news` and `https://www.airopa.news` are in `DEFAULT_ORIGINS` or set via `ALLOWED_ORIGINS` env var

### Issue 9: No retry logic for LLM API calls

- **Symptom:** `llm_complete()` makes one attempt; on failure returns error status with no retry
- **Location:** `llm.py:llm_complete`
- **Impact:** Transient Groq API errors cause immediate fallback to keywords; reduces LLM classification coverage
- **Severity:** S3
- **Fix sketch:** Add exponential backoff retry (1-2 retries) for transient errors (rate limits, 5xx)

### Issue 10: mypy error codes disabled broadly

- **Symptom:** Multiple mypy `disable_error_code` overrides suppress `arg-type`, `assignment`, `valid-type` across entire modules
- **Location:** `pyproject.toml` — `[[tool.mypy.overrides]]` sections
- **Impact:** Type errors in routes and services may go undetected; defeats purpose of type checking
- **Severity:** S3
- **Fix sketch:** Fix the underlying type issues (likely FastAPI/SQLAlchemy type stubs) and remove overrides, or narrow suppressions to specific lines with `# type: ignore[code]`

---

## 5. OPEN QUESTIONS

1. **Frontend contract:** The Vercel frontend (separate repo at `~/Airopa`) consumes these APIs — is there a shared API contract or schema? What fields does the frontend actually use from `ArticleResponse`?

2. **scraper-cron service:** Railway has a second service `scraper-cron` but there's no `Procfile` entry or code for it in this repo. What does it run? Is it still active, or has the GitHub Actions cron replaced it?

3. **Phase 3 scope:** The agentic upgrade spec mentions Phase 3 as "NEXT" but its scope is listed as TBD. What's planned?

4. **Content licensing:** The pipeline scrapes full article text from 14 sources. Are there licensing agreements for storing and serving this content?

5. **Monitoring/alerting:** Beyond the health endpoint, is there any monitoring for scrape failures, LLM budget exhaustion, or data quality degradation?

6. **Backup strategy:** With no migration framework and `create_all()` as the only schema tool, what's the database backup/recovery strategy for the Railway PostgreSQL instance?

7. **`ContentGeneratorAgent` and `GitCommitAgent` usage:** These agents exist in `agents.py` (lines 755–838) but aren't called from the pipeline. Are they legacy code from a previous workflow, or planned for future use?

8. **Shadow mode data:** When `shadow_mode=true`, LLM results are logged to telemetry but not applied. Is there tooling to analyze shadow mode results for validation before going live?

---

## 6. CONFIDENCE REPORT

| # | Claim | Confidence | Reasoning |
|---|-------|------------|-----------|
| 1 | **Pipeline flow is scrape→classify→summarize→score→store, orchestrated by `PipelineService.run_scrape_job`** | **HIGH** | Directly traced through `pipeline.py:44–224`; each step calls the corresponding agent with clear sequential flow |
| 2 | **Auth bypass exists when `API_KEY` env var is unset** | **HIGH** | Read `auth.py:verify_api_key` — explicitly returns `"no_key_configured"` with a warning log instead of raising |
| 3 | **Single uvicorn worker blocks during sync scrape** | **HIGH** | `Procfile` has no `--workers` flag (defaults to 1); `trigger_scrape_sync` runs pipeline synchronously within the request handler |
| 4 | **Quality score 0.4 API filter is redundant given 0.6 storage gate** | **MEDIUM** | The pipeline stores at >=0.6 and the API filters at >=0.4. These could diverge if the storage threshold is later lowered, so the API filter may be intentional future-proofing. But currently, it's dead code. |
| 5 | **`ContentGeneratorAgent` and `GitCommitAgent` are unused** | **MEDIUM** | They exist in `agents.py` but are not imported or called in `pipeline.py`. Could be used by scripts not in the main pipeline path — I didn't exhaustively check all scripts. |
