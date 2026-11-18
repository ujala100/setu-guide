from app.core import pipeline


class SequenceProvider:
    """Return or raise the next configured result on each call."""

    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        result = next(self.results)

        if isinstance(result, Exception):
            raise result

        return result


def test_pipeline_retries_after_provider_exception(monkeypatch):
    expected = {
        "intent": "next_steps",
        "response": ["Consider one small, mutually agreed next step."],
    }
    provider = SequenceProvider([
        RuntimeError("temporary provider failure"),
        expected,
    ])
    monkeypatch.setattr(pipeline, "get_provider", lambda: provider)

    result = pipeline.run_pipeline("What are the next steps?")

    assert result == expected
    assert provider.calls == 2


def test_pipeline_falls_back_after_two_invalid_responses(monkeypatch):
    provider = SequenceProvider([
        {"intent": "next_steps", "response": []},
        {"intent": "wrong_intent", "response": ["Invalid intent"]},
    ])
    monkeypatch.setattr(pipeline, "get_provider", lambda: provider)

    result = pipeline.run_pipeline("What are the next steps?")

    assert provider.calls == 2
    assert result["intent"] == "next_steps"
    assert pipeline.validate_response(result) is True


def test_pipeline_retries_after_invalid_response(monkeypatch):
    expected = {
        "intent": "conversation_ideas",
        "response": ["Ask about a topic you both enjoy."],
    }
    provider = SequenceProvider([
        {"intent": "conversation_ideas", "response": []},
        expected,
    ])
    monkeypatch.setattr(pipeline, "get_provider", lambda: provider)

    result = pipeline.run_pipeline("What can we talk about?")

    assert result == expected
    assert provider.calls == 2


def test_pipeline_falls_back_after_two_provider_exceptions(monkeypatch):
    provider = SequenceProvider([
        RuntimeError("temporary failure"),
        RuntimeError("second failure"),
    ])
    monkeypatch.setattr(pipeline, "get_provider", lambda: provider)

    result = pipeline.run_pipeline("What are the next steps?")

    assert provider.calls == 2
    assert result["intent"] == "next_steps"
    assert pipeline.validate_response(result) is True
