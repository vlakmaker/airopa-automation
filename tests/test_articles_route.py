"""Tests for the articles API route, specifically eu_relevance filtering."""

from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from airopa_automation.api.models.database import Article as DBArticle
from airopa_automation.api.models.database import Base, get_db


@pytest.fixture()
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    # Seed test articles
    articles = [
        DBArticle(
            url="https://example.com/high-relevance",
            title="High Relevance Article",
            source="Sifted",
            category="startups",
            quality_score=0.8,
            eu_relevance=7.0,
            content_hash="hash1",
            created_at=datetime(2025, 1, 1),
        ),
        DBArticle(
            url="https://example.com/low-relevance",
            title="Low Relevance Article",
            source="WIRED",
            category="research",
            quality_score=0.7,
            eu_relevance=1.5,
            content_hash="hash2",
            created_at=datetime(2025, 1, 2),
        ),
        DBArticle(
            url="https://example.com/null-relevance",
            title="Null Relevance Article",
            source="Tech.eu",
            category="industry",
            quality_score=0.9,
            eu_relevance=None,
            content_hash="hash3",
            created_at=datetime(2025, 1, 3),
        ),
        DBArticle(
            url="https://example.com/borderline",
            title="Borderline Article",
            source="EU-Startups",
            category="policy",
            quality_score=0.75,
            eu_relevance=3.0,
            content_hash="hash4",
            created_at=datetime(2025, 1, 4),
        ),
    ]
    for a in articles:
        session.add(a)
    session.commit()

    yield session
    session.close()


@pytest.fixture()
def client(test_db):
    """Create a test client with the test database."""
    from airopa_automation.api.main import app

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_eu_relevance_filter_hides_low_relevance(client):
    """Articles with eu_relevance < threshold should be hidden."""
    with patch("airopa_automation.api.routes.articles.config") as mock_config:
        mock_config.scraper.eu_relevance_threshold = 3.0

        response = client.get("/api/articles")
        assert response.status_code == 200

        data = response.json()
        titles = [a["title"] for a in data["articles"]]

        # High relevance (7.0) should be included
        assert "High Relevance Article" in titles
        # Borderline (3.0 == threshold) should be included
        assert "Borderline Article" in titles
        # Null relevance should be included (legacy articles)
        assert "Null Relevance Article" in titles
        # Low relevance (1.5) should be excluded
        assert "Low Relevance Article" not in titles

        assert data["total"] == 3


def test_eu_relevance_filter_disabled_when_zero(client):
    """When threshold is 0, all articles should be returned."""
    with patch("airopa_automation.api.routes.articles.config") as mock_config:
        mock_config.scraper.eu_relevance_threshold = 0.0

        response = client.get("/api/articles")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 4
