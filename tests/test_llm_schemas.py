from airopa_automation.llm_schemas import (
    VALID_CATEGORIES,
    ClassificationResult,
    parse_classification,
)


class TestParseClassification:
    """Test LLM classification response parsing"""

    def test_valid_response(self):
        """Test parsing a valid classification JSON"""
        result = parse_classification(
            '{"category": "startups", "country": "Germany", "eu_relevance": 8}'
        )
        assert result.valid is True
        assert result.category == "startups"
        assert result.country == "Germany"
        assert result.eu_relevance == 8.0

    def test_all_valid_categories(self):
        """Test all valid categories are accepted"""
        for cat in VALID_CATEGORIES:
            result = parse_classification(
                f'{{"category": "{cat}", "country": "Europe", "eu_relevance": 5}}'
            )
            assert result.valid is True
            assert result.category == cat

    def test_invalid_category(self):
        """Test invalid category triggers fallback"""
        result = parse_classification(
            '{"category": "country", "country": "France", "eu_relevance": 7}'
        )
        assert result.valid is False
        assert "invalid_category" in result.fallback_reason

    def test_empty_response(self):
        """Test empty string triggers fallback"""
        result = parse_classification("")
        assert result.valid is False
        assert "empty_response" in result.fallback_reason

    def test_none_like_response(self):
        """Test whitespace-only triggers fallback"""
        result = parse_classification("   ")
        assert result.valid is False

    def test_malformed_json(self):
        """Test malformed JSON triggers fallback"""
        result = parse_classification("not json at all")
        assert result.valid is False
        assert "json_parse_error" in result.fallback_reason

    def test_json_with_markdown_fences(self):
        """Test JSON wrapped in markdown code fences"""
        result = parse_classification(
            '```json\n{"category": "policy", "country": "EU", "eu_relevance": 9}\n```'
        )
        assert result.valid is True
        assert result.category == "policy"
        assert result.country == "EU"

    def test_eu_relevance_clamped_high(self):
        """Test eu_relevance > 10 is clamped to 10"""
        result = parse_classification(
            '{"category": "research", "country": "Europe", "eu_relevance": 15}'
        )
        assert result.valid is True
        assert result.eu_relevance == 10.0

    def test_eu_relevance_clamped_low(self):
        """Test eu_relevance < 0 is clamped to 0"""
        result = parse_classification(
            '{"category": "industry", "country": "US", "eu_relevance": -3}'
        )
        assert result.valid is True
        assert result.eu_relevance == 0.0

    def test_eu_relevance_non_numeric(self):
        """Test non-numeric eu_relevance defaults to 0"""
        result = parse_classification(
            '{"category": "startups", "country": "Germany", "eu_relevance": "high"}'
        )
        assert result.valid is True
        assert result.eu_relevance == 0.0

    def test_missing_country_defaults_empty(self):
        """Test missing country field defaults to empty string"""
        result = parse_classification('{"category": "policy", "eu_relevance": 6}')
        assert result.valid is True
        assert result.country == ""

    def test_missing_eu_relevance_defaults_zero(self):
        """Test missing eu_relevance defaults to 0"""
        result = parse_classification('{"category": "research", "country": "France"}')
        assert result.valid is True
        assert result.eu_relevance == 0.0

    def test_category_case_insensitive(self):
        """Test category matching is case-insensitive"""
        result = parse_classification(
            '{"category": "STARTUPS", "country": "Germany", "eu_relevance": 7}'
        )
        assert result.valid is True
        assert result.category == "startups"

    def test_category_with_whitespace(self):
        """Test category with whitespace is trimmed"""
        result = parse_classification(
            '{"category": " policy ", "country": "EU", "eu_relevance": 8}'
        )
        assert result.valid is True
        assert result.category == "policy"

    def test_response_not_dict(self):
        """Test non-dict JSON triggers fallback"""
        result = parse_classification('["startups", "Germany", 8]')
        assert result.valid is False
        assert "response_not_dict" in result.fallback_reason

    def test_country_non_string(self):
        """Test non-string country defaults to empty"""
        result = parse_classification(
            '{"category": "startups", "country": 42, "eu_relevance": 5}'
        )
        assert result.valid is True
        assert result.country == ""


class TestClassificationResult:
    """Test ClassificationResult dataclass"""

    def test_default_valid(self):
        """Test default valid state"""
        r = ClassificationResult("startups", "Germany", 8.0)
        assert r.valid is True
        assert r.fallback_reason == ""

    def test_invalid_with_reason(self):
        """Test invalid state with reason"""
        r = ClassificationResult("", "", 0.0, valid=False, fallback_reason="test")
        assert r.valid is False
        assert r.fallback_reason == "test"
