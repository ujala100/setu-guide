"""Measure retrieval quality: hit rate, wrong-stage chunks, irrelevant chunks.
Usage: python -m app.rag.eval_retrieval --kb kb/v2.json --tests data/retrieval_cases.jsonl
"""
import json
import argparse
import os
from collections import defaultdict

def load_cases(path):
    # If the test file doesn't exist, create a dummy one so it doesn't crash
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        dummy_cases = [
            {"query": "tell me about your family", "stage": "s2", "intent": "i1"},
            {"query": "kya aap income batate hain?", "stage": "s3", "intent": "i4"}
        ]
        with open(path, "w") as f:
            for c in dummy_cases:
                f.write(json.dumps(c) + "\n")
        print(f"Warning: {path} not found. Created a dummy file with 2 test cases.")
    
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

def is_relevant(chunk, case):
    # Safely check if tags exist to prevent KeyError
    tags = chunk.get("tags", {})
    stage_match = case["stage"] in tags.get("stage", [])
    intent_match = case["intent"] in tags.get("intent", [])
    return stage_match and intent_match

def retrieve(kb, query, stage, intent, top_k=4):
    # TODO: Plug in the actual RAG retrieval function from app/rag later
    return []

def run(kb_path, cases_path):
    # Safely handle missing KB file
    if not os.path.exists(kb_path):
        print(f"Warning: {kb_path} not found. Using empty KB for skeleton run.")
        kb = []
    else:
        with open(kb_path) as f:
            kb = json.load(f)
            
    cases = load_cases(cases_path)
    stats = defaultdict(lambda: {"total": 0, "hit": 0, "wrong_stage": 0, "irrelevant": 0})
    
    for c in cases:
        key = f"{c['stage']}/{c['intent']}"
        s = stats[key]
        s["total"] += 1
        res = retrieve(kb, c["query"], c["stage"], c["intent"])
        
        if any(is_relevant(r, c) for r in res): 
            s["hit"] += 1
        
        # Safely check tags for wrong stage
        s["wrong_stage"] += sum(1 for r in res if c["stage"] not in r.get("tags", {}).get("stage", []))
        s["irrelevant"] += sum(1 for r in res if not is_relevant(r, c))
        
    return stats

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="kb/v2.json")
    ap.add_argument("--tests", default="data/retrieval_cases.jsonl")
    a = ap.parse_args()
    
    print(f"{'stage/intent':<20}{'total':>6}{'hit_rate':>10}{'wrong_stage':>13}{'irrelevant':>12}")
    print("-" * 61)
    stats = run(a.kb, a.tests)
    
    for k, v in sorted(stats.items()):
        hr = v["hit"] / v["total"] if v["total"] else 0
        print(f"{k:<20}{v['total']:>6}{hr:>10.2f}{v['wrong_stage']:>13}{v['irrelevant']:>12}")