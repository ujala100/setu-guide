"""No-relevant-chunk threshold: return 'don't know' instead of inventing."""
NO_ANSWER_THRESHOLD = 0.55 
NO_ANSWER_TEXT = "I don't have enough information to answer that safely."

def filter_or_fallback(results):
    """
    Filters retrieved chunks by score. If none pass, returns a safe fallback.
    """
    # If the list is completely empty, trigger the fallback
    if not results:
        return {"answer": NO_ANSWER_TEXT, "sources": [], "fallback_used": True}
        
    # Check the score of the first result (defaulting to 1.0 if no score is provided)
    first_score = results[0].get("score", 1.0)
    
    if first_score < NO_ANSWER_THRESHOLD:
        return {"answer": NO_ANSWER_TEXT, "sources": [], "fallback_used": True}
        
    # Otherwise, return the chunks as a normal list
    return {"answer": results[0]["text"], "sources": [r["chunk_id"] for r in results], "fallback_used": False}