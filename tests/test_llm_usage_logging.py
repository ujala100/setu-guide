import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.llm_provider import GeminiLLMProvider


def make_provider(interaction):
    provider = GeminiLLMProvider.__new__(GeminiLLMProvider)
    provider.client = MagicMock()
    provider.client.interactions.create.return_value = interaction
    return provider


def test_logs_token_usage(caplog):
    interaction = SimpleNamespace(
        usage=SimpleNamespace(
            total_input_tokens=100,
            total_output_tokens=40,
            total_tokens=140,
        ),
        output_text='{"intent": "next_steps", "response": ["Step one"]}',
    )
    provider = make_provider(interaction)

    with caplog.at_level(logging.INFO, logger="setu.guide.llm"):
        result = provider.generate("test prompt")

    assert result["intent"] == "next_steps"
    assert "input_tokens=100" in caplog.text
    assert "output_tokens=40" in caplog.text
    assert "total_tokens=140" in caplog.text
    assert "estimated_cost_usd=0.0001300000" in caplog.text
    assert "provider=gemini" in caplog.text


def test_handles_missing_usage(caplog):
    interaction = SimpleNamespace(
        usage=None,
        output_text='{"intent": "next_steps", "response": ["Step one"]}',
    )
    provider = make_provider(interaction)

    with caplog.at_level(logging.INFO, logger="setu.guide.llm"):
        result = provider.generate("test prompt")

    assert result["intent"] == "next_steps"
    assert "usage_available=false" in caplog.text


def test_invalid_json_returns_none():
    interaction = SimpleNamespace(
        usage=None,
        output_text="not valid JSON",
    )
    provider = make_provider(interaction)

    assert provider.generate("test prompt") is None
