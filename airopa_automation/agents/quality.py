# AIropa Automation - Quality Score Agent

from .models import Article


class QualityScoreAgent:
    # Source credibility tiers
    TIER_1_SOURCES = {"Sifted", "Tech.eu", "EURACTIV", "AlgorithmWatch"}
    TIER_2_SOURCES = {
        "EuroNews",
        "The Parliament Magazine",
        "Science Business",
        "Innovation Origins",
        "TNW",
        "Politico Europe",
    }

    def __init__(self):
        pass

    def assess_quality(self, article: Article) -> Article:
        """Assess article quality using 5 weighted signals."""
        article.quality_score = min(self._calculate_rule_score(article), 1.0)
        return article

    def _calculate_rule_score(self, article: Article) -> float:
        """Calculate quality score from 5 signals (weights sum to 1.0)."""
        return (
            self._score_content_depth(article)
            + self._score_eu_relevance(article)
            + self._score_title_quality(article)
            + self._score_source_credibility(article)
            + self._score_metadata(article)
        )

    def _score_content_depth(self, article: Article) -> float:
        """Content depth signal (weight: 0.30)."""
        word_count = len(article.content.split())
        if word_count >= 800:
            return 0.30
        elif word_count >= 400:
            return 0.20
        elif word_count >= 200:
            return 0.10
        return 0.0

    def _score_eu_relevance(self, article: Article) -> float:
        """EU relevance signal (weight: 0.25)."""
        if article.eu_relevance >= 7:
            return 0.25
        elif article.eu_relevance >= 5:
            return 0.18
        elif article.eu_relevance >= 3:
            return 0.10
        return 0.0

    def _score_title_quality(self, article: Article) -> float:
        """Title quality signal (weight: 0.15)."""
        title_words = len(article.title.split())
        if 5 <= title_words <= 20:
            return 0.15
        elif 3 <= title_words <= 25:
            return 0.08
        return 0.0

    def _score_source_credibility(self, article: Article) -> float:
        """Source credibility signal (weight: 0.15)."""
        if article.source in self.TIER_1_SOURCES:
            return 0.15
        elif article.source in self.TIER_2_SOURCES:
            return 0.10
        return 0.05

    def _score_metadata(self, article: Article) -> float:
        """Metadata completeness signal (weight: 0.15)."""
        score = 0.0
        if article.category:
            score += 0.05
        if article.country:
            score += 0.05
        if article.summary:
            score += 0.05
        return score
