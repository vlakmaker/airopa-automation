from airopa_automation.llm_schemas import (
    VALID_CATEGORIES,
    ClassificationResult,
    SummaryResult,
    parse_classification,
    parse_summary,
    validate_classification,
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

    def test_confidence_parsed(self):
        """Test confidence is parsed from response"""
        result = parse_classification(
            '{"category": "startups", "country": "Germany",'
            ' "eu_relevance": 8, "confidence": 0.85}'
        )
        assert result.valid is True
        assert result.confidence == 0.85

    def test_confidence_missing_defaults_zero(self):
        """Test missing confidence defaults to 0"""
        result = parse_classification(
            '{"category": "startups", "country": "Germany", "eu_relevance": 8}'
        )
        assert result.valid is True
        assert result.confidence == 0.0

    def test_confidence_clamped(self):
        """Test confidence is clamped to 0-1"""
        result = parse_classification(
            '{"category": "startups", "country": "Germany",'
            ' "eu_relevance": 8, "confidence": 1.5}'
        )
        assert result.confidence == 1.0

    def test_other_category_accepted(self):
        """Test that 'other' is a valid category"""
        result = parse_classification(
            '{"category": "other", "country": "", "eu_relevance": 0, "confidence": 0.9}'
        )
        assert result.valid is True
        assert result.category == "other"


class TestValidateClassification:
    """Test post-validation rules"""

    def test_low_confidence_demoted(self):
        """Test low confidence demotes to other"""
        r = ClassificationResult("startups", "Germany", 8.0, confidence=0.3)
        result = validate_classification(r)
        assert result.category == "other"
        assert result.eu_relevance == 0.0

    def test_adequate_confidence_kept(self):
        """Test adequate confidence is kept"""
        r = ClassificationResult("startups", "Germany", 8.0, confidence=0.7)
        result = validate_classification(r)
        assert result.category == "startups"

    def test_low_eu_relevance_demoted(self):
        """Test very low EU relevance demotes to other"""
        r = ClassificationResult("industry", "", 1.0, confidence=0.8)
        result = validate_classification(r)
        assert result.category == "other"
        assert result.eu_relevance == 0.0

    def test_other_forces_zero_eu_relevance(self):
        """Test 'other' category forces eu_relevance to 0"""
        r = ClassificationResult("other", "", 5.0, confidence=0.9)
        result = validate_classification(r)
        assert result.category == "other"
        assert result.eu_relevance == 0.0

    def test_invalid_result_passthrough(self):
        """Test invalid result passes through unchanged"""
        r = ClassificationResult("", "", 0.0, valid=False, fallback_reason="test")
        result = validate_classification(r)
        assert result.valid is False


class TestClassificationResult:
    """Test ClassificationResult dataclass"""

    def test_default_valid(self):
        """Test default valid state"""
        r = ClassificationResult("startups", "Germany", 8.0)
        assert r.valid is True
        assert r.fallback_reason == ""
        assert r.confidence == 0.0

    def test_invalid_with_reason(self):
        """Test invalid state with reason"""
        r = ClassificationResult("", "", 0.0, valid=False, fallback_reason="test")
        assert r.valid is False
        assert r.fallback_reason == "test"


class TestParseSummary:
    """Test LLM summary response parsing"""

    def test_valid_two_sentence_summary(self):
        """Test valid 2-sentence summary"""
        result = parse_summary(
            "The startup raised €10M for AI innovation. "
            "This is significant for European deep tech."
        )
        assert result.valid is True
        assert "startup raised" in result.text

    def test_valid_three_sentence_summary(self):
        """Test valid 3-sentence summary"""
        result = parse_summary(
            "Company X launched a new product. "
            "It targets the European market. "
            "The funding round was led by a Berlin-based VC."
        )
        assert result.valid is True

    def test_empty_string_rejected(self):
        """Test empty string triggers fallback"""
        result = parse_summary("")
        assert result.valid is False
        assert result.fallback_reason == "empty_summary"

    def test_whitespace_only_rejected(self):
        """Test whitespace-only triggers fallback"""
        result = parse_summary("   ")
        assert result.valid is False
        assert result.fallback_reason == "empty_summary"

    def test_none_rejected(self):
        """Test None triggers fallback"""
        result = parse_summary(None)
        assert result.valid is False
        assert result.fallback_reason == "empty_summary"

    def test_markdown_heading_rejected(self):
        """Test markdown headings are rejected"""
        result = parse_summary("## Summary\nThe startup raised funding.")
        assert result.valid is False
        assert result.fallback_reason == "contains_formatting"

    def test_markdown_bold_rejected(self):
        """Test markdown bold is rejected"""
        result = parse_summary("The **startup** raised funding.")
        assert result.valid is False
        assert result.fallback_reason == "contains_formatting"

    def test_html_tags_rejected(self):
        """Test HTML tags are rejected"""
        result = parse_summary("<p>The startup raised funding.</p>")
        assert result.valid is False
        assert result.fallback_reason == "contains_formatting"

    def test_too_many_sentences_rejected(self):
        """Test summaries with >5 sentences are rejected"""
        text = ". ".join([f"Sentence {i}" for i in range(7)]) + "."
        result = parse_summary(text)
        assert result.valid is False
        assert result.fallback_reason == "too_long"

    def test_strips_wrapping_quotes(self):
        """Test that wrapping quotes are stripped"""
        result = parse_summary('"A valid summary sentence."')
        assert result.valid is True
        assert result.text == "A valid summary sentence."

    def test_single_sentence_valid(self):
        """Test single sentence is valid"""
        result = parse_summary("The EU AI Act was approved.")
        assert result.valid is True

    def test_not_relevant_signal(self):
        """Test NOT_RELEVANT signal is accepted"""
        result = parse_summary("NOT_RELEVANT")
        assert result.valid is True
        assert result.text == "NOT_RELEVANT"

    def test_not_relevant_case_insensitive(self):
        """Test NOT_RELEVANT is case-insensitive"""
        result = parse_summary("Not Relevant")
        assert result.valid is True
        assert result.text == "NOT_RELEVANT"


class TestSummaryResult:
    """Test SummaryResult dataclass"""

    def test_default_valid(self):
        """Test default valid state"""
        r = SummaryResult(text="A summary.", valid=True)
        assert r.valid is True
        assert r.text == "A summary."

    def test_invalid_with_reason(self):
        """Test invalid state with reason"""
        r = SummaryResult(valid=False, fallback_reason="empty_summary")
        assert r.valid is False
        assert r.fallback_reason == "empty_summary"
