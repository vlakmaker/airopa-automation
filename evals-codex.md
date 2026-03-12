# Repository Architecture Review (Codex)

## 1. HIGH-LEVEL ARCHITECTURE (Grounded only)

- FastAPI service shell: `airopa_automation/api/main.py` (`app`, `startup_event`, `app.include_router`).
  - Startup initializes tables via `init_db()` in `airopa_automation/api/main.py:30`.
  - Routers attached in `airopa_automation/api/main.py:64`, `airopa_automation/api/main.py:65`, `airopa_automation/api/main.py:66`.
- API route layer:
  - Health route: `airopa_automation/api/routes/health.py` (`health_check`).
  - Articles routes: `airopa_automation/api/routes/articles.py` (`list_articles`, `get_article`).
  - Jobs routes: `airopa_automation/api/routes/jobs.py` (`trigger_scrape`, `trigger_scrape_sync`, `get_job_status`).
- Pipeline orchestration service: `airopa_automation/api/services/pipeline.py` (`PipelineService`, `run_scrape_job`).
  - Interface used by jobs route background/sync calls in `airopa_automation/api/routes/jobs.py`.
  - Also invoked by cron script in `scripts/cron_scrape.py` (`main`).
- Domain agents in `airopa_automation/agents.py`:
  - Scraping: `ScraperAgent` (`scrape_rss_feeds`, `scrape_web_sources`).
  - Classification: `CategoryClassifierAgent` (`classify`, `_classify_with_llm`, `_classify_with_keywords`).
  - Summarization: `SummarizerAgent` (`summarize`, `_summarize_with_llm`).
  - Quality scoring: `QualityScoreAgent` (`assess_quality`).
- Persistence and DB models in `airopa_automation/api/models/database.py`:
  - Tables: `Article`, `SourceMetric`, `LLMTelemetry`, `Job`.
  - Session and setup: `SessionLocal`, `get_db`, `init_db`.
  - DB URL config key: `DATABASE_URL`.
- Config/feature flags in `airopa_automation/config.py`:
  - Global `config = Config()`.
  - Scraper keys: `rss_feeds`, `web_sources`, `eu_relevance_threshold`, `max_article_age_days`.
  - AI keys: `classification_enabled`, `summary_enabled`, `quality_enabled`, `shadow_mode`, `budget_max_tokens_per_run`.
- Deploy/runtime entrypoints:
  - API process command in `Procfile:1`.
  - Startup DB init + uvicorn in `start.sh`.

## 2. DATAFLOW WALKTHROUGH

- Entry:
  - `POST /api/scrape` in `airopa_automation/api/routes/jobs.py` (`trigger_scrape`) creates a `DBJob` and enqueues `run_scrape_job`.
  - `POST /api/scrape/sync` in `airopa_automation/api/routes/jobs.py` (`trigger_scrape_sync`) creates `DBJob` and directly calls `run_scrape_job`.
- Processing:
  - `PipelineService.run_scrape_job` in `airopa_automation/api/services/pipeline.py`:
    - Scrapes RSS and web (`self.scraper.scrape_rss_feeds`, `self.scraper.scrape_web_sources`) at lines 67-68.
    - Deduplicates via `_remove_duplicates` at line 70.
    - Classifies in loop at lines 73-103 (`self.classifier.classify` / keyword fallback).
    - Summarizes in loop at lines 128-156 (`self.summarizer.summarize`).
    - Tracks budget with `TokenBudget` (`airopa_automation/budget.py`, used at lines 74, 80, 132).
    - Persists telemetry with `_record_telemetry` at line 159 into `LLMTelemetry`.
    - Scores quality via `self.quality_assessor.assess_quality` at line 165.
    - Keeps `quality_score >= 0.6` at lines 173-175.
    - Stores articles via `_store_article` in lines 181-183 into `Article`.
    - Records source metrics via `_record_source_metrics` at lines 194-196 into `SourceMetric`.
    - Finalizes job status/result at lines 198-202 in `Job`.
- Serving:
  - `GET /api/articles` in `airopa_automation/api/routes/articles.py` (`list_articles`) queries `DBArticle`, filters and paginates, returns `ArticlesListResponse`.
  - `GET /api/articles/{article_id}` in `airopa_automation/api/routes/articles.py` (`get_article`) returns one record.
  - `GET /api/jobs/{job_id}` in `airopa_automation/api/routes/jobs.py` (`get_job_status`) returns job state.

## 3. DECISION RECORD (Why)

1. What: Use FastAPI + SQLAlchemy service.
   - Why: Evidence-backed from code structure and API metadata.
   - Evidence: `airopa_automation/api/main.py` (`app = FastAPI`), `airopa_automation/api/models/database.py` (`Base`, models, sessions).
   - Alternatives: Flask/Django or worker-only architecture.
   - Trade-offs: Good DX and schema typing; still needs careful worker strategy for long jobs.

2. What: Provide both async (`/api/scrape`) and sync (`/api/scrape/sync`) scrape triggers.
   - Why: Explicit endpoint docs describe sync for cron/CI callers.
   - Evidence: `airopa_automation/api/routes/jobs.py` docstring in `trigger_scrape_sync`.
   - Alternatives: async-only with polling.
   - Trade-offs: Easier cron integration; risk of long blocking HTTP requests.

3. What: LLM classification with keyword fallback and shadow mode.
   - Why: Explicit behavior documented in classifier method comments.
   - Evidence: `airopa_automation/agents.py` (`CategoryClassifierAgent.classify`), config flags in `airopa_automation/config.py`.
   - Alternatives: LLM-only or rules-only.
   - Trade-offs: Better reliability/rollout control; increased complexity.

4. What: Enforce per-run token budget for LLM calls.
   - Why: Explicit module intent says prevent runaway costs.
   - Evidence: `airopa_automation/budget.py` module docstring and `TokenBudget`; usage in `run_scrape_job`.
   - Alternatives: unlimited or daily global budget.
   - Trade-offs: Cost control; potential quality fallback when budget is exhausted.

5. What: Persist telemetry and source metrics for observability.
   - Why: Explicit model intent mentions observability/cost analysis.
   - Evidence: `LLMTelemetry` docstring in `airopa_automation/api/models/database.py`; `_record_telemetry`, `_record_source_metrics` in `airopa_automation/api/services/pipeline.py`.
   - Alternatives: logs-only.
   - Trade-offs: Better diagnostics; extra write overhead/schema maintenance.

6. What: Serve filtered article list (hide irrelevant/low-quality content).
   - Why: Explicit route comments and tested behavior.
   - Evidence: `airopa_automation/api/routes/articles.py` filters (`category != "other"`, relevance threshold, `quality_score >= 0.4`); tests in `tests/test_articles_route.py`.
   - Alternatives: no server-side filtering.
   - Trade-offs: Cleaner feed; potentially hides borderline content.

7. What: Keep a separate legacy markdown+git pipeline.
   - Why: INFERRED from separate executable pipeline in `main.py` and content/git agents in `airopa_automation/agents.py`.
   - Evidence: `main.py` (`AutomationPipeline.run`), `ContentGeneratorAgent`, `GitCommitAgent`.
   - Alternatives: single unified API pipeline.
   - Trade-offs: Flexibility; risk of drift and maintainer confusion.

## 4. ISSUES AND RISKS

- Symptom: Scrape endpoints are effectively unprotected when `API_KEY` is missing.
  - Location: `airopa_automation/api/auth.py` (`verify_api_key`, lines 45-50).
  - Impact: Unauthorized triggering of expensive scrape jobs.
  - Severity: S1.
  - Fix sketch: Fail closed by default; require explicit dev-only override to allow missing key.

- Symptom: Sync scrape runs full pipeline in request lifecycle.
  - Location: `airopa_automation/api/routes/jobs.py` (`trigger_scrape_sync`, lines 113-116).
  - Impact: Worker occupancy, timeout risk, degraded API responsiveness.
  - Severity: S2.
  - Fix sketch: Move execution to queue/worker and keep endpoint as submit+poll.

- Symptom: Health endpoint always reports pipeline as available.
  - Location: `airopa_automation/api/routes/health.py` (`pipeline_status = "available"` at line 37).
  - Impact: False positives for operations.
  - Severity: S3.
  - Fix sketch: Add real pipeline readiness checks or recent successful run indicator.

- Symptom: Telemetry/metric writes use `flush()` and depend on later commit.
  - Location: `airopa_automation/api/services/pipeline.py` (`_record_telemetry` line 370, `_record_source_metrics` line 342).
  - Impact: Observability rows can be lost if a later failure rolls back transaction.
  - Severity: S2.
  - Fix sketch: Commit observability writes in isolated transaction/session.

- Symptom: DB config split across two sources can diverge.
  - Location: `airopa_automation/config.py` (`DatabaseConfig.db_path`) vs `airopa_automation/api/models/database.py` (`DATABASE_URL`).
  - Impact: Different code paths may read/write different DBs.
  - Severity: S2.
  - Fix sketch: Consolidate DB config to one source of truth.

- Symptom: Frontmatter generation interpolates unescaped text.
  - Location: `airopa_automation/agents.py` (`ContentGeneratorAgent._generate_frontmatter` lines 790-801).
  - Impact: YAML breakage/injection-like parsing failures from quotes/newlines.
  - Severity: S2.
  - Fix sketch: Use YAML serializer (`safe_dump`) and sanitize multiline values.

## 5. OPEN QUESTIONS

- UNKNOWN: Is `main.py` legacy pipeline still used in production, or only API path?
  - Needed info: maintainer deployment/runbook.
- UNKNOWN: Is missing `API_KEY` ever acceptable in production?
  - Needed info: environment policy/security requirements.
- UNKNOWN: Which DB config is authoritative (`DATABASE_URL` vs `config.database.db_path`)?
  - Needed info: current deployment conventions.
- UNKNOWN: Is there a migration framework (Alembic) outside this repo?
  - Needed info: schema change process.
- UNKNOWN: Should `/api/scrape/sync` remain externally exposed?
  - Needed info: intended clients and SLAs.

## 6. CONFIDENCE REPORT

1. Claim: API architecture is FastAPI + SQLAlchemy with health/articles/jobs routers.
   - Confidence: HIGH.
   - Why: Directly defined in `airopa_automation/api/main.py` and model/session files.

2. Claim: Primary job pipeline stages are scrape -> classify -> summarize -> score -> store -> finalize.
   - Confidence: HIGH.
   - Why: Explicit stepwise code in `PipelineService.run_scrape_job`.

3. Claim: LLM behavior is feature-flagged and supports shadow/fallback modes.
   - Confidence: HIGH.
   - Why: Clear conditional logic in `CategoryClassifierAgent.classify` and config flags.

4. Claim: Article-serving route enforces relevance and quality display filters.
   - Confidence: HIGH.
   - Why: Query filters in `list_articles`; behavior validated in `tests/test_articles_route.py`.

5. Claim: Repository maintains two distinct processing paths (API DB path and markdown/git path).
   - Confidence: MEDIUM.
   - Why: Both implementations exist (`airopa_automation/api/services/pipeline.py`, `main.py`), but active production intent for `main.py` is not explicit.
