# Monitoring and alert requirements

Owner: DevOps 2. Status: **requirements only — no monitoring stack is
implemented in this repo.** This document defines what must be observed, the
thresholds, and who gets alerted. It does not add tooling, code or CI steps.

Scope note: the service today exposes only structured logs and a liveness
endpoint. There is **no** Prometheus/Grafana/alerting config anywhere in the
repo (checked: no `prometheus`, `grafana`, `alertmanager`, `datadog`, `sentry`,
`opentelemetry` files). Everything below is derived from data the app already
emits, so nothing here is aspirational plumbing that the code cannot support.

## 1. Signals that already exist

The service emits one structured access line per request on logger `setu.guide`
(`app/api/main.py:121-130`, fields set in `app/api/chat.py:94-99`):

`request_id`, `method`, `path`, `status`, `latency_ms`, `cache`, `intent`,
`stage`, `fallback_used`.

Additional lines already available for alerting:

| Log line | Source | Meaning |
|---|---|---|
| `rate_limited scope=user\|ip retry_after=N` | `app/api/chat.py:58` | A 429 was issued (scope only, no id) |
| `orchestrator_failed mode=real type=...` | `app/api/chat.py:87` | Real-mode call failed; safe fallback served |
| `unhandled <Exc> -> 500 internal_error` | `app/api/main.py:97` | Unhandled exception -> 500 |
| `llm_failed type=...` / `generation_failed type=...` | `app/core/orchestrator.py:205,246` | LLM / generation error |

Liveness: `GET /health` -> `200 {"status":"ok"}` (`app/api/main.py:133`),
probed by the container `HEALTHCHECK` every 30 s, timeout 5 s, 3 retries
(`docker/Dockerfile:48-49`).

All metrics below are computable from these logs; none require new app code.

## 2. Baselines (measured, Day 3)

From `docs/load_and_failure_test_notes.md` (Scenario A/B/D, `USE_MOCK=true`,
commit `4753b75`):

| Signal | Measured baseline | Source |
|---|---|---|
| Error rate (5xx) | 0.00 % | notes §2 (Scenarios A, B, D) |
| p95 chat latency (mock/cached) | 57 ms (A), 61–64 ms (B) | notes §2 |
| p99 chat latency | 66–72 ms | notes §2 |
| p95 `/health` latency | 17 ms | notes §2 (Scenario D) |
| Cache hit ratio (quick action, mixed) | 70.5 % | notes §2 (Scenario A) |
| Cache hit ratio (repeated quick action) | 98.7 % | notes §2 (Scenario B) |
| `/health` 429 count under load | 0 | notes §2 (Scenario D) |

Pass criteria from the brief (`docs/load_and_failure_test_notes.md:22-23`,
`README.md:140`): 5xx < 1 %; p95 < 2 s (mock/cached) and < 12 s (real LLM).

## 3. Metrics to observe

| # | Metric | How derived | Baseline | Alert threshold | Severity |
|---|---|---|---|---|---|
| M1 | 5xx count / rate | count `http_request` with `status >= 500` | 0 % | > 1 % over 5 min, or any sustained 5xx | Critical |
| M2 | p95 chat latency | `latency_ms` p95 for `path=/v1/guide/chat` | ~57 ms | > 2 s (mock/cached) sustained 5 min | High |
| M3 | p99 chat latency | `latency_ms` p99 for chat | ~66 ms | > 5 s sustained (leading indicator for M2) | Medium |
| M4 | `fallback_used=true` rate | count `http_request` where `fallback_used` is true | ~0 mock / always-true in real mode today | rising trend vs. prior window | High |
| M5 | 429 rate | count `http_request` `status=429` + `rate_limited` lines | 0 in normal traffic | spike isolated to many users (limiter breach) vs. one abusive id (expected) | Medium |
| M6 | `/health` availability | probe success ratio | 100 % | < 100 % over 3 probes | Critical |
| M7 | Cache hit ratio (quick action) | HIT / (HIT+MISS) for cacheable requests | 70.5 % / 98.7 % | sudden drop (cache ineffective) | Low |
| M8 | Request volume / RPS | count of `http_request` | 18–57 RPS in tests | zero traffic (silent outage) or unexpected spike | Medium |

## 4. Alert definitions

| Alert | Fires when | Route to | First action |
|---|---|---|---|
| **Service down** | M6 fails (health unreachable / non-200) | DevOps 2 (+ lead) | Check container/platform status; check `unhandled` lines |
| **Error spike** | M1 > 1 % for 5 min | DevOps 1 (API) + DevOps 2 | Inspect `unhandled` / 5xx `request_id`s in logs |
| **Latency regression** | M2 > 2 s for 5 min | DevOps 1 | Check LLM mode / `orchestrator_failed` lines |
| **Degradation (fallback)** | M4 trend rises unexpectedly | Lead (orchestrator owner) | Check `orchestrator_failed` / `llm_failed` types |
| **Rate-limit anomaly** | M5 spike across many distinct users | DevOps 1 | Confirm limiter config; rule out an attack |
| **Cache ineffective** | M7 drops sharply | DevOps 1 | Check `CACHE_ENABLED`, cacheable rules |

Escalation follows `CONTRIBUTING.md` / `docs/team/`: API → DevOps 1,
`.github`/deploy → DevOps 2, orchestrator/RAG/safety → lead or AI/ML.

## 5. Privacy constraint (mandatory)

Alerts and dashboards may use **counts, rates and timings only**. Never alert
on, display, or store the `message`, `topic`, `user_id`, `match_id`, `context`
or any API key — the same rule the access log already enforces
(`docs/api.md` §18). Any future metric pipeline must be verified with
`docs/verification/privacy-log-audit.md` before it ships.

## 6. Health probes

- **Liveness**: `GET /health` — already wired to the container `HEALTHCHECK`
  (`docker/Dockerfile:48`). Never rate limited (`app/api/main.py:133`,
  `docs/api.md` §5).
- **Readiness**: not implemented. Decide with the lead whether a readiness
  probe is needed before multi-instance deployment (the cache/rate limiter are
  in-memory and per-process — see §7).

## 7. Known gaps (open, need decisions)

- **Single instance only.** Rate limiter and cache are in-memory
  (`docs/load_and_failure_test_notes.md:172-175`); per-instance counters are not
  comparable across replicas. Needs Redis before scaling — outside this doc.
- **No metrics pipeline.** Logs are emitted but not aggregated; M1–M8 cannot be
  charted until a log/metric sink (e.g. Render metrics, or Prometheus + Loki)
  is chosen. Tooling choice is unassigned. For the current Render Free service,
  treat only outbound bandwidth metrics and the Events timeline as available;
  no custom dashboard or metrics exporter is implemented.
- **Real-LLM p95 (12 s)** unvalidated for this staging service. The
  `handle_chat` entry point now exists, but real-provider latency has not been
  measured (`docs/api.md` §17).
- **Alert destinations/channels** not defined (email/Slack/webhook) — needs
  team input. Render's failed-deploy and unhealthy-service notifications should
  be configured in the dashboard.

## 8. Verification (once tooling exists)

- [ ] Each metric M1–M8 is charted and a threshold is configured.
- [ ] Each alert in §4 has been triggered in a test and delivered to the right owner.
- [ ] A synthetic load run (Scenario A) reproduces the baselines in §2 within tolerance.
- [ ] No alert payload contains private data (§5) — audit with
      `docs/verification/privacy-log-audit.md`.
- [ ] `/health` alert fires when the container is stopped and clears on restart.
