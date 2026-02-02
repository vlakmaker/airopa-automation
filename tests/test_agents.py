import pytest
from unittest.mock import Mock, patch
from airopa_automation.agents import (
    ScraperAgent, 
    CategoryClassifierAgent,
    QualityScoreAgent,
    ContentGeneratorAgent,
    GitCommitAgent
)
from airopa_automation.config import (
    ScraperConfig,
    CategoryClassifierConfig,
    QualityScoreConfig,
    ContentGeneratorConfig,
    GitConfig
)


def test_scraper_agent_rss():
    """Test RSS scraping functionality"""
    config = ScraperConfig(
        rss_feeds=[],
        web_sources=[],
        user_agent="Test Agent",
        timeout=10
    )
    scraper = ScraperAgent(config)
    
    # Mock feedparser
    with patch('feedparser.parse') as mock_parse:
        mock_parse.return_value.entries = [
            Mock(title="Test Title", link="http://test.com", description="Test content")
        ]
        
        results = scraper.scrape_rss("http://test-rss.com")
        assert len(results) == 1
        assert results[0]['title'] == "Test Title"
        assert results[0]['url'] == "http://test.com"


def test_scraper_agent_web():
    """Test web scraping functionality"""
    config = ScraperConfig(
        rss_feeds=[],
        web_sources=[],
        user_agent="Test Agent",
        timeout=10
    )
    scraper = ScraperAgent(config)
    
    # Mock newspaper Article
    with patch('airopa_automation.agents.Article') as mock_article:
        mock_instance = Mock()
        mock_instance.title = "Test Article"
        mock_instance.text = "Test article content"
        mock_article.return_value = mock_instance
        
        result = scraper.scrape_web("http://test.com")
        assert result['title'] == "Test Article"
        assert result['content'] == "Test article content"


def test_category_classifier():
    """Test content classification"""
    config = CategoryClassifierConfig(
        categories=["policy", "innovation", "research"]
    )
    classifier = CategoryClassifierAgent(config)
    
    # Test with matching content
    categories = classifier.classify("This is about AI policy and innovation")
    assert "policy" in categories
    assert "innovation" in categories
    
    # Test with no matches
    categories = classifier.classify("Random content without keywords")
    assert categories == ["general"]


def test_quality_score_agent():
    """Test quality scoring"""
    config = QualityScoreConfig(
        min_length=100,
        max_length=1000,
        quality_threshold=0.5
    )
    scorer = QualityScoreAgent(config)
    
    # Test with good content
    good_content = "AI policy in Europe is evolving. Regulation and innovation are key factors. " * 10
    score = scorer.calculate_score(good_content)
    assert 0 <= score <= 1.0
    
    # Test with short content
    short_content = "Short"
    score = scorer.calculate_score(short_content)
    assert score < 0.5


def test_content_generator():
    """Test content generation"""
    config = ContentGeneratorConfig(
        output_dir="./test_output",
        template="{title}.md",
        frontmatter_template="""---
title: {title}
date: {date}
categories: {categories}
tags: {tags}
---
"""
    )
    generator = ContentGeneratorAgent(config)
    
    # Test content generation
    item = {
        'title': "Test Article",
        'content': "Test content here"
    }
    categories = ["policy", "innovation"]
    
    content = generator.generate_content(item, categories)
    assert "Test Article" in content
    assert "policy" in content
    assert "innovation" in content
    assert "Test content here" in content


def test_git_commit_agent():
    """Test git commit functionality"""
    config = GitConfig(
        repo_path="./test_repo",
        commit_message="Test commit",
        author_name="Test Author",
        author_email="test@example.com"
    )
    
    # Mock git repo
    with patch('airopa_automation.agents.Repo') as mock_repo:
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        
        agent = GitCommitAgent(config)
        agent.commit_changes("Custom test message")
        
        # Verify git operations were called
        mock_instance.git.add.assert_called_once_with('.')
        mock_instance.index.commit.assert_called_once()