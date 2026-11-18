
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.llm_provider import OpenAILLMProvider
from app.core.pipeline import get_provider


def test_openai_provider_parses_valid_json():
    provider = OpenAILLMProvider.__new__(OpenAILLMProvider)
    provider.client = MagicMock()
    provider.client.responses.create.return_value = SimpleNamespace(
        output_text=json.dumps({
            "intent": "next_steps",
            "response": ["Step one", "Step two"],
        }),
        usage=None,
    )

    result = provider.generate("test prompt")

    assert result == {
        "intent": "next_steps",
        "response": ["Step one", "Step two"],
    }


def test_openai_provider_returns_none_for_invalid_json():
    provider = OpenAILLMProvider.__new__(OpenAILLMProvider)
    provider.client = MagicMock()
    provider.client.responses.create.return_value = SimpleNamespace(
        output_text="not valid JSON",
        usage=None,
    )

    assert provider.generate("test prompt") is None


def test_openai_provider_returns_none_on_api_exception():
    provider = OpenAILLMProvider.__new__(OpenAILLMProvider)
    provider.client = MagicMock()
    provider.client.responses.create.side_effect = RuntimeError("API error")

    assert provider.generate("test prompt") is None


def test_provider_selection_uses_openai_when_configured():
    settings = SimpleNamespace(
        use_mock=False,
        llm_provider="openai",
        llm_api_key="test-key",
        llm_timeout_seconds=10.0,
    )

    with patch("app.core.pipeline.get_settings", return_value=settings):
        with patch(
            "app.core.pipeline.OpenAILLMProvider"
        ) as openai_class:
            get_provider()

    openai_class.assert_called_once_with(
        api_key="test-key",
        timeout_seconds=10.0,
    )


def test_mock_mode_takes_precedence_over_openai():
    settings = SimpleNamespace(
        use_mock=True,
        llm_provider="openai",
        llm_api_key=None,
        llm_timeout_seconds=10.0,
    )

    with patch("app.core.pipeline.get_settings", return_value=settings):
        provider = get_provider()

    assert provider.__class__.__name__ == "MockLLMProvider"
