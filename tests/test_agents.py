from datetime import datetime
from unittest.mock import MagicMock, patch

from airopa_automation.agents import (
    Article,
    CategoryClassifierAgent,
    ContentGeneratorAgent,
    QualityScoreAgent,
    ScraperAgent,
)


class TestArticle:
    """Test Article model"""

    def test_article_creation(self):
        """Test creating an Article instance"""
        article = Article(
            title="Test Article",
            url="http://example.com/article",
            source="Test Source",
            content="This is the article content.",
        )

        assert article.title == "Test Article"
        assert article.url == "http://example.com/article"
        assert article.source == "Test Source"
        assert article.content == "This is the article content."
        assert article.category == ""
        assert article.quality_score == 0.0
        assert article.image_url is None

    def test_article_generate_hash(self):
        """Test Article hash generation"""
        article = Article(
            title="Test Article",
            url="http://example.com/article",
            source="Test Source",
            content="Content",
        )

        hash1 = article.generate_hash()
        assert len(hash1) == 64  # SHA256 hex digest length

        # Same article should generate same hash
        article2 = Article(
            title="Test Article",
            url="http://example.com/article",
            source="Test Source",
            content="Different content",
        )
        hash2 = article2.generate_hash()
        assert hash1 == hash2  # Hash is based on title, url, source

    def test_article_with_optional_fields(self):
        """Test Article with optional fields populated"""
        article = Article(
            title="Test",
            url="http://test.com",
            source="Source",
            content="Content",
            summary="Summary text",
            published_date=datetime(2024, 1, 15),
            category="policy",
            country="France",
            quality_score=0.8,
            image_url="https://example.com/image.jpg",
        )

        assert article.summary == "Summary text"
        assert article.published_date == datetime(2024, 1, 15)
        assert article.category == "policy"
        assert article.country == "France"
        assert article.quality_score == 0.8
        assert article.image_url == "https://example.com/image.jpg"


class TestCategoryClassifierAgent:
    """Test CategoryClassifierAgent"""

    def test_classify_startup_category(self):
        """Test classification of startup-related content"""
        classifier = CategoryClassifierAgent()
        article = Article(
            title="New AI Startup Raises Funding",
            url="http://test.com",
            source="Test",
            content="A new startup company has received investment.",
        )

        result = classifier.classify(article)

        assert result.category == "startups"

    def test_classify_policy_category(self):
        """Test classification of policy-related content"""
        classifier = CategoryClassifierAgent()
        article = Article(
            title="New AI Regulation Proposed",
            url="http://test.com",
            source="Test",
            content="The government has proposed new policy for AI.",
        )

        result = classifier.classify(article)

        assert result.category == "policy"

    def test_classify_country(self):
        """Test country classification"""
        classifier = CategoryClassifierAgent()
        article = Article(
            title="AI Development in France",
            url="http://test.com",
            source="Test",
            content="France is leading AI innovation.",
        )

        result = classifier.classify(article)

        assert result.country == "France"

    def test_classify_default_category(self):
        """Test default category for unclassified content"""
        classifier = CategoryClassifierAgent()
        article = Article(
            title="Random Title",
            url="http://test.com",
            source="Test",
            content="Some random content without keywords.",
        )

        result = classifier.classify(article)

        assert result.category == "stories"


class TestQualityScoreAgent:
    """Test QualityScoreAgent"""

    def test_quality_score_short_content(self):
        """Test quality score for short content"""
        scorer = QualityScoreAgent()
        article = Article(
            title="Short",
            url="http://test.com",
            source="Test",
            content="Very short content.",
        )

        result = scorer.assess_quality(article)

        assert result.quality_score < 0.5

    def test_quality_score_good_content(self):
        """Test quality score for good content"""
        scorer = QualityScoreAgent()
        long_content = " ".join(["word"] * 600)  # >500 words
        article = Article(
            title="A Good Article Title Here",
            url="http://test.com",
            source="Test",
            content=long_content,
            category="policy",
            country="Europe",
        )

        result = scorer.assess_quality(article)

        assert result.quality_score > 0.5

    def test_quality_score_max_is_one(self):
        """Test that quality score doesn't exceed 1.0"""
        scorer = QualityScoreAgent()
        article = Article(
            title="Excellent Article With Many Words",
            url="http://test.com",
            source="europa.eu",  # credible source
            content=" ".join(["word"] * 1000),
            category="policy",
            country="France",
        )

        result = scorer.assess_quality(article)

        assert result.quality_score <= 1.0


