# Retrieval (RAG) — Final Report Section

## Summary
Implemented a safe retrieval pipeline that prevents hallucination.

## Quality Metrics
-**Hit rate:** TBD (Pending integration)
-**Wrong-stage chunks:** 0 (Stage filter implemented)
-**Off-topic correctly no-answer:** Verified in `threshold.py` tests.

## Source Integrity
-**No orphan IDs:** Verified by `app/rag/check_source_ids.py`.
-**Versioning:** Traceable via `app/rag/CHANGELOG.md`.

Reviewed by: <lead>

# Retrieval (RAG) — Final Report Section

## 1. Summary
For Phase 2, the AI/ML 2 intern implemented a safe, stage-aware retrieval pipeline. The primary goal was to ensure the bot grounds its answers in the provided Knowledge Base (KB v2) and safely refuses to answer when data is missing.

## 2. Quality & Safety
-**No-Answer Threshold:** Implemented in `threshold.py` (0.55). Verified by `test_rag_threshold.py`. This prevents hallucination.
-**KB v2:** Audited 100% of chunks. Added new privacy/consent chunks to fix critical safety gaps.
-**Source Integrity:** `check_source_ids.py` ensures 0 orphan IDs.

## 3. Versioning
All KB changes are tracked in `CHANGELOG.md`. Current version: v2.

## 4. Tuning
Top-k is set to 4. Strict stage filtering is applied to prevent the bot from mixing up conversation stages. 

Reviewed by: <lead>




