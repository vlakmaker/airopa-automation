# AIropa Automation Agents
#
# This package splits the agent classes into focused modules:
#   models.py     - Article model + clean_content utility
#   scraper.py    - ScraperAgent (RSS + web scraping)
#   classifier.py - CategoryClassifierAgent (LLM + keyword classification)
#   summarizer.py - SummarizerAgent (LLM summarization)
#   quality.py    - QualityScoreAgent (quality scoring)
#   content.py    - ContentGeneratorAgent + GitCommitAgent
#
# All public names are re-exported here for backward compatibility:
#   from airopa_automation.agents import Article, ScraperAgent, ...

from .classifier import CategoryClassifierAgent
from .content import ContentGeneratorAgent, GitCommitAgent
from .models import Article, clean_content
from .quality import QualityScoreAgent
from .scraper import ScraperAgent
from .summarizer import SummarizerAgent

__all__ = [
    "Article",
    "clean_content",
    "ScraperAgent",
    "CategoryClassifierAgent",
    "SummarizerAgent",
    "QualityScoreAgent",
    "ContentGeneratorAgent",
    "GitCommitAgent",
]
