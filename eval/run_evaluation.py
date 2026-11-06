"""Deterministic evaluation for the Sambandh Setu intent responder.

Run from the repository root:
    python eval/run_evaluation.py

This script does not call a live LLM or consume API credits.
"""

import json
from collections import Counter
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.router import route_intent
from app.core.responder import SUPPORTED_INTENTS, create_response, validate_response


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "eval" / "evaluation-results.json"

ROUTER_CASES = [
    ("What can we talk about?", "conversation_ideas"),
    ("Give us some conversation ideas", "conversation_ideas"),
    ("What questions can we ask each other?", "conversation_ideas"),
    ("What topics should we discuss?", "conversation_ideas"),
    ("Hum kya baat karein?", "conversation_ideas"),
    ("Em matladali?", "conversation_ideas"),
    ("Can you explain this to me?", "help_me_understand"),
    ("I don't understand what this means", "help_me_understand"),
    ("Please clarify this topic", "help_me_understand"),
    ("Mujhe samjhao", "help_me_understand"),
    ("Ardham kaaledu", "help_me_understand"),
    ("What does this mean?", "help_me_understand"),
    ("What should we discuss next?", "next_steps"),
    ("What are the next steps?", "next_steps"),
    ("Where do we go from here?", "next_steps"),
    ("Ab kya karein?", "next_steps"),
    ("Next em cheyyali?", "next_steps"),
    ("Ippudu em cheyyali?", "next_steps"),
    ("Is my information private?", "privacy_safety"),
    ("Who can see my information?", "privacy_safety"),
    ("Is this safe to share?", "privacy_safety"),
    ("Meri information kaun dekh sakta hai?", "privacy_safety"),
    ("Privacy gurinchi cheppandi", "privacy_safety"),
    ("Should I share my personal details?", "privacy_safety"),
    ("Hello, I have a question.", None),
    ("Tell me something interesting.", None),
    ("What is the weather today?", None),
    ("I like watching movies.", None),
    ("12345", None),
    ("", None),
    ("   ", None),
    ("Tell me a joke", None),
]

MALFORMED_JSON_CASES = [
    "",
    "{",
    '{"intent": "conversation_ideas", "response": ',
    "```json\n{}\n```",
    '{"intent": "conversation_ideas", "response": []} trailing text',
]


def run_router_evaluation():
    rows = []
    correct = 0

    for message, expected in ROUTER_CASES:
        actual = route_intent(message)
        passed = actual == expected
        correct += int(passed)
        rows.append({
            "message": message,
            "expected": expected,
            "actual": actual,
            "passed": passed,
        })

    return {
        "total": len(rows),
        "correct": correct,
        "accuracy_percent": round(correct * 100 / len(rows), 2),
        "failures": [row for row in rows if not row["passed"]],
    }


