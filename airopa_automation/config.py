# AIropa Automation Configuration

import os
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ScraperConfig(BaseModel):
    rss_feeds: List[str] = [
        "https://ai.europa.eu/rss.xml",
        "https://www.european-ai-alliance.eu/rss.xml",
        "https://ai4eu.eu/feed.xml"
    ]
    web_sources: List[str] = [
        "https://ai.europa.eu",
        "https://www.european-ai-alliance.eu",
        "https://ai4eu.eu"
    ]
    max_articles_per_source: int = 10
    rate_limit_delay: float = 1.0  # seconds between requests
    user_agent: str = "AIropaBot/1.0 (+https://airopa.eu)"

class AIConfig(BaseModel):
    model: str = "llama3-70b-8192"
    temperature: float = 0.7
    max_tokens: int = 1024
    api_key: str = os.getenv("GROQ_API_KEY", "")

class DatabaseConfig(BaseModel):
    db_path: str = "database/airopa.db"
    max_connections: int = 5
    timeout: float = 10.0

class ContentConfig(BaseModel):
    output_dir: str = "../airopa/src/content/post"
    default_author: str = "AIropa Bot"
    default_cover_image: str = "/assets/featured-story.jpg"

class GitConfig(BaseModel):
    repo_path: str = "../airopa"
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

# Ensure output directory exists
def ensure_directories():
    Path(config.content.output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.database.db_path).parent.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    ensure_directories()
    print("Configuration loaded successfully")