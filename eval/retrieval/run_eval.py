"""Run: python eval/retrieval/run_eval.py   (from the repo root)
Prints topic-hit rate for the dev and held-out case files. Topic hit = an expected
topic appears in the top-3 chunks. This checks labels only, not answer quality."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.rag.retriever import retrieve  # noqa: E402


def run(name):
    cases = json.loads((Path(__file__).parent / name).read_text(encoding="utf-8"))["cases"]
    hits, empty, misses = 0, 0, []
    for c in cases:
        got = retrieve(c["q"], c["stage"], c["intent"], k=3)
        topics = [g["topic"] for g in got]
        empty += not got
        if any(t in topics for t in c["expect_topics"]):
            hits += 1
        else:
            misses.append((c["q"], c["stage"], c["intent"], c["expect_topics"], topics))
    print(f"{name}: {hits}/{len(cases)} = {hits / len(cases):.1%}   empty results: {empty}")
    for m in misses:
        print("   MISS", m)
    return hits / len(cases)


if __name__ == "__main__":
    run("dev_cases.json")
    run("heldout_cases.json")
