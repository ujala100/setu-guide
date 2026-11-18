# Integration Handover Guide for Backend Intern

**Date:** 2026-11-01 · **For:** Backend Intern (Authentication, Error Format, Response Times)
**Team:** Setu Guide API · **Owners:** DevOps 1 (this guide), AI/ML 3 (provider code)

---

## 1. Authentication (Day 4 Feature)

### How it works

The API supports three authentication modes, configured via `AUTH_METHOD` env var:

| AUTH_METHOD | Header | Example |
|-------------|--------|---------|
| `none` (default) | N/A | Endpoint open |
| `api_key` | `X-API-Key: <key>` | `X-API-Key: sk-your-key` |
| `bearer` | `Authorization: Bearer <token>` | `Authorization: Bearer eyJhbG...` |

### Key implementation details

**File:** `app/api/auth.py`

- `require_api_key(request)` is a FastAPI dependency on the `/v1/guide/chat` route
- Key comparison uses `secrets.compare_digest()` for constant-time comparison
- Missing key and wrong key both return `401` (same response, so callers can't probe which keys exist)
- `/health` stays open — liveness probes can't carry credentials

### Setup

1. Set `AUTH_METHOD=api_key` (or `bearer`) in the environment
2. Set `API_KEY=<your-secret-key>` in the environment
3. The key must NOT be the placeholder value (`placeholder-not-a-real-key`)
4. Startup fails fast if `API_KEY` is missing when auth is on

### Test it

```bash
# Without key (should 401)
curl -s -X POST https://setu-guide-1wiy.onrender.com/v1/guide/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","match_id":"m1","stage":"connect","intent":"next_steps"}'

# With correct key (should 200)
curl -s -X POST https://setu-guide-1wiy.onrender.com/v1/guide/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-real-key" \
  -d '{"user_id":"u1","match_id":"m1","stage":"connect","intent":"next_steps"}'
```

### Switching to Bearer

No code change needed — just set `AUTH_METHOD=bearer` and use `Authorization: Bearer <token>` header instead.

---

## 2. Error Format

### Contract (identical for every failure)

```json
{
  "error": {
    "code": "error_code_here",
    "message": "Human-readable message",
    "details": []
  }
}
```

### Error codes

| Status | Code | Message |
|--------|------|---------|
| 400 | `invalid_request` | Request could not be processed. |
| 401 | `unauthorized` | Missing or invalid credentials. |
| 403 | `forbidden` | Access to this resource is not allowed. |
| 404 | `not_found` | Route not found. |
| 405 | `method_not_allowed` | Method not allowed for this route. |
| 429 | `rate_limited` | Too many requests. Please retry shortly. |
| 503 | `service_unavailable` | Service temporarily unavailable. |
| 422 | `invalid_request` | Request did not match the schema. (details include field errors) |
| 500 | `internal_error` | An unexpected error occurred. |

### Important rules

1. **Never echo caller input into errors** — the error message is a fixed string, never built from user data
2. **Validation errors** include `field: error_type` details (e.g., `"user_id: missing"`) — but never the actual values
3. **500 errors** log the exception type and traceback server-side, but return only the generic message to the caller
4. **Rate limit errors** include a `Retry-After` header (seconds)

### Success response format

```json
{
  "intent": "next_steps",
  "reply": "Take it at your own pace...",
  "questions": [],
  "chips": ["Conversation ideas", "Help me understand", ...],
  "sources": [],
  "safety": {
    "status": "pass",
    "flags": []
  },
  "fallback_used": false
}
```

---

## 3. Response Times

### Budgets

| Component | Timeout | Notes |
|-----------|---------|-------|
| LLM call (Gemini) | `LLM_TIMEOUT_SECONDS` (default 10s) | Configurable via env |
| Orchestrator overall | `LLM_TIMEOUT_SECONDS + 1s` margin | ThreadPoolExecutor with timeout |
| Rate limit check | < 1ms | In-memory, per-request |
| Cache lookup | < 1ms | In-memory TTLCache |
| Health check | < 5s | Container HEALTHCHECK timeout |

### What to monitor

1. **p50/p95/p99 latency** for `/v1/guide/chat`
2. **429 rate** — indicates rate limits being hit
3. **500 rate** — should be 0 in normal operation (fallback returns 200)
4. **Cache hit rate** — `X-Cache: HIT` vs `MISS` headers

### Load test results (reference)

From Day 2 load runs (see `docs/load_test_report.md`):
- 20 users: p95 within budget
- 50 users: p95 within budget
- 10-minute sustained: stable

### When response times degrade

- Check if LLM is timing out (look for `fallback_used: true` in responses)
- Check rate limiting (429 responses)
- Check cache hit rate (low hit rate = more orchestrator calls)
- On Render Free: first request after idle can take ~60s (cold start)

---

## 4. Key Files to Know

| File | Purpose |
|------|---------|
| `app/api/auth.py` | Authentication (API key / Bearer) |
| `app/api/main.py` | FastAPI app, error handlers, routes |
| `app/api/chat.py` | Chat endpoint logic (rate limit, cache, orchestrator) |
| `app/api/ratelimit.py` | In-memory rate limiter (per-user, per-IP) |
| `app/api/cache.py` | In-memory response cache |
| `app/config.py` | All configuration from environment |
| `app/core/llm_provider.py` | LLM provider (mock + Gemini) |
| `app/core/orchestrator.py` | Pipeline: route → safety → retrieve → generate |
| `app/schemas/guide.py` | Request/response schemas (frozen contract) |
| `app/safety/guard.py` | Input/output safety checks |

---

## 5. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `USE_MOCK` | No | `true` | Use mock LLM (`true`) or real Gemini (`false`) |
| `LLM_API_KEY` | When `USE_MOCK=false` | — | Gemini API key (secret) |
| `LLM_TIMEOUT_SECONDS` | No | `10.0` | LLM call timeout in seconds |
| `LLM_MODEL` | No | `gemini-3.8-flash` | Gemini model name |
| `RATE_LIMIT_PER_USER` | No | `30/minute` | Per-user rate limit |
| `RATE_LIMIT_PER_IP` | No | `60/minute` | Per-IP rate limit |
| `TRUSTED_PROXY` | No | `false` | Trust X-Forwarded-For (see `docs/trusted_proxy_analysis.md`) |
| `CACHE_ENABLED` | No | `true` | Enable response cache |
| `CACHE_TTL_SECONDS` | No | `600` | Cache TTL |
| `CACHE_MAX_ITEMS` | No | `500` | Cache max entries |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `AUTH_METHOD` | No | `none` | `none`/`api_key`/`bearer` |
| `API_KEY` | When auth on | — | API key for auth (secret) |

---

## 6. Testing

### Run the test suite

```bash
source .venv/Scripts/activate
python -m pytest tests/ -x
# 393 tests, all should pass
```

### Key test files for integration work

- `tests/integration/test_auth.py` — authentication tests (401/200, api_key vs bearer, /health open)
- `tests/integration/test_contract.py` — API contract tests (error format, response schema)
- `tests/test_day2_rate_limit.py` — rate limiting tests
- `tests/test_day2_cache.py` — caching tests
- `tests/cache/test_cache_isolation.py` — cache isolation (cross-user)
- `tests/ratelimit/test_rate_limit_review.py` — rate limit audit

---

## 7. Common Pitfalls

1. **Don't commit real keys** — `.env` is git-ignored; use `.env.example` as template
2. **Don't point load tests at real LLM** — use `USE_MOCK=true` for load testing
3. **Auth method is case-insensitive** — `api_key`, `API_KEY`, `Api_Key` all work
4. **Rate limits are per-process** — on Render with multiple instances, each has its own counters (Redis needed for cross-instance)
5. **Cache is per-process** — same limitation as rate limits

---

## 8. Who to Ask

- **DevOps 1** — config, deployment, rate limiting, caching, auth
- **AI/ML 3** — LLM provider, Gemini integration, model selection, prompts
- **Lead** — overall architecture, schema changes, orchestrator
