
import json
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.core.llm_provider import GeminiLLMProvider
from app.core.pipeline import load_prompt
from app.core.responder import validate_response


# Benchmark configuration
MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

REPETITIONS = 3
TIMEOUT_SECONDS = 30

SUCCESS_DELAY_SECONDS = 12
FAILURE_COOLDOWN_SECONDS = 20
MAX_CONSECUTIVE_FAILURES = 3

SCENARIO_SOURCE = (
    "teammate/data/scenarios-v1:data/scenarios_v1.json"
)

# Six scenarios approved for the reduced benchmark
SAMPLE_SCENARIO_IDS = [
    "s01",
    "s02",
    "s03",
    "s04",
    "f06",
    "f08",
]

OUTPUT_DIR = ROOT / "eval"
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = (
    OUTPUT_DIR /
    "gemini_benchmark_sample_6scenarios_20261106.json"
)


def load_official_scenarios():
    """Load selected scenarios from the official Setu Guide dataset."""

    result = subprocess.run(
        ["git", "show", SCENARIO_SOURCE],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    data = json.loads(result.stdout)
    all_cases = data["cases"]

    cases_by_id = {
        case["id"]: case
        for case in all_cases
    }

    missing_ids = [
        sid for sid in SAMPLE_SCENARIO_IDS
        if sid not in cases_by_id
    ]

    if missing_ids:
        raise SystemExit(
            f"Missing official scenario IDs: {missing_ids}"
        )

    return [
        cases_by_id[sid]
        for sid in SAMPLE_SCENARIO_IDS
    ]


def build_summary(results):
    """Calculate latency, reliability and response consistency."""

    summary = {}
    consistency = {}

    for model in MODELS:

        model_results = [
            r for r in results
            if r["model"] == model
        ]

        successful = [
            r for r in model_results
            if r["success"]
        ]

        valid_results = [
            r for r in model_results
            if r["valid_response"]
        ]

        summary[model] = {
            "total_requests": len(model_results),

            "successful_requests": len(successful),

            "failed_requests": (
                len(model_results) - len(successful)
            ),

            "failure_rate_percent": round(
                100 * (
                    len(model_results) - len(successful)
                ) / len(model_results),
                2,
            ) if model_results else None,

            "average_latency_all_seconds": round(
                mean(
                    r["latency_seconds"]
                    for r in model_results
                ),
                3,
            ) if model_results else None,

            "average_latency_success_seconds": round(
                mean(
                    r["latency_seconds"]
                    for r in successful
                ),
                3,
            ) if successful else None,

            "valid_responses": len(valid_results),

            "intent_matches": sum(
                bool(r["intent_match"])
                for r in model_results
            ),
        }

        # Group results by scenario
        scenario_groups = defaultdict(list)

        for record in model_results:
            scenario_groups[
                record["scenario_id"]
            ].append(record)

        complete_groups = [
            records
            for records in scenario_groups.values()
            if len(records) == REPETITIONS
        ]

        exact_response_matches = 0
        response_count_consistent = 0

        for records in complete_groups:

            if all(
                r["valid_response"]
                for r in records
            ):

                normalized = [
                    json.dumps(
                        r["response"],
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                    for r in records
                ]

                if len(set(normalized)) == 1:
                    exact_response_matches += 1

                counts = [
                    len(
                        r["response"].get(
                            "response", []
                        )
                    )
                    for r in records
                ]

                if len(set(counts)) == 1:
                    response_count_consistent += 1

        consistency[model] = {
            "scenarios_tested": len(scenario_groups),

            "scenarios_with_all_repetitions": (
                len(complete_groups)
            ),

            "scenarios_valid_in_all_runs": sum(
                len(records) == REPETITIONS
                and all(
                    r["valid_response"]
                    for r in records
                )
                for records in scenario_groups.values()
            ),

            "scenarios_intent_matched_in_all_runs": sum(
                len(records) == REPETITIONS
                and all(
                    r["intent_match"]
                    for r in records
                )
                for records in scenario_groups.values()
            ),

            "scenarios_with_consistent_response_count": (
                response_count_consistent
            ),

            "scenarios_with_exact_same_response_all_runs": (
                exact_response_matches
            ),
        }

    return summary, consistency


def main():

    settings = get_settings()

    if not settings.gemini_api_key:
        raise SystemExit(
            "GEMINI_API_KEY is missing."
        )

    cases = load_official_scenarios()

    if len(cases) != len(SAMPLE_SCENARIO_IDS):
        raise SystemExit(
            f"Expected {len(SAMPLE_SCENARIO_IDS)} "
            f"selected scenarios, found {len(cases)}."
        )

    total_requests = (
        len(cases) * REPETITIONS * len(MODELS)
    )

    # Resume existing sample report if available.
    if OUTPUT_FILE.exists():

        report = json.loads(
            OUTPUT_FILE.read_text(
                encoding="utf-8"
            )
        )

        expected_config = {
            "benchmark_type": (
                "official_setu_guide_reduced_sample"
            ),
            "scenario_source": SCENARIO_SOURCE,
            "scenario_count": len(cases),
            "scenario_ids": SAMPLE_SCENARIO_IDS,
            "repetitions_per_model": REPETITIONS,
            "models": MODELS,
            "total_planned_requests": total_requests,
        }

        for key, expected_value in expected_config.items():

            if report.get(key) != expected_value:
                raise SystemExit(
                    f"Existing sample report has "
                    f"mismatched {key}. "
                    "It was not modified."
                )

        results = report.get("results", [])

    else:

        results = []

        report = {
            "benchmark_type": (
                "official_setu_guide_reduced_sample"
            ),

            "scenario_source": SCENARIO_SOURCE,

            "created_at_utc": (
                datetime.now(timezone.utc).isoformat()
            ),

            "scenario_count": len(cases),

            "scenario_ids": SAMPLE_SCENARIO_IDS,

            "repetitions_per_model": REPETITIONS,

            "timeout_seconds": TIMEOUT_SECONDS,

            "success_delay_seconds": SUCCESS_DELAY_SECONDS,

            "failure_cooldown_seconds": (
                FAILURE_COOLDOWN_SECONDS
            ),

            "total_planned_requests": total_requests,

            "models": MODELS,

            "summary": {},

            "consistency": {},

            "results": results,
        }

    # Identify already completed requests.
    completed_keys = {
        (
            r["scenario_id"],
            r["repetition"],
            r["model"],
        )
        for r in results
    }

    if len(completed_keys) != len(results):
        raise SystemExit(
            "Duplicate scenario/model/repetition "
            "records found. Stopping safely."
        )

    if len(completed_keys) > total_requests:
        raise SystemExit(
            "Existing report contains more requests "
            "than planned. Stopping safely."
        )

    provider = GeminiLLMProvider()

    def save_report():

        summary, consistency = build_summary(results)

        report["summary"] = summary

        report["consistency"] = consistency

        report["completed_requests"] = len(results)

        report["remaining_requests"] = (
            total_requests - len(results)
        )

        temp_file = OUTPUT_FILE.with_name(
            OUTPUT_FILE.name + ".tmp"
        )

        temp_file.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temp_file.replace(OUTPUT_FILE)

    print(
        "\nStarting / resuming reduced Gemini benchmark",
        flush=True,
    )

    print(
        "Official scenario IDs:",
        ", ".join(SAMPLE_SCENARIO_IDS),
        flush=True,
    )

    print(
        "Models:",
        ", ".join(MODELS),
        flush=True,
    )

    print(
        "Repetitions per model:",
        REPETITIONS,
        flush=True,
    )

    print(
        "Total planned requests:",
        total_requests,
        flush=True,
    )

    print(
        "Already completed:",
        len(completed_keys),
        flush=True,
    )

    print(
        "Remaining:",
        total_requests - len(completed_keys),
        flush=True,
    )

    print(
        "Delay after success:",
        SUCCESS_DELAY_SECONDS,
        "seconds",
        flush=True,
    )

    print(
        "Cooldown after failure:",
        FAILURE_COOLDOWN_SECONDS,
        "seconds",
        flush=True,
    )

    print(
        "Report:",
        OUTPUT_FILE,
        "\n",
        flush=True,
    )

    request_number = len(results)

    consecutive_failures = 0

    stopped_early = False

    try:

        for repetition in range(
            1,
            REPETITIONS + 1
        ):

            for case_index, case in enumerate(cases):

                expected_intent = case.get(
                    "expected_intent",
                    case.get("intent"),
                )

                if not expected_intent:
                    raise SystemExit(
                        f"Missing expected intent "
                        f"for {case.get('id')}"
                    )

                if (
                    repetition + case_index
                ) % 2 == 0:

                    model_order = MODELS

                else:

                    model_order = list(
                        reversed(MODELS)
                    )

                for model in model_order:

                    key = (
                        case["id"],
                        repetition,
                        model,
                    )

                    # Skip requests already saved.
                    if key in completed_keys:
                        continue

                    request_number += 1

                    prompt = load_prompt(
                        intent=expected_intent,
                        user_message=case["q"].strip(),
                        journey_stage=case["stage"],
                        retrieved_context="",
                    )

                    provider.model = model

                    print(
                        f"\nStarting "
                        f"{request_number}/{total_requests} | "
                        f"{case['id']} | Run {repetition} | "
                        f"{model}",
                        flush=True,
                    )

                    start = time.perf_counter()

                    result = None
                    error = None

                    try:

                        result = provider.generate(
                            prompt,
                            timeout=TIMEOUT_SECONDS,
                        )

                    except Exception as exc:

                        error = (
                            f"{type(exc).__name__}: "
                            f"{str(exc)[:250]}"
                        )

                    elapsed = (
                        time.perf_counter() - start
                    )

                    valid = validate_response(result)

                    intent_match = bool(
                        valid
                        and result.get("intent")
                        == expected_intent
                    )

                    if result is None and error is None:
                        error = "Provider returned no response"

                    record = {
                        "request": request_number,

                        "scenario_id": case["id"],

                        "input_type": case["input_type"],

                        "language": case["language"],

                        "repetition": repetition,

                        "model": model,

                        "scenario": case["q"].strip(),

                        "stage": case["stage"],

                        "expected_intent": expected_intent,

                        "latency_seconds": round(
                            elapsed,
                            3,
                        ),

                        "success": (
                            result is not None
                            and error is None
                        ),

                        "valid_response": bool(valid),

                        "intent_match": intent_match,

                        "error": error,

                        "response": result,
                    }

                    results.append(record)

                    completed_keys.add(key)

                    # Save after each request.
                    save_report()

                    print(
                        f"{request_number}/{total_requests} | "
                        f"{case['id']} | Run {repetition} | "
                        f"{model} | {elapsed:.2f}s | "
                        f"valid={valid} | "
                        f"intent_match={intent_match} | "
                        f"error={error}",
                        flush=True,
                    )

                    if result is None or error is not None:

                        consecutive_failures += 1

                        print(
                            "Request failed. Cooling down "
                            f"for {FAILURE_COOLDOWN_SECONDS} seconds.",
                            flush=True,
                        )

                        time.sleep(
                            FAILURE_COOLDOWN_SECONDS
                        )

                        if (
                            consecutive_failures
                            >= MAX_CONSECUTIVE_FAILURES
                        ):

                            print(
                                "Stopping after three consecutive "
                                "failures. Progress saved.",
                                flush=True,
                            )

                            stopped_early = True
                            break

                    else:

                        consecutive_failures = 0

                        if (
                            len(completed_keys)
                            < total_requests
                        ):

                            time.sleep(
                                SUCCESS_DELAY_SECONDS
                            )

                if stopped_early:
                    break

            if stopped_early:
                break

    except KeyboardInterrupt:

        save_report()

        print(
            "\nInterrupted by user. "
            "Completed results were saved.",
            flush=True,
        )

        return

    save_report()

    print("\nCURRENT BENCHMARK SUMMARY")

    print(
        json.dumps(
            report["summary"],
            indent=2,
        )
    )

    print("\nRESPONSE CONSISTENCY SUMMARY")

    print(
        json.dumps(
            report["consistency"],
            indent=2,
        )
    )

    print(
        "\nCompleted requests:",
        len(results),
        "/",
        total_requests,
    )

    print(
        "Report saved to:",
        OUTPUT_FILE,
    )

    if stopped_early:

        print(
            "Benchmark stopped after consecutive "
            "failures. Run again to resume."
        )

    elif len(completed_keys) == total_requests:

        print(
            "REDUCED-SAMPLE BENCHMARK COMPLETED."
        )

    else:

        print(
            "Benchmark has remaining requests."
        )


if __name__ == "__main__":
    main()
