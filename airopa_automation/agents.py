# AIropa Automation Agents - Base Classes

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle
from pydantic import BaseModel
from slugify import slugify

from airopa_automation.config import config

logger = logging.getLogger(__name__)


def clean_content(raw: str) -> str:
    """Strip residual HTML tags and collapse whitespace.

    Uses BeautifulSoup to extract text from any HTML fragments
    left by newspaper3k extraction or RSS feed descriptions.
    """
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r"https?://\S+\.(jpg|jpeg|png|gif|webp|svg)\S*", "", text)
    cleaned: str = " ".join(text.split())
    return cleaned.strip()


class Article(BaseModel):
    title: str
    url: str
    source: str
    content: str
    summary: str = ""
    published_date: Optional[datetime] = None
    scraped_date: datetime = datetime.now()
    category: str = ""
    country: str = ""
    quality_score: float = 0.0
    eu_relevance: float = 0.0
    confidence: float = 0.0
    image_url: Optional[str] = None

    def generate_hash(self) -> str:
        """Generate a unique hash for this article"""
        hash_input = f"{self.title}{self.url}{self.source}".encode("utf-8")
        return hashlib.sha256(hash_input).hexdigest()


class ScraperAgent:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.scraper.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",  # noqa: E501
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    def _normalize_source_name(self, raw_source: str) -> str:
        """Normalize source name using config mapping.

        Deduplicates sources like "https://sifted.eu" and "Sifted" into
        a single canonical name.
        """
        return config.scraper.source_name_map.get(raw_source, raw_source)

    def _is_article_too_old(self, published_date: Optional[datetime]) -> bool:
        """Check if article is older than the configured max age.

        Returns True if the article should be skipped.
        Articles with no published_date are NOT skipped (we can't tell).
        """
        if not published_date:
            return False
        max_age = timedelta(days=config.scraper.max_article_age_days)
        now = datetime.now(timezone.utc)
        # Make published_date offset-aware if it's naive
        if published_date.tzinfo is None:
            published_date = published_date.replace(tzinfo=timezone.utc)
        return (now - published_date) > max_age

    def scrape_rss_feeds(self) -> List[Article]:
        """Scrape articles from RSS feeds"""
        articles = []

        for feed_url in config.scraper.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                raw_source = feed.feed.get("title", feed_url)
                source_name = self._normalize_source_name(raw_source)

                for entry in feed.entries[: config.scraper.max_articles_per_source]:
                    try:
                        published_date = self._parse_date(entry.get("published", ""))

                        # Skip stale articles
                        if self._is_article_too_old(published_date):
                            logger.info(
                                "Skipping stale article: %s (published %s)",
                                entry.get("title", "unknown"),
                                published_date,
                            )
                            continue

                        content, image_url = self._extract_article_data(
                            entry.get("link", "")
                        )

                        # Fallback: check RSS media:content and enclosures for image
                        if not image_url:
                            image_url = self._extract_rss_image(entry)

                        article = Article(
                            title=entry.get("title", "No title"),
                            url=entry.get("link", ""),
                            source=source_name,
                            content=content,
                            summary=entry.get("summary", ""),
                            published_date=published_date,
                            scraped_date=datetime.now(),
                            image_url=image_url,
                        )
                        articles.append(article)

                        # Rate limiting
                        time.sleep(config.scraper.rate_limit_delay)

                    except Exception as e:
                        print(
                            f"Error processing RSS entry {entry.get('title', 'unknown')}: {e}"  # noqa: E501
                        )
                        continue

            except Exception as e:
                print(f"Error scraping RSS feed {feed_url}: {e}")
                continue

        return articles

    def scrape_web_sources(self) -> List[Article]:
        """Scrape articles from web sources"""
        articles = []

        for source_url in config.scraper.web_sources:
            try:
                response = self.session.get(source_url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                article_links = self._extract_article_links(soup, source_url)

                for link in article_links[: config.scraper.max_articles_per_source]:
                    try:
                        article = self._scrape_article_page(link, source_url)
                        if article:
                            articles.append(article)

                        # Rate limiting
                        time.sleep(config.scraper.rate_limit_delay)

                    except Exception as e:
                        print(f"Error scraping article {link}: {e}")
                        continue

            except Exception as e:
                print(f"Error accessing web source {source_url}: {e}")
                continue

        return articles

    def _extract_article_links(self, soup: BeautifulSoup, source_url: str) -> List[str]:
        """Extract article links from a webpage"""
        links = []

        # Look for common article link patterns
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(
                keyword in href.lower()
                for keyword in ["article", "news", "post", "blog"]
            ):
                if href.startswith("http"):
                    links.append(href)
                else:
                    # Handle relative URLs
                    from urllib.parse import urljoin

                    links.append(urljoin(source_url, href))

        return list(set(links))  # Remove duplicates

    def _scrape_article_page(self, url: str, source: str) -> Optional[Article]:
        """Scrape content from a single article page"""
        try:
            # Use newspaper3k for article extraction
            newspaper_article = NewspaperArticle(url)
            newspaper_article.download()
            newspaper_article.parse()

            image_url = self._validate_image_url(newspaper_article.top_image)

            return Article(
                title=newspaper_article.title,
                url=url,
                source=source,
                content=newspaper_article.text,
                summary=newspaper_article.summary,
                published_date=newspaper_article.publish_date,
                scraped_date=datetime.now(),
                image_url=image_url,
            )

        except Exception as e:
            print(f"Error scraping article page {url}: {e}")
            return None

    def _extract_article_data(self, url: str) -> tuple[str, Optional[str]]:
        """Extract content and image URL from an article URL.

        Returns:
            Tuple of (article_text, image_url). image_url may be None.
        """
        try:
            newspaper_article = NewspaperArticle(url)
            newspaper_article.download()
            newspaper_article.parse()
            image_url = self._validate_image_url(newspaper_article.top_image)
            return str(newspaper_article.text), image_url
        except Exception as e:
            print(f"Error extracting content from {url}: {e}")
            return "", None

    def _validate_image_url(self, url: Optional[str]) -> Optional[str]:
        """Validate and sanitize an image URL.

        Returns the URL if valid, None otherwise.
        """
        if not url or not isinstance(url, str):
            return None
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return None
        if len(url) > 2048:
            return None
        return url

    def _extract_rss_image(self, entry) -> Optional[str]:
        """Extract image URL from RSS entry media:content or enclosures."""
        # media:content
        media_content = getattr(entry, "media_content", None)
        if media_content:
            url = media_content[0].get("url") if media_content else None
            validated = self._validate_image_url(url)
            if validated:
                return validated

        # enclosures
        enclosures = getattr(entry, "enclosures", None)
        if enclosures:
            for enc in enclosures:
                if enc.get("type", "").startswith("image/"):
                    validated = self._validate_image_url(enc.get("href"))
                    if validated:
                        return validated

        return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats"""
        if not date_str:
            return None

        # Try multiple date formats
        from dateutil import parser as dateutil_parser

        try:
            parsed: datetime = dateutil_parser.parse(date_str)
            return parsed
        except Exception:
            return None


class CategoryClassifierAgent:
    CLASSIFICATION_PROMPT = """You are an editorial classifier for AIropa, \
a European AI and technology news platform.

Your job is to classify articles AND filter out irrelevant content.

STEP 1: RELEVANCE CHECK
Is this article about AI, technology, startups, tech policy, or digital innovation?
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

    PROMPT_VERSION = "classification_v2"

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

    def _classify_with_keywords(self, article: Article) -> Article:
        """Keyword-based classification fallback."""
        title_lower = article.title.lower()
        content_lower = article.content.lower()

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
        if "france" in title_lower or "france" in content_lower:
            article.country = "France"
        elif "germany" in title_lower or "germany" in content_lower:
            article.country = "Germany"
        elif "netherlands" in title_lower or "netherlands" in content_lower:
            article.country = "Netherlands"
        elif "europe" in title_lower or "eu" in title_lower:
            article.country = "Europe"
        else:
            article.country = ""

        return article


class SummarizerAgent:
    """Generate 2-3 sentence editorial summaries with European angle."""

    SUMMARY_PROMPT = """\
You are a news editor for AIropa, a European AI and technology platform.

Write a 2-3 sentence summary of this article for a news card.
The summary should help a reader decide whether to click through.

Rules:
- State what happened, who is involved, and why it matters
- If the article has a European angle, emphasize it
- If the article is not about AI or technology, write exactly: NOT_RELEVANT
- Do NOT include any HTML tags, image URLs, or markup in your summary
- Do NOT invent or introduce facts not present in the article
- Do NOT repeat the title as the first sentence
- Write in plain text only

Source: {source}
Title: {title}
Content: {content}

Summary:"""

    PROMPT_VERSION = "summary_v2"
    MIN_CONTENT_LENGTH = 200  # Skip articles with very short content

    def __init__(self):
        self.last_telemetry = None

    def summarize(self, article: Article) -> Article:
        """Summarize article using LLM if enabled.

        Behavior depends on feature flags:
        - summary_enabled=False: return article unchanged
        - summary_enabled=True, shadow_mode=True: run LLM, log, don't apply
        - summary_enabled=True, shadow_mode=False: use LLM summary

        After calling, check self.last_telemetry for LLM call details.
        """
        self.last_telemetry = None

        if not config.ai.summary_enabled:
            return article

        # Skip articles with very short or missing content
        if len(article.content) < self.MIN_CONTENT_LENGTH:
            logger.info(
                "Skipping summary for '%s': content too short (%d chars)",
                article.title[:60],
                len(article.content),
            )
            return article

        summary_text = self._summarize_with_llm(article)

        if config.ai.shadow_mode:
            if summary_text:
                logger.info(
                    "Shadow summary for '%s': %s",
                    article.title[:60],
                    summary_text[:80],
                )
            return article

        # Live mode: apply summary if valid
        if summary_text:
            if summary_text == "NOT_RELEVANT":
                logger.info(
                    "Summarizer flagged '%s' as not relevant",
                    article.title[:60],
                )
                return article
            article.summary = summary_text

        return article

    def _summarize_with_llm(self, article: Article) -> Optional[str]:
        """Summarize article using LLM. Returns summary text or None.

        Sets self.last_telemetry with LLM call details.
        """
        from airopa_automation.llm import llm_complete
        from airopa_automation.llm_schemas import parse_summary

        prompt = self.SUMMARY_PROMPT.format(
            title=article.title,
            content=clean_content(article.content)[:2000],
            source=article.source,
        )

        result = llm_complete(prompt)

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
                "LLM summary call failed for '%s': %s - %s",
                article.title[:60],
                result["status"],
                result["error"],
            )
            return None

        parsed = parse_summary(result["text"])

        if not parsed.valid:
            self.last_telemetry["llm_status"] = "parse_error"
            self.last_telemetry["fallback_reason"] = parsed.fallback_reason
            logger.warning(
                "Summary validation failed for '%s': %s",
                article.title[:60],
                parsed.fallback_reason,
            )
            return None

        return parsed.text


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


class ContentGeneratorAgent:
    def __init__(self):
        self.output_dir = Path(config.content.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, article: Article) -> Optional[Path]:
        """Generate markdown file for an article"""
        try:
            # Generate filename
            title_slug: str = slugify(article.title)
            date_str = (
                article.published_date.strftime("%Y-%m-%d")
                if article.published_date
                else datetime.now().strftime("%Y-%m-%d")
            )
            filename = f"{date_str}-{title_slug}.md"
            filepath: Path = self.output_dir / filename

            # Generate frontmatter
            frontmatter = self._generate_frontmatter(article)

            # Write markdown file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter)
                f.write(f"\n\n{article.content}")

            return filepath

        except Exception as e:
            print(f"Error generating markdown for {article.title}: {e}")
            return None

    def _generate_frontmatter(self, article: Article) -> str:
        """Generate YAML frontmatter for markdown file"""
        frontmatter = "---\n"
        frontmatter += f'title: "{article.title}"\n'
        frontmatter += f"date: \"{article.published_date.strftime('%Y-%m-%d') if article.published_date else datetime.now().strftime('%Y-%m-%d')}\"\n"  # noqa: E501
        frontmatter += f'author: "{config.content.default_author}"\n'
        frontmatter += f'source: "{article.source}"\n'
        frontmatter += f'url: "{article.url}"\n'
        frontmatter += f'pillar: "{article.category}"\n'

        if article.country:
            frontmatter += f'country: "{article.country}"\n'

        if article.summary:
            frontmatter += f'description: "{article.summary[:160]}"\n'

        frontmatter += f'coverImage: "{config.content.default_cover_image}"\n'
        frontmatter += "isFeatured: false\n"
        frontmatter += "isAiGenerated: true\n"
        frontmatter += "---"

        return frontmatter


class GitCommitAgent:
    def __init__(self):
        import git

        self.repo_path = Path(config.git.repo_path)
        self.repo = git.Repo(self.repo_path)

    def commit_new_content(self, files: List[Path]) -> bool:
        """Commit new content files to git repository"""
        try:
            # Add files to git
            for file in files:
                relative_path = file.relative_to(self.repo_path)
                self.repo.index.add([str(relative_path)])

            # Commit changes
            import git

            self.repo.index.commit(
                config.git.commit_message,
                author=git.Actor(config.git.author_name, config.git.author_email),
            )

            return True

        except Exception as e:
            print(f"Error committing files to git: {e}")
            return False
