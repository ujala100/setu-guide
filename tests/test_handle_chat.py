from app.core import orchestrator


def test_handle_chat_exists_for_real_mode():
    assert callable(getattr(orchestrator, "handle_chat", None))