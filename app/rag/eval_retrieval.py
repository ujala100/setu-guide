"""Evaluate the real retriever. Usage: python -m app.rag.eval_retrieval"""
import json
import subprocess
from collections import defaultdict
from app.rag.retriever import retrieve

# 20 Hand-written cases based on KB topics
TEST_CASES = [
    {"stage": "connect", "intent": "conversation_ideas", "query": "how to start a chat"},
    {"stage": "connect", "intent": "help_me_understand", "query": "what should I ask"},
    {"stage": "understand", "intent": "conversation_ideas", "query": "family background"},
    {"stage": "understand", "intent": "privacy_safety", "query": "is my income private"},
    {"stage": "understand", "intent": "next_steps", "query": "what happens next"},
    {"stage": "reflect", "intent": "conversation_ideas", "query": "values and goals"},
    {"stage": "reflect", "intent": "help_me_understand", "query": "am I ready"},
    {"stage": "discuss", "intent": "conversation_ideas", "query": "career plans"},
    {"stage": "discuss", "intent": "privacy_safety", "query": "who sees this"},
    {"stage": "agree", "intent": "next_steps", "query": "how to agree"},
    {"stage": "agree", "intent": "conversation_ideas", "query": "lifestyle match"},
    {"stage": "family", "intent": "conversation_ideas", "query": "talking to parents"},
    {"stage": "family", "intent": "privacy_safety", "query": "family pressure"},
    {"stage": "reflect_again", "intent": "help_me_understand", "query": "second thoughts"},
    {"stage": "reflect_again", "intent": "conversation_ideas", "query": "what to ask again"},
    {"stage": "decision", "intent": "next_steps", "query": "final decision"},
    {"stage": "decision", "intent": "privacy_safety", "query": "can I withdraw"},
    {"stage": "decision", "intent": "help_me_understand", "query": "is this right"},
    {"stage": "global", "intent": "privacy_safety", "query": "data privacy"},
    {"stage": "connect", "intent": "conversation_ideas", "query": "predict our future"}, 
]

def get_git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("utf-8").strip()
    except:
        return "unknown"

def run_eval():
    sha = get_git_sha()
    print(f"\n=== Retrieval Evaluation (Commit: {sha}) ===\n")
    print(f"{'Stage/Intent':<30} | {'Hit Rate':<10} | {'Wrong Stage':<12} | {'Irrelevant':<10}")
    print("-" * 70)

    stats = defaultdict(lambda: {"total": 0, "hits": 0, "wrong_stage": 0, "irrelevant": 0})

    for case in TEST_CASES:
        key = f"{case['stage']}/{case['intent']}"
        stats[key]["total"] += 1
        
        results = retrieve(case["query"], case["stage"], case["intent"], k=3)
        
        if len(results) > 0:
            stats[key]["hits"] += 1
            
        for r in results:
            if r["stage"] != case["stage"] and r["stage"] != "global":
                stats[key]["wrong_stage"] += 1
            if r["intent"] != case["intent"]:
                stats[key]["irrelevant"] += 1

    for key, data in sorted(stats.items()):
        hit_rate = (data["hits"] / data["total"]) * 100 if data["total"] > 0 else 0
        print(f"{key:<30} | {hit_rate:>8.1f}% | {data['wrong_stage']:>12} | {data['irrelevant']:>10}")

if __name__ == "__main__":
    run_eval()