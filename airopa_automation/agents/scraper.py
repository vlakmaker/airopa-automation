# AIropa Automation - Scraper Agent

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle

from airopa_automation.config import config

from .models import Article, clean_content

logger = logging.getLogger(__name__)


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

    def _fetch_feed(self, feed_url: str):
        """Fetch and parse an RSS feed with a timeout.

        Uses requests to download the feed (respecting feed_timeout),
        then passes the content to feedparser. This prevents a single
        slow or hanging feed from blocking the entire pipeline.
        """
        resp = self.session.get(feed_url, timeout=config.scraper.feed_timeout)
        resp.raise_for_status()
        return feedparser.parse(resp.content)

    def scrape_rss_feeds(self) -> List[Article]:  # noqa: C901
        """Scrape articles from RSS feeds"""
        articles = []

        for feed_url in config.scraper.rss_feeds:
            try:
                feed = self._fetch_feed(feed_url)
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

                        # RSS content fallback: when newspaper3k fails or returns
                        # very short content (paywall, 403, etc.), use RSS
                        # content:encoded or description as fallback so articles
                        # still get quality credit and LLM classification context.
                        rss_summary = entry.get("summary", "")
                        if len(content) < 200:
                            rss_content = self._extract_rss_content(entry)
                            if rss_content and len(rss_content) > len(content):
                                logger.info(
                                    "Using RSS content as fallback for '%s' "
                                    "(newspaper3k: %d chars, RSS: %d chars)",
                                    entry.get("title", "unknown")[:60],
                                    len(content),
                                    len(rss_content),
                                )
                                content = rss_content

                        article = Article(
                            title=entry.get("title", "No title"),
                            url=entry.get("link", ""),
                            source=source_name,
                            content=content,
                            summary=rss_summary,
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

            except requests.exceptions.Timeout:
                logger.warning(
                    "Feed timed out after %ds: %s",
                    config.scraper.feed_timeout,
                    feed_url,
                )
                continue
            except requests.exceptions.ConnectionError as e:
                logger.warning("Feed connection error: %s — %s", feed_url, e)
                continue
            except Exception as e:
                logger.warning("Error scraping RSS feed %s: %s", feed_url, e)
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

        Downloads the page with a configurable timeout (article_timeout),
        then uses newspaper3k to parse the HTML. This prevents a single
        slow page from stalling the pipeline.

        Returns:
            Tuple of (article_text, image_url). image_url may be None.
        """
        try:
            resp = self.session.get(url, timeout=config.scraper.article_timeout)
            resp.raise_for_status()
            newspaper_article = NewspaperArticle(url)
            newspaper_article.download(input_html=resp.text)
            newspaper_article.parse()
            image_url = self._validate_image_url(newspaper_article.top_image)
            return str(newspaper_article.text), image_url
        except requests.exceptions.Timeout:
            logger.warning(
                "Article download timed out after %ds: %s",
                config.scraper.article_timeout,
                url,
            )
            return "", None
        except Exception as e:
            logger.warning("Error extracting content from %s: %s", url, e)
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

    def _extract_rss_content(self, entry) -> Optional[str]:
        """Extract best available text from RSS entry fields.

        Checks content:encoded first (full article body in some feeds),
        then falls back to summary/description. Returns cleaned text
        or None if nothing useful is available.
        """
        # content:encoded (feedparser stores as entry.content list)
        content_list = entry.get("content", [])
        if content_list:
            raw = content_list[0].get("value", "")
            cleaned = clean_content(raw)
            if cleaned:
                return cleaned

        # summary / description
        summary = entry.get("summary", "")
        if summary:
            cleaned = clean_content(summary)
            if cleaned:
                return cleaned

        return None

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
