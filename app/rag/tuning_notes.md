# Retrieval Tuning Notes

## Current Settings
- **Top-k:** 4 (Retrieves the 4 most relevant chunks).
- **Filters:** Hard filter on `stage` to prevent cross-stage hallucinations.
- **Chunk Size:** ~120 words.

## Evaluation Findings
- *Pending RAG engine integration.*
- Once `eval_retrieval.py` is connected to the real `retrieve()` function, we will record failures and adjust `top-k` if the hit rate drops. 

# Retrieval Tuning Notes

## Current Settings
- **Top-k:** 4 (Retrieves the 4 most relevant chunks).
- **Filters:** Hard filter on `stage` to prevent cross-stage hallucinations.
- **Chunk Size:** ~120 words (Based on `kb_chunks.json`).

## Tuning based on Evaluation
- **Issue:** Off-topic questions were causing the bot to guess.
- **Fix:** Added `NO_ANSWER_THRESHOLD = 0.55` in `threshold.py`. If the score is lower, it returns a safe fallback.
- **Issue:** Bot was grabbing chunks from the wrong stage.
- **Fix:** Enforced a strict `stage` filter in the retrieval logic.
