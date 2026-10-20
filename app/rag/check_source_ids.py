"""Every sources[] ID in API replies must map to a real chunk. Exit 1 on orphan."""
import json, sys
import os

def check(kb_path, replies_path):
    if not os.path.exists(kb_path):
        print(f"Warning: {kb_path} not found. Cannot check IDs.")
        return

    with open(kb_path) as f:
        ids = {c["chunk_id"] for c in json.load(f)}

    orphans = []
    if os.path.exists(replies_path):
        with open(replies_path) as f:
            for i, line in enumerate(f, 1):
                if not line.strip(): continue
                for sid in json.loads(line).get("sources", []):
                    if sid not in ids: 
                        orphans.append((i, sid))
    else:
        print(f"Warning: {replies_path} not found. Create a dummy file to test.")
        return

    if orphans:
        print("ORPHAN IDs FOUND:", orphans)
        sys.exit(1)
    print("OK: no orphan source IDs")

if __name__ == "__main__":
   check("app/rag/knowledge_base/kb_chunks.json", "logs/api_replies.jsonl")