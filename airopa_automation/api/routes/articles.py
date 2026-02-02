"""
Articles API endpoints
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from ..models.schemas import ArticleResponse, ArticlesListResponse, ArticleCategory, ArticleCountry
from ..models.database import get_db, Article as DBArticle

router = APIRouter(prefix="/api", tags=["articles"])


@router.get("/articles", response_model=ArticlesListResponse)
async def list_articles(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of articles to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    category: Optional[ArticleCategory] = Query(None, description="Filter by article category"),
    country: Optional[ArticleCountry] = Query(None, description="Filter by country"),
    min_quality: float = Query(0.0, ge=0.0, le=1.0, description="Minimum quality score"),
    db: Session = Depends(get_db)
):
    """
    List processed articles

    Returns a paginated list of articles that have been processed by the automation pipeline.
    Supports filtering by category, country, and minimum quality score.
    """
    try:
        # Build query with filters
        query = db.query(DBArticle)

        if category:
            query = query.filter(DBArticle.category == category.value)

        if country:
            query = query.filter(DBArticle.country == country.value)

        if min_quality > 0.0:
            query = query.filter(DBArticle.quality_score >= min_quality)

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering (most recent first)
        articles = query.order_by(DBArticle.created_at.desc()).offset(offset).limit(limit).all()

        # Convert to ArticleResponse models
        article_responses = [
            ArticleResponse(
                id=str(article.id),
                title=article.title,
                url=article.url,
                source=article.source,
                category=article.category,
                country=article.country,
                quality_score=article.quality_score,
                created_at=article.created_at,
                published_date=article.published_date
            )
            for article in articles
        ]

        return ArticlesListResponse(
            articles=article_responses,
            total=total,
            limit=limit,
            offset=offset,
            timestamp=datetime.now()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving articles: {str(e)}"
        )


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: Session = Depends(get_db)):
    """
    Get a specific article by ID

    Returns detailed information about a single article.
    """
    try:
        # Query article by ID
        article = db.query(DBArticle).filter(DBArticle.id == article_id).first()

        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        return ArticleResponse(
            id=str(article.id),
            title=article.title,
            url=article.url,
            source=article.source,
            category=article.category,
            country=article.country,
            quality_score=article.quality_score,
            created_at=article.created_at,
            published_date=article.published_date
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving article: {str(e)}"
        )