"""
SQLAlchemy database models for the API
"""

from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

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
    category = Column(String, nullable=False)  # startups, policy, country, stories
    country = Column(String, nullable=True)
    quality_score = Column(Float, nullable=False)
    content_hash = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=True)  # Full article content
    summary = Column(Text, nullable=True)  # Article summary
    published_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return (
            f"<Article(id={self.id}, title='{self.title}', "
            f"category='{self.category}')>"
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
    echo=False  # Set to True for SQL debugging
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
    print(f"Database initialized at {DATABASE_URL}")


def drop_db():
    """
    Drop all tables (useful for development/testing)
    """
    Base.metadata.drop_all(bind=engine)
    print(f"Database tables dropped at {DATABASE_URL}")
