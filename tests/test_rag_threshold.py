from app.rag.threshold import filter_or_fallback, NO_ANSWER_TEXT

def test_off_topic_returns_no_answer():
    out = filter_or_fallback([])
    assert out["fallback_used"] is True
    assert out["answer"] == NO_ANSWER_TEXT

def test_on_topic_passes():
    out = filter_or_fallback([{"chunk_id": "c1", "text": "hello"}])
    assert out["fallback_used"] is False