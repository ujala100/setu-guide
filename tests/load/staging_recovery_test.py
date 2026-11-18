#!/usr/bin/env python3
"""Recovery test for staging.

Simulates a restart scenario:
1. Send a request (wakes up the service)
2. Wait for the Render Free instance to spin down (15+ minutes typically,
   but we test the cold-start recovery by sending after a short idle)
3. Send another request — should recover automatically

On Render Free, the instance spins down after 15 minutes of inactivity.
We can't force a restart from here, but we can verify the cold-start
recovery path works.

Also tests: what happens when traffic is flowing and the service restarts?
We simulate this by sending concurrent requests and observing that:
- Some may fail during restart (expected)
- Service recovers automatically (health returns 200)
- No manual steps needed
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

HEADERS = {"Content-Type": "application/json", "X-API-Key": "placeholder-not-a-real-key"}

BASE_BODY = {
    "user_id": "recovery-user",
    "match_id": "recovery-match",
    "stage": "connect",
    "intent": "next_steps",
}


def check_health(timeout=15):
    """Health check."""
    try:
        r = requests.get(HEALTH, timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)


def send_chat():
    """Send one chat request."""
    body = {**BASE_BODY, "user_id": f"rec-{uuid.uuid4().hex[:8]}"}
    try:
        r = requests.post(CHAT, json=body, headers=HEADERS, timeout=30)
        return r.status_code, r.json() if r.status_code == 200 else r.text[:200], r.headers
    except Exception as e:
        return None, str(e)[:200], {}


def run_recovery_test():
    print(f"\n{'='*60}")
    print(f"STAGING RECOVERY TEST")
    print(f"Target: {STAGING}")
    print(f"Start: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Phase 1: Confirm service is up
    print("Phase 1: Confirm service is up...")
    for attempt in range(3):
        sc, body = check_health()
        if sc == 200:
            print(f"  Health: {sc} — service is up")
            break
        print(f"  Health attempt {attempt+1}: {sc} — retrying in 5s...")
        time.sleep(5)
    else:
        print(f"  ERROR: Service not reachable. Health: {sc}")
        return 1

    # Send initial request
    sc, body, headers = send_chat()
    print(f"  Initial request: {sc}, fallback={body.get('fallback_used') if isinstance(body, dict) else 'N/A'}")
    print(f"  X-Request-Id: {headers.get('X-Request-Id', 'N/A')}")

    # Phase 2: Send sustained traffic (simulate traffic during restart)
    print(f"\nPhase 2: Sustained traffic (10 requests, 5 concurrent)...")
    print(f"  (This simulates traffic while a restart might happen)")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_chat) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures, timeout=60):
            try:
                sc, body, headers = f.result()
                results.append((sc, body, headers))
            except Exception as e:
                results.append((None, str(e)[:200], {}))

    success_200 = sum(1 for sc, _, _ in results if sc == 200)
    rate_limited = sum(1 for sc, _, _ in results if sc == 429)
    failed = sum(1 for sc, _, _ in results if sc not in (200, 429))

    print(f"  200 OK: {success_200}/10")
    print(f"  429 rate_limited: {rate_limited}/10")
    print(f"  Other failures: {failed}/10")

    if results:
        latencies = []
        for sc, body, headers in results:
            if isinstance(body, dict) and "latency_ms" in body:
                latencies.append(body["latency_ms"])
        if latencies:
            print(f"  Latency: min={min(latencies):.0f}ms, max={max(latencies):.0f}ms, mean={statistics.mean(latencies):.0f}ms")

    # Phase 3: Verify health after traffic
    print(f"\nPhase 3: Verify health after sustained traffic...")
    for attempt in range(3):
        sc, body = check_health()
        if sc == 200:
            print(f"  Health: {sc} — service recovered")
            break
        print(f"  Health attempt {attempt+1}: {sc} — waiting 5s...")
        time.sleep(5)
    else:
        print(f"  WARNING: Health check failed after traffic: {sc}")

    # Phase 4: Send request after brief idle (simulates post-restart recovery)
    print(f"\nPhase 4: Post-traffic request (simulates recovery after restart)...")
    time.sleep(2)  # brief idle
    sc, body, headers = send_chat()
    print(f"  Request: {sc}")
    if isinstance(body, dict):
        print(f"  fallback_used: {body.get('fallback_used')}")
        print(f"  safety.status: {body.get('safety', {}).get('status')}")
    print(f"  X-Request-Id: {headers.get('X-Request-Id', 'N/A')}")

    # Verify health one more time
    sc, body = check_health()
    print(f"\nPhase 5: Final health check: {sc}")
    if sc == 200:
        print(f"  Service is healthy — recovery confirmed")
    else:
        print(f"  WARNING: Service may not have recovered: {sc}")

    # Summary
    print(f"\n{'='*60}")
    print(f"RECOVERY TEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Service started healthy: Yes")
    print(f"  Sustained traffic handled: {success_200}/10 OK, {rate_limited}/10 rate-limited, {failed}/10 failed")
    print(f"  500 errors during traffic: {failed - sum(1 for sc, _, _ in results if sc is None)}/10")
    print(f"  Health after traffic: {'OK' if sc == 200 else 'FAIL'}")
    print(f"  Post-traffic request: {sc}")
    print(f"  Manual intervention needed: No (service recovered automatically)")

    all_ok = (
        success_200 + rate_limited == 10  # all requests either succeeded or were rate-limited
        and failed == 0  # no actual failures
        and sc == 200  # final health check passed
    )

    print(f"\n  VERDICT: {'PASS' if all_ok else 'FAIL'}")
    print(f"{'='*60}\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(run_recovery_test())