class TestScraperAgent:
    """Test ScraperAgent"""

    def test_scraper_init(self):
        """Test ScraperAgent initialization"""
        scraper = ScraperAgent()

        assert scraper.session is not None
        assert "User-Agent" in scraper.session.headers

    @patch("airopa_automation.agents.feedparser.parse")
    def test_scrape_rss_feeds_empty(self, mock_parse):
        """Test RSS scraping with empty config"""
        mock_parse.return_value = MagicMock(entries=[])

        with patch("airopa_automation.agents.config") as mock_config:
            mock_config.scraper.rss_feeds = []
            mock_config.scraper.user_agent = "Test"

            scraper = ScraperAgent()
            articles = scraper.scrape_rss_feeds()

            assert articles == []

    def test_validate_image_url_valid_https(self):
        """Test validation accepts valid HTTPS URLs"""
        scraper = ScraperAgent()
        assert (
            scraper._validate_image_url("https://example.com/image.jpg")
            == "https://example.com/image.jpg"
        )

    def test_validate_image_url_valid_http(self):
        """Test validation accepts valid HTTP URLs"""
        scraper = ScraperAgent()
        assert (
            scraper._validate_image_url("http://example.com/image.jpg")
            == "http://example.com/image.jpg"
        )

    def test_validate_image_url_none(self):
        """Test validation rejects None"""
        scraper = ScraperAgent()
        assert scraper._validate_image_url(None) is None

    def test_validate_image_url_empty(self):
        """Test validation rejects empty string"""
        scraper = ScraperAgent()
        assert scraper._validate_image_url("") is None

    def test_validate_image_url_no_scheme(self):
        """Test validation rejects URLs without http(s) scheme"""
        scraper = ScraperAgent()
        assert scraper._validate_image_url("ftp://example.com/image.jpg") is None
        assert scraper._validate_image_url("//example.com/image.jpg") is None

    def test_validate_image_url_too_long(self):
        """Test validation rejects URLs over 2048 characters"""
        scraper = ScraperAgent()
        long_url = "https://example.com/" + "a" * 2048
        assert scraper._validate_image_url(long_url) is None

    def test_validate_image_url_strips_whitespace(self):
        """Test validation strips whitespace"""
        scraper = ScraperAgent()
        assert (
            scraper._validate_image_url("  https://example.com/img.jpg  ")
            == "https://example.com/img.jpg"
        )

    def test_extract_rss_image_media_content(self):
        """Test RSS image extraction from media:content"""
        scraper = ScraperAgent()
        entry = MagicMock()
        entry.media_content = [{"url": "https://example.com/media.jpg"}]
        entry.enclosures = []

        result = scraper._extract_rss_image(entry)
        assert result == "https://example.com/media.jpg"

    def test_extract_rss_image_enclosure(self):
        """Test RSS image extraction from enclosures"""
        scraper = ScraperAgent()
        entry = MagicMock()
        entry.media_content = None
        entry.enclosures = [
            {"type": "image/jpeg", "href": "https://example.com/enc.jpg"}
        ]

        result = scraper._extract_rss_image(entry)
        assert result == "https://example.com/enc.jpg"

    def test_extract_rss_image_none(self):
        """Test RSS image extraction returns None when no images"""
        scraper = ScraperAgent()
        entry = MagicMock()
        entry.media_content = None
        entry.enclosures = []

        result = scraper._extract_rss_image(entry)
        assert result is None

    @patch("airopa_automation.agents.NewspaperArticle")
    def test_extract_article_data_with_image(self, mock_newspaper):
        """Test _extract_article_data returns content and image URL"""
        mock_article = MagicMock()
        mock_article.text = "Article content here"
        mock_article.top_image = "https://example.com/top.jpg"
        mock_newspaper.return_value = mock_article

        scraper = ScraperAgent()
        content, image_url = scraper._extract_article_data(
            "https://example.com/article"
        )

        assert content == "Article content here"
        assert image_url == "https://example.com/top.jpg"

    @patch("airopa_automation.agents.NewspaperArticle")
    def test_extract_article_data_no_image(self, mock_newspaper):
        """Test _extract_article_data with no image available"""
        mock_article = MagicMock()
        mock_article.text = "Article content here"
        mock_article.top_image = ""
        mock_newspaper.return_value = mock_article

        scraper = ScraperAgent()
        content, image_url = scraper._extract_article_data(
            "https://example.com/article"
        )

        assert content == "Article content here"
        assert image_url is None


class TestContentGeneratorAgent:
    """Test ContentGeneratorAgent"""

    def test_content_generator_init(self):
        """Test ContentGeneratorAgent initialization"""
        with patch("airopa_automation.agents.config") as mock_config:
            mock_config.content.output_dir = "/tmp/test_output"

            generator = ContentGeneratorAgent()

            assert generator.output_dir.exists()

    def test_generate_frontmatter(self):
        """Test frontmatter generation"""
        with patch("airopa_automation.agents.config") as mock_config:
            mock_config.content.output_dir = "/tmp/test_output"
            mock_config.content.default_author = "Test Author"
            mock_config.content.default_cover_image = "/test.jpg"

            generator = ContentGeneratorAgent()
            article = Article(
                title="Test Article",
                url="http://test.com",
                source="Test Source",
                content="Content",
                category="policy",
                published_date=datetime(2024, 1, 15),
            )

            frontmatter = generator._generate_frontmatter(article)

            assert "title:" in frontmatter
            assert "Test Article" in frontmatter
            assert "policy" in frontmatter
            assert "---" in frontmatter
