import pytest
from app.core.orchestrator import route
from app.schemas.guide import GuideRequest, Intent

HINGLISH_CASES = [
    ("mujhe next steps batao", Intent.next_steps),
    ("kaise baat karu", Intent.conversation_ideas),
]

@pytest.mark.parametrize("text,expected", HINGLISH_CASES)
def test_hinglish_routing(text, expected):
    req = GuideRequest(user_id="u1", match_id="m1", stage="connect", message=text)
    result = route(req)
    assert result == expected, f"Router returned {result}, expected {expected}"
