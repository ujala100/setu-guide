# Recovery, timeout and graceful-shutdown notes - Phase 2, Day 4

**Date:** 2026-10-22 · **Owner:** DevOps 1 (`app/api/`, `docker/`) · **Branch:** `feature/phase2-day4-recovery-integration`
**Suite:** `tests/recovery/test_timeouts_shutdown.py` (8 tests) · **Result: 8/8 PASS** (the 7 shutdown/timeout tests all failed before the graceful-shutdown fix; the 8th, the container auth check, is new)

Environment: real Linux container (`docker run`, Docker Desktop 29.8.2, WSL2
kernel 6.6), image `setu-guide-api:day3` built from the current
`docker/Dockerfile` (the lead's instruction was to run on `setu-guide-api:day3`).
Synthetic ids only (`recovery_user`, `recovery_m1`).

**Staging is [PLACEHOLDER].** The lead has not confirmed a staging endpoint
("treat staging as not ready"), so every staging result below is a placeholder
and no staging run is claimed. See the **Staging** section at the end.

Real mode does not have a working orchestrator entry yet
(`app.core.orchestrator.handle_chat` is a lead follow-up, tracked as #15), so a
real-mode request would fall back instantly and never stay in flight. To
exercise the timeout and shutdown paths the tests run a **mounted launcher**
(`tests/recovery/slow_orchestrator.py`) that installs a slow `handle_chat` and
starts uvicorn with the same flags as the image CMD. **Nothing under `app/core`
is modified** and the repo image stays production-shaped.

## Checklist

| # | Scenario | Steps | Expected | Actual | Recovery time | Verdict |
|---|----------|-------|----------|--------|---------------|---------|
| 1 | LLM timeout exceeded | `LLM_TIMEOUT_SECONDS=2`, orchestrator sleeps 6s; one `POST /v1/guide/chat` | 200 with `fallback_used=true`, no hang, no 5xx | 200, `fallback_used=true`, **3.0s** (= 2s budget + 1s margin) | n/a (bounded latency) | PASS |
| 2 | Request inside budget | `LLM_TIMEOUT_SECONDS=90`, orchestrator sleeps 3s | 200 with the real reply, `fallback_used=false` | 200, real reply, `fallback_used=false`, **3.0s** | n/a | PASS |
| 3 | SIGTERM with one in-flight request | orchestrator sleeps 8s; request in flight; `docker stop -t 35` | in-flight request answered 200; container exits 0 | 200 with real reply, **8.0s**; `docker stop` returned in 7.2s; exit **0** | 7.2s to stop | PASS |
| 4 | SIGTERM with 3 concurrent in-flight requests | 3 requests, 20s each; `docker stop -t 35` | all three answered 200; container exits 0 | 200, 200, 200 (**20.0s** each); exit **0** | 19.2s to stop | PASS |
| 5 | Server keep-alive is bounded | one HTTP/1.1 connection, first request, then idle | server closes the idle connection near `--timeout-keep-alive` (5s) | idle socket closed by the server inside the window | n/a | PASS |
| 6 | Restart in the middle of a load run | 3 loader threads; `docker restart` while loading; then poll `/health` | service returns healthy on its own; load client recovers; no manual step | `/health` 200 after **1.65s**; running load resumed (32/40 tail requests 200; the rest are the restart window) | 1.65s to healthy | PASS |
| 7 | Shipped config guard (regression) | read `docker/Dockerfile` CMD and `docker-compose.yml` | `--timeout-graceful-shutdown`, `--timeout-keep-alive` present; `stop_grace_period` > graceful window | flags present (30s / 5s); `stop_grace_period: 35s` > 30s | n/a | PASS |
| 8 | API key enforced in the real container | container started with `AUTH_METHOD=api_key` and a key in the environment | no key -> 401; wrong key -> 401; right key -> 200; `/health` -> 200 without a key; the key never appears in the body or the logs | 401, 401, 200, 200; key absent from the response body and from `docker logs` | n/a | PASS |

### Restart policy and HEALTHCHECK

The container runs with `restart: unless-stopped` (already in
`docker-compose.yml`) and the image `HEALTHCHECK` (`--interval=30s
--timeout=5s --start-period=15s --retries=3`, probing `/health` with the
standard library). Scenario 6 shows the pair working together: the container
comes back by itself and reports healthy with no manual step and no
`docker compose up` re-run.

## Finding - in-flight requests were SIGKILLed on stop (High, fixed here)

**Before (probe):** the image CMD carried no graceful-shutdown flag and
`docker-compose.yml` had no `stop_grace_period`. On `docker stop` uvicorn
announced "Waiting for connections to close" but the container was killed
anyway and the caller saw a dropped connection:

| Config | Orchestrator work | Request result | Stop duration | Exit code |
|--------|-------------------|----------------|---------------|-----------|
| image CMD default, no `stop_grace_period` | 3s | 200 (fits) | 2.3s | 0 |
| image CMD default, no `stop_grace_period` | **8s** | **connection DROPPED** (`RemoteDisconnected`) | 3.3s | **137 (SIGKILL)** |
| CMD default, explicit `-t 10` | 8s | **connection DROPPED** | 3.3s | **137** |
| CMD `--timeout-graceful-shutdown` 30 + `-t 35` | 8s | 200 | 7.2s | 0 |
| CMD `--timeout-graceful-shutdown` 30 + `-t 35` | 20s | 200 | 19.3s | 0 |
| CMD `--timeout-graceful-shutdown` 30 + `-t 35` | 3 × 20s | 200, 200, 200 | 19.2s | 0 |

Any request whose work outlasts the stop window was cut off, so a caller could
see a dropped connection instead of a reply or the clean `fallback_used=true`
answer. This is exactly the case a rolling restart or a deploy creates.

**Fix (API/infra layer only, no `app/core`, `app/rag` or `app/safety` edits):**

- `docker/Dockerfile` CMD now sets `--timeout-graceful-shutdown 30` (a superset
  of the request budget, `LLM_TIMEOUT_SECONDS` + 1s margin) and
  `--timeout-keep-alive 5` (idle connections cannot pin worker slots).
- `docker-compose.yml` sets `stop_grace_period: 35s`, greater than the uvicorn
  graceful window, so Docker does not SIGKILL before uvicorn finishes draining.

**After:** scenarios 3-4 above - in-flight requests complete with 200 and the
container exits cleanly (code 0).

## Notes and limits

- **Keep-alive value.** 5s is deliberately short. Uvicorn's default is 5s
  already; making it explicit and tested stops a future change from silently
  holding idle connections open. If a load balancer in front needs longer-lived
  upstream connections this value should be revisited with DevOps 2.
- **Graceful window.** 30s assumes `LLM_TIMEOUT_SECONDS` <= 29s. If the real
  provider budget is raised above that, both the CMD flag and
  `stop_grace_period` must move together - test 7 will fail loudly if they
  drift apart.
- **Windows is not a valid signal source.** `send_signal(SIGTERM)` on Windows
  terminates the process without running handlers, so graceful shutdown can
  only be proven inside the Linux container. The suite therefore does no
  host-side signal test.
- **Overall request timeout.** The API caps each call at
  `LLM_TIMEOUT_SECONDS + 1.0s` (`TIMEOUT_MARGIN_SECONDS` in
  `app/api/chat.py`). Scenario 1 confirms the fallback fires at that budget.
- **Restart mid-load** is also covered end to end by
  `tests/failure/test_container.py` (Day 3); scenario 6 keeps a Day-4 view that
  ties the recovery to the graceful-stop work.

## Staging - [PLACEHOLDER]

**No staging endpoint has been confirmed by the lead** ("I have not confirmed a
staging endpoint yet, so please treat staging as not ready"). There is no base
URL, no access method (VPN or allowlist), no deploy owner and no shared test
window yet. **Everything in this section is a placeholder and no staging run is
claimed.**

| # | Scenario | Steps | Expected | Actual | Recovery time | Verdict |
|---|----------|-------|----------|--------|---------------|---------|
| 8 | Staging liveness | `GET /health` | 200 `{"status":"ok"}` | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 9 | Staging chat | `POST /v1/guide/chat`, synthetic ids | 200 with the 7 documented fields | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 10 | Staging cache | same request twice | `MISS` then `HIT` | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 11 | Staging rate limit | 31 rapid calls, one user | 30 allowed, the 31st -> 429 + `Retry-After` | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 12 | Staging per-user isolation | a different `user_id` after the quota was used up | 200 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 13 | Staging latency | 10 sequential calls | within the client budget | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |

**What needs staging before these can be filled in** (the lead says DevOps 2
deploys via CI):

- [PLACEHOLDER] staging base URL
- [PLACEHOLDER] who deploys, and who may restart the service during a test
  window - the shutdown scenarios (3-4) need a restart on a real deployment
- [PLACEHOLDER] access method (VPN or allowlist)
- [PLACEHOLDER] the image tag deployed on staging - the Day 3 and Day 4 fixes
  are both still un-deployed
- [PLACEHOLDER] a shared test window for the load and restart runs

**Note for the lead - an unconfirmed public endpoint was reachable.** While
looking for the staging URL, one was found in the Postman collection
description: `https://setu-guide.onrender.com` (Render behind Cloudflare). On
2026-10-21 it was reachable from this machine and answered the same contract.
It is **not** treated as staging here because the lead has not confirmed it,
but it needs a decision: if it is ours it is **public and unauthenticated** and
runs a build without the Day 3 rate-limit fix; if it is not ours it should be
taken down. The probe was read-only, with synthetic ids. The same note is in
`docs/integration_check.md`.

**Staging also runs with mock mode** (`USE_MOCK=true`) in the observed
deployment, so the timeout scenarios (1-2) cannot be reproduced there without a
real provider - a real-mode run also needs `app.core.orchestrator.handle_chat`
(issue #15).

## Bug tracker

| Ref | Severity | Finding | Owner | Status |
|-----|----------|---------|-------|--------|
| Day-4 / finding 1 | High | In-flight request SIGKILLed on stop (no graceful-shutdown flag, no `stop_grace_period`) | DevOps 1 | Fixed in this branch; container test `test_inflight_request_survives_graceful_stop` |
| Day-4 / finding 2 | Low | No explicit keep-alive bound (default only) | DevOps 1 | Fixed: `--timeout-keep-alive 5` + test `test_idle_keepalive_connection_is_released` |
| Day-4 / finding 3 | Medium | Staging runs a pre-Day-3 build: the rate-limit bucket is not normalised, so `user_id` case/whitespace variants still get a fresh quota | DevOps 1 / lead | Open - needs PR #18 merged and deployed to staging, then re-check |
| Day-4 / finding 4 | Info | Staging is publicly reachable and has no authentication | lead | Open - decision needed, see `docs/integration_check.md` |
| Day-4 / finding 5 | Medium | No inbound authentication on the API at all | DevOps 1 / lead | Fixed in this branch (`X-API-Key` / Bearer, method configurable) + scenario 8; the rollout default stays `none` until the lead confirms the method |
