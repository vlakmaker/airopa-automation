from datetime import datetime, timedelta, timezone
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

        assert result.category == "industry"

    def test_classify_research_category(self):
        """Test classification of research-related content"""
        classifier = CategoryClassifierAgent()
        article = Article(
            title="New Research Paper on Neural Networks",
            url="http://test.com",
            source="Test",
            content="A breakthrough study in deep learning.",
        )

        result = classifier.classify(article)

        assert result.category == "research"

    def test_classify_industry_category(self):
        """Test classification of industry-related content"""
        classifier = CategoryClassifierAgent()
        article = Article(
            title="Tech Giant Deploys AI Platform",
            url="http://test.com",
            source="Test",
            content="A major technology deployment across the enterprise.",
        )

        result = classifier.classify(article)

        assert result.category == "industry"

    @patch("airopa_automation.agents.config")
    def test_classify_uses_keywords_when_llm_disabled(self, mock_config):
        """Test that classify uses keywords when LLM is disabled"""
        mock_config.ai.classification_enabled = False
        classifier = CategoryClassifierAgent()
        article = Article(
            title="Startup Raises Funding",
            url="http://test.com",
            source="Test",
            content="A startup company received investment.",
        )

        result = classifier.classify(article)

        assert result.category == "startups"

    @patch("airopa_automation.agents.config")
    @patch("airopa_automation.agents.CategoryClassifierAgent._classify_with_llm")
    def test_classify_shadow_mode_logs_llm_uses_keywords(self, mock_llm, mock_config):
        """Test shadow mode: runs LLM but applies keyword result"""
        mock_config.ai.classification_enabled = True
        mock_config.ai.shadow_mode = True

        mock_llm_result = MagicMock()
        mock_llm_result.category = "policy"
        mock_llm_result.country = "Germany"
        mock_llm_result.eu_relevance = 9.0
        mock_llm.return_value = mock_llm_result

        classifier = CategoryClassifierAgent()
        article = Article(
            title="Startup Raises Funding",
            url="http://test.com",
            source="Test",
            content="A startup company received investment.",
        )

        result = classifier.classify(article)

        # Shadow mode: keyword result is used, not LLM
        assert result.category == "startups"
        mock_llm.assert_called_once()

    @patch("airopa_automation.agents.config")
    @patch("airopa_automation.agents.CategoryClassifierAgent._classify_with_llm")
    def test_classify_live_mode_uses_llm(self, mock_llm, mock_config):
        """Test live mode: uses LLM result when valid"""
        mock_config.ai.classification_enabled = True
        mock_config.ai.shadow_mode = False

        mock_llm_result = MagicMock()
        mock_llm_result.valid = True
        mock_llm_result.category = "policy"
        mock_llm_result.country = "France"
        mock_llm_result.eu_relevance = 8.5
        mock_llm.return_value = mock_llm_result

        classifier = CategoryClassifierAgent()
        article = Article(
            title="Random Title",
            url="http://test.com",
            source="Test",
            content="Some content.",
        )

        result = classifier.classify(article)

        assert result.category == "policy"
        assert result.country == "France"
        assert result.eu_relevance == 8.5

    @patch("airopa_automation.agents.config")
    @patch("airopa_automation.agents.CategoryClassifierAgent._classify_with_llm")
    def test_classify_live_mode_fallback_on_invalid_llm(self, mock_llm, mock_config):
        """Test live mode: falls back to keywords when LLM returns invalid"""
        mock_config.ai.classification_enabled = True
        mock_config.ai.shadow_mode = False

        mock_llm_result = MagicMock()
        mock_llm_result.valid = False
        mock_llm.return_value = mock_llm_result

        classifier = CategoryClassifierAgent()
        article = Article(
            title="Startup Raises Funding",
            url="http://test.com",
            source="Test",
            content="A startup company received investment.",
        )

        result = classifier.classify(article)

        # Falls back to keyword classification
        assert result.category == "startups"

    @patch("airopa_automation.agents.config")
    @patch("airopa_automation.agents.CategoryClassifierAgent._classify_with_llm")
    def test_classify_live_mode_fallback_on_none(self, mock_llm, mock_config):
        """Test live mode: falls back to keywords when LLM returns None"""
        mock_config.ai.classification_enabled = True
        mock_config.ai.shadow_mode = False
        mock_llm.return_value = None

        classifier = CategoryClassifierAgent()
        article = Article(
            title="Government Policy Update",
            url="http://test.com",
            source="Test",
            content="New regulation proposed by government.",
        )

        result = classifier.classify(article)

        assert result.category == "policy"

    @patch("airopa_automation.llm.llm_complete")
    @patch("airopa_automation.agents.config")
    def test_classify_with_llm_success(self, mock_config, mock_llm_complete):
        """Test _classify_with_llm with successful LLM response"""
        mock_config.ai.classification_enabled = True
        mock_llm_complete.return_value = {
            "status": "ok",
            "text": '{"category": "research", "country": "Germany", "eu_relevance": 7}',
        }

        classifier = CategoryClassifierAgent()
        article = Article(
            title="AI Breakthrough",
            url="http://test.com",
            source="Test",
            content="A new research paper on transformers.",
        )

        result = classifier._classify_with_llm(article)

        assert result is not None
        assert result.valid is True
        assert result.category == "research"
        assert result.country == "Germany"
        assert result.eu_relevance == 7.0

    @patch("airopa_automation.llm.llm_complete")
    @patch("airopa_automation.agents.config")
    def test_classify_with_llm_api_error(self, mock_config, mock_llm_complete):
        """Test _classify_with_llm returns None on API error"""
        mock_config.ai.classification_enabled = True
        mock_llm_complete.return_value = {
            "status": "api_error",
            "text": "",
            "error": "Rate limited",
        }

        classifier = CategoryClassifierAgent()
        article = Article(
            title="Test",
            url="http://test.com",
            source="Test",
            content="Content.",
        )

        result = classifier._classify_with_llm(article)

        assert result is None

    @patch("airopa_automation.llm.llm_complete")
    @patch("airopa_automation.agents.config")
    def test_classify_with_llm_invalid_json(self, mock_config, mock_llm_complete):
        """Test _classify_with_llm returns None on invalid JSON from LLM"""
        mock_config.ai.classification_enabled = True
        mock_llm_complete.return_value = {
            "status": "ok",
            "text": "I think the category is startups",
        }

        classifier = CategoryClassifierAgent()
        article = Article(
            title="Test",
            url="http://test.com",
            source="Test",
            content="Content.",
        )

        result = classifier._classify_with_llm(article)

        assert result is None


