"""
SQLAlchemy database models for the API
"""

import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Article(Base):
    """
    Article model - stores processed articles from the automation pipeline
    """

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    source = Column(String, nullable=False)
    category = Column(String, nullable=False)  # startups, policy, research, industry
    country = Column(String, nullable=True)
    quality_score = Column(Float, nullable=False)
    eu_relevance = Column(Float, nullable=True)  # European relevance score 0-10
    content_hash = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=True)  # Full article content
    summary = Column(Text, nullable=True)  # Article summary
    image_url = Column(String, nullable=True)  # Article cover image URL
    published_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return (
            f"<Article(id={self.id}, title='{self.title}', "
            f"category='{self.category}')>"
        )


class SourceMetric(Base):
    """
    Source metric model - tracks per-source stats per scrape run
    """

    __tablename__ = "source_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(String, nullable=False, index=True)  # Job ID of the scrape run
    source_name = Column(String, nullable=False, index=True)
    articles_fetched = Column(Integer, nullable=False, default=0)
    articles_stored = Column(Integer, nullable=False, default=0)
    articles_passed_relevance = Column(Integer, nullable=True)  # eu_relevance >= 3.0
    avg_eu_relevance = Column(Float, nullable=True)
    avg_quality_score = Column(Float, nullable=True)
    category_distribution = Column(Text, nullable=True)  # JSON string
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<SourceMetric(run_id='{self.run_id}', "
            f"source='{self.source_name}', fetched={self.articles_fetched})>"
        )


class LLMTelemetry(Base):
    """
    LLM telemetry - tracks per-article LLM call results
    for observability and cost analysis
    """

    __tablename__ = "llm_telemetry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(String, nullable=False, index=True)  # Job ID of the scrape run
    article_url = Column(String, nullable=False)
    llm_model = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)  # e.g. "classification_v1"
    llm_latency_ms = Column(Integer, nullable=False, default=0)
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    llm_status = Column(
        String, nullable=False
    )  # ok, no_api_key, api_error, timeout, etc.
    fallback_reason = Column(String, nullable=True)  # null if LLM succeeded
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<LLMTelemetry(run_id='{self.run_id}', "
            f"article='{self.article_url[:40]}', status='{self.llm_status}')>"
        )


class Job(Base):
    """
    Job model - tracks background jobs (scraping, processing, etc.)
    """

    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)  # UUID
    status = Column(String, nullable=False)  # queued, running, completed, failed
    job_type = Column(String, nullable=False)  # scrape, classify, etc.
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    result_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Job(id='{self.id}', status='{self.status}', type='{self.job_type}')>"


# Database configuration and session management
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database/airopa_api.db")

# Railway uses postgres:// but SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ),
    echo=False,  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Database session dependency for FastAPI endpoints

    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database - create all tables
    """
    # Ensure database directory exists
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Create all tables
    Base.metadata.create_all(bind=engine)
    # Don't log DATABASE_URL as it may contain credentials
    db_type = "PostgreSQL" if DATABASE_URL.startswith("postgresql") else "SQLite"
    print(f"Database initialized successfully (type: {db_type})")


def drop_db():
    """
    Drop all tables (useful for development/testing)
    """
    Base.metadata.drop_all(bind=engine)
    # Don't log DATABASE_URL as it may contain credentials
    print("Database tables dropped successfully")
