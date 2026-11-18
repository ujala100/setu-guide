"""Runs the evaluation and ensures every returned chunk has a valid source."""
import json
import os
import sys
from app.rag.eval_retrieval import TEST_CASES
from app.rag.retriever import retrieve

KB_PATH = "app/rag/knowledge_base/kb_chunks.json"

def check():
    if not os.path.exists(KB_PATH):
        print(f"Error: {KB_PATH} not found. Failing.")
        sys.exit(1)

    with open(KB_PATH, "r", encoding="utf-8") as f:
        valid_ids = {c["chunk_id"] for c in json.load(f)}

    print("Running evaluation to check source IDs...")
    orphans = []
    
    for case in TEST_CASES:
        results = retrieve(case["query"], case["stage"], case["intent"], k=3)
        for r in results:
            if r["chunk_id"] not in valid_ids:
                orphans.append(r["chunk_id"])

    if orphans:
        print(f"ERROR: Found orphan chunk IDs: {orphans}")
        sys.exit(1)
        
    print("OK: All chunks returned by evaluation map to real KB source IDs.")

if __name__ == "__main__":
    check()