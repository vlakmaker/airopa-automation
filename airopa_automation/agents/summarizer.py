# AIropa Automation - Summarizer Agent

import logging
from typing import Optional

from airopa_automation.config import config

from .models import Article, clean_content

logger = logging.getLogger(__name__)


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