def run_schema_evaluation():
    valid_total = 0
    valid_passed = 0
    invalid_total = 0
    invalid_rejected = 0
    cases = []

    # 120 valid object/JSON round-trip cases: 30 per supported intent.
    for intent in sorted(SUPPORTED_INTENTS):
        for index in range(30):
            candidate = {
                "intent": intent,
                "response": [
                    f"Evaluation response {index + 1} for {intent}.",
                    "A second concise response item.",
                ],
            }

            encoded = json.dumps(candidate, ensure_ascii=False)
            try:
                decoded = json.loads(encoded)
                passed = validate_response(decoded)
            except (json.JSONDecodeError, TypeError, ValueError):
                passed = False

            valid_total += 1
            valid_passed += int(passed)
            cases.append({
                "case": f"valid_{intent}_{index + 1}",
                "expected_valid": True,
                "passed": passed,
            })

    # Invalid objects cover missing fields, wrong types, unsupported intents,
    # empty content, and non-string response items.
    invalid_candidates = [
        None,
        [],
        "not an object",
        {},
        {"response": ["Missing intent"]},
        {"intent": "conversation_ideas"},
        {"intent": "unknown_intent", "response": ["Unsupported intent"]},
        {"intent": "conversation_ideas", "response": "Must be a list"},
        {"intent": "conversation_ideas", "response": []},
        {"intent": "conversation_ideas", "response": [123]},
        {"intent": "conversation_ideas", "response": [None]},
        {"intent": "conversation_ideas", "response": [True]},
        {"intent": "conversation_ideas", "response": [{}]},
        {"intent": None, "response": ["Invalid intent type"]},
        {"intent": "next_steps", "response": ["Valid", 5]},
        {"intent": "privacy_safety", "response": []},
        {"intent": "help_me_understand", "response": None},
        {"intent": "other", "response": ["Unsupported"]},
    ]

    # Repeat the set to exercise the validator across 180 invalid cases.
    for index in range(180):
        candidate = invalid_candidates[index % len(invalid_candidates)]
        passed = not validate_response(candidate)
        invalid_total += 1
        invalid_rejected += int(passed)
        cases.append({
            "case": f"invalid_{index + 1}",
            "expected_valid": False,
            "passed": passed,
        })

    malformed_json = []
    for raw in MALFORMED_JSON_CASES:
        try:
            json.loads(raw)
            rejected = False
        except (json.JSONDecodeError, TypeError, ValueError):
            rejected = True
        malformed_json.append({
            "input": raw,
            "malformed_json_rejected": rejected,
        })

    return {
        "valid_cases": {
            "total": valid_total,
            "passed": valid_passed,
            "pass_percent": round(valid_passed * 100 / valid_total, 2),
        },
        "invalid_cases": {
            "total": invalid_total,
            "rejected": invalid_rejected,
            "rejection_percent": round(
                invalid_rejected * 100 / invalid_total, 2
            ),
        },
        "malformed_json_cases": {
            "total": len(malformed_json),
            "rejected": sum(
                item["malformed_json_rejected"] for item in malformed_json
            ),
            "results": malformed_json,
        },
        "case_failures": [case for case in cases if not case["passed"]],
    }


def run_fallback_evaluation():
    results = {}
    for intent in sorted(SUPPORTED_INTENTS):
        response = create_response(intent, "Evaluation input")
        results[intent] = {
            "valid": validate_response(response),
            "response": response,
        }

    return {
        "total": len(results),
        "valid": sum(item["valid"] for item in results.values()),
        "results": results,
    }


def main():
    report = {
        "evaluation_type": "deterministic; no live LLM calls",
        "router": run_router_evaluation(),
        "schema_validation": run_schema_evaluation(),
        "fallback_templates": run_fallback_evaluation(),
        "limitations": [
            "Synthetic schema cases test the validator, not live model output.",
            "Router accuracy is measured only on the labelled cases in this script.",
            "Relevance, five-run consistency, provider comparison, and token costs "
            "require separate evaluation.",
            "Safety cases here do not replace a full human-reviewed red-team test.",
        ],
    }

    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "results_file": str(OUTPUT_PATH.relative_to(ROOT)),
        "router": {
            "total": report["router"]["total"],
            "correct": report["router"]["correct"],
            "accuracy_percent": report["router"]["accuracy_percent"],
            "failures": report["router"]["failures"],
        },
        "schema_validation": {
            "valid_cases": report["schema_validation"]["valid_cases"],
            "invalid_cases": report["schema_validation"]["invalid_cases"],
            "malformed_json_cases": {
                "total": report["schema_validation"]["malformed_json_cases"]["total"],
                "rejected": report["schema_validation"]["malformed_json_cases"]["rejected"],
            },
            "failures": report["schema_validation"]["case_failures"],
        },
        "fallback_templates": {
            "total": report["fallback_templates"]["total"],
            "valid": report["fallback_templates"]["valid"],
        },
    }, indent=2, ensure_ascii=False))

    if (
        report["schema_validation"]["valid_cases"]["passed"]
        != report["schema_validation"]["valid_cases"]["total"]
        or report["schema_validation"]["invalid_cases"]["rejected"]
        != report["schema_validation"]["invalid_cases"]["total"]
        or report["fallback_templates"]["valid"]
        != report["fallback_templates"]["total"]
    ):
        raise SystemExit("Evaluation failed: inspect the results above.")

    if report["router"]["failures"]:
        raise SystemExit("Router evaluation has failures: inspect the results above.")


if __name__ == "__main__":
    main()
