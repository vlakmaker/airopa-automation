from unittest.mock import MagicMock, patch

from airopa_automation.llm import llm_complete


class TestLLMComplete:
    """Test llm_complete wrapper"""

    @patch("airopa_automation.llm.config")
    def test_no_api_key_returns_error(self, mock_config):
        """Test that missing API key returns structured error"""
        mock_config.ai.provider = "groq"
        mock_config.ai.model = "test-model"
        mock_config.ai.temperature = 0.3
        mock_config.ai.api_key = ""

        result = llm_complete("test prompt")

        assert result["status"] == "no_api_key"
        assert result["text"] == ""
        assert "No API key" in result["error"]

    @patch("airopa_automation.llm.config")
    @patch("airopa_automation.llm._call_groq")
    def test_groq_provider_routes_correctly(self, mock_call, mock_config):
        """Test that groq provider calls _call_groq"""
        mock_config.ai.provider = "groq"
        mock_config.ai.model = "llama-3.3-70b-versatile"
        mock_config.ai.temperature = 0.3
        mock_config.ai.api_key = "test-key"
        mock_call.return_value = {"status": "ok", "text": "response"}

        llm_complete("test prompt")

        mock_call.assert_called_once()

    @patch("airopa_automation.llm.config")
    @patch("airopa_automation.llm._call_mistral")
    def test_mistral_provider_routes_correctly(self, mock_call, mock_config):
        """Test that mistral provider calls _call_mistral"""
        mock_config.ai.provider = "mistral"
        mock_config.ai.model = "mistral-small-latest"
        mock_config.ai.temperature = 0.3
        mock_config.ai.api_key = "test-key"
        mock_call.return_value = {"status": "ok", "text": "response"}

        llm_complete("test prompt")

        mock_call.assert_called_once()

    @patch("airopa_automation.llm.config")
    def test_model_override(self, mock_config):
        """Test that model parameter overrides config"""
        mock_config.ai.provider = "groq"
        mock_config.ai.model = "default-model"
        mock_config.ai.temperature = 0.3
        mock_config.ai.api_key = ""

        result = llm_complete("test", model="custom-model")

        assert result["model"] == "custom-model"

    @patch("airopa_automation.llm.config")
    def test_result_structure(self, mock_config):
        """Test that result always has all required keys"""
        mock_config.ai.provider = "groq"
        mock_config.ai.model = "test-model"
        mock_config.ai.temperature = 0.3
        mock_config.ai.api_key = ""

        result = llm_complete("test")

        required_keys = [
            "text",
            "latency_ms",
            "tokens_in",
            "tokens_out",
            "status",
            "error",
            "provider",
            "model",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"


class TestCallGroq:
    """Test Groq API call"""

    @patch("groq.Groq")
    def test_successful_groq_call(self, mock_groq_class):
        """Test successful Groq API call"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"category": "startups"}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 20

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class.return_value = mock_client

        from airopa_automation.llm import _call_groq

        with patch("airopa_automation.llm.config") as mock_config:
            mock_config.ai.max_tokens = 1024

            base = {
                "text": "",
                "latency_ms": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "status": "ok",
                "error": "",
                "provider": "groq",
                "model": "test-model",
            }
            result = _call_groq("test prompt", "test-model", 0.3, "key", base)

        assert result["status"] == "ok"
        assert result["text"] == '{"category": "startups"}'
        assert result["tokens_in"] == 100
        assert result["tokens_out"] == 20
        assert result["latency_ms"] >= 0

    @patch("groq.Groq")
    def test_groq_api_error(self, mock_groq_class):
        """Test Groq API error is caught gracefully"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limited")
        mock_groq_class.return_value = mock_client

        from airopa_automation.llm import _call_groq

        with patch("airopa_automation.llm.config") as mock_config:
            mock_config.ai.max_tokens = 1024

            base = {
                "text": "",
                "latency_ms": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "status": "ok",
                "error": "",
                "provider": "groq",
                "model": "test-model",
            }
            result = _call_groq("test prompt", "test-model", 0.3, "key", base)

        assert result["status"] == "api_error"
        assert "Rate limited" in result["error"]
        assert result["text"] == ""


class TestCallMistral:
    """Test Mistral API call"""

    @patch("mistralai.Mistral")
    def test_successful_mistral_call(self, mock_mistral_class):
        """Test successful Mistral API call"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"category": "policy"}'
        mock_response.usage.prompt_tokens = 80
        mock_response.usage.completion_tokens = 15

        mock_client = MagicMock()
        mock_client.chat.complete.return_value = mock_response
        mock_mistral_class.return_value = mock_client

        from airopa_automation.llm import _call_mistral

        with patch("airopa_automation.llm.config") as mock_config:
            mock_config.ai.max_tokens = 1024

            base = {
                "text": "",
                "latency_ms": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "status": "ok",
                "error": "",
                "provider": "mistral",
                "model": "test-model",
            }
            result = _call_mistral("test prompt", "test-model", 0.3, "key", base)

        assert result["status"] == "ok"
        assert result["text"] == '{"category": "policy"}'
        assert result["tokens_in"] == 80
        assert result["tokens_out"] == 15

    @patch("mistralai.Mistral")
    def test_mistral_api_error(self, mock_mistral_class):
        """Test Mistral API error is caught gracefully"""
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = Exception("Unauthorized")
        mock_mistral_class.return_value = mock_client

        from airopa_automation.llm import _call_mistral

        with patch("airopa_automation.llm.config") as mock_config:
            mock_config.ai.max_tokens = 1024

            base = {
                "text": "",
                "latency_ms": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "status": "ok",
                "error": "",
                "provider": "mistral",
                "model": "test-model",
            }
            result = _call_mistral("test prompt", "test-model", 0.3, "key", base)

        assert result["status"] == "api_error"
        assert "Unauthorized" in result["error"]
