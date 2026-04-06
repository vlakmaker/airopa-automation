# AIropa Automation - Classification Agent

import logging

from airopa_automation.config import config

from .models import Article, clean_content

logger = logging.getLogger(__name__)


class CategoryClassifierAgent:
    CLASSIFICATION_PROMPT = """You are an editorial classifier for AIropa, \
a European AI and technology news platform.

Your job is to classify articles AND filter out irrelevant content.

STEP 1: RELEVANCE CHECK
Is this article PRIMARILY about AI, machine learning, tech startups, EU tech policy,
or digital innovation? General business, politics, lifestyle, or science articles
that merely MENTION technology are NOT relevant.
If NO -> set category to "other", country to "", eu_relevance to 0, confidence to 0.9.

STEP 2: CLASSIFY into exactly ONE category based on the PRIMARY focus:
- startups: Funding rounds, product launches, acquisitions, founder stories
- policy: Regulation, government policy, AI ethics, governance, legal frameworks
- research: Academic papers, technical breakthroughs, new models, benchmarks
- industry: Enterprise adoption, corporate partnerships, market analysis, big tech moves
- other: Not relevant to AI/tech (lifestyle, psychology, generic business)

Tiebreaker rules:
- Regulation affecting startups -> "policy" (the regulation is the news)
- New model from a startup -> "startups" (funding/company is the angle)
- New model from a research lab -> "research" (the science is the angle)
- Technical blog post / tutorial -> "research"

STEP 3: EUROPEAN RELEVANCE (0-10)
- 8-10: European company, EU policy, European research lab
- 5-7: Global story with meaningful European angle
- 2-4: Primarily US/global story with minor European mention
- 0-1: No European connection at all
Be strict. A US company story reported by a European outlet is NOT European news.

STEP 4: COUNTRY
Use full country name: "France", "Germany", "Netherlands", etc.
Use "Europe" ONLY if genuinely pan-European (EU-wide policy, multi-country).
Use "" (empty) if not European.

STEP 5: CONFIDENCE (0.0-1.0)
Rate your confidence in this classification.

EXAMPLES:
Source: Sifted
Title: "French AI startup Mistral raises EUR 400M Series B"
{{"category": "startups", "country": "France", "eu_relevance": 9, "confidence": 0.95}}

Title: "EU AI Act enforcement timeline announced"
{{"category": "policy", "country": "Europe", "eu_relevance": 10, "confidence": 0.95}}

Title: "OpenAI launches GPT-5 with improved reasoning"
{{"category": "industry", "country": "", "eu_relevance": 1, "confidence": 0.9}}

Title: "Psychology says people who enjoy grocery shopping alone possess these traits"
{{"category": "other", "country": "", "eu_relevance": 0, "confidence": 0.95}}

Source: {source}
Title: {title}
Content: {content}

Respond in JSON only:
{{"category": "...", "country": "...", "eu_relevance": N, "confidence": N.N}}"""

    PROMPT_VERSION = "classification_v3"

    def __init__(self):
        self.last_telemetry = None  # Telemetry from most recent classify call

    def classify(self, article: Article) -> Article:
        """Classify article using LLM if enabled, with keyword fallback.

        Behavior depends on feature flags:
        - classification_enabled=False: keywords only (current default)
        - classification_enabled=True, shadow_mode=True: run both,
          log LLM result, apply keyword result to article
        - classification_enabled=True, shadow_mode=False: use LLM result,
          fall back to keywords on failure

        After calling, check self.last_telemetry for LLM call details.
        """
        self.last_telemetry = None

        if not config.ai.classification_enabled:
            return self._classify_with_keywords(article)

        llm_result = self._classify_with_llm(article)

        if config.ai.shadow_mode:
            # Shadow mode: log LLM result but keep keyword output
            if llm_result:
                logger.info(
                    "Shadow classification for '%s': "
                    "llm=%s/%s/eu%.1f, using keywords instead",
                    article.title[:60],
                    llm_result.category,
                    llm_result.country,
                    llm_result.eu_relevance,
                )
            return self._classify_with_keywords(article)

        # Live mode: use LLM result, fall back to keywords
        if llm_result and llm_result.valid:
            article.category = llm_result.category
            article.country = llm_result.country
            article.eu_relevance = llm_result.eu_relevance
            article.confidence = llm_result.confidence
            return article

        logger.warning(
            "LLM classification failed for '%s', falling back to keywords",
            article.title[:60],
        )
        return self._classify_with_keywords(article)

    def _classify_with_llm(self, article: Article):
        """Classify article using LLM. Returns ClassificationResult or None.

        Sets self.last_telemetry with LLM call details.
        """
        from airopa_automation.llm import llm_complete
        from airopa_automation.llm_schemas import (
            parse_classification,
            validate_classification,
        )

        prompt = self.CLASSIFICATION_PROMPT.format(
            title=article.title,
            content=clean_content(article.content)[:1500],
            source=article.source,
        )

        result = llm_complete(prompt)

        # Build telemetry dict for persistence
        self.last_telemetry = {
            "article_url": article.url,
            "llm_model": result.get("model", ""),
            "prompt_version": self.PROMPT_VERSION,
            "llm_latency_ms": result.get("latency_ms", 0),
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
            "llm_status": result.get("status", "unknown"),
            "fallback_reason": None,
        }

        if result["status"] != "ok":
            self.last_telemetry[
                "fallback_reason"
            ] = f"{result['status']}: {result.get('error', '')}"
            logger.warning(
                "LLM call failed for '%s': %s - %s",
                article.title[:60],
                result["status"],
                result["error"],
            )
            return None

        parsed = parse_classification(result["text"])

        if not parsed.valid:
            self.last_telemetry["llm_status"] = "parse_error"
            self.last_telemetry["fallback_reason"] = parsed.fallback_reason
            logger.warning(
                "LLM response validation failed for '%s': %s",
                article.title[:60],
                parsed.fallback_reason,
            )
            return None

        # Apply post-validation business rules
        parsed = validate_classification(parsed, article.title)

        return parsed

    # Sources known to focus on European tech/policy
    _EU_SOURCES = {
        "Sifted",
        "Tech.eu",
        "EURACTIV",
        "EuroNews",
        "AlgorithmWatch",
        "The Parliament Magazine",
        "Science Business",
        "Innovation Origins",
        "Politico Europe",
        "TNW",
    }

    # Keywords that signal European relevance in title or content
    _EU_KEYWORDS = [
        "europe",
        "european",
        " eu ",
        "eu's",
        "brussels",
        "gdpr",
        "ai act",
        "digital markets act",
        "digital services act",
        "france",
        "french",
        "germany",
        "german",
        "netherlands",
        "dutch",
        "spain",
        "spanish",
        "italy",
        "italian",
        "sweden",
        "swedish",
        "denmark",
        "danish",
        "finland",
        "finnish",
        "ireland",
        "irish",
        "poland",
        "polish",
        "austria",
        "austrian",
        "belgium",
        "belgian",
        "portugal",
        "portuguese",
        "czech",
        "romania",
        "romanian",
        "hungary",
        "hungarian",
        "greece",
        "greek",
        "estonia",
        "estonian",
        "latvia",
        "latvian",
        "lithuania",
        "lithuanian",
        "croatia",
        "croatian",
        "slovenia",
        "slovenian",
        "slovakia",
        "slovak",
        "bulgaria",
        "bulgarian",
        "cyprus",
        "malta",
        "luxembourg",
    ]

    # Strong keywords: a single match is enough to pass the relevance gate.
    # These are unambiguously about AI, tech, or digital innovation.
    _TECH_KEYWORDS_STRONG = [
        # AI / Machine Learning
        "artificial intelligence",
        " ai ",
        "ai-",
        "machine learning",
        "deep learning",
        "neural network",
        "large language model",
        " llm",
        "generative ai",
        "chatgpt",
        "openai",
        "gpt-",
        "transformer model",
        "natural language processing",
        " nlp ",
        "computer vision",
        "reinforcement learning",
        "diffusion model",
        # Core tech
        "semiconductor",
        "microchip",
        "quantum computing",
        "cloud computing",
        "cybersecurity",
        "cyber security",
        "blockchain",
        "cryptocurrency",
        "saas",
        "robotics",
        "self-driving",
        # Startups / Digital business
        "startup",
        "start-up",
        "venture capital",
        "seed round",
        "series a",
        "series b",
        "series c",
        "fintech",
        "healthtech",
        "edtech",
        "proptech",
        "deeptech",
        "agritech",
        "insurtech",
        "neobank",
        # Digital innovation
        "digital innovation",
        "digital transformation",
        "data science",
        "open source",
        "open-source",
        # Tech policy
        "ai act",
        "ai regulation",
        "digital markets act",
        "digital services act",
        "tech regulation",
        "data protection",
        "gdpr",
        "ai ethics",
        "ai governance",
        "ai safety",
    ]

    # Weak keywords: need 2+ matches to pass the relevance gate.
    # These are common in tech articles but also appear in non-tech contexts
    # (e.g. "platform" in politics, "automation" in manufacturing).
    _TECH_KEYWORDS_WEAK = [
        "technology",
        " tech ",
        "software",
        "hardware",
        " chip ",
        "platform",
        "algorithm",
        "automation",
        " robot ",
        "autonomous",
        "biotech",
        "cleantech",
        "unicorn",
        "big data",
        "api ",
        "developer",
        "coding",
        "programming",
    ]

    # Country detection: maps keywords to country names.
    # Checked in order; first match wins. "Europe" is last (catch-all).
    _COUNTRY_SIGNALS = [
        (["france", "french", "paris"], "France"),
        (["germany", "german", "berlin", "munich"], "Germany"),
        (["netherlands", "dutch", "amsterdam"], "Netherlands"),
        (["spain", "spanish", "madrid", "barcelona"], "Spain"),
        (["italy", "italian", "rome", "milan"], "Italy"),
        (["sweden", "swedish", "stockholm"], "Sweden"),
        (["denmark", "danish", "copenhagen"], "Denmark"),
        (["finland", "finnish", "helsinki"], "Finland"),
        (["ireland", "irish", "dublin"], "Ireland"),
        (["poland", "polish", "warsaw"], "Poland"),
        (["austria", "austrian", "vienna"], "Austria"),
        (["belgium", "belgian"], "Belgium"),
        (["portugal", "portuguese", "lisbon"], "Portugal"),
        (["czech", "prague"], "Czech Republic"),
        (["romania", "romanian", "bucharest"], "Romania"),
        (["hungary", "hungarian", "budapest"], "Hungary"),
        (["greece", "greek", "athens"], "Greece"),
        (["estonia", "estonian", "tallinn"], "Estonia"),
        (["latvia", "latvian", "riga"], "Latvia"),
        (["lithuania", "lithuanian", "vilnius"], "Lithuania"),
        (["croatia", "croatian", "zagreb"], "Croatia"),
        (["slovenia", "slovenian", "ljubljana"], "Slovenia"),
        (["slovakia", "slovak", "bratislava"], "Slovakia"),
        (["bulgaria", "bulgarian", "sofia"], "Bulgaria"),
        (
            [
                "luxembourg",
            ],
            "Luxembourg",
        ),
        (
            [
                "malta",
            ],
            "Malta",
        ),
        (
            [
                "cyprus",
            ],
            "Cyprus",
        ),
    ]

    @classmethod
    def _detect_country(cls, title_lower: str, content_lower: str) -> str:
        """Detect the primary country from title and content keywords.

        Returns the country name, "Europe" for pan-European content,
        or "" if no country is identified.
        """
        combined = f"{title_lower} {content_lower}"
        for keywords, country in cls._COUNTRY_SIGNALS:
            if any(kw in combined for kw in keywords):
                return country
        # Pan-European catch-all
        if "europe" in combined or "european" in combined or " eu " in f" {combined} ":
            return "Europe"
        return ""

    def _is_tech_relevant(self, combined_text: str) -> bool:
        """Check whether text contains AI/tech relevance keywords.

        Uses a two-tier system:
        - Strong keywords (e.g. "machine learning"): one match is enough
        - Weak keywords (e.g. "platform", "automation"): need 2+ matches

        This prevents generic business articles that mention "platform" or
        "technology" once from passing the gate.

        Args:
            combined_text: Lowercased, space-padded title + content.

        Returns:
            True if the article is about AI/tech.
        """
        if any(kw in combined_text for kw in self._TECH_KEYWORDS_STRONG):
            return True
        weak_hits = sum(1 for kw in self._TECH_KEYWORDS_WEAK if kw in combined_text)
        return weak_hits >= 2

    def _classify_with_keywords(self, article: Article) -> Article:
        """Keyword-based classification fallback.

        Sets category, country, eu_relevance, and confidence based on
        keyword signals. EU relevance is estimated from source credibility
        and keyword density so that articles are not silently filtered
        downstream by the eu_relevance threshold.

        Includes a tech/AI relevance gate: articles that contain no
        AI or technology keywords are classified as "other" so they are
        filtered out by the API layer.
        """
        title_lower = article.title.lower()
        content_lower = article.content.lower()
        combined = f" {title_lower} {content_lower} "

        # --- STEP 0: Tech/AI relevance gate ---
        # Check whether the article is about AI, tech, or digital innovation.
        # If none of the relevance keywords appear, classify as "other".
        if not self._is_tech_relevant(combined):
            article.category = "other"
            article.country = ""
            article.eu_relevance = 0.0
            article.confidence = 0.7
            return article

        # Category classification
        if any(
            keyword in title_lower or keyword in content_lower
            for keyword in ["startup", "company", "funding", "investment"]
        ):
            article.category = "startups"
        elif any(
            keyword in title_lower or keyword in content_lower
            for keyword in ["policy", "regulation", "law", "act", "government"]
        ):
            article.category = "policy"
        elif any(
            keyword in title_lower or keyword in content_lower
            for keyword in ["research", "paper", "study", "breakthrough"]
        ):
            article.category = "research"
        else:
            article.category = "industry"

        # Country classification
        article.country = self._detect_country(title_lower, content_lower)

        # --- EU relevance estimation (keyword heuristic) ---
        eu_score = 0.0

        # Signal 1: EU keywords in title (+2.0 each, max +4.0)
        title_hits = sum(1 for kw in self._EU_KEYWORDS if kw in f" {title_lower} ")
        eu_score += min(title_hits * 2.0, 4.0)

        # Signal 2: EU keywords in content (+0.5 each, max +3.0)
        content_hits = sum(1 for kw in self._EU_KEYWORDS if kw in combined)
        # Subtract title hits to avoid double-counting
        content_only_hits = max(content_hits - title_hits, 0)
        eu_score += min(content_only_hits * 0.5, 3.0)

        # Signal 3: Source is a known European outlet (+2.0)
        # Only applies when the article also has EU keyword signals,
        # so a US story published by a EU outlet doesn't inflate the score.
        has_eu_keywords = title_hits > 0 or content_only_hits > 0
        if article.source in self._EU_SOURCES and has_eu_keywords:
            eu_score += 2.0

        # Signal 4: Country was identified (+1.0)
        if article.country:
            eu_score += 1.0

        article.eu_relevance = min(eu_score, 10.0)

        # Confidence: keyword classification is inherently less certain
        # than LLM. Use 0.6 as a baseline — high enough to pass the
        # confidence > 0.5 gate in validate_classification, low enough
        # to signal this is a heuristic result.
        article.confidence = 0.6

        return article
