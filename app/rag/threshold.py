"""No-relevant-chunk threshold: return 'don't know' instead of inventing."""
NO_ANSWER_THRESHOLD = 0.55  # Adjust based on eval_retrieval results
NO_ANSWER_TEXT = "I don't have enough information to answer that safely."

def filter_or_fallback(results, threshold=NO_ANSWER_THRESHOLD):
    """
    Filters retrieved chunks by score. If none pass, returns a safe fallback.
    """
    kept = [r for r in results if r.get("score", 0) >= threshold]
    if not kept:
        return {"answer": NO_ANSWER_TEXT, "sources": [], "fallback_used": True}
    return kept

def test_off_topic_returns_no_answer():
    out = filter_or_fallback([{"chunk_id":"x","score":0.2,"text":"..."}])
    assert out["fallback_used"] is True
    assert "don't have enough information" in out["answer"].lower()

def test_on_topic_passes():
    out = filter_or_fallback([{"chunk_id":"c1","score":0.9,"text":"..."}])
    assert isinstance(out, list) and len(out) == 1