
import json
import time
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

SCENARIO_FILE = ROOT / "data" / "scenarios_v1.json"
REDTEAM_FILE = ROOT / "data" / "red_team_v1.json"
OUTPUT_FILE = ROOT / "eval" / "baseline_results.json"

BASE_URL = os.getenv("SETU_API_URL", "http://127.0.0.1:8000")
ENDPOINT = f"{BASE_URL}/v1/guide/chat"

REPETITIONS = 5

QUICK_ACTIONS = [
    "conversation_ideas",
    "help_me_understand",
    "next_steps",
    "privacy_safety"
]


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_commit_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True
        ).strip()
    except Exception:
        return "unavailable"



def api_request(payload):
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                time.sleep(1.1)
                return json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt < 5:
                retry_after = error.headers.get("Retry-After", "2")

                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = 2

                print(f"Rate limited. Retrying in {wait + 0.5:.1f}s...")
                time.sleep(wait + 0.5)
                continue

            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"API returned HTTP {error.code}: {body}"
            )

        except urllib.error.URLError as error:
            raise RuntimeError(
                f"Could not connect to API: {error.reason}"
            )

    raise RuntimeError("Maximum retries exceeded")


# --------------------------------------------------
# SCENARIO EVALUATION
# --------------------------------------------------

def evaluate_scenarios(cases):
    correct = 0
    total = 0
    failures = []

    for case in cases:
        payload = {
            "user_id": f"eval_{case['id']}",
            "match_id": f"match_{case['id']}",
            "stage": case["stage"],
            "message": case["q"]
        }

        # Structured cases explicitly supply their intent.
        if case.get("input_type") == "structured" and case.get("intent"):
            payload["intent"] = case["intent"]

        expected = case.get("expected_intent")

        if not expected:
            continue

        total += 1

        try:
            response = api_request(payload)
            actual = response.get("intent")

            if actual == expected:
                correct += 1
            else:
                failures.append({
                    "id": case["id"],
                    "expected": expected,
                    "actual": actual
                })

        except Exception as error:
            failures.append({
                "id": case["id"],
                "error": str(error)
            })

    accuracy = correct / total if total else 0

    return {
        "correct": correct,
        "total": total,
        "accuracy": round(accuracy, 4),
        "failures": failures
    }


# --------------------------------------------------
# RED-TEAM EVALUATION
# --------------------------------------------------

def evaluate_redteam(cases):
    passed = 0
    total = len(cases)
    failures = []
    category_results = defaultdict(lambda: {"passed": 0, "total": 0})

    for case in cases:
        expected = case["expected"]
        category = case["category"]

        category_results[category]["total"] += 1

        try:
            response = api_request(case["request"])

            safety = response.get("safety", {})

            actual_status = safety.get("status")
            actual_flags = safety.get("flags", [])

            status_correct = (
                actual_status == expected["safety_status"]
            )

            flag_correct = (
                expected["safety_flag"] in actual_flags
            )

            success = status_correct and flag_correct

            if success:
                passed += 1
                category_results[category]["passed"] += 1
            else:
                failures.append({
                    "id": case["id"],
                    "category": category,
                    "expected_status": expected["safety_status"],
                    "actual_status": actual_status,
                    "expected_flag": expected["safety_flag"],
                    "actual_flags": actual_flags
                })

        except Exception as error:
            failures.append({
                "id": case["id"],
                "category": category,
                "error": str(error)
            })

    pass_rate = passed / total if total else 0

    return {
        "passed": passed,
        "total": total,
        "pass_rate": round(pass_rate, 4),
        "category_results": dict(category_results),
        "failures": failures
    }


# --------------------------------------------------
# QUICK-ACTION CONSISTENCY
# --------------------------------------------------

def evaluate_consistency():
    results = {}

    for intent in QUICK_ACTIONS:
        observed_intents = []

        for run in range(REPETITIONS):
            payload = {
                "user_id": f"consistency_{intent}",
                "match_id": "consistency_match",
                "stage": "connect",
                "intent": intent
            }

            try:
                response = api_request(payload)
                observed_intents.append(response.get("intent"))

            except Exception as error:
                observed_intents.append(f"ERROR: {error}")

        consistent = (
            len(set(observed_intents)) == 1
            and observed_intents[0] == intent
        )

        results[intent] = {
            "runs": REPETITIONS,
            "observed_intents": observed_intents,
            "consistent": consistent
        }

    return results


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    print("\n========== SETU GUIDE EVALUATION ==========\n")

    scenarios_data = load_json(SCENARIO_FILE)
    redteam_data = load_json(REDTEAM_FILE)

    scenarios = scenarios_data["cases"]
    redteam = redteam_data

    print(f"Scenarios loaded: {len(scenarios)}")
    print(f"Red-team cases loaded: {len(redteam)}")

    # Check API availability.
    try:
        with urllib.request.urlopen(
            f"{BASE_URL}/health", timeout=10
        ) as response:
            print("API health:", response.status)
    except Exception as error:
        raise SystemExit(
            f"API unavailable. Start the server first.\n{error}"
        )

    # Run evaluations.
    scenario_results = evaluate_scenarios(scenarios)
    redteam_results = evaluate_redteam(redteam)
    consistency_results = evaluate_consistency()

    commit_sha = get_commit_sha()

    # Display metrics.
    print("\n========== RESULTS ==========")

    print(
        f"\nIntent accuracy: "
        f"{scenario_results['correct']}/{scenario_results['total']} "
        f"({scenario_results['accuracy']:.2%})"
    )

    print(
        f"Safety pass rate: "
        f"{redteam_results['passed']}/{redteam_results['total']} "
        f"({redteam_results['pass_rate']:.2%})"
    )

    print("\nQuick-action consistency:")

    for intent, result in consistency_results.items():
        status = "PASS" if result["consistent"] else "FAIL"
        print(f"{intent}: {status}")

    print(f"\nCommit SHA: {commit_sha}")

    # Save baseline.
    baseline = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "configuration": {
            "api_url": BASE_URL,
            "repetitions": REPETITIONS
        },
        "scenario_evaluation": scenario_results,
        "redteam_evaluation": redteam_results,
        "quick_action_consistency": consistency_results
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(baseline, file, indent=4)

    print(f"\nBaseline saved to: {OUTPUT_FILE}")
    print("\n========== EVALUATION COMPLETE ==========\n")
if __name__ == "__main__":
    main()