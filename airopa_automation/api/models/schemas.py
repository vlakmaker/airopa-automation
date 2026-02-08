"""
Pydantic models for API responses and requests
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ArticleCategory(str, Enum):
    """Valid article categories"""

    startups = "startups"
    policy = "policy"
    research = "research"
    industry = "industry"
    other = "other"
    # Legacy categories (kept for backward compatibility with older articles)
    country = "country"
    stories = "stories"


class ArticleCountry(str, Enum):
    """Common country classifications (used for documentation/filtering)"""

    austria = "Austria"
    belgium = "Belgium"
    bulgaria = "Bulgaria"
    croatia = "Croatia"
    cyprus = "Cyprus"
    czech_republic = "Czech Republic"
    denmark = "Denmark"
    estonia = "Estonia"
    finland = "Finland"
    france = "France"
    germany = "Germany"
    greece = "Greece"
    hungary = "Hungary"
    ireland = "Ireland"
    italy = "Italy"
    latvia = "Latvia"
    lithuania = "Lithuania"
    luxembourg = "Luxembourg"
    malta = "Malta"
    netherlands = "Netherlands"
    poland = "Poland"
    portugal = "Portugal"
    romania = "Romania"
    slovakia = "Slovakia"
    slovenia = "Slovenia"
    spain = "Spain"
    sweden = "Sweden"
    europe = "Europe"


class ArticleResponse(BaseModel):
    """Response model for a single article"""

    id: str = Field(..., description="Unique article identifier")
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Original article URL")
    source: str = Field(..., description="Source website")
    category: ArticleCategory = Field(..., description="Article category")
    country: Optional[str] = Field(None, description="Country classification")
    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Quality score (0.0-1.0)"
    )
    summary: Optional[str] = Field(None, description="AI-generated article summary")
    image_url: Optional[str] = Field(None, description="Article cover image URL")
    created_at: datetime = Field(..., description="When article was processed")
    published_date: Optional[datetime] = Field(
        None, description="Original publication date"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "abc123",
                "title": "European Startup Raises €10M for AI Innovation",
                "url": "https://tech.eu/startup-funding",
                "source": "Tech.eu",
                "category": "startups",
                "country": "Europe",
                "quality_score": 0.85,
                "created_at": "2024-01-15T10:30:00Z",
                "published_date": "2024-01-10T09:00:00Z",
            }
        }


class ArticlesListResponse(BaseModel):
    """Response model for listing articles"""

    articles: List[ArticleResponse] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles")
    limit: int = Field(..., description="Number of articles returned")
    offset: int = Field(0, description="Pagination offset")
    timestamp: datetime = Field(..., description="Response timestamp")


class ErrorResponse(BaseModel):
    """Standard error response model"""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(..., description="When error occurred")


class JobStatus(str, Enum):
    """Valid job status values"""

    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobResponse(BaseModel):
    """Response model for job operations"""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    job_type: str = Field(..., description="Type of job")
    timestamp: datetime = Field(..., description="When job was created")
    result_count: Optional[int] = Field(
        None, description="Number of results if completed"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")


class HealthResponse(BaseModel):
    """Response model for health check"""

    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current timestamp")
    api: str = Field(..., description="API name")
    database: Optional[str] = Field(None, description="Database connection status")
    pipeline: Optional[str] = Field(None, description="Pipeline status")
