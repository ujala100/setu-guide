"""Stage-aware retrieval over the Setu Guide knowledge base.

Owner: AI/ML 2 (Pooja Hiwale). Refined version of the Day 3 retriever.

What changed from the notebook version, and why:
- Filters by stage BEFORE ranking. The notebook fetched the top-18 chunks from
  the whole index and filtered afterwards, so 4 of 30 test queries returned
  nothing. Here the candidate set is filtered first, so a request for a valid
  stage always gets an answer.
- Intent is a ranking boost, not a hard filter (a hard filter returned only two
  chunks for connect + conversation_ideas).
- No model download, no PyTorch, no FAISS, no Google Drive paths: the knowledge
  base has 86 short chunks, so a small TF-IDF ranker is enough and keeps the
  Docker image and CI light. The retrieve() signature is unchanged, so an
  embedding ranker can replace the scoring later.
"""
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

KB_PATH = Path(__file__).parent / "knowledge_base" / "kb_chunks.json"

STAGES = {"connect", "understand", "reflect", "discuss", "agree",
          "family", "reflect_again", "decision"}

# Score boosts (added to the cosine similarity, which is usually 0.0 - 0.4).
INTENT_MATCH_BOOST = 0.30      # chunk intent equals the requested intent
STAGE_SPECIFIC_BOOST = 0.05    # chunk belongs to the stage, not "global"
PRIVACY_BOOST = 0.15           # privacy words in the query -> privacy/safety chunks
RISK_BOOST = 0.60              # prediction / decision-for-me requests -> safety rules
MAX_PER_TOPIC = 2              # keep results varied
GLOBAL_PENALTY = 0.15          # global chunks are filler unless the query is about privacy/safety

PRIVACY_WORDS = {
    "salary", "income", "dob", "birth", "contact", "phone", "number", "private",
    "privacy", "safe", "safety", "share", "shared", "consent", "password", "see",
    "visible", "data", "photo", "pressured", "judged", "report", "block",
}
RISK_PATTERNS = [
    re.compile(r"\bpredict|\bwill (it|this|we)\b.*\b(work|last|succeed)|\bsucceed|\bguarantee"
               r"|\bwork out\b", re.I),
    re.compile(r"\bdecide for\b|\bchoose for me\b|\btell me (what|whether) to\b"
               r"|\bshould i (say yes|say no|marry|accept|reject|leave|continue)\b", re.I),
]

STOPWORDS = set("""a an the and or of to in on for with is are was were be been it its this that these those
i me my we our us you your they them their he she his her do does did can could should would will
what how when where why who which if then than so as at by from about into not no yes just""".split())


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return [_stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


class _Index:
    def __init__(self, chunks: List[Dict]):
        self.chunks = chunks
        docs = [_tokens(f"{c['topic'].replace('_', ' ')} {c['text']}") for c in chunks]
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (f + 1)) + 1.0 for t, f in df.items()}
        self.vectors = [self._vector(d) for d in docs]

    def _vector(self, tokens: List[str]) -> Dict[str, float]:
        counts = Counter(tokens)
        vec = {t: (1.0 + math.log(c)) * self.idf.get(t, 1.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def similarity(self, query_vec: Dict[str, float], i: int) -> float:
        doc = self.vectors[i]
        return sum(w * doc.get(t, 0.0) for t, w in query_vec.items())


_index: Optional[_Index] = None


def _get_index() -> _Index:
    global _index
    if _index is None:
        with open(KB_PATH, encoding="utf-8") as f:
            _index = _Index(json.load(f))
    return _index


def retrieve(query: str, stage: str, intent: Optional[str] = None, k: int = 3) -> List[Dict]:
    """Return up to k chunks for this stage (plus global safety/privacy chunks).

    Each result is the knowledge-base chunk plus a "score". Results are
    deterministic: ties are broken by chunk_id.
    """
    if stage not in STAGES and stage != "global":
        raise ValueError(f"unknown stage: {stage!r}")
    idx = _get_index()
    q_text = query or ""
    q_tokens = _tokens(q_text)
    q_vec = idx._vector(q_tokens) if q_tokens else {}
    privacy_hit = any(t in PRIVACY_WORDS for t in re.findall(r"[a-z]+", q_text.lower()))
    risk_hit = any(p.search(q_text) for p in RISK_PATTERNS)

    scored = []
    for i, chunk in enumerate(idx.chunks):
        if chunk["stage"] not in (stage, "global"):
            continue
        score = idx.similarity(q_vec, i) if q_vec else 0.0
        if intent and chunk["intent"] == intent:
            score += INTENT_MATCH_BOOST
        if chunk["stage"] == stage:
            score += STAGE_SPECIFIC_BOOST
        elif not (privacy_hit or risk_hit or intent == "privacy_safety"):
            score -= GLOBAL_PENALTY
        if privacy_hit and chunk["topic"] in ("privacy_consent", "safety"):
            score += PRIVACY_BOOST
        if risk_hit and chunk["topic"] == "safety" and re.search(
                r"predict|decid|decision|judge", chunk["text"], re.I):
            score += RISK_BOOST
        scored.append((score, chunk))

    scored.sort(key=lambda sc: (-sc[0], sc[1]["chunk_id"]))

    # Keep the answer varied: at most MAX_PER_TOPIC chunks of the same topic,
    # unless that would leave fewer than k results.
    picked, topic_count = [], Counter()
    for score, chunk in scored:
        if topic_count[chunk["topic"]] < MAX_PER_TOPIC:
            picked.append((score, chunk))
            topic_count[chunk["topic"]] += 1
        if len(picked) == k:
            break
    if len(picked) < k:
        for item in scored:
            if item not in picked:
                picked.append(item)
            if len(picked) == k:
                break
    return [{**chunk, "score": round(score, 4)} for score, chunk in picked]


def retrieve_for_orchestrator(intent, ctx: dict, query: str, k: int = 3) -> List[dict]:
    """Adapter for app.core.orchestrator.retrieve(intent, ctx, query).

    Returns [{"id", "text", "topic", "source"}], the chunk format the
    orchestrator expects. `intent` may be an Intent enum or a plain string.
    """
    stage = (ctx or {}).get("stage") or "connect"
    intent_value = getattr(intent, "value", intent)
    hits = retrieve(query, stage, intent_value, k=k)
    return [{"id": h["chunk_id"], "text": h["text"], "topic": h["topic"], "source": h["source"]}
            for h in hits]
