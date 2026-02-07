"""
LLM response schema validation.

Parses and validates JSON responses from LLM classification and
summarization calls. Returns typed results with safe defaults on
validation failure.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"startups", "policy", "research", "industry"}


class ClassificationResult:
    """Validated classification result from LLM."""

    def __init__(
        self,
        category: str,
        country: str,
        eu_relevance: float,
        valid: bool = True,
        fallback_reason: str = "",
    ):
        self.category = category
        self.country = country
        self.eu_relevance = eu_relevance
        self.valid = valid
        self.fallback_reason = fallback_reason


def parse_classification(raw_text: str) -> ClassificationResult:  # noqa: C901
    """Parse and validate LLM classification JSON response.

    Expected format:
        {"category": "startups", "country": "Germany", "eu_relevance": 8}

    Validation rules:
        - category must be one of VALID_CATEGORIES
        - eu_relevance is clamped to 0-10
        - country defaults to "" if missing

    Args:
        raw_text: Raw LLM response text (should be JSON).

    Returns:
        ClassificationResult with valid=True on success,
        or valid=False with fallback_reason on failure.
    """
    if not raw_text or not raw_text.strip():
        return _fallback("empty_response")

    # Strip markdown code fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("LLM response is not valid JSON: %s", e)
        return _fallback(f"json_parse_error: {e}")

    if not isinstance(data, dict):
        return _fallback("response_not_dict")

    # Validate category
    category = data.get("category", "")
    if not isinstance(category, str):
        return _fallback(f"category_not_string: {type(category)}")
    category = category.strip().lower()
    if category not in VALID_CATEGORIES:
        return _fallback(f"invalid_category: {category}")

    # Validate and clamp eu_relevance
    eu_relevance = data.get("eu_relevance", 0)
    try:
        eu_relevance = float(eu_relevance)
    except (TypeError, ValueError):
        eu_relevance = 0.0
    eu_relevance = max(0.0, min(10.0, eu_relevance))

    # Country — optional, default to empty string
    country = data.get("country", "")
    if not isinstance(country, str):
        country = ""
    country = country.strip()

    return ClassificationResult(
        category=category,
        country=country,
        eu_relevance=eu_relevance,
    )


def _fallback(reason: str) -> ClassificationResult:
    """Return an invalid result that signals the caller to use keyword fallback."""
    logger.warning("Classification validation failed: %s", reason)
    return ClassificationResult(
        category="",
        country="",
        eu_relevance=0.0,
        valid=False,
        fallback_reason=reason,
    )


# --- Summary validation ---


class SummaryResult:
    """Validated summary result from LLM."""

    def __init__(
        self,
        text: str = "",
        valid: bool = True,
        fallback_reason: str = "",
    ):
        self.text = text
        self.valid = valid
        self.fallback_reason = fallback_reason


def parse_summary(raw_text: str) -> SummaryResult:
    """Parse and validate LLM summary response.

    Validation rules:
        - Non-empty after stripping
        - No markdown (headings, bold, links) or HTML tags
        - Between 1 and 5 sentences
    """
    if not raw_text or not raw_text.strip():
        return SummaryResult(valid=False, fallback_reason="empty_summary")

    text = raw_text.strip()

    # Strip wrapping quotes if present
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1].strip()

    if not text:
        return SummaryResult(valid=False, fallback_reason="empty_summary")

    # Reject markdown formatting
    if re.search(r"^#{1,6}\s", text, re.MULTILINE) or "**" in text:
        return SummaryResult(valid=False, fallback_reason="contains_formatting")

    # Reject HTML tags
    if re.search(r"<[a-zA-Z/][^>]*>", text):
        return SummaryResult(valid=False, fallback_reason="contains_formatting")

    # Count sentences (period/exclamation/question followed by space or end)
    sentences = re.split(r"[.!?](?:\s|$)", text)
    # Filter out empty fragments
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) < 1:
        return SummaryResult(valid=False, fallback_reason="too_short")
    if len(sentences) > 5:
        return SummaryResult(valid=False, fallback_reason="too_long")

    return SummaryResult(text=text, valid=True)
