# Retrieval Tuning Notes

## Current Settings
- **Top-k:** 4 (Retrieves the 4 most relevant chunks).
- **Filters:** Hard filter on `stage` to prevent cross-stage hallucinations.
- **Chunk Size:** ~120 words.

## Evaluation Findings
- *Pending RAG engine integration.*
- Once `eval_retrieval.py` is connected to the real `retrieve()` function, we will record failures and adjust `top-k` if the hit rate drops.