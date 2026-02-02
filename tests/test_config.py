import pytest
from pydantic import ValidationError
from airopa_automation.config import (
    ScraperConfig,
    CategoryClassifierConfig,
    QualityScoreConfig,
    ContentGeneratorConfig,
    GitConfig,
    AIropaConfig
)


def test_scraper_config():
    """Test ScraperConfig validation"""
    config = ScraperConfig(
        rss_feeds=["http://test.com/rss"],
        web_sources=["http://test.com"],
        user_agent="Test Agent/1.0",
        timeout=60
    )
    
    assert config.rss_feeds == ["http://test.com/rss"]
    assert config.web_sources == ["http://test.com"]
    assert config.user_agent == "Test Agent/1.0"
    assert config.timeout == 60


def test_category_classifier_config():
    """Test CategoryClassifierConfig validation"""
    config = CategoryClassifierConfig(
        categories=["policy", "regulation", "innovation"]
    )
    
    assert config.categories == ["policy", "regulation", "innovation"]


def test_quality_score_config():
    """Test QualityScoreConfig validation"""
    config = QualityScoreConfig(
        min_length=200,
        max_length=2000,
        quality_threshold=0.8
    )
    
    assert config.min_length == 200
    assert config.max_length == 2000
    assert config.quality_threshold == 0.8


def test_content_generator_config():
    """Test ContentGeneratorConfig validation"""
    config = ContentGeneratorConfig(
        output_dir="./output",
        template="{title}.md",
        frontmatter_template="title: {title}"
    )
    
    assert config.output_dir == "./output"
    assert config.template == "{title}.md"
    assert config.frontmatter_template == "title: {title}"


def test_git_config():
    """Test GitConfig validation"""
    config = GitConfig(
        repo_path="./repo",
        commit_message="Test commit message",
        author_name="Test Author",
        author_email="test@example.com"
    )
    
    assert config.repo_path == "./repo"
    assert config.commit_message == "Test commit message"
    assert config.author_name == "Test Author"
    assert config.author_email == "test@example.com"


def test_airopa_config():
    """Test full AIropaConfig integration"""
    config = AIropaConfig()
    
    # Test default values
    assert config.scraper.user_agent == "AIropa Bot/1.0"
    assert config.scraper.timeout == 30
    assert config.classifier.categories == [
        "policy", "regulation", "innovation", 
        "research", "funding", "ethics"
    ]
    assert config.quality.min_length == 500
    assert config.quality.max_length == 5000
    assert config.quality.quality_threshold == 0.7
    assert config.generator.output_dir == "../src/content/post"
    assert config.git.repo_path == ".."


def test_config_validation():
    """Test config validation errors"""
    # Test invalid timeout
    with pytest.raises(ValidationError):
        ScraperConfig(timeout=-1)
    
    # Test invalid quality threshold
    with pytest.raises(ValidationError):
        QualityScoreConfig(quality_threshold=1.5)


def test_config_overrides():
    """Test config override functionality"""
    config = AIropaConfig(
        scraper=ScraperConfig(timeout=120),
        quality=QualityScoreConfig(quality_threshold=0.9)
    )
    
    assert config.scraper.timeout == 120
    assert config.quality.quality_threshold == 0.9
    # Other defaults should remain
    assert config.scraper.user_agent == "AIropa Bot/1.0"