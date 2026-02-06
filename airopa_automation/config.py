# AIropa Automation Configuration

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()


class ScraperConfig(BaseModel):
    rss_feeds: list[str] = [
        "https://sifted.eu/feed/?post_type=article",
        "https://tech.eu/category/deep-tech/feed",
        "https://european-champions.org/feed",
        "https://tech.eu/category/robotics/feed",
    ]
    web_sources: list[str] = [
        "https://sifted.eu",
        "https://tech.eu",
        "https://european-champions.org",
    ]
    max_articles_per_source: int = 10
    max_article_age_days: int = int(os.getenv("MAX_ARTICLE_AGE_DAYS", "30"))
    rate_limit_delay: float = 1.0  # seconds between requests
    user_agent: str = "AIropaBot/1.0 (+https://airopa.eu)"
    # Source name normalization mapping
    source_name_map: dict[str, str] = {
        "https://sifted.eu": "Sifted",
        "Sifted - News, Analysis and Opinion on European Startups": "Sifted",
        "Deeptech - Tech.eu": "Tech.eu",
        "Robotics - Tech.eu": "Tech.eu",
    }


class AIConfig(BaseModel):
    model: str = "llama3-70b-8192"
    temperature: float = 0.7
    max_tokens: int = 1024
    api_key: str = os.getenv("GROQ_API_KEY", "")
    # Note: AI features will be limited due to Python 3.13 compatibility issues


class DatabaseConfig(BaseModel):
    db_path: str = "database/airopa.db"
    max_connections: int = 5
    timeout: float = 10.0


class ContentConfig(BaseModel):
    output_dir: str = "../airopa/src/content/post"
    default_author: str = "AIropa Bot"
    default_cover_image: str = "/assets/featured-story.jpg"


class GitConfig(BaseModel):
    repo_path: str = ".."
    commit_message: str = "chore(content): add automated AI news articles"
    author_name: str = "AIropa Bot"
    author_email: str = "bot@airopa.eu"


class Config(BaseModel):
    scraper: ScraperConfig = ScraperConfig()
    ai: AIConfig = AIConfig()
    database: DatabaseConfig = DatabaseConfig()
    content: ContentConfig = ContentConfig()
    git: GitConfig = GitConfig()
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"


# Global configuration instance
config = Config()


def ensure_directories() -> None:
    """Ensure required directories exist"""
    Path(config.content.output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.database.db_path).parent.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_directories()
    print("Configuration loaded successfully")
