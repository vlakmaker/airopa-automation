"""
Articles API endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime
from typing import Optional
from uuid import uuid4

from ..models.schemas import ArticleResponse, ArticlesListResponse, ArticleCategory, ArticleCountry

router = APIRouter(prefix="/api", tags=["articles"])

# Mock data for development (will replace with real data later)
MOCK_ARTICLES = [
    {
        "id": str(uuid4()),
        "title": "European AI Startup Secures €15M in Series A Funding",
        "url": "https://tech.eu/ai-startup-funding",
        "source": "Tech.eu",
        "category": "startups",
        "country": "Europe",
        "quality_score": 0.87,
        "created_at": datetime.now(),
        "published_date": datetime(2024, 1, 10, 9, 0, 0)
    },
    {
        "id": str(uuid4()),
        "title": "New EU Regulation on Artificial Intelligence Adopted",
        "url": "https://europa.eu/ai-regulation",
        "source": "Europa.eu",
        "category": "policy",
        "country": "Europe",
        "quality_score": 0.92,
        "created_at": datetime.now(),
        "published_date": datetime(2024, 1, 12, 14, 30, 0)
    },
    {
        "id": str(uuid4()),
        "title": "French Deep Tech Startup Wins Innovation Award",
        "url": "https://sifted.eu/french-startup-award",
        "source": "Sifted.eu",
        "category": "startups",
        "country": "France",
        "quality_score": 0.78,
        "created_at": datetime.now(),
        "published_date": datetime(2024, 1, 8, 11, 15, 0)
    },
    {
        "id": str(uuid4()),
        "title": "Germany Invests €1B in Quantum Computing Research",
        "url": "https://tech.eu/germany-quantum-investment",
        "source": "Tech.eu",
        "category": "country",
        "country": "Germany",
        "quality_score": 0.85,
        "created_at": datetime.now(),
        "published_date": datetime(2024, 1, 15, 8, 45, 0)
    },
    {
        "id": str(uuid4()),
        "title": "Dutch AI Company Expands to US Market",
        "url": "https://european-champions.org/dutch-ai-expansion",
        "source": "European Champions",
        "category": "startups",
        "country": "Netherlands",
        "quality_score": 0.76,
        "created_at": datetime.now(),
        "published_date": datetime(2024, 1, 11, 10, 30, 0)
    }
]


@router.get("/articles", response_model=ArticlesListResponse)
async def list_articles(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of articles to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    category: Optional[ArticleCategory] = Query(None, description="Filter by article category"),
    country: Optional[ArticleCountry] = Query(None, description="Filter by country"),
    min_quality: float = Query(0.0, ge=0.0, le=1.0, description="Minimum quality score")
):
    """
    List processed articles
    
    Returns a paginated list of articles that have been processed by the automation pipeline.
    Supports filtering by category, country, and minimum quality score.
    """
    try:
        # Filter articles based on query parameters
        filtered_articles = MOCK_ARTICLES
        
        if category:
            filtered_articles = [a for a in filtered_articles if a["category"] == category]
            
        if country:
            filtered_articles = [a for a in filtered_articles if a.get("country") == country]
            
        if min_quality > 0.0:
            filtered_articles = [a for a in filtered_articles if a["quality_score"] >= min_quality]
        
        # Apply pagination
        paginated_articles = filtered_articles[offset:offset + limit]
        
        # Convert to ArticleResponse models
        article_responses = [
            ArticleResponse(
                id=a["id"],
                title=a["title"],
                url=a["url"],
                source=a["source"],
                category=a["category"],
                country=a.get("country"),
                quality_score=a["quality_score"],
                created_at=a["created_at"],
                published_date=a.get("published_date")
            )
            for a in paginated_articles
        ]
        
        return ArticlesListResponse(
            articles=article_responses,
            total=len(filtered_articles),
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
async def get_article(article_id: str):
    """
    Get a specific article by ID
    
    Returns detailed information about a single article.
    """
    try:
        # Find article by ID (using mock data for now)
        article = next((a for a in MOCK_ARTICLES if a["id"] == article_id), None)
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return ArticleResponse(
            id=article["id"],
            title=article["title"],
            url=article["url"],
            source=article["source"],
            category=article["category"],
            country=article.get("country"),
            quality_score=article["quality_score"],
            created_at=article["created_at"],
            published_date=article.get("published_date")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving article: {str(e)}"
        )