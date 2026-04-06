# AIropa Automation - Article model and shared utilities

import hashlib
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel


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
