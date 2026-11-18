import pytest
from app.core.orchestrator import handle_chat
from app.schemas.guide import GuideRequest, SafetyStatus

REQ = GuideRequest(user_id="u1", match_id="m1", stage="connect", message="mujhe next steps batao")

@pytest.mark.parametrize("mock_name, mock_value", [
    ("timeout", TimeoutError()),
    ("malformed", "{ broken json"),
    ("empty", "")
])
def test_fallback(monkeypatch, mock_name, mock_value):
    # 1. Break the LLM
    def fake_generate(*args, **kwargs):
        if isinstance(mock_value, Exception):
            raise mock_value
        return mock_value
    monkeypatch.setattr("app.core.llm_provider.MockLLMProvider.generate", fake_generate)
    
    # 2. Break the Knowledge Base retrieval so it has nothing to fall back to
    monkeypatch.setattr("app.core.orchestrator.rag_retrieve", lambda *args, **kwargs: [])
    
    # 3. Trigger the handler
    result = handle_chat(REQ)
    
    # 4. Prove the template fallback was used
    assert result.fallback_used is True, f"Fallback not used for {mock_name}"
    assert result.safety.status in (SafetyStatus.passed, "pass"), f"Safety failed for {mock_name}"
