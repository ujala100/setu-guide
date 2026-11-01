# Render Retest & Recovery Test Plan

**Status:** Blocked — staging server `https://setu-guide-1wiy.onrender.com` not reachable from this session.

---

## Task 5: Render Retest (Load Test with LLM Stubbed)

### Prerequisites
1. Staging service must be awake (Free instance needs a warm-up call first)
2. `USE_MOCK=true` must be set on staging (or the LLM must be stubbed)
3. Locust or similar load testing tool available

### Warm-up
```bash
# First call wakes up the Free instance (~60s)
curl -s https://setu-guide-1wiy.onrender.com/health
# Expected: {"status": "ok"} after ~60s
```

### Load test with LLM stubbed (mock mode)
```bash
# Using locust (already in requirements-dev.txt)
locust -f tests/load/scenario_c.py --headless -u 20 -r 5 --run-time 5m \
  --host https://setu-guide-1wiy.onrender.com
```

**Key constraint:** Do NOT point 50 users at the real LLM. Use mock mode (`USE_MOCK=true`) or a stubbed orchestrator.

### What to verify
- `/health` stays 200 throughout
- `/v1/guide/chat` returns 200 with proper error format
- No 500 errors during the run
- Response times acceptable (p95 < reasonable threshold)
- Cache headers present (X-Cache: HIT/MISS)
- X-Request-Id present on all responses

---

## Task 6: Recovery Test (Restart During Traffic)

### Prerequisites
1. Service running on staging with active traffic
2. Ability to restart the service (Render dashboard, CLI, or API)

### Procedure
1. Start load test (e.g., 10 users sustained)
2. While traffic is flowing, restart the service:
   ```bash
   # Via Render CLI (if available)
   render deploy setu-guide-1wiy --service-id <id>
   
   # Or via Render dashboard: Manual Deploy → Restart
   ```
3. Monitor during restart:
   - Some requests may fail during the restart window
   - Service should become healthy again automatically
   - No manual intervention should be needed
4. Verify after restart:
   - `/health` returns 200
   - `/v1/guide/chat` returns 200
   - No stuck state, no manual steps required

### What to verify
- Service recovers without manual steps
- Health check passes after restart
- In-flight requests either complete or get proper fallback (200 with fallback_used=true)
- No zombie processes or stuck state

---

## Local Testing Alternative

If staging is unavailable, the same tests can be run locally:

```bash
# Start the service locally
source .venv/Scripts/activate
USE_MOCK=true uvicorn app.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Warm up
curl -s http://localhost:8000/health

# Run load test
locust -f tests/load/scenario_c.py --headless -u 20 -r 5 --run-time 2m \
  --host http://localhost:8000

# Kill the server
kill $UVICORN_PID
```

For recovery testing locally:
```bash
# Start server and load test in background
source .venv/Scripts/activate
USE_MOCK=true uvicorn app.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!
locust -f tests/load/scenario_c.py --headless -u 10 -r 2 --run-time 5m \
  --host http://localhost:8000 &
LOCUST_PID=$!

# Wait for traffic to start, then restart
sleep 30
kill -SIGTERM $UVICORN_PID
sleep 2
# Restart
USE_MOCK=true uvicorn app.main:app --host 0.0.0.0 --port 8000 &
wait $LOCUST_PID
```

---

## Blocker Resolution

To unblock Tasks 5 and 6, one of these is needed:

1. **Network access to staging** — allow this session to reach `setu-guide-1wiy.onrender.com`
2. **Local test environment** — run the equivalent tests locally and report results
3. **Manual execution** — someone with staging access runs the tests and shares results

Once any of these is available, the tests can be executed and results documented.
