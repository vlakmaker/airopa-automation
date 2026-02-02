"""
AIropa Automation Layer - Core Package

This package provides the foundation for AI-powered automation workflows.
"""

from .agents import (
    CategoryClassifierAgent,
    ContentGeneratorAgent,
    GitCommitAgent,
    QualityScoreAgent,
    ScraperAgent,
)
from .config import Config
from .database import Database

__version__ = "0.1.0"
__all__ = [
    "ScraperAgent",
    "CategoryClassifierAgent",
    "QualityScoreAgent",
    "ContentGeneratorAgent",
    "GitCommitAgent",
    "Config",
    "Database",
]
