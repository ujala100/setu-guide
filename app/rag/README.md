# RAG: stage-aware guidance retrieval (owner: AI/ML 2)

`retrieve(query, stage, intent=None, k=3)` returns the best knowledge-base chunks for the user's
journey stage. `retrieve_for_orchestrator(intent, ctx, query, k=3)` is the adapter for
`app/core/orchestrator.py` (returns `[{"id", "text", "topic", "source"}]`).

- `knowledge_base/kb_chunks.json`: 86 chunks (8 stages + `global`), each with `chunk_id`, `stage`,
  `topic`, `intent`, `text`, `source` (roadmap section or deck page). Built in
  `docs/aiml2/notebooks/day1_knowledge_base.ipynb`.
- Ranking: filter by stage (plus `global`), then TF-IDF similarity + intent boost + privacy/risk boosts.
  No model download, no GPU, no extra dependencies.
- Evaluation: `python eval/retrieval/run_eval.py`. Tests: `pytest tests/test_retriever.py`.

## Known limits
- Hit rate is label-based (expected topic in top 3). It does not prove the chunk answers the question.
  Needs AI/ML 1's held-out conversations and a human relevance check.
- English only.
- Chunks sourced from the fundraising deck (`deck_*`) contain policy claims (data erasure period, DPDP,
  "never sells data", Aadhaar handling). Product owner must confirm them before the assistant repeats them.
- Stage descriptions must match the Figma stage copy (see review notes).
