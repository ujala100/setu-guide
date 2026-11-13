"""D2-24: a failing LLM provider must not leak the prompt or the provider
error text into the logs or stdout.

Before this change `app/core/llm_provider.py` and `app/core/pipeline.py` used
`print(f"... {error}")`, and provider errors can echo the prompt. The markers
below are synthetic and exist only inside this test.
"""
import logging
from types import SimpleNamespace

import app.core.pipeline as pipeline
from app.core.llm_provider import GeminiLLMProvider

MARKER = "PRIVACY-MARKER-PROVIDER-4242"


class _FailingInteractions:
    def create(self, **_kwargs):
        raise RuntimeError(f"upstream rejected payload containing {MARKER}")


def _provider_with(interactions):
    provider = object.__new__(GeminiLLMProvider)
    provider.client = SimpleNamespace(interactions=interactions)
    return provider


def test_provider_failure_logs_type_only(caplog, capsys):
    provider = _provider_with(_FailingInteractions())

    with caplog.at_level(logging.INFO, logger="setu.guide"):
        assert provider.generate(f"user prompt {MARKER}") is None

    captured = capsys.readouterr()
    combined = caplog.text + captured.out + captured.err
    assert MARKER not in combined, "provider error text leaked"
    assert "gemini_request_failed type=RuntimeError" in caplog.text


def test_pipeline_provider_failure_logs_type_only(monkeypatch, caplog, capsys):
    def boom(use_gemini=False):
        raise RuntimeError(f"factory failed for {MARKER}")

    monkeypatch.setattr(pipeline, "get_provider", boom)

    with caplog.at_level(logging.INFO, logger="setu.guide"):
        result = pipeline.run_pipeline("How do I start a conversation?", use_gemini=True)

    assert result is not None, "template fallback should still answer"
    captured = capsys.readouterr()
    combined = caplog.text + captured.out + captured.err
    assert MARKER not in combined, "provider error text leaked"
    assert "llm_provider_failed type=RuntimeError" in caplog.text
