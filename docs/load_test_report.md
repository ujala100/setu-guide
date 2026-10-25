# Load test report - Setu Guide API (Phase 2, Day 2)

Owner: DevOps 1. Verification only - no new features. How to re-run:
[`tests/README.md`](../tests/README.md) (Day 2 load runs section).

Raw locust output for every run: `tests/load/results/day2_*`
(`*_stats.csv`, `*_failures.csv`, `*_exceptions.csv`, `*_docker_stats.csv`).

## 1. Environment

| Item | Value |
|---|---|
| Date | 2026-10-18 |
| `TARGET_URL` | `http://localhost:8000` **[PLACEHOLDER: staging URL]** |
| Service | container `setu-day2-load`, image `setu-guide-api:day2` (python:3.11-slim) |
| `USE_MOCK` | `true` for all runs (never hit a real LLM - free-tier quota) |
| Rate limits (runs only) | `RATE_LIMIT_PER_USER=100000/minute`, `RATE_LIMIT_PER_IP=100000/minute` - raised for these runs only so the limiter does not distort latency |
| Traffic | Scenario A: 70 % quick-action (cacheable) / 30 % free-text (never cached), random stage (8) x intent (4) + synthetic prompts |
| Inputs | synthetic only (`data/` has no evaluation scenarios; prompts in `tests/load/common.py`) |
| Container resources | no CPU/memory limit set; Docker Desktop VM (7.58 GiB). Usage sampled every 5 s with `docker stats` |
| Tooling | `locust==2.46.7` (pinned in `requirements-dev.txt`) |

## 2. Pass criteria (PLACEHOLDERS - until the lead confirms)

Kept as variables, not hard-coded magic numbers. Source:
`tests/load/common.py` (and mirrored here for the report).

| Criterion | Placeholder value | Applies to |
|---|---|---|
| `PASS_MAX_5XX_PERCENT` | **< 1 %** 5xx error rate | every run |
| `PASS_MAX_P95_MOCK_MS` | **< 2000 ms** p95 | mock / cached replies |
| `PASS_MAX_P95_REAL_MS` | **< 12000 ms** p95 | real-LLM replies (not exercised - no provider key) |
| `PASS_MAX_429S` | **0** during a run | every run (limits are raised for the run) |

## 3. Results

Every number below is from a real run captured on 2026-10-18 (re-runs so that
`docker stats` was sampled for each profile - see §5 for the sampler fix).

| Metric | Run 1 - 20 users | Run 2 - 50 users | Run 3 - 10-min sustained |
|---|---|---|---|
| Duration / ramp | 2 min / ramp 1 s | 2 min / ramp 2 s | 10 min / ramp 0.5 s |
| Requests | 2 091 | 5 045 | 10 969 |
| Requests/s | 17.56 | 42.43 | 18.30 |
| p50 / p95 / p99 | 46 / 49 / 51 ms | 52 / 63 / 70 ms | 51 / 59 / 66 ms |
| Max latency | 52.39 ms | 112.39 ms | 200.12 ms |
| Error rate by status | 0 x 4xx, 0 x 5xx (0.00 %) | 0 x 4xx, 0 x 5xx (0.00 %) | 0 x 4xx, 0 x 5xx (0.00 %) |
| 429s | 0 | 0 | 0 |
| Cache hit ratio | 41.8 % (877 HIT / 1 223 MISS) | 20.3 % (1 026 HIT / 4 030 MISS) | 51.4 % (5 643 HIT / 5 326 MISS) |
| Container CPU (min/avg/max) | 0.4 / 5.5 / 21.7 % | 7.4 / 25.6 / 91.7 % | 0.2 / 11.1 / 40.3 % |
| Container memory (min/avg/max) | 68.6 / 69.4 / 70.0 MiB | 69.5 / 70.8 / 81.3 MiB | 68.7 / 70.0 / 78.7 MiB |
| Docker-stats samples (5 s) | 20 | 20 | 96 |
| Result vs criteria | PASS (all) | PASS (all) | PASS (all) |

