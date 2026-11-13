# Final Report — Platform Section (Setu Guide API, Phase 2)

**Owner:** DevOps 1 · **Date:** 2026-10-24 · **Scope:** Days 1–4, reports in `docs/` only. No estimated numbers.

## 1. Summary

- **Service:** Setu Guide — stage-aware assistant API (`POST /v1/guide/chat`, `GET /health`) for the Chat with Setu Guide screen.
- **Stack:** Python 3.11, FastAPI 0.142.2, Pydantic v2, uvicorn 0.54.0; `python:3.11-slim` image (non-root, read-only, digest-pinned); in-process limiter and cache.
- **Verified:** load (20u/50u/10 min), failure drills, rate limit, cache isolation, security/secrets, timeout/shutdown/restart, contract, auth.
- **Results:** **393/393 tests pass**; **0 Critical**; 2 Medium rate-limit and 1 High shutdown defects found and fixed; **no real secret found**.
- **Not verified:** real LLM (`handle_chat` missing), backend end-to-end, and on staging the deploy SHA/restart policy/`API_KEY` path/mock-vs-real mode plus every load, failure and recovery re-run — `[PLACEHOLDER]`. Staging URL is confirmed (`https://setu-guide.onrender.com`); `/health`, `/docs` and a POST smoke returned 200 on 2026-10-24.

## 2. Validation results

All **393 tests pass** (100 %, 0 failed, 0 skipped, 2026-10-22); sub-suites: failure 47, recovery 8, integration 45, rate limit 9, cache 13. Re-run 2026-10-23 (Docker off): **382 passed, 0 failed, 11 container tests skipped**. Defects found and fixed are in §9.

## 3. Load test

Local container, `USE_MOCK=true`, locust 2.46.7, limits raised for the runs; 70 % quick-action / 30 % free-text.

| Metric | 20 users / 2 min | 50 users / 2 min | 10 min |
|---|---|---|---|
| Requests / rps | 2,091 / 17.56 | 5,045 / 42.43 | 10,969 / 18.30 |
| p50 / p95 / p99 | 46 / 49 / 51 ms | 52 / 63 / 70 ms | 51 / 59 / 66 ms |
| 4xx / 5xx error rate | 0.00 % | 0.00 % | 0.00 % |
| 429 responses | 0 | 0 | 0 |
| Cache hit ratio | 41.8 % | 20.3 % | 51.4 % |
| CPU avg / max | 5.5 % / 21.7 % | 25.6 % / 91.7 % | 11.1 % / 40.3 % |
| Memory avg / max | 69.4 / 70.0 MiB | 70.8 / 81.3 MiB | 70.0 / 78.7 MiB |
| **vs limits** | **PASS** | **PASS** | **PASS** |

**Limits:** 5xx < 1 %, p95 < 2 s mock / < 12 s real (not exercised), 429 = 0 — all met (max 200 ms, stable memory).

## 4. Failure drills

In-process, mock off, fake `handle_chat`; each drill must return 200, `fallback_used=true`, safety `pass`, no 5xx, not cached.

| Drill | Injected fault | Result | `fallback_used` |
|---|---|---|---|
| LLM down | `ConnectionRefusedError` | 200, `MISS`; repeat also `MISS` | `true` |
| LLM slow | 1 s work vs 0.05 s budget | 200, timeout in **0.06 s** | `true` |
| Provider rate limit | 429 from provider | 200, no `Retry-After`, provider text not echoed | `true` |
| Garbage output | empty, whitespace, bad JSON/schema | 200 template, no 500 | `true` |

**47/47 pass**; provider 429 not forwarded, no fallback cached; a healthy stub returns `fallback_used=false`.

## 5. Rate limiting and cache isolation

- **Rate limit 9/9:** 30/min user + 60/min IP, integer `Retry-After`, `/health` exempt (3,397 requests → 0 × 429), `X-Forwarded-For` spoof ignored; burst 5 × 200 / 195 × 429 / 0 × 5xx.
- **Abusive id:** 1,302 requests → 60 × 200 + **1,242 × 429**; 58/58 innocent requests 200. Fixed: case/space quota bypass (12 > limit 3), limiter growth (11,001 > 10,000).
- **Cache 13/13, no cross-user reply** (the Critical check). Key = `stage + intent + topic + match_id + user_id`; not cached: free text, errors, fallbacks, `modified`/`blocked`/flagged. Repeat hit **98.7 %**.

## 6. Security

| Check | Before (`day2`) | After (`day3`) |
|---|---|---|
| `pip-audit` (runtime deps) | 0 CVEs | **0 CVEs** |
| Python HIGH / MEDIUM / LOW | 4 / 12 / 2 | **0 / 0 / 0** |
| OS HIGH (rows) / UNKNOWN | 8 (44) / 3 | 8 (44) / 1 (no Debian fix) |
| Trivy secrets / image size | 0 / 307 MB | 0 / **271 MB** |

**Hardening:** digest-pinned base, build tools removed, `apt-get upgrade`, non-root, read-only rootfs, `cap_drop: [ALL]`, `no-new-privileges`, `HEALTHCHECK`, no baked secrets.

**Secrets:** gitleaks (41 commits) → 3 locations, one **synthetic** marker; **0 real secrets**; `.env` absent/untracked; image clean. **Residual:** 8 OS HIGH CVEs, no Debian fix — accepted (local-only, non-root, read-only). The chat-pasted PAT needs revocation.

## 7. Recovery

Linux container, image `setu-guide-api:day3`, mounted slow `handle_chat`.

