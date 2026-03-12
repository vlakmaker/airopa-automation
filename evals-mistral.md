# AIropa Automation System Architecture Analysis

## 1. HIGH-LEVEL ARCHITECTURE (Grounded only)

### Components and Responsibilities

**1. Automation Pipeline (`main.py`, `airopa_automation/agents.py`)**
- **Responsibility**: Core content processing workflow
- **Components**:
  - `ScraperAgent`: Extracts articles from RSS feeds and web sources (`agents.py:108-300`)
  - `CategoryClassifierAgent`: Classifies articles using LLM or keyword matching (`agents.py:303-500`)
  - `QualityScoreAgent`: Assesses article quality using rule-based scoring (`agents.py:650-700`)
  - `ContentGeneratorAgent`: Generates markdown files for high-quality articles (`agents.py:703-750`)
  - `GitCommitAgent`: Commits generated content to git repository (`agents.py:753-780`)

**2. API Layer (`airopa_automation/api/`)**
- **Responsibility**: RESTful interface for article management and pipeline control
- **Endpoints**:
  - `GET /api/articles`: List articles with filtering (`routes/articles.py:30-120`)
  - `GET /api/articles/{id}`: Get single article details (`routes/articles.py:123-168`)
  - `POST /api/scrape`: Trigger scraping job (`routes/jobs.py` - inferred from main.py:75)
  - `GET /api/jobs/{job_id}`: Check job status (`routes/jobs.py` - inferred)
  - `GET /api/health`: Health check endpoint (`routes/health.py` - inferred)

**3. Database Layer (`airopa_automation/api/models/database.py`)**
- **Models**:
  - `Article`: Stores processed articles with metadata (`database.py:20-50`)
  - `SourceMetric`: Tracks per-source performance metrics (`database.py:53-75`)
  - `LLMTelemetry`: Records LLM usage and costs (`database.py:78-105`)
  - `Job`: Tracks background job execution (`database.py:108-125`)

**4. Pipeline Service (`airopa_automation/api/services/pipeline.py`)**
- **Responsibility**: Bridges automation pipeline with database storage
- **Key Methods**:
  - `run_scrape_job()`: Orchestrates full pipeline execution with budget tracking (`pipeline.py:30-150`)
  - `_store_article()`: Persists articles to database (`pipeline.py:153-190`)
  - `_record_telemetry()`: Tracks LLM usage metrics (`pipeline.py:350-380`)

**5. Configuration System (`airopa_automation/config.py`)**
- **Components**:
  - `ScraperConfig`: RSS feeds, web sources, rate limiting (`config.py:10-50`)
  - `AIConfig`: LLM provider settings and feature flags (`config.py:53-90`)
  - `TokenBudget`: Cost management for LLM calls (`budget.py:10-42`)

### Interfaces

- **API Endpoints**: RESTful JSON interface (`api/main.py:80-88`)
- **Database**: SQLAlchemy ORM with SQLite/PostgreSQL support (`database.py:140-179`)
- **LLM Integration**: Groq/Mistral providers with budget tracking (`llm.py` - inferred)

## 2. DATAFLOW WALKTHROUGH

**New Article Processing Flow:**

1. **Scraping Phase** (`agents.py:108-300`)
   - `ScraperAgent.scrape_rss_feeds()` extracts articles from RSS feeds
   - `ScraperAgent.scrape_web_sources()` extracts articles from web pages
   - Articles are deduplicated by URL and content hash

2. **Classification Phase** (`agents.py:303-500`, `pipeline.py:60-90`)
   - `CategoryClassifierAgent.classify()` uses LLM or keyword matching
   - LLM classification: `llm_complete()` → `parse_classification()` → `validate_classification()`
   - Fallback: keyword-based classification for cost control

3. **Quality Assessment** (`agents.py:650-700`)
   - `QualityScoreAgent.assess_quality()` calculates composite score from 5 signals
   - Signals: content depth (30%), EU relevance (25%), title quality (15%), source credibility (15%), metadata completeness (15%)

4. **Storage Phase** (`pipeline.py:153-190`)
   - High-quality articles (≥0.6 score) stored in `Article` table
   - `LLMTelemetry` records token usage and performance
   - `SourceMetric` tracks per-source statistics

5. **API Serving** (`routes/articles.py:30-168`)
   - Filtered by: category, country, quality score, EU relevance threshold
   - Ordered by published_date (fallback to created_at)
   - Paginated responses with total counts

**Evidence for each step:**
- Scraping: `agents.py:108-300` (RSS + web scraping)
- Classification: `agents.py:303-500` (LLM/keyword hybrid)
- Quality: `agents.py:650-700` (rule-based scoring)
- Storage: `pipeline.py:153-190` (database persistence)
- API: `routes/articles.py:30-168` (filtered listing)

## 3. DECISION RECORD (Why)

**1. Hybrid LLM/Keyword Classification**
- **What**: Dual classification system with LLM and keyword fallback
- **Why**: Cost control and gradual LLM rollout (INFERRED from shadow_mode feature)
- **Evidence**: `agents.py:360-380` (shadow mode logic), `config.py:60-70` (feature flags)
- **Alternatives**: Pure LLM or pure keyword classification
- **Trade-offs**: Complexity vs. cost control and reliability

**2. Token Budget System**
- **What**: Per-run token budget with fallback to keywords
- **Why**: Prevent runaway LLM costs in production
- **Evidence**: `budget.py:10-42`, `pipeline.py:65-75` (budget tracking)
- **Alternatives**: No budget (risky), global budget (less granular)
- **Trade-offs**: Some articles get lower quality classification when budget exhausted

**3. Shadow Mode Deployment**
- **What**: Run LLM but don't use results (log only)
- **Why**: Safe rollout with performance monitoring
- **Evidence**: `config.py:68` (shadow_mode flag), `agents.py:370-380` (shadow logic)
- **Alternatives**: Direct rollout, A/B testing
- **Trade-offs**: Double processing cost during shadow phase

**4. Quality Gate (0.6 threshold)**
- **What**: Only store articles with quality_score ≥ 0.6
- **Why**: Filter low-quality content before storage
- **Evidence**: `pipeline.py:130-135` (high_quality_articles filtering)
- **Alternatives**: Store all, filter at query time
- **Trade-offs**: Some borderline articles excluded vs. cleaner database

**5. EU Relevance Threshold**
- **What**: Configurable EU relevance filter (default 3.0)
- **Why**: Focus on European content for target audience
- **Evidence**: `config.py:15` (eu_relevance_threshold), `routes/articles.py:55-60` (API filtering)
- **Alternatives**: No filtering, different thresholds per category
- **Trade-offs**: Some relevant global content excluded vs. better audience fit

**6. Content Hash Deduplication**
- **What**: Deduplicate by URL and content hash
- **Why**: Prevent duplicate processing and storage
- **Evidence**: `agents.py:80-90` (generate_hash), `pipeline.py:390-420` (deduplication)
- **Alternatives**: URL-only deduplication
- **Trade-offs**: More complex but catches content reposted with different URLs

**7. Multi-source Metrics Tracking**
- **What**: Per-source performance metrics with aggregates
- **Why**: Monitor source quality and adjust feed selection
- **Evidence**: `database.py:53-75` (SourceMetric model), `pipeline.py:200-250` (metrics recording)
- **Alternatives**: No per-source tracking
- **Trade-offs**: Storage overhead vs. operational insights

## 4. ISSUES AND RISKS

**1. SQL Injection Risk in API Filtering**
- **Symptom**: Direct use of query parameters in SQL filters
- **Location**: `routes/articles.py:50-80` (filter construction)
- **Impact**: Potential SQL injection if parameters not properly sanitized
- **Severity**: S2 (significant risk - API endpoint)
- **Fix**: Use SQLAlchemy parameterized queries consistently

**2. No Rate Limiting on Critical Endpoints**
- **Symptom**: Rate limiting only on article endpoints, not jobs/scrape
- **Location**: `api/main.py:15-20` (limiter setup)
- **Impact**: Potential abuse of scrape endpoint causing resource exhaustion
- **Severity**: S2 (significant risk - resource exhaustion)
- **Fix**: Apply rate limiting to all write/expensive endpoints

