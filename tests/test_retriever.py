import json
from pathlib import Path

import pytest

from app.rag.retriever import KB_PATH, STAGES, retrieve, retrieve_for_orchestrator

CASES_DIR = Path(__file__).resolve().parents[1] / "eval" / "retrieval"
INTENTS = ["conversation_ideas", "help_me_understand", "next_steps", "privacy_safety"]


def _cases(name):
    return json.loads((CASES_DIR / name).read_text(encoding="utf-8"))["cases"]


def _hit_rate(cases):
    hits = sum(any(r["topic"] in c["expect_topics"]
                   for r in retrieve(c["q"], c["stage"], c["intent"], k=3)) for c in cases)
    return hits / len(cases)


def test_kb_is_valid():
    kb = json.loads(Path(KB_PATH).read_text(encoding="utf-8"))
    assert len(kb) >= 80
    ids = [c["chunk_id"] for c in kb]
    assert len(ids) == len(set(ids))
    for c in kb:
        assert {"chunk_id", "stage", "topic", "intent", "text", "source"} <= set(c)
        assert c["text"].strip()
        assert c["stage"] in STAGES | {"global"}
        assert c["intent"] in INTENTS


@pytest.mark.parametrize("stage", sorted(STAGES))
@pytest.mark.parametrize("intent", INTENTS)
def test_every_stage_and_intent_returns_results_from_that_stage(stage, intent):
    results = retrieve("anything", stage, intent, k=3)
    assert len(results) == 3
    assert all(r["stage"] in (stage, "global") for r in results)


def test_empty_and_odd_queries_do_not_crash():
    for q in ("", "   ", "???", "नमस्ते", "a" * 5000):
        assert len(retrieve(q, "connect", "next_steps", k=3)) == 3


def test_unknown_stage_raises():
    with pytest.raises(ValueError):
        retrieve("hi", "teleport", "next_steps")


def test_results_are_deterministic():
    runs = [[r["chunk_id"] for r in retrieve("what should I ask on a first call", "connect",
                                              "conversation_ideas")] for _ in range(5)]
    assert all(r == runs[0] for r in runs)


def test_k_is_respected():
    assert len(retrieve("privacy", "family", "privacy_safety", k=1)) == 1
    assert len(retrieve("privacy", "family", "privacy_safety", k=5)) == 5


def test_prediction_and_decision_requests_return_safety_rules():
    for q in ("can you predict if we will succeed", "should I say yes", "decide for me"):
        topics = [r["topic"] for r in retrieve(q, "decision", "help_me_understand", k=3)]
        assert "safety" in topics, q


def test_dev_and_heldout_hit_rates():
    # Label-based check only. A real relevance review is still needed.
    assert _hit_rate(_cases("dev_cases.json")) >= 0.90
    assert _hit_rate(_cases("heldout_cases.json")) >= 0.90


def test_orchestrator_adapter_shape():
    out = retrieve_for_orchestrator("next_steps", {"stage": "discuss"}, "what now", k=3)
    assert len(out) == 3
    assert all(set(c) == {"id", "text", "topic", "source"} for c in out)
    assert retrieve_for_orchestrator("next_steps", {}, "what now")  # missing stage -> connect
