"""
Pipeline service - Connects the automation pipeline to the database

This service handles running the scraping pipeline and storing results in the database.
"""

import hashlib
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from airopa_automation.agents import (
    ScraperAgent,
    CategoryClassifierAgent,
    QualityScoreAgent,
    Article as PipelineArticle
)
from airopa_automation.config import config, ensure_directories
from ..models.database import SessionLocal, Article as DBArticle, Job as DBJob


class PipelineService:
    """
    Service for running the automation pipeline and storing results in the database
    """

    def __init__(self):
        """Initialize the pipeline service"""
        ensure_directories()

        self.scraper = ScraperAgent()
        self.classifier = CategoryClassifierAgent()
        self.quality_assessor = QualityScoreAgent()

    def run_scrape_job(self, job_id: str) -> None:
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

            # Step 2: Classify articles
            classified_articles = []
            for article in articles:
                try:
                    classified_article = self.classifier.classify(article)
                    classified_articles.append(classified_article)
                except Exception as e:
                    print(f"Error classifying article {article.title}: {e}")
                    continue
            print(f"Classified {len(classified_articles)} articles")

            # Step 3: Assess quality
            quality_articles = []
            for article in classified_articles:
                try:
                    assessed_article = self.quality_assessor.assess_quality(article)
                    quality_articles.append(assessed_article)
                except Exception as e:
                    print(f"Error assessing quality for article {article.title}: {e}")
                    continue

            high_quality_articles = [a for a in quality_articles if a.quality_score >= 0.6]
            print(f"Found {len(high_quality_articles)} high-quality articles")

            # Store articles in database
            stored_count = 0
            for article in high_quality_articles:
                if self._store_article(article, db):
                    stored_count += 1

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
            existing = db.query(DBArticle).filter(
                (DBArticle.url == article.url) | (DBArticle.content_hash == content_hash)
            ).first()

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
                content_hash=content_hash,
                content=article.content if article.content else None,
                summary=article.summary if article.summary else None,
                published_date=article.published_date,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
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

    def _remove_duplicates(self, articles: List[PipelineArticle]) -> List[PipelineArticle]:
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
