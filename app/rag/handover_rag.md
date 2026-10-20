# RAG Handover — New Interns (AI/ML Intern 2)

## What retrieval does
`retrieve(query, stage, intent) -> list[Chunk]`
- query: raw user message (Hindi / Hinglish / emoji allowed)
- stage: s1..s8
- intent: i1..i8
Returns top-k chunks with: chunk_id, text, tags{stage,intent,topic,safety}.

## Golden rule
No chunk above threshold -> return `NO_ANSWER_TEXT`. Never invent facts.

## Team rules (§2 of PDF)
- Daily 15-min check-in.
- One branch per person; PR reviewed before merge.
- No real user data, no secrets in repo.