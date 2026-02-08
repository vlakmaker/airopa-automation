"""
Pipeline service - Connects the automation pipeline to the database

This service handles running the scraping pipeline and storing results
in the database.
"""

import hashlib
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from airopa_automation.agents import Article as PipelineArticle
from airopa_automation.agents import (
    CategoryClassifierAgent,
    QualityScoreAgent,
    ScraperAgent,
    SummarizerAgent,
)
from airopa_automation.budget import TokenBudget
from airopa_automation.config import config, ensure_directories

from ..models.database import Article as DBArticle
from ..models.database import Job as DBJob
from ..models.database import LLMTelemetry, SessionLocal, SourceMetric


class PipelineService:
    """
    Service for running the automation pipeline and storing results
    in the database
    """

    def __init__(self):
        """Initialize the pipeline service"""
        ensure_directories()

        self.scraper = ScraperAgent()
        self.classifier = CategoryClassifierAgent()
        self.summarizer = SummarizerAgent()
        self.quality_assessor = QualityScoreAgent()

    def run_scrape_job(self, job_id: str) -> None:  # noqa: C901
        """
        Run a scraping job and store results in the database

        Args:
            job_id: The ID of the job to run
        """
        db = SessionLocal()

        try:
            # Update job status to running
            job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if not job:
                print(f"Job {job_id} not found")
                return

            job.status = "running"
            db.commit()

            # Run the pipeline steps and capture articles
            print(f"Starting scrape job {job_id}...")

            # Step 1: Scrape content
            rss_articles = self.scraper.scrape_rss_feeds()
            web_articles = self.scraper.scrape_web_sources()
            all_articles = rss_articles + web_articles
            articles = self._remove_duplicates(all_articles)
            print(f"Scraped {len(articles)} articles")

            # Step 2: Classify articles (with budget tracking)
            budget = TokenBudget()
            classified_articles = []
            telemetry_rows = []
            budget_skipped = 0
            for article in articles:
                try:
                    if budget.exceeded and config.ai.classification_enabled:
                        # Budget exceeded: fall back to keywords for remaining
                        if budget_skipped == 0:
                            print(
                                f"Token budget exceeded ({budget.tokens_used}/"
                                f"{budget.max_tokens}), using keywords for "
                                f"remaining articles"
                            )
                        budget_skipped += 1
                        classified_article = self.classifier._classify_with_keywords(
                            article
                        )
                    else:
                        classified_article = self.classifier.classify(article)
                    classified_articles.append(classified_article)
                    # Collect telemetry and record tokens if LLM was called
                    if self.classifier.last_telemetry:
                        telem = self.classifier.last_telemetry
                        telemetry_rows.append(telem)
                        budget.record(telem["tokens_in"], telem["tokens_out"])
                except Exception as e:
                    print(f"Error classifying article {article.title}: {e}")
                    continue
            # Classification path diagnostics
            llm_ok = sum(
                1
                for t in telemetry_rows
                if t["llm_status"] == "ok"
                and t["prompt_version"].startswith("classification")
            )
            llm_failed = sum(
                1
                for t in telemetry_rows
                if t["llm_status"] != "ok"
                and t["prompt_version"].startswith("classification")
            )
            keyword_only = (
                len(classified_articles) - llm_ok - llm_failed - budget_skipped
            )
            if budget_skipped:
                print(f"Budget: {budget_skipped} articles used keyword fallback")
            print(
                f"Classified {len(classified_articles)} articles "
                f"(LLM: {llm_ok} ok, {llm_failed} failed, "
                f"{budget_skipped} budget-skipped, {keyword_only} keyword-only, "
                f"tokens used: {budget.tokens_used})"
            )

            # Step 2.5: Summarize articles (with budget tracking)
            summary_skipped = 0
            for article in classified_articles:
                try:
                    if budget.exceeded and config.ai.summary_enabled:
                        if summary_skipped == 0:
                            print(
                                f"Token budget exceeded ({budget.tokens_used}/"
                                f"{budget.max_tokens}), skipping summaries "
                                f"for remaining articles"
                            )
                        summary_skipped += 1
                    else:
                        self.summarizer.summarize(article)
                    if self.summarizer.last_telemetry:
                        telem = self.summarizer.last_telemetry
                        telemetry_rows.append(telem)
                        budget.record(telem["tokens_in"], telem["tokens_out"])
                except Exception as e:
                    print(f"Error summarizing article {article.title}: {e}")
                    continue
            summarized_count = len([a for a in classified_articles if a.summary])
            if summary_skipped:
                print(f"Budget: {summary_skipped} articles skipped " f"summarization")
            if config.ai.summary_enabled:
                print(
                    f"Summarized {summarized_count}/{len(classified_articles)}"
                    f" articles (tokens used: {budget.tokens_used})"
                )

            # Persist LLM telemetry
            self._record_telemetry(job_id, telemetry_rows, db)

            # Step 3: Assess quality
            quality_articles = []
            for article in classified_articles:
                try:
                    assessed_article = self.quality_assessor.assess_quality(article)
                    quality_articles.append(assessed_article)
                except Exception as e:
                    print(
                        f"Error assessing quality for article {article.title}: " f"{e}"
                    )
                    continue

            high_quality_articles = [
                a for a in quality_articles if a.quality_score >= 0.6
            ]
            print(f"Found {len(high_quality_articles)} high-quality articles")

            # Store articles in database and track per-source counts
            stored_count = 0
            source_stored: dict[str, int] = {}
            for article in high_quality_articles:
                if self._store_article(article, db):
                    stored_count += 1
                    source_stored[article.source] = (
                        source_stored.get(article.source, 0) + 1
                    )

            # Record source metrics (with aggregates from scored articles)
            source_fetched: dict[str, int] = {}
            for article in all_articles:
                source_fetched[article.source] = (
                    source_fetched.get(article.source, 0) + 1
                )
            self._record_source_metrics(
                job_id, source_fetched, source_stored, quality_articles, db
            )

            # Update job with success status
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.result_count = stored_count
            db.commit()

            print(f"Scrape job {job_id} completed: {stored_count} articles stored")

        except Exception as e:
            # Update job with error status
            print(f"Error in scrape job {job_id}: {e}")
            import traceback

            traceback.print_exc()
            try:
                job = db.query(DBJob).filter(DBJob.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.completed_at = datetime.utcnow()
                    job.error_message = str(e)
                    db.commit()
            except Exception as commit_error:
                print(f"Error updating job status: {commit_error}")
                db.rollback()

        finally:
            db.close()

    def _store_article(self, article: PipelineArticle, db: Session) -> bool:
        """
        Store an article in the database

        Args:
            article: The article to store
            db: Database session

        Returns:
            True if article was stored successfully, False otherwise
        """
        try:
            # Generate content hash
            content_hash = self._generate_hash(article.url, article.title)

            # Check if article already exists (by URL or content hash)
            existing = (
                db.query(DBArticle)
                .filter(
                    (DBArticle.url == article.url)
                    | (DBArticle.content_hash == content_hash)
                )
                .first()
            )

            if existing:
                print(f"Article already exists: {article.title}")
                return False

            # Create new article record
            db_article = DBArticle(
                url=article.url,
                title=article.title,
                source=article.source,
                category=article.category,
                country=article.country if article.country else None,
                quality_score=article.quality_score,
                eu_relevance=article.eu_relevance if article.eu_relevance else None,
                confidence=article.confidence if article.confidence else None,
                content_hash=content_hash,
                content=article.content if article.content else None,
                summary=article.summary if article.summary else None,
                image_url=article.image_url,
                published_date=article.published_date,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            db.add(db_article)
            db.commit()
            db.refresh(db_article)

            print(f"Stored article: {article.title} (ID: {db_article.id})")
            return True

        except Exception as e:
            print(f"Error storing article {article.title}: {e}")
            import traceback

            traceback.print_exc()
            db.rollback()
            return False

    def _record_source_metrics(
        self,
        job_id: str,
        source_fetched: dict[str, int],
        source_stored: dict[str, int],
        scored_articles: List[PipelineArticle],
        db: Session,
    ) -> None:
        """Record per-source metrics with aggregates for this scrape run."""
        import json

        try:
            # Group scored articles by source for aggregate computation
            source_articles: dict[str, list] = {}
            for article in scored_articles:
                source_articles.setdefault(article.source, []).append(article)

            all_sources = (
                set(source_fetched.keys())
                | set(source_stored.keys())
                | set(source_articles.keys())
            )
            for source_name in all_sources:
                arts = source_articles.get(source_name, [])
                eu_scores = [a.eu_relevance for a in arts if a.eu_relevance]
                q_scores = [a.quality_score for a in arts if a.quality_score]
                category_counts: dict[str, int] = {}
                for a in arts:
                    if a.category:
                        category_counts[a.category] = (
                            category_counts.get(a.category, 0) + 1
                        )

                metric = SourceMetric(
                    run_id=job_id,
                    source_name=source_name,
                    articles_fetched=source_fetched.get(source_name, 0),
                    articles_stored=source_stored.get(source_name, 0),
                    articles_passed_relevance=(
                        len([s for s in eu_scores if s >= 3.0]) if eu_scores else 0
                    ),
                    avg_eu_relevance=(
                        round(sum(eu_scores) / len(eu_scores), 2) if eu_scores else None
                    ),
                    avg_quality_score=(
                        round(sum(q_scores) / len(q_scores), 2) if q_scores else None
                    ),
                    category_distribution=(
                        json.dumps(category_counts) if category_counts else None
                    ),
                    timestamp=datetime.utcnow(),
                )
                db.add(metric)
            db.flush()
        except Exception as e:
            print(f"Error recording source metrics: {e}")

    def _record_telemetry(
        self,
        job_id: str,
        telemetry_rows: list[dict],
        db: Session,
    ) -> None:
        """Persist LLM telemetry rows for this scrape run."""
        if not telemetry_rows:
            return
        try:
            for row in telemetry_rows:
                entry = LLMTelemetry(
                    run_id=job_id,
                    article_url=row["article_url"],
                    llm_model=row["llm_model"],
                    prompt_version=row["prompt_version"],
                    llm_latency_ms=row["llm_latency_ms"],
                    tokens_in=row["tokens_in"],
                    tokens_out=row["tokens_out"],
                    llm_status=row["llm_status"],
                    fallback_reason=row.get("fallback_reason"),
                    timestamp=datetime.utcnow(),
                )
                db.add(entry)
            db.flush()
            total_tokens = sum(r["tokens_in"] + r["tokens_out"] for r in telemetry_rows)
            print(
                f"Recorded {len(telemetry_rows)} telemetry rows "
                f"(total tokens: {total_tokens})"
            )
        except Exception as e:
            print(f"Error recording telemetry: {e}")

    def _remove_duplicates(
        self, articles: List[PipelineArticle]
    ) -> List[PipelineArticle]:
        """
        Remove duplicate articles based on URL and hash

        Args:
            articles: List of articles to deduplicate

        Returns:
            List of unique articles
        """
        seen_urls = set()
        seen_hashes = set()
        unique_articles = []

        for article in articles:
            # Check URL first
            if article.url in seen_urls:
                continue

            # Check content hash
            article_hash = article.generate_hash()
            if article_hash in seen_hashes:
                continue

            # Add to unique list
            seen_urls.add(article.url)
            seen_hashes.add(article_hash)
            unique_articles.append(article)

        return unique_articles

    def _generate_hash(self, url: str, title: str) -> str:
        """
        Generate a unique hash for an article

        Args:
            url: Article URL
            title: Article title

        Returns:
            SHA-256 hash of the article
        """
        content = f"{url}|{title}"
        return hashlib.sha256(content.encode()).hexdigest()


# Global pipeline service instance
pipeline_service = PipelineService()


def get_pipeline_service() -> PipelineService:
    """
    Get the global pipeline service instance

    Returns:
        The pipeline service instance
    """
    return pipeline_service
