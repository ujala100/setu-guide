# Cache Isolation Test — Phase 2, Day 3

**Date:** 2026-10-20 · **Owner:** DevOps 1 (`app/api/`) · **Branch:** `feature/phase2-day3-security`
**Suite:** `tests/cache/test_cache_isolation.py` (13 tests) · **Result: 13/13 PASS — on the first run, before any fix.**

**CRITICAL check result: NO cross-user response was found.** The task marks any
cross-user cached reply as Critical-to-escalate-immediately; none exists, so
nothing was escalated. The cache key already contains `user_id` and every
dimension was verified at the response-body level, not just by call counts.

Environment: `TestClient`, `USE_MOCK=true`, synthetic ids (`alice`, `bob`,
`m1`/`m2`). Every test starts from a cleared cache and cleared rate limiter
(autouse fixture).

## Method — why call counts alone are not enough

Day 2 proved isolation by counting orchestrator calls. Day 3 installs a **fake
orchestrator that encodes the request it saw into the reply**:

```
user={user_id}|match={match_id}|stage={stage}|topic={topic}
```

Every assertion below checks the **content of the response that the client
actually received** — including responses served as cache `HIT`s. A cached
reply that leaked across any dimension would be visible in the body.

## Cross-user isolation (the Critical check)

| # | Case | Setup | Expected | Actual | Verdict |
|---|------|-------|----------|--------|---------|
| 1 | Two users, identical everything else | same stage/intent/topic/`match_id`, fake replies `reply-for-{user}`; A→B→A→B | each user always gets its own reply | A: `reply-for-alice` (MISS then **HIT**), B: `reply-for-bob` (MISS then **HIT**); `alice` never in bob's body, `bob` never in alice's; orchestrator called exactly **2×** | PASS |
| 2 | Interleaved rounds | 3 rounds alternating alice/bob | every HIT replays that user's own reply | all 6 responses `user=…|match=m1|stage=connect|topic=-` for the correct user | PASS |
| 3 | Different `match_id` | user alice, m1 then m2 | separate entries, own replies | MISS/MISS then HIT/HIT; HITs carry `match=m1` / `match=m2` respectively; orchestrator **2×** | PASS |
| 4 | Different `stage` | connect then reflect | separate entries, own replies | MISS/MISS then HIT/HIT; bodies carry own stage; orchestrator **2×** | PASS |
| 5 | Different `topic` | `budget` then `family` | separate entries, own replies | MISS/MISS then HIT(`budget`); bodies carry own topic; orchestrator **2×** | PASS |

## Never cached (each: identical request twice → two orchestrator calls, both `MISS`)

| Case | Setup | Actual | Verdict |
|------|-------|--------|---------|
| Free-text message | `message` only, no `intent` | 200/200, `MISS`+`MISS`, calls=2 | PASS |
| Error (500) | fake orchestrator raises `RuntimeError` | 500/500, **no `X-Cache` header at all**, calls=2 | PASS |
| Fallback reply | `fallback_used=true` | `MISS`+`MISS`, calls=2 | PASS |
| Safety **modified** | `safety.status="modified"` | `MISS`+`MISS`, calls=2 | PASS |
| Safety **blocked** | `safety.status="blocked"` | `MISS`+`MISS`, calls=2 | PASS |
| Flags with `pass` status | `flags=["outcome_prediction"]`, status `pass` | `MISS`+`MISS`, calls=2 | PASS |
| `CACHE_ENABLED=false` | two identical quick actions | `MISS`+`MISS`, calls=2, **and `response_cache._cache is None`** — the store is never even built | PASS |

## Cache key composition (unit test)

Pinned: `cache_key(req) == ("connect", "next_steps", "budget", "m1", "alice")`
= **stage + intent + topic + match_id + user_id**, byte-exact and
deterministic. Changing any one of the five components produces a different
key (all five variants asserted) — so a reply can only ever be served to a
request identical on all five.

## Overlap with Day 2

`tests/test_day2_cache.py` already covers MISS→HIT, free text, fallback,
blocked safety, error 422, disabled cache and different user/topic by
**call counting**. This suite deliberately re-checks those through
**response content** (and adds: match_id, stage, modified-safety, flags,
500-path and the deep disabled-store assertion) — improved evidence, not
duplicated tests. No Day-2 test was changed.

## Files

| File | Change |
|------|--------|
| `tests/cache/test_cache_isolation.py` | new — 13 isolation tests (fake orchestrator with request-encoding replies) |

## Findings log (bug tracker)

| # | Finding | Severity | Owner | Status |
|---|---------|----------|-------|--------|
| — | **No findings.** No cross-user response, no never-cached violation, no key gap. | — | — | nothing to file |

(If any cross-user response had been found, it would have gone to the lead
immediately as Critical, before anything else in this task.)
