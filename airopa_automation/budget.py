"""
Token budget tracking for LLM calls within a single pipeline run.

Prevents runaway costs by enforcing a per-run token cap.
When the budget is exceeded, callers should fall back to non-LLM paths.
"""

import logging

from airopa_automation.config import config

logger = logging.getLogger(__name__)


class TokenBudget:
    """Tracks cumulative token usage for a pipeline run."""

    def __init__(self, max_tokens: int | None = None):
        """Initialize with a token cap. 0 means unlimited, None reads from config."""
        if max_tokens is not None:
            self.max_tokens = max_tokens
        else:
            self.max_tokens = config.ai.budget_max_tokens_per_run
        self.tokens_used = 0

    def record(self, tokens_in: int, tokens_out: int) -> None:
        """Record tokens consumed by an LLM call."""
        self.tokens_used += tokens_in + tokens_out

    @property
    def exceeded(self) -> bool:
        """Return True if the token budget has been exceeded."""
        if self.max_tokens == 0:
            return False
        return self.tokens_used >= self.max_tokens

    @property
    def remaining(self) -> int:
        """Return remaining tokens, or -1 if unlimited."""
        if self.max_tokens == 0:
            return -1
        return max(0, self.max_tokens - self.tokens_used)