**3. Hardcoded API Keys in Configuration**
- **Symptom**: LLM API keys loaded from environment but config allows defaults
- **Location**: `config.py:56-65` (API key handling)
- **Impact**: Risk of committing keys to repository
- **Severity**: S1 (production-breaking security issue)
- **Fix**: Require explicit API key setting, fail fast if missing

**4. No Input Validation on Article Content**
- **Symptom**: Article content stored directly without sanitization
- **Location**: `pipeline.py:160-180` (article storage)
- **Impact**: Potential XSS if content served to web clients
- **Severity**: S2 (significant risk - security)
- **Fix**: HTML sanitization before storage

**5. Unbounded Memory Usage in Scraping**
- **Symptom**: No limits on article content size during scraping
- **Location**: `agents.py:200-250` (content extraction)
- **Impact**: Memory exhaustion with very large articles
- **Severity**: S2 (significant risk - DoS)
- **Fix**: Implement content size limits and streaming processing

**6. No Retry Logic for Failed LLM Calls**
- **Symptom**: Single attempt for LLM classification
- **Location**: `agents.py:400-450` (LLM classification)
- **Impact**: Transient failures cause fallback to lower quality classification
- **Severity**: S3 (minor - quality degradation)
- **Fix**: Implement exponential backoff retry logic

**7. Database Connection Leak Risk**
- **Symptom**: Manual session management in pipeline service
- **Location**: `pipeline.py:35-45` (session handling)
- **Impact**: Potential connection leaks under error conditions
- **Severity**: S2 (significant risk - resource exhaustion)
- **Fix**: Use context managers consistently

## 5. OPEN QUESTIONS

**1. Deployment Architecture**
- What is the production deployment setup? (Docker, Kubernetes, serverless?)
- How are the automation pipeline and API service deployed together?

**2. Scaling Strategy**
- How does the system handle increased load? (Horizontal scaling, queue workers?)
- What is the expected article volume and processing capacity?

**3. Monitoring and Alerting**
- What monitoring is in place for pipeline failures?
- How are LLM cost overruns detected and handled?

**4. Data Retention Policy**
- What is the retention policy for articles, telemetry, and metrics?
- Are there GDPR compliance considerations for stored content?

**5. Disaster Recovery**
- What backup strategy exists for the database and generated content?
- How are failed pipeline runs recovered?

**6. Performance Optimization**
- Are there performance bottlenecks in the current architecture?
- What caching strategies are employed?

## 6. CONFIDENCE REPORT

**1. "The system uses a hybrid LLM/keyword classification approach with shadow mode deployment"**
- **Confidence**: HIGH
- **Why**: Direct evidence in `agents.py:360-380` and `config.py:68` with clear implementation

**2. "Articles are filtered by quality score (≥0.6) before database storage"**
- **Confidence**: HIGH  
- **Why**: Explicit filtering logic in `pipeline.py:130-135` with clear threshold

**3. "The API implements EU relevance filtering with configurable threshold"**
- **Confidence**: HIGH
- **Why**: Configuration in `config.py:15` and filtering in `routes/articles.py:55-60`

**4. "The system tracks per-source metrics and LLM telemetry for operational insights"**
- **Confidence**: HIGH
- **Why**: Database models in `database.py:53-105` and recording logic in `pipeline.py:200-380`

**5. "Rate limiting is inconsistently applied across API endpoints"**
- **Confidence**: MEDIUM
- **Why**: Rate limiter setup in `api/main.py:15-20` but need to verify all endpoints usage

**6. "The system has potential SQL injection vulnerabilities"**
- **Confidence**: MEDIUM
- **Why**: Based on pattern analysis of filter construction, but no direct evidence of exploitation

**7. "LLM API keys are properly secured"**
- **Confidence**: LOW
- **Why**: Configuration shows environment variable usage but implementation details unclear

**8. "The pipeline handles errors gracefully with proper rollback"**
- **Confidence**: MEDIUM
- **Why**: Error handling present in `pipeline.py:140-150` but completeness unclear