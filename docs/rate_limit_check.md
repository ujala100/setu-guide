# Rate Limit Check — Phase 2, Day 3

**Date:** 2026-10-20 · **Owner:** DevOps 1 (`app/api/`) · **Branch:** `feature/phase2-day3-security`
**Suite:** `tests/ratelimit/test_rate_limit_review.py` (9 tests) · **Result: 9/9 PASS** (after 2 fixes; both failed before them)

Environment: `TestClient` against the FastAPI app, `USE_MOCK=true`, synthetic
ids only (`u1`, `alice`, `rotating_*`, `flood_*`). Every run starts from a
reset limiter (autouse fixture), so no test can inherit another's counters.
Overlap with `tests/test_day2_rate_limit.py` is deliberate: this suite is the
Day-3 audit artifact that pins every behaviour under review in one place.

## Checklist

| # | Check | Setup | Expected | Actual | Verdict |
|---|-------|-------|----------|--------|---------|
| 1 | Per-user N+1 | `RATE_LIMIT_PER_USER=3/minute` | 3×200, then 429 `rate_limited` + `Retry-After` | 3×200; 4th → 429, `error.code=rate_limited`, `details=[]`, `Retry-After=60` | PASS |
| 2 | Per-IP N+1 | `RATE_LIMIT_PER_IP=3/minute`, rotating `user_id` each call | 3×200, then 429 + `Retry-After` | 3×200 (u0–u2); u_next → 429 with `Retry-After` | PASS |
| 3 | One user at limit ≠ others affected | user `a` exhausted (2/min), user `b` | `b` keeps a full quota; `a`-blocked calls never consume `b`'s | `a` → 429; `b` → 200,200 then exactly 429 on its 3rd (own limit) | PASS |
| 4 | `/health` never limited | user+IP budget exhausted (2/2 per minute) | `/health` stays 200 while chat is 429 | chat → 429; `/health` ×20 → all 200 | PASS |
| 5 | `X-Forwarded-For` spoof, `TRUSTED_PROXY=false` | IP limit 3/min; every request forges a different `X-Forwarded-For` | forged headers ignored → one real-IP bucket → 429 | 3×200 (forged 10.9.8.0-2); 4th (forged 10.9.8.99) → 429 from the real bucket | PASS |
| 6 | Many `user_id`s from one IP | IP limit 5/min, 10 different `user_id`s | IP limit still applies | statuses `[200×5, 429×5]`; 11th → 429 | PASS |
| 7 | `user_id` format/case bypass | limit 3/min, then `U1`, `" u1"`, `"u1 "`, `"u1\xa0"`, `"U1 "` | variants share one quota → all 429 | all 5 variants → 429 (`Retry-After` present); distinct id `u0001` still gets its own quota (200) — normalisation is scoped | PASS (after fix A) |
| 8 | Service stays up under a burst | 5/min user, 10/min IP, 200 rapid requests | only 200/429, no 5xx, service recovers | 200 statuses: exactly 5; 429: 195; **5xx: 0**; `/health` ×5 → 200; after window elapses (`limiter.reset()`) next request → 200 | PASS |
| 9 | Limiter memory bounded | 11 000 distinct `user_id`s against `_MAX_KEYS=10_000` | dict stays ≤ 10 000 keys | **before fix B: 11 001 keys** (sweep dropped 0 — all buckets younger than 1 day); **after fix B: ≤ 10 000**, and the active IP bucket still returns 429 | PASS (after fix B) |

## Findings (both fixed in this PR, API layer)

### Finding A — per-user limit bypassed by `user_id` case/format variants (Medium)

**Before (probe, `RATE_LIMIT_PER_USER=3/minute`):**

| Sent | Statuses |
|------|----------|
| `u1` ×3 | 200, 200, 200 |
| `U1` ×3 | **200, 200, 200** (fresh bucket) |
| `" u1"` ×2 | **200, 200** |
| `"u1 "`, `"u1\xa0"`, `"U1 "` | **200 each** |

One logical user got **12 requests through a limit of 3** by varying case and
leading/trailing whitespace: the bucket key used the raw string.

**Fix (app/api/chat.py):** the user bucket key is normalised —
`f"user:{req.user_id.strip().casefold()}"` — so case/whitespace variants share
one quota. Scope is deliberate: a genuinely different id (`u0001`) keeps its
own bucket (asserted by test 7). Rate limiting is the only place where this
normalisation applies; cache keys and stored ids stay byte-exact.
Note: the per-IP limit already capped the blast radius (default `60/minute`
per IP), which is why severity is Medium, not Critical.

### Finding B — limiter dict unbounded under a high-cardinality flood (Medium)

**Before (probe):** 12 000 requests with 12 000 distinct `user_id`s →
`len(limiter._hits) = 12 001` against `_MAX_KEYS = 10 000`; the existing sweep
only drops buckets older than 1 day, so nothing was droppable during the
attack (0 removed). One IP at the default 60/min creates up to ~86 400
buckets/day, so the cap never held — slow memory growth (DoS surface).

**Fix (app/api/ratelimit.py, `_sweep`):** after the day-old sweep, if the dict
is still over the cap, the least recently used buckets are evicted (down to
90 % of `_MAX_KEYS`, so the sort runs once per ~1 000 new keys, not per
request). Just-used buckets keep their counters — verified: the active IP
bucket still returns 429 after an 11 000-id flood. Trade-off (documented in
the code): above `_MAX_KEYS` distinct ids inside one window, per-user limits
become approximate; memory stays bounded. A shared store (Redis) removes even
that trade-off — already noted in the README scaling note.

## Service-up evidence (test 8, exact numbers)

- 200 rapid requests: **5×200, 195×429, 0×5xx**
- `/health` during exhaustion: **5/5 → 200**
- after the window elapses: next request → **200** (full recovery, process never restarted)

## Files

| File | Change |
|------|--------|
| `tests/ratelimit/test_rate_limit_review.py` | new — 9 audit tests (checks 1–9 above) |
| `app/api/chat.py` | fix A — normalised user bucket key (+ comment) |
| `app/api/ratelimit.py` | fix B — `_sweep` bounds the dict with LRU eviction (+ comment) |

## Findings log (bug tracker)

| # | Finding | Severity | Owner | Status |
|---|---------|----------|-------|--------|
| A | Per-user rate limit bypassed by `user_id` case/whitespace variants | Medium | DevOps 1 (`app/api/`) | **Fixed** in this PR, regression test added |
| B | Limiter counters dict grows past `_MAX_KEYS` under id floods (memory DoS surface) | Medium | DevOps 1 (`app/api/`) | **Fixed** in this PR, regression test added |

No Critical findings. Bypass attempts 5 and 6 (spoofed `X-Forwarded-For`,
rotating `user_id`s) were **already correctly blocked** — no gap there.
