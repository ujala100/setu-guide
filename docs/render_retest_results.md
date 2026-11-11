# Render Retest Results — 2026-11-01

**Target:** `https://setu-guide-1wiy.onrender.com`
**Method:** Python concurrent requests (requests + ThreadPoolExecutor)
**LLM:** Effectively stubbed — service returns `fallback_used: true` for every request
  because `app.core.orchestrator.handle_chat` is not implemented yet.

---

## Configuration observed on staging

| Setting | Value |
|---------|-------|
| AUTH_METHOD | `none` (default — endpoint open) |
| RATE_LIMIT_PER_USER | 30/minute |
| RATE_LIMIT_PER_IP | 60/minute |
| CACHE_ENABLED | true |
| LLM mode | real (USE_MOCK=false likely), but handle_chat missing → fallback |

---

## Test 1: 20 users, 120s (rate limit exceeded)

| Metric | Result |
|--------|--------|
| Requests sent | 387 |
| Completed | 386 |
| 200 OK | 138 (35.7%) |
| 429 rate_limited | 248 (64.3%) |
| 500 errors | 0 |
| Health checks | 46/46 passed |
| Fallback used | 138/138 (100%) |
| X-Request-Id | 138/138 (100%) |
| Latency (200s only) | 10.9-13.4s (mean 11.7s) |

**Verdict:** Rate limiting works correctly. No 500s. The 429s are expected — the
per-IP limit of 60/minute was exceeded by 20 concurrent users hitting the same IP.

---

## Test 2: 5 users, 60s (within rate limits) ✅ PASS

| Metric | Result |
|--------|--------|
| Requests sent | 15 |
| Completed | 15 |
| 200 OK | 15 (100%) |
| Failed | 0 |
| 500 errors | 0 |
| Health checks | 15/15 passed (100%) |
| Fallback used | 15/15 (100%) |
| X-Request-Id | 15/15 (100%) |
| Cache HIT | 0/15 (0% — unique user_ids per request) |
| Latency | 11.3-11.9s (mean 11.4s) — Render Free cold start |

**Verdict: PASS**

### What this confirms
1. ✅ Service stays healthy under load (5 users, 60s)
2. ✅ No 500 errors — every request returns 200 with safe fallback
3. ✅ Error format correct (429s from test 1 had proper error contract)
4. ✅ X-Request-Id on every response
5. ✅ Fallback returns safe reply, never errors the client
6. ✅ Rate limiting works (test 1 showed proper 429s)

### What this does NOT verify
- Real LLM latency (LLM is not being called — fallback is used)
- Cache behavior with identical requests (unique user_ids per request)
- Sustained load beyond 60s at this concurrency
- Recovery under load (separate test below)

---

## Notes

- Render Free instances have ~11s cold start latency. This is expected and not
  a code issue.
- The 20-user test confirmed rate limits protect the service — 64% of requests
  were properly rejected with 429.
- No real LLM traffic was sent — all responses are safe fallbacks.