| Scenario | Result |
|---|---|
| Timeout (2 s budget, 6 s work) | 200 + `fallback_used=true` at **3.0 s** |
| SIGTERM, 1 request (8 s) | **200**, exit **0**, stop 7.2 s |
| SIGTERM, 3 requests (20 s) | **200, 200, 200**, exit **0**, stop 19.2 s |
| Restart mid-load | `/health` 200 after **1.65 s**; 32/40 tail requests 200 |

Keep-alive 5 s; graceful 30 s / `stop_grace_period: 35s`; auth 401/401/200. **8/8 PASS on the Day-4 branch.** On this branch (`app/` = `dev`) the auth container check moved with the auth suite to `feature/auth-tests` → **7/7 PASS, re-verified 2026-11-10**. Before, an 8 s request was SIGKILLed (exit 137); Windows cannot prove graceful shutdown, so evidence is from Linux.

## 8. Integration with Sakshi (the new backend engineer)

| Item | Status |
|---|---|
| Backend end-to-end | **Not started** (lead, 2026-10-22); the previous engineer left; Sakshi now reviews the backend |
| Contract (45/45 → re-verified 36/36 on this branch, 2026-11-10) | Frozen: 8 stages, 4 intents, `message` ≤ 500, `topic` ≤ 100; required `user_id`/`match_id`/`stage`; 7-field response; one error envelope; 429 `Retry-After`; `fallback_used=true` = normal 200; 15 s client timeout. The auth half (25 tests) moved to `feature/auth-tests` — `dev` has no inbound auth |
| Auth | `X-API-Key` / Bearer, default `none`, key from env, constant-time — implemented and tested on `feature/auth-tests` / `feature/phase2-day4-recovery-integration`, **not in `dev`**; no credential issued |
| Gap | AI/ML `handle_request()` uses a different internal shape; mapping unagreed; ~~`handle_chat` missing (#15)~~ landed via PRs #36/#37, staging build predates it |
| Staging | URL confirmed 2026-10-24 (`https://setu-guide.onrender.com`); `/health`, `/docs` and POST smoke → 200; 2026-11-01 retest on the lead's target → `docs/render_retest_results.md`; restart recovery → `docs/recovery_test_results.md` |

**Open items:** schema mapping; backend URL/test window; auth issuer/rotation; backend handling of 429/422/`fallback_used`; staging deploy details and test window; `handle_chat` timeline.

## 9. Bugs

| Severity | Found | Fixed | Open / accepted | Owner(s) |
|---|---|---|---|---|
| Critical | 0 | 0 | 0 | — |
| High | 3 | 2 | 1 (accepted) | DevOps 1 |
| Medium | 7 | 4 | 3 | DevOps 1, lead, DevOps 2 |
| Low | 4 | 2 | 2 | DevOps 1, AI/ML 3 |
| Info | 1 | 0 | 1 (by design) | DevOps 1 / DevOps 2 |
| Unknown | 1 | 1 | 0 | DevOps 1 |
| **Total** | **16** | **9** | **7** | |

**Fixed (9):** 2 High (SIGKILL, build tooling), 4 Medium (quota bypass, limiter, 500 id, auth), 2 Low, 1 Unknown. **Open (7):** 1 High (OS CVEs), 3 Medium (`handle_chat`, staging build, public endpoint), 2 Low (provider timeout, `api.md`), 1 Info (marker).

*Counts consolidate the findings logs in the Phase-2 reports and scan reports; the shared `docs/verification/bug-tracker.csv` is still header-only.*

## 10. Known limits

- **Ops gaps:** single instance — in-memory limiter/cache, Redis needed for replicas; no monitoring beyond logs and `/health`.
- **Free-tier quota:** mock load runs; real mode hit the fallback without a provider, so p95 < 12 s stays unmeasured until `handle_chat`.
- **Container tests need Docker** and skip in CI; no readiness probe; 8 OS HIGH CVEs.

## 11. Exit criteria status

| Criterion | Status | Evidence |
|---|---|---|
| Stable under agreed load | **Met** for tested profiles (limits pending lead) | 0 % 5xx, 0 × 429, p95 49–63 ms vs < 2 s, stable memory |
| LLM-failure fallback proven | **Met** | 4 drills → 200 + `fallback_used=true`, not cached; recovery → `false` |
| No private data in logs | **Met** | Sentinel tests on 5 status paths; 53,000+ lines, 0 markers |
| No secrets found | **Met** | History, worktree, image, env/logs → 0 real secrets; 1 synthetic marker |

All four met **locally**; staging shows reachability only (one POST smoke → 200, 2026-10-24), no load/failure/recovery run. The PAT still needs revocation.

## 12. Recommendations for production

1. Redis for the limiter and cache before more than one instance.
2. Finish `handle_chat`, wire the provider timeout, re-run real mode (5u/60 s) for p95 < 12 s.
3. Deploy Day-3/4 to staging; set `terminationGracePeriodSeconds ≥ 35 s`; re-run shutdown tests; then enable auth.
4. Add alerts on 5xx, p95, `fallback_used` and 429; clients use a 15 s timeout and honour `Retry-After`.

## 13. Placeholders still unconfirmed

| Placeholder | Current | Owner |
|---|---|---|
| Staging deploy SHA, restart policy, `API_KEY`, mock/real, auth envs, test window | `[PLACEHOLDER]` — Render owner | lead / DevOps 2 |
| Auth method, issuer/rotation, environments | `X-API-Key` choice, default `none` | lead |
| Load profiles, limits, timeout, provider, `handle_chat` | 20u/50u/10-min; p95 < 2 s/12 s; 5xx < 1 %; 429 = 0; 30/60 min; 10 s; missing | lead, AI-ML, DevOps 2 |
