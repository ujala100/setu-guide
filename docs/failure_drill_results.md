# Failure drill results - Setu Guide API (Phase 2, Day 2)

Owner: DevOps 1. Verification only - no new features, nothing under `app/core`,
`app/rag`, `app/safety` or `app/schemas` was edited. Re-run commands:
[`tests/README.md`](../tests/README.md).

Drills live in `tests/failure/test_provider_drills.py` (the Day 2 set) and
`tests/failure/test_llm_failures.py` (the Day 3 set - timeout, invalid JSON,
invalid schema, wrong type, fallback-not-cached, recovery, unexpected 500).
One home per case: the Day 2 file only adds what the Day 3 suite did not cover.

## 1. Environment

| Item | Value |
|---|---|
| Date | 2026-10-18 |
| How they run | in-process, `USE_MOCK=false`, a fake `handle_chat` planted with `monkeypatch` (app/core is never edited) |
| Command | `python -m pytest tests/failure -q` |
| Contract under test | every drill must return HTTP 200, the template reply, `fallback_used=true`, `safety.status="pass"`, `flags=[]`, never a 500, and the fallback reply must NOT be cached |

The drill set proves the **API-layer safety net** (`app/api/chat.py`): whatever
the orchestrator/LLM layer throws or returns, the caller gets one safe,
schema-correct response. Provider faults themselves are simulated at the
orchestrator entry point because there is no base-URL override for the provider
client in this POC.

## 2. Results

Every row below is a real captured response (capture script run on 2026-10-18),
not an estimate.

| # | Drill | Setup | Expected | Actual | Pass/Fail |
|---|---|---|---|---|---|
| 1 | LLM down (connection refused) | fake `handle_chat` raises `ConnectionRefusedError` | 200, template reply, `fallback_used=true`, `safety.status="pass"`, `flags=[]`, not cached | `200`, `X-Cache: MISS`, `fallback_used=true`, reply = `FALLBACK_REPLY`, `safety.status="pass"`, `flags=[]`; second identical request also `MISS` | **PASS** |
| 2 | LLM slow (beyond `LLM_TIMEOUT_SECONDS`) | `LLM_TIMEOUT_SECONDS=0.05`, margin `0`, fake entry sleeps 1 s | 200 template fallback, timeout enforced in well under 1 s, not cached | `200`, enforced in `0.06 s` (assert `< 0.9 s`), `X-Cache: MISS`, `fallback_used=true`, `safety.status="pass"`, `flags=[]`; second request also `MISS` | **PASS** |
| 3 | LLM rate-limited by provider (429 from provider) | fake entry raises a provider-quota `429` error | 200 template fallback - NOT forwarded as 429, no `Retry-After`, provider text not echoed, not cached | `200`, `X-Cache: MISS`, **no `Retry-After` header**, `fallback_used=true`, reply = template (no "quota" text), `safety.status="pass"`, `flags=[]`; second request also `MISS` | **PASS** |
| 4 | LLM returns garbage - empty reply | fake entry returns `""` | 200 template fallback, not cached | `200`, `X-Cache: MISS`, `fallback_used=true`, reply = `FALLBACK_REPLY`, `safety.status="pass"`, `flags=[]` | **PASS** |
| 5 | LLM returns garbage - whitespace-only reply | fake entry returns `"   \n\t  "` | 200 template fallback, not cached | `200`, `X-Cache: MISS`, `fallback_used=true`, reply = `FALLBACK_REPLY`, `safety.status="pass"`, `flags=[]` | **PASS** |
| 6 | LLM returns garbage - invalid JSON | fake entry returns a truncated JSON string | 200 template fallback, no 500 | `200`, `X-Cache: MISS`, `fallback_used=true`, reply = template, `safety.status="pass"`, `flags=[]` | **PASS** |
| 7 | LLM returns garbage - wrong schema | fake entry returns `{"intent": "not-a-real-intent", "reply": 12345}` | 200 template fallback, no 500 | `200`, `X-Cache: MISS`, `fallback_used=true`, reply = template, `safety.status="pass"`, `flags=[]` | **PASS** |
| 8 | Fallback never cached | after drills 1-3, repeat the identical quick action | second request also `MISS` (fallback not stored) | every repeat returned `X-Cache: MISS` with `fallback_used=true` | **PASS** |
| 9 | Recovery after drills | plant a healthy `handle_chat` again | next reply served normally, `fallback_used=false` | `200`, `fallback_used=false`, reply = "provider recovered", `safety.status="pass"`, `flags=[]` | **PASS** |
| 10 | Drill-path log hygiene | drill 1 with marker message/topic/user_id/match_id/API key | no marker in any log line; failure logged by type only | no marker in logs; `orchestrator_failed mode=real type=ConnectionRefusedError` logged (type name only) | **PASS** |

**Suite result:** `python -m pytest tests/failure -q` -> **47 passed** (26 bad-input
+ 3 container + 9 Day 3 LLM-failure + 2 log-privacy + **7 new Day 2 drills**).
Full repo suite: `python -m pytest -q` -> **318 passed** (311 pre-existing tests
on `dev` + these 7), so nothing earlier broke.

## 3. What the logs show for every drill

Structured access log for a drill (no message text, no topic, no `user_id`, no
`match_id`, no API key - only whitelisted fields):

```
WARNING setu.guide.chat orchestrator_failed mode=real type=ConnectionRefusedError fallback_used=true
INFO    setu.guide http_request {"cache": "MISS", "fallback_used": true, "intent": "next_steps",
        "latency_ms": 6.0, "method": "POST", "path": "/v1/guide/chat",
        "request_id": "35bbb7ce567f", "stage": "reflect", "status": 200}
```

The failure line carries the exception **type name only** - the message text of
the exception (which could contain provider or user data) is never logged.

## 4. Bugs found

| # | Where | Description | Severity | Status | Owner |
|---|---|---|---|---|---|
| - | - | **No API-layer bug found.** Every provider failure mode tested returned the safe 200 template fallback in the standard shape, never a 500, never cached, never leaking internal or private text. The Day 2 drills add coverage for connection-refused, provider-429 and empty/whitespace replies, all of which behaved correctly. | - | - | - |

### Observations for the tracker (not fixed here - outside `app/api`)

These are logged as issues for their owner with steps to reproduce; DevOps 1
does not edit `app/core` / `app/rag` / `app/safety`:

| # | Where | Description | Severity | Owner |
|---|---|---|---|---|
| 1 | `app/core/llm_provider.py` | Gemini client timeout is hardcoded (`http_options={"timeout": 10000}`) and is NOT wired to `LLM_TIMEOUT_SECONDS`. A request can therefore wait on the provider up to the hardcoded value while the API layer abandons it at `LLM_TIMEOUT_SECONDS + 1s`. Repro: set `LLM_TIMEOUT_SECONDS=0.05` and inspect the provider construction. | Low | AI/ML (intern 3) |
| 2 | `app/core/orchestrator.py` | `handle_chat` (the real-mode entry point) is still not implemented, so real mode always short-circuits to the API-layer fallback before reaching any provider. Repro: `USE_MOCK=false` + key -> `fallback_used=true` on every request. | Medium | Lead / AI/ML |
| 3 | `app/api/main.py` (doc drift) | `docs/api.md` still says the mock reply is the literal `"(mock reply)"`; the mock path actually returns knowledge-base/template replies. | Low | DevOps 1 (doc fix in a follow-up, not code) |

No **Critical** bug (no crash, no leak, no exposed secret) was found in any
drill, so nothing needed an immediate escalation to the lead.
