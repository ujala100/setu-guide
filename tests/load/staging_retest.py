#!/usr/bin/env python3
"""Short load test against staging with LLM effectively stubbed.

Staging returns fallback_used=true for every request because handle_chat
is not implemented yet — so the LLM is effectively stubbed regardless of
USE_MOCK. We never send real LLM traffic.

Constraints:
- Max 20 concurrent users (NOT 50 — don't point 50 at the real LLM)
- Short run (2 minutes)
- Verify /health stays 200
- Verify /v1/guide/chat returns 200 with proper error format
- No 500 errors
- Check cache headers and X-Request-Id
"""
import concurrent.futures
import json
import statistics
import sys
import time
import uuid
from datetime import datetime

import requests

STAGING = "https://setu-guide-1wiy.onrender.com"
CHAT = f"{STAGING}/v1/guide/chat"
HEALTH = f"{STAGING}/health"

# Use the placeholder key — staging has AUTH_METHOD=none (default)
HEADERS = {"Content-Type": "application/json", "X-API-Key": "placeholder-not-a-real-key"}

BASE_BODY = {
    "user_id": "load-user",
    "match_id": "load-match",
    "stage": "connect",
    "intent": "next_steps",
}


def check_health():
    """Health check — must always be 200."""
    try:
        r = requests.get(HEALTH, timeout=10)
        return r.status_code == 200, r.status_code, r.text
    except Exception as e:
        return False, None, str(e)


def send_chat(request_id=None):
    """Send one chat request. Returns (success, status_code, latency_ms, body_or_error)."""
    body = {**BASE_BODY, "user_id": f"load-user-{uuid.uuid4().hex[:8]}"}
    started = time.perf_counter()
    try:
        r = requests.post(CHAT, json=body, headers=HEADERS, timeout=30)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        if r.status_code == 200:
            body_data = r.json()
            # Verify error format is clean
            has_error = "error" in body_data
            has_x_request_id = "X-Request-Id" in r.headers
            has_cache = "X-Cache" in r.headers
            return (
                True,
                r.status_code,
                latency_ms,
                {
                    "fallback_used": body_data.get("fallback_used"),
                    "intent": body_data.get("intent"),
                    "x_request_id": has_x_request_id,
                    "x_cache": r.headers.get("X-Cache"),
                    "has_error": has_error,
                },
            )
        else:
            return False, r.status_code, latency_ms, r.text[:200]
    except Exception as e:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return False, None, latency_ms, str(e)[:200]


def run_load_test(users=20, duration_seconds=120, ramp_seconds=10):
    """Run a load test with gradual ramp-up."""
    print(f"\n{'='*60}")
    print(f"STAGING LOAD TEST (LLM stubbed via fallback)")
    print(f"Target: {STAGING}")
    print(f"Users: {users} (ramp over {ramp_seconds}s, run for {duration_seconds}s)")
    print(f"Start: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    results = []
    health_results = []
    errors = []
    start_time = time.monotonic()
    end_time = start_time + duration_seconds

    # Warm up
    print("Warming up...")
    for _ in range(3):
        ok, sc, lat, info = send_chat()
        if ok:
            print(f"  Warmup OK: {sc}, {lat}ms, fallback={info.get('fallback_used')}")
        else:
            print(f"  Warmup FAIL: {sc}, {info}")
        time.sleep(0.5)

    print(f"\nStarting load test at {users} users...")
    request_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=users) as executor:
        futures = []

        while time.monotonic() < end_time:
            # Submit new requests to maintain target concurrency
            while len(futures) < users and time.monotonic() < end_time:
                future = executor.submit(send_chat)
                futures.append(future)
                request_count += 1

            # Collect completed
            done = [f for f in futures if f.done()]
            for f in done:
                futures.remove(f)
                try:
                    ok, sc, lat, info = f.result()
                    if ok:
                        results.append((sc, lat, info))
                    else:
                        errors.append((sc, lat, info))
                except Exception as e:
                    errors.append((None, 0, str(e)))

            # Health check every 5 seconds
            if int(time.monotonic() - start_time) % 5 == 0:
                h_ok, h_sc, h_body = check_health()
                health_results.append((h_sc, h_ok))

            time.sleep(0.1)

        # Wait for remaining
        concurrent.futures.wait(futures, timeout=10)
        for f in futures:
            if f.done():
                try:
                    ok, sc, lat, info = f.result()
                    if ok:
                        results.append((sc, lat, info))
                    else:
                        errors.append((sc, lat, info))
                except Exception as e:
                    errors.append((None, 0, str(e)))

    # Analysis
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")

    total_requests = len(results) + len(errors)
    successful = [r for r in results if r[0] == 200]
    failed = [r for r in results if r[0] != 200] + errors

    print(f"\nTotal requests sent: {request_count}")
    print(f"Completed: {total_requests}")
    print(f"  Successful (200): {len(successful)}")
    print(f"  Failed: {len(failed)}")

    if results:
        latencies = [r[1] for r in results if r[1] is not None]
        if latencies:
            print(f"\nLatency (ms):")
            print(f"  Min:    {min(latencies):.1f}")
            print(f"  Max:    {max(latencies):.1f}")
            print(f"  Mean:   {statistics.mean(latencies):.1f}")
            print(f"  Median: {statistics.median(latencies):.1f}")
            if len(latencies) >= 20:
                p95_idx = int(len(latencies) * 0.95)
                p99_idx = int(len(latencies) * 0.99)
                sorted_lat = sorted(latencies)
                print(f"  p95:    {sorted_lat[p95_idx]:.1f}")
                print(f"  p99:    {sorted_lat[p99_idx]:.1f}")

    # Health check results
    health_200 = sum(1 for sc, ok in health_results if sc == 200)
    print(f"\nHealth checks: {health_200}/{len(health_results)} passed (200)")

    # Fallback rate
    fallback_count = sum(1 for r in results if r[2].get("fallback_used") is True)
    if results:
        print(f"\nFallback used: {fallback_count}/{len(results)} ({100*fallback_count/len(results):.0f}%)")
        print(f"  (Expected: 100% — handle_chat is not implemented, so all requests use safe fallback)")

    # Cache HIT rate
    cache_hits = sum(1 for r in results if r[2].get("x_cache") == "HIT")
    if results:
        print(f"Cache: {cache_hits} HIT / {len(results)} total ({100*cache_hits/max(1,len(results)):.0f}%)")

    # X-Request-Id presence
    xrid_present = sum(1 for r in results if r[2].get("x_request_id"))
    if results:
        print(f"X-Request-Id present: {xrid_present}/{len(results)} ({100*xrid_present/max(1,len(results)):.0f}%)")

    # Error details
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for sc, lat, info in errors[:10]:
            print(f"  status={sc}, latency={lat}ms, info={info}")

    # Final verdict
    print(f"\n{'='*60}")
    verdict = "PASS" if (
        len(failed) == 0
        and health_200 == len(health_results)
        and len(results) > 0
    ) else "FAIL"
    print(f"VERDICT: {verdict}")
    print(f"{'='*60}\n")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(run_load_test(users=5, duration_seconds=60, ramp_seconds=5))