class TestArticleEuRelevance:
    """Test eu_relevance field on Article model"""

    def test_eu_relevance_default(self):
        """Test eu_relevance defaults to 0.0"""
        article = Article(
            title="Test",
            url="http://test.com",
            source="Test",
            content="Content.",
        )
        assert article.eu_relevance == 0.0

    def test_eu_relevance_set(self):
        """Test eu_relevance can be set"""
        article = Article(
            title="Test",
            url="http://test.com",
            source="Test",
            content="Content.",
            eu_relevance=7.5,
        )
        assert article.eu_relevance == 7.5


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

    def test_normalize_source_name_known_duplicate(self):
        """Test source normalization maps known duplicates"""
        scraper = ScraperAgent()
        assert scraper._normalize_source_name("https://sifted.eu") == "Sifted"
        assert scraper._normalize_source_name("Deeptech - Tech.eu") == "Tech.eu"
        assert scraper._normalize_source_name("Robotics - Tech.eu") == "Tech.eu"

    def test_normalize_source_name_unknown_passthrough(self):
        """Test source normalization passes through unknown names"""
        scraper = ScraperAgent()
        assert scraper._normalize_source_name("Unknown Source") == "Unknown Source"

    def test_is_article_too_old_recent(self):
        """Test that recent articles are not filtered"""
        scraper = ScraperAgent()
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        assert scraper._is_article_too_old(recent) is False

    def test_is_article_too_old_stale(self):
        """Test that old articles are filtered"""
        scraper = ScraperAgent()
        old = datetime.now(timezone.utc) - timedelta(days=60)
        assert scraper._is_article_too_old(old) is True

    def test_is_article_too_old_none_date(self):
        """Test that articles with no date are not filtered"""
        scraper = ScraperAgent()
        assert scraper._is_article_too_old(None) is False

    def test_is_article_too_old_naive_datetime(self):
        """Test that naive datetime is handled correctly"""
        scraper = ScraperAgent()
        old_naive = datetime.now() - timedelta(days=60)
        assert scraper._is_article_too_old(old_naive) is True

    def test_is_article_too_old_boundary(self):
        """Test boundary: exactly at the max age limit"""
        scraper = ScraperAgent()
        boundary = datetime.now(timezone.utc) - timedelta(days=29)
        assert scraper._is_article_too_old(boundary) is False

    @patch("airopa_automation.agents.feedparser.parse")
    @patch("airopa_automation.agents.ScraperAgent._extract_article_data")
    def test_scrape_rss_feeds_normalizes_source(self, mock_extract, mock_parse):
        """Test that RSS scraping normalizes source names"""
        mock_extract.return_value = ("content", None)
        mock_feed = MagicMock()
        mock_feed.feed.get.return_value = "https://sifted.eu"
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key, default="": {
            "title": "Test",
            "link": "https://example.com/article",
            "summary": "",
            "published": "",
        }.get(key, default)
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed

        with patch("airopa_automation.agents.config") as mock_config:
            mock_config.scraper.rss_feeds = ["https://sifted.eu/feed"]
            mock_config.scraper.max_articles_per_source = 10
            mock_config.scraper.max_article_age_days = 30
            mock_config.scraper.rate_limit_delay = 0
            mock_config.scraper.user_agent = "Test"
            mock_config.scraper.source_name_map = {
                "https://sifted.eu": "Sifted",
            }

            scraper = ScraperAgent()
            articles = scraper.scrape_rss_feeds()

            assert len(articles) == 1
            assert articles[0].source == "Sifted"

    @patch("airopa_automation.agents.feedparser.parse")
    @patch("airopa_automation.agents.ScraperAgent._extract_article_data")
    def test_scrape_rss_feeds_skips_stale_articles(self, mock_extract, mock_parse):
        """Test that RSS scraping skips articles older than max age"""
        mock_extract.return_value = ("content", None)
        mock_feed = MagicMock()
        mock_feed.feed.get.return_value = "Test Source"

        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).strftime(
            "%a, %d %b %Y %H:%M:%S %z"
        )

        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key, default="": {
            "title": "Old Article",
            "link": "https://example.com/old",
            "summary": "",
            "published": old_date,
        }.get(key, default)
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed

        with patch("airopa_automation.agents.config") as mock_config:
            mock_config.scraper.rss_feeds = ["https://test.com/feed"]
            mock_config.scraper.max_articles_per_source = 10
            mock_config.scraper.max_article_age_days = 30
            mock_config.scraper.rate_limit_delay = 0
            mock_config.scraper.user_agent = "Test"
            mock_config.scraper.source_name_map = {}

            scraper = ScraperAgent()
            articles = scraper.scrape_rss_feeds()

            assert len(articles) == 0


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
