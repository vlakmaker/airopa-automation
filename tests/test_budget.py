"""Tests for TokenBudget class."""

from unittest.mock import patch

from airopa_automation.budget import TokenBudget


class TestTokenBudget:
    """Test TokenBudget tracking and enforcement."""

    def test_initial_state(self):
        """Test budget starts at zero usage."""
        budget = TokenBudget(max_tokens=10000)
        assert budget.tokens_used == 0
        assert budget.exceeded is False
        assert budget.remaining == 10000

    def test_record_tokens(self):
        """Test recording token usage."""
        budget = TokenBudget(max_tokens=10000)
        budget.record(tokens_in=500, tokens_out=50)
        assert budget.tokens_used == 550
        assert budget.remaining == 9450

    def test_record_multiple_calls(self):
        """Test cumulative token recording."""
        budget = TokenBudget(max_tokens=1000)
        budget.record(tokens_in=200, tokens_out=30)
        budget.record(tokens_in=300, tokens_out=40)
        assert budget.tokens_used == 570
        assert budget.exceeded is False

    def test_exceeded_when_over_limit(self):
        """Test exceeded returns True when budget is used up."""
        budget = TokenBudget(max_tokens=1000)
        budget.record(tokens_in=800, tokens_out=300)
        assert budget.tokens_used == 1100
        assert budget.exceeded is True
        assert budget.remaining == 0

    def test_exceeded_at_exact_limit(self):
        """Test exceeded returns True at exactly the limit."""
        budget = TokenBudget(max_tokens=500)
        budget.record(tokens_in=400, tokens_out=100)
        assert budget.exceeded is True

    def test_unlimited_budget(self):
        """Test budget with max_tokens=0 is unlimited."""
        budget = TokenBudget(max_tokens=0)
        budget.record(tokens_in=999999, tokens_out=999999)
        assert budget.exceeded is False
        assert budget.remaining == -1

    @patch("airopa_automation.budget.config")
    def test_default_from_config(self, mock_config):
        """Test budget reads default from config."""
        mock_config.ai.budget_max_tokens_per_run = 25000
        budget = TokenBudget()
        assert budget.max_tokens == 25000
