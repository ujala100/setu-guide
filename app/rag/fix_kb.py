import json

kb_path = "app/rag/knowledge_base/kb_chunks.json"

# Map stage numbers to stage words
stage_map = {
    "s1": "connect",
    "s2": "understand",
    "s3": "reflect",
    "s4": "discuss",
    "s5": "agree",
    "s6": "family",
    "s7": "reflect_again",
    "s8": "decision",
    "global": "global"
}

with open(kb_path, "r", encoding="utf-8") as f:
    old_kb = json.load(f)

new_kb = []

for c in old_kb:
    # Get data whether it's at the root or inside 'tags'
    tags = c.get("tags", {})
    
    def get_val(key):
        val = c.get(key) or tags.get(key)
        if isinstance(val, list) and len(val) > 0:
            return val[0]
        return val

    raw_stage = get_val("stage")
    raw_intent = get_val("intent")
    raw_topic = get_val("topic")
    raw_source = get_val("source")

    # Translate stage number to word
    final_stage = stage_map.get(raw_stage, "connect")

    new_chunk = {
        "chunk_id": c.get("chunk_id", "unknown"),
        "stage": final_stage,             # Now a string like "connect"
        "topic": raw_topic or "general",  # Now a string like "privacy"
        "intent": raw_intent or "all",    # Now a string like "conversation_ideas"
        "text": c.get("text", ""),
        "source": raw_source or "roadmap",
        "status": "verified"              # So the retriever accepts it
    }
    new_kb.append(new_chunk)

with open(kb_path, "w", encoding="utf-8") as f:
    json.dump(new_kb, f, ensure_ascii=False, indent=2)

print("Successfully fixed the KB format!")