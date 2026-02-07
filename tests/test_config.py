from airopa_automation.config import (
    Config,
    ContentConfig,
    DatabaseConfig,
    GitConfig,
    ScraperConfig,
)


def test_scraper_config_defaults():
    """Test ScraperConfig default values"""
    config = ScraperConfig()

    assert len(config.rss_feeds) == 16  # 4 existing + 6 Tier 1 + 4 Tier 2 + 2 Tier 3
    assert len(config.web_sources) == 3
    assert config.max_articles_per_source == 10
    assert config.rate_limit_delay == 1.0
    assert "AIropaBot" in config.user_agent
    assert config.eu_relevance_threshold == 3.0
    # Test that source URLs are present across tiers
    assert any("sifted.eu" in url for url in config.rss_feeds)
    assert any("tech.eu" in url for url in config.rss_feeds)
    assert any("european-champions.org" in url for url in config.rss_feeds)
    assert any("eu-startups.com" in url for url in config.rss_feeds)
    assert any("algorithmwatch.org" in url for url in config.rss_feeds)
    assert any("deepmind.com" in url for url in config.rss_feeds)


def test_scraper_config_custom():
    """Test ScraperConfig with custom values"""
    config = ScraperConfig(
        rss_feeds=["http://test.com/rss"],
        web_sources=["http://test.com"],
        max_articles_per_source=5,
        rate_limit_delay=2.0,
        user_agent="Test Agent/1.0",
    )

    assert config.rss_feeds == ["http://test.com/rss"]
    assert config.web_sources == ["http://test.com"]
    assert config.max_articles_per_source == 5
    assert config.rate_limit_delay == 2.0
    assert config.user_agent == "Test Agent/1.0"


def test_database_config_defaults():
    """Test DatabaseConfig default values"""
    config = DatabaseConfig()

    assert config.db_path == "database/airopa.db"
    assert config.max_connections == 5
    assert config.timeout == 10.0


def test_content_config_defaults():
    """Test ContentConfig default values"""
    config = ContentConfig()

    assert "content/post" in config.output_dir
    assert config.default_author == "AIropa Bot"
    assert config.default_cover_image != ""


def test_git_config_defaults():
    """Test GitConfig default values"""
    config = GitConfig()

    assert config.repo_path == ".."
    assert "content" in config.commit_message.lower()
    assert config.author_name == "AIropa Bot"
    assert "@" in config.author_email


def test_git_config_custom():
    """Test GitConfig with custom values"""
    config = GitConfig(
        repo_path="./repo",
        commit_message="Test commit message",
        author_name="Test Author",
        author_email="test@example.com",
    )

    assert config.repo_path == "./repo"
    assert config.commit_message == "Test commit message"
    assert config.author_name == "Test Author"
    assert config.author_email == "test@example.com"


def test_full_config():
    """Test full Config integration"""
    config = Config()

    # Test that all sub-configs are present
    assert config.scraper is not None
    assert config.ai is not None
    assert config.database is not None
    assert config.content is not None
    assert config.git is not None

    # Test some default values
    assert config.scraper.max_articles_per_source == 10
    assert config.database.db_path == "database/airopa.db"


def test_config_override():
    """Test config with overridden sub-configs"""
    config = Config(
        scraper=ScraperConfig(max_articles_per_source=20),
        git=GitConfig(author_name="Custom Bot"),
    )

    assert config.scraper.max_articles_per_source == 20
    assert config.git.author_name == "Custom Bot"
    # Other defaults should remain
    assert config.database.db_path == "database/airopa.db"


def test_source_name_map_covers_all_tiers():
    """Test that source_name_map has entries for all expected sources"""
    config = ScraperConfig()
    mapped_names = set(config.source_name_map.values())

    # Tier 1
    assert "EU-Startups" in mapped_names
    assert "Silicon Canals" in mapped_names
    assert "The Next Web" in mapped_names
    assert "WIRED" in mapped_names
    assert "Silicon Republic" in mapped_names

    # Tier 2
    assert "AlgorithmWatch" in mapped_names
    assert "EURACTIV" in mapped_names
    assert "Artificial Lawyer" in mapped_names
    assert "Tech Funding News" in mapped_names

    # Tier 3
    assert "DeepMind" in mapped_names
    assert "Hugging Face" in mapped_names


def test_eu_relevance_threshold_default():
    """Test default eu_relevance threshold is 3.0"""
    config = ScraperConfig()
    assert config.eu_relevance_threshold == 3.0


def test_eu_relevance_threshold_custom():
    """Test eu_relevance threshold can be customized"""
    config = ScraperConfig(eu_relevance_threshold=5.0)
    assert config.eu_relevance_threshold == 5.0
