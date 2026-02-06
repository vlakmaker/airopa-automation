# AIropa Automation Agents - Base Classes

import hashlib
import logging
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
    def __init__(self):
        # Initialize AI client (will be implemented)
        pass

    def classify(self, article: Article) -> Article:
        """Classify article into appropriate category"""
        # This will use AI/ML for classification
        # For now, implement basic keyword-based classification

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
            country in title_lower or country in content_lower
            for country in ["france", "germany", "netherlands", "europe", "eu"]
        ):
            article.category = "country"
        else:
            article.category = "stories"

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


class QualityScoreAgent:
    def __init__(self):
        pass

    def assess_quality(self, article: Article) -> Article:
        """Assess article quality and relevance"""
        # Basic quality scoring algorithm
        score = 0.0

        # Title quality
        if len(article.title.split()) > 3:
            score += 0.2

        # Content length
        word_count = len(article.content.split())
        if word_count > 200:
            score += 0.3
        if word_count > 500:
            score += 0.2

        # Source credibility
        if any(source in article.source.lower() for source in ["europa.eu", "airopa"]):
            score += 0.3

        # Category relevance
        if article.category:
            score += 0.1

        # Country relevance
        if article.country:
            score += 0.1

        article.quality_score = min(score, 1.0)
        return article


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
