# AIropa Automation Configuration

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()


class ScraperConfig(BaseModel):
    rss_feeds: list[str] = [
        # Existing sources
        "https://sifted.eu/feed/?post_type=article",
        "https://tech.eu/category/deep-tech/feed",
        "https://tech.eu/category/robotics/feed",
        "https://european-champions.org/feed",
        # Tier 1 — European startup/tech ecosystem
        "https://www.eu-startups.com/feed/",
        "https://siliconcanals.com/feed/",
        "https://tech.eu/category/artificial-intelligence/feed",
        "https://thenextweb.com/feed",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://www.siliconrepublic.com/feed",
        # Tier 2 — Policy, regulation, funding
        "https://algorithmwatch.org/en/feed/",
        "https://www.euractiv.com/feed/",
        "https://www.artificiallawyer.com/feed/",
        "https://techfundingnews.com/feed/",
        # Tier 3 — Research and academic
        "https://deepmind.com/blog/feed/basic/",
        "https://huggingface.co/blog/feed.xml",
    ]
    web_sources: list[str] = [
        "https://sifted.eu",
        "https://tech.eu",
        "https://european-champions.org",
    ]
    max_articles_per_source: int = 10
    # Articles with eu_relevance below this are stored but hidden from API
    eu_relevance_threshold: float = float(os.getenv("EU_RELEVANCE_THRESHOLD", "3.0"))
    max_article_age_days: int = int(os.getenv("MAX_ARTICLE_AGE_DAYS", "30"))
    rate_limit_delay: float = 1.0  # seconds between requests
    user_agent: str = "AIropaBot/1.0 (+https://airopa.eu)"
    # Source name normalization mapping (RSS feed title → canonical name)
    source_name_map: dict[str, str] = {
        # Existing
        "https://sifted.eu": "Sifted",
        "Sifted - News, Analysis and Opinion on European Startups": "Sifted",
        "Deeptech - Tech.eu": "Tech.eu",
        "Robotics - Tech.eu": "Tech.eu",
        "Artificial Intelligence - Tech.eu": "Tech.eu",
        # Tier 1
        "EU-Startups": "EU-Startups",
        "Silicon Canals": "Silicon Canals",
        "The Next Web": "The Next Web",
        "Feed: Artificial Intelligence Latest": "WIRED",
        "Silicon Republic": "Silicon Republic",
        # Tier 2
        "AlgorithmWatch": "AlgorithmWatch",
        "Euractiv": "EURACTIV",
        "EURACTIV": "EURACTIV",
        "Artificial Lawyer": "Artificial Lawyer",
        "Tech Funding News": "Tech Funding News",
        # Tier 3
        "Google DeepMind News": "DeepMind",
        "Hugging Face - Blog": "Hugging Face",
    }


class AIConfig(BaseModel):
    # LLM provider: "groq" or "mistral"
    provider: str = os.getenv("LLM_PROVIDER", "groq")
    temperature: float = 0.3
    max_tokens: int = 1024
    # Groq
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = "llama-3.3-70b-versatile"
    # Mistral
    mistral_api_key: str = os.getenv("MISTRAL_API_KEY", "")
    mistral_model: str = "mistral-small-latest"
    # Feature flags — control LLM rollout via env vars
    classification_enabled: bool = (
        os.getenv("LLM_CLASSIFICATION_ENABLED", "false").lower() == "true"
    )
    summary_enabled: bool = os.getenv("LLM_SUMMARY_ENABLED", "false").lower() == "true"
    quality_enabled: bool = os.getenv("LLM_QUALITY_ENABLED", "false").lower() == "true"
    shadow_mode: bool = os.getenv("LLM_SHADOW_MODE", "true").lower() == "true"
    # Budget: max total tokens (in+out) per scrape run. 0 = unlimited.
    budget_max_tokens_per_run: int = int(os.getenv("LLM_BUDGET_MAX_TOKENS", "50000"))

    @property
    def api_key(self) -> str:
        """Return API key for the active provider."""
        if self.provider == "mistral":
            return self.mistral_api_key
        return self.groq_api_key

    @property
    def model(self) -> str:
        """Return model name for the active provider."""
        if self.provider == "mistral":
            return self.mistral_model
        return self.groq_model


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