All three profiles: **0 failures, 0 exceptions**, 5xx error rate 0.00 % < 1 %,
p95 49-63 ms << 2 000 ms, 0 x 429. Every criterion met with a large margin.

### Split by request type

| Run | Type | Requests | p50 / p95 / p99 |
|---|---|---|---|
| 20 users | quick-action | 1 483 | 46 / 49 / 51 ms |
| 20 users | free-text | 608 | 46 / 49 / 50 ms |
| 50 users | quick-action | 3 558 | 52 / 63 / 70 ms |
| 50 users | free-text | 1 487 | 52 / 62 / 69 ms |
| 10-min | quick-action | 7 658 | 51 / 59 / 66 ms |
| 10-min | free-text | 3 311 | 52 / 59 / 66 ms |

The 70/30 split holds in every run (quick-action share: 70.9 % / 70.5 % / 69.8 %).

### Observations

- **Cache hit ratio depends on how long a profile runs, not just how many
  users.** 20 users / 2 min -> 41.8 %, 50 users / 2 min -> 20.3 %,
  20 users / 10 min -> 51.4 %. The response cache is bounded
  (`CACHE_MAX_ITEMS=500`) and keyed on `(stage, intent, user_id, match_id,
  topic)`, so a **cold** run spends most quick-actions on first-touch MISSes:
  50 distinct users fill more unique keys than the 500 slots hold (evictions
  before a second touch), hence the 20 %. Given more wall-clock time at a fixed
  user count (the 10-min run), each virtual user re-touches its own keys inside
  the TTL and the ratio recovers to 51 %. Free-text traffic (30 %) is never
  cached by design, which also pulls the overall ratio down. Not a bug - two
  sizing observations: `CACHE_MAX_ITEMS` should scale with active users, and the
  steady-state ratio is a property of run length as much as concurrency.
- **Latency stays flat and far under the 2 s criterion.** p95 moves 49 ms (20u)
  -> 63 ms (50u) -> 59 ms (10-min sustained), i.e. the API layer is not the
  bottleneck at these loads; the mock reply itself costs ~45-50 ms. Max latency
  stays at 200 ms even in the 10-minute run.
- **CPU and memory are stable - no leak.** Container CPU averages 5.5 % (20u) /
  25.6 % (50u) / 11.1 % (10-min). Memory stays 68.7-70.1 MiB across all 96
  samples of the 10-minute run (no monotonic growth), so the process is not
  leaking under sustained load. The single 78.7 MiB max is a momentary spike
  that immediately returned to ~69 MiB.
- **Zero 429s and zero 5xx in every run** because limits are raised for the run
  (the deliberate 429 behaviour is proven separately by Scenario C and the
  failure drills).

## 4. Log hygiene after the runs

Privacy rule: no run may leave message text, topic, `user_id`, `match_id` or an
API key in the container logs. Verified after the Day 2 runs:

```bash
docker logs setu-day2-load | grep -E 'load_user_|load_match_|How do I start|sk-LOAD-PLACEHOLDER'
# must print nothing
```

Result after all Day 2 runs (53 000+ container log lines, 20u + 50u + 10-min
combined), every leak channel checked separately:

| Leak channel | Grep pattern | Matches |
|---|---|---|
| Synthetic `user_id` / `match_id` | `load_user_`, `load_match_` | **0** |
| Message text | `How do I start a conversation`, `What should I ask`, `I feel nervous about` | **0** |
| API key | `sk-LOAD-PLACEHOLDER`, `sk-PRIVACY`, `api_key` | **0** |
| Free-text prompt bodies | `relocating for work`, `weekend routines`, `privacy concerns` | **0** |

Only whitelisted structured fields are logged. A representative access-log line:

```
INFO setu.guide http_request {"cache": "HIT", "fallback_used": false,
        "intent": "conversation_ideas", "latency_ms": 45.3, "method": "POST",
        "path": "/v1/guide/chat", "request_id": "a2190a02357f",
        "stage": "reflect_again", "status": 200}
```

No message text, no topic, no `user_id`, no `match_id`, no API key - the only
per-request identifier is an opaque `request_id`.

## 5. Measurement notes and fixes

- **`docker stats` sampler runs from `Start-Job` with an absolute path.** The
  first pass of these runs passed a *relative* path; `Start-Job` starts in its
  own working directory, so the CSV silently never appeared and CPU/memory could
  not be reported. All three runs were re-run with the absolute-path collector
  (`tests/load/collect_docker_stats.ps1`, documented in `tests/README.md`) so
  each reported profile has a matching `docker stats` sample.
- **Cache hit ratio is measured per run** from the container access log for that
  run's exact window (`docker logs --since <run-start> --until <run-end>`),
  counting `"cache": "HIT"` / `"cache": "MISS"`.
- **Locust and the container share one machine** (localhost). Absolute latency
  on staging (a remote `TARGET_URL`) will include network time.
- **The real-mode run exercises the safety-net path, not a live provider.**
  `handle_chat` is still not implemented on `dev` (see
  `docs/failure_drill_results.md`, observation #2), so with `USE_MOCK=false` and
  a placeholder key the request short-circuits to the API-layer fallback
  (`fallback_used=true`) before any provider is contacted. The run therefore
  validates the fallback contract under light load; re-run the same profile once
  a provider is wired in to get a true end-to-end p95 against the 12 s target.

## 6. Real-mode run (5 users, 60 s) - `USE_MOCK=false`

The brief allows one small real-mode run. Container restarted as
`setu-day2-real` on port 8001 with `USE_MOCK=false` and a placeholder key
(`sk-LOAD-PLACEHOLDER-KEY-99`); the same Scenario A traffic at 5 users / 60 s.

| Metric | Value |
|---|---|
| Requests | 266 (270 incl. health checks) |
| Requests/s | 4.58 |
| p50 / p95 / p99 | 52 / 57 / 79 ms |
| Max latency | 85.69 ms |
| Errors (4xx / 5xx) | 0 / 0 |
| `fallback_used=true` | 268 / 268 chat requests (100 %) |
| Cache HIT / MISS | 0 / 268 (fallback never cached) |
| p95 vs 12 s real-LLM criterion | **57 ms < 12 000 ms - PASS** |
| Container CPU avg / max | 3.0 % / 4.6 % |
| Container memory avg / max | 52.2 / 52.7 MiB |

**Interpretation.** Every request got a schema-correct 200 with the template
reply and `fallback_used=true`; nothing 5xx'd, and no fallback reply was cached
(0 HIT). This is the documented safety-net behaviour while `handle_chat` is
unimplemented - the provider is never contacted, so this run is **not** a real
end-to-end latency measurement. It does confirm the fallback contract holds
under load and the placeholder key is never echoed to logs (log-hygiene check
§5). The 12 s real-LLM p95 target stays **unverified** until a provider is wired
in; this run should be repeated at that point.

## 7. Bugs found

| # | Where | Description | Severity | Status | Owner |
|---|---|---|---|---|---|
| - | - | **No API-layer bug found in the load runs.** All three profiles ran error-free: 0 x 4xx, 0 x 5xx, 0 x 429, no locust exceptions, latency far below the p95 criterion, container healthy throughout. | - | - | - |

(Cache sizing observation in §3 is recorded as a note, not a defect.)

## 8. Placeholder values still unconfirmed

| Placeholder | Current value | Needs confirmation |
|---|---|---|
| `TARGET_URL` | `http://localhost:8000` | staging URL |
| Load profiles | 20 users / 50 users / 10-min sustained, ramps as above | lead |
| Pass criteria (§2) | 5xx < 1 %, p95 < 2 s mock, < 12 s real, 429 = 0 | lead |
| `CACHE_MAX_ITEMS` | 500 | lead (see §3 sizing note) |
| Real-LLM run | run at 5u/60 s but only as fallback (`handle_chat` missing) - true end-to-end p95 still pending | AI/ML - `handle_chat` |
