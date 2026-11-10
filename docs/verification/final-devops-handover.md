# Final DevOps 2 handover — audit and release readiness

Owner: DevOps 2. Audit date: **2026-11-05** (UTC).
Repository: `/home/kali/setu-guide`, remote `https://github.com/ujala100/setu-guide.git`.
Code audit ref: `feature/devops2-deploy-runbook` at
`7ebf17d6c11d3d442433c11e401f96af1eacb700`. This handover was added in
docs-only commit `f013b2e` and is updated by a further docs-only commit
recording release verification; neither commit changes application code or CI.
The original audit results remain as written; §9 records the later release-tag
and Render deployment evidence that supersedes specific pending statuses in §8.

## 1. Completed tasks

| # | Task | Result |
|---|---|---|
| 1 | Repository and PR audit | Done — working tree clean, remote refs fetched, PR #33 and #13 inspected. |
| 2 | CI verification | Done — PR #33 runs `41604222814` and `41975639594` green; intentional failure run `41601173424` confirmed. |
| 3 | Test verification | Done — full suite via `.venv`, `git diff --check` clean. |
| 4 | Staging verification | Partial — live `GET /health` verified; supplied Render deployment evidence recorded in §9; no independent dashboard session. No POST, no mutation. |
| 5 | Privacy and monitoring audit | Repository/automated checks done; live Render log checks not done. |
| 6 | Release readiness | At audit start: blocked — no frozen SHA, no approval, no tags, no deployed-SHA evidence. Superseded for frozen SHA, tag, deployment SHA and Auto-Deploy by §9; PR #33 approval and other checks remain pending. |
| 7 | Final handover | This document. |
| 8 | Finalization | Handover cross-checked; PR #33 description updated; docs-only commit `f013b2e` created on the same branch. |
| 9 | v0.1 release verification | Done — annotated `v0.1` at `eef7ac2`; remote tag, local tag and supplied Render deployment evidence match (§9). |

This documentation update did not change application code, CI workflow,
dependencies, tags, branches, merge state or staging settings. The `v0.1` tag
and Render deployment were performed outside this documentation update and are
recorded as supplied evidence in §9.

## 2. Repository and PR status

### 2.1 Git state (historical at audit start; see §9 for release state)

| Item | Value |
|---|---|
| Current branch | `feature/devops2-deploy-runbook` |
| Code audit HEAD | `7ebf17d` — `docs(devops2): clarify orchestrator entry-point wording` (2026-11-03 14:03:51 +0530) |
| Upstream at audit start | `origin/feature/devops2-deploy-runbook` (same commit) |
| vs `origin/dev` at audit start | 7 ahead, 0 behind; 8 ahead after `f013b2e`; 9 ahead after the release-verification commit |
| `origin/dev` tip | `eef7ac2` — `Fix/handle chat alias (#37)` |
| Working tree | Clean at audit start; only this report was modified for the release-verification update |
| Preserved stash | `stash@{0}: On feature/devops2-deploy-runbook: WIP runbook before syncing with origin/dev` |
| Local `dev` | `5f91a1a`, behind `origin/dev` by 3 |
| Finalization commit | `f013b2e` — docs-only commit adding this handover |
| Release-verification commit | Docs-only commit recording the `v0.1` evidence; see PR #33 head |

### 2.2 PR #33

| Field | Value |
|---|---|
| Title | `docs(devops2): expand deployment and rollback runbook` |
| State | **OPEN**, not draft |
| Base / head | `dev` / `feature/devops2-deploy-runbook` |
| Head commit at audit start | `7ebf17d6c11d3d442433c11e401f96af1eacb700` |
| PR head after finalization | `f013b2e597bab059d1b2560bb4fbadc987fdc0e7` |
| PR head after release verification | Docs-only release-verification commit (see PR #33 head) |
| Mergeability | `MERGEABLE` / `CLEAN` |
| Review decision | Empty — **no approving review submitted** |
| Reviews / review requests | None / none |
| Review comments / issue comments | 0 / 0 |
| Changed files | 7 files before the release-verification update; that update changes only this document |
| Checks at audit start | `test` pass, `GitGuardian Security Checks` pass |
| Checks after finalization | Run `41975639594` — `test` pass, `GitGuardian Security Checks` pass |
| Checks after release verification | New run triggered by the docs-only commit; see PR #33 Checks |
| URL | `https://github.com/ujala100/setu-guide/pull/33` |

The PR description was updated on 2026-11-05 to correct three stale claims in
the original body:

- The original body claimed **315 passed, 3 skipped**; the current CI run at
  `7ebf17d` reports **321 passed, 3 skipped**.
- The original body described the change as only
  `docs/verification/runbook.md`; the PR changes six pre-existing files
  (`README.md`, `docs/api.md`, the Postman collection,
  `docs/verification/devops2-handover.md`, `docs/verification/monitoring.md`,
  `docs/verification/runbook.md`) plus this handover.
- The original body referred to an "existing `v0.1` tag"; **no tag exists**
  locally or on the remote (verified with `git tag -l`,
  `git ls-remote --tags`, and the GitHub tags API).

No review comment threads are open on PR #33.

### 2.3 PR #13

Confirmed **MERGED** on `2026-10-20T04:42:08Z`, merge commit
`4b48e5b97a330ec201a29cd8318f2fcf7e383aa8`
(`docs(devops2): add verification and handover docs (#13)`), present on
`origin/dev`.

### 2.4 Other open PRs

All have green latest checks and no recorded review decision:

| PR | Target | Branch |
|---|---|---|
| #39 | `dev` | `feature/phase2-day4-recovery-integration-v2` |
| #35 | **`main`** | `aiml-intern1-improvements` |
| #34 | `dev` | `feature/aiml3-router-responder` |
| #29 | `dev` | `feature/phase2-day4-recovery-integration` |
| #25 | `dev` | `feature/rag-evaluation-and-safety` |
| #18 | `dev` | `feature/phase2-day3-security` |

PR #35 targeting `main` is a release-scope question for the project lead.

## 3. CI results

Workflow: `.github/workflows/ci.yml` — the only workflow. Triggers: PRs to
`dev`/`main`, pushes to `dev`, and `workflow_dispatch`. One job (`test`) on
`ubuntu-latest`, Python 3.11: checkout → setup-python → `pip install -r
requirements-dev.txt` → `python -m pytest -q`. CI does **not** build Docker
images or run Locust.

| Run | Event / ref | Result | pytest evidence |
|---|---|---|---|
| `41604222814` | PR #33, `7ebf17d` | **success** | 321 passed, 3 skipped, 1 warning in 2.66s |
| `41975639594` | PR #33, `f013b2e` | **success** | 321 passed, 3 skipped, 1 warning in 2.08s |
| `41601173424` | `workflow_dispatch`, `demo/ci-intentional-failure-20261103133902`, `8e5e5e3` | **failure (intentional)** | 1 failed, 321 passed, 3 skipped, 1 warning in 3.96s |

The release-verification commit triggers another `ci / test` run; check PR #33's
Checks tab for its result rather than treating the `f013b2e` run as the final
head.

### 3.1 Intentional failure demonstration

The retained failure is deliberate:

- Test: `tests/test_intentional_ci_failure_demo.py::test_intentional_ci_failure_demo`
- Failure: `AssertionError: intentional CI failure demonstration` at
  `assert False`, file line 8.
- It ran on a throwaway `demo/...` branch via `workflow_dispatch`, not on `dev`
  or on PR #33. That branch has since been deleted and the demo file is not in
  the current tree.
- It is **not** a project regression. PR #25's failure `41417132940` was
  superseded by later green runs on the same branch. The `feature/company-pr`
  run `41328904676` is a standalone historical failure: that branch is no longer
  on the remote and has no later run, and it is not the head branch of any open
  PR. No open PR has a failing latest check.

## 4. Test results (current)

Environment: `.venv/bin/python` = Python **3.11.17**, pytest **9.1.1**.

| Check | Result |
|---|---|
| Full suite, before local image build | 321 passed, 3 skipped, 1 warning |
| Container tests after local image build | 3 passed, 1 warning |
| Full suite, `f013b2e` finalization run | 324 passed, 0 skipped, 1 warning in 28.67s |
| **Full suite, release-verification run** | **324 passed, 0 skipped, 1 warning in 28.40s** |
| Privacy tests (`tests/failure/test_log_privacy.py`) | 2 passed, 1 warning |
| `git diff --check` | Exit 0, no output |

The three earlier skips were `tests/failure/test_container.py` because
`setu-guide-api:day3` was not built. I built it locally with
`docker build -t setu-guide-api:day3 -f docker/Dockerfile .`; the container
tests then passed. This is local runtime evidence only — CI still skips them.

Warning (unchanged): `StarletteDeprecationWarning: Using httpx with
starlette.testclient is deprecated; install httpx2 instead`, emitted from
`fastapi/testclient.py`.

## 5. Staging verification

Base URL confirmed from `docs/api.md` §2 and §22, README, the Postman collection
default and `docs/verification/runbook.md`:
`https://setu-guide-1wiy.onrender.com`.

### 5.1 Live read-only evidence (this audit)

`GET /health` with `X-Request-Id: audit-health-20261105053843`, at
`Thu, 05 Nov 2026 05:39:15 GMT`:

- `HTTP/2 200`, body `{"status":"ok"}`
- `x-request-id` echoed exactly
- No `X-Cache`, no `Retry-After`
- `server: cloudflare`, `x-render-origin-server: uvicorn`,
  `cf-cache-status: DYNAMIC`
- `GET /docs` returned `HTTP 200` in 0.277s

Post-release read-only check, `GET /health` with
`X-Request-Id: audit-release-20261105071454`, at
`Thu, 05 Nov 2026 07:15:36 GMT`: `HTTP/2 200`, body `{"status":"ok"}`,
`x-request-id` echoed, no `X-Cache`/`Retry-After`; `GET /docs` returned
`HTTP 200` in 0.3046s. This confirms liveness only; it does **not** prove which
commit Render is serving. The deployment SHA evidence in §9 comes from the
supplied Render dashboard evidence.

No POST request was sent and no staging state was mutated. The full §22 smoke
checklist (chat, cache HIT/MISS, safety, 422/404/405) is therefore **not run**.

### 5.2 Documented or verifiable from the repository

| Item | Fact | Source |
|---|---|---|
| Runtime entry point | `app.main:app` re-exports `app.api.main:app` | `app/main.py` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | `docs/verification/runbook.md`; Docker `CMD` uses port 8000 |
| Build command | `pip install -r requirements.txt` | `docs/verification/runbook.md` |
| Health path | `GET /health` | `app/api/main.py`; `docker/Dockerfile` |
| Docker healthcheck | `/health` every 30s, 5s timeout, 3 retries | `docker/Dockerfile` |
| Env var names | `USE_MOCK`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`, `RATE_LIMIT_PER_USER`, `RATE_LIMIT_PER_IP`, `TRUSTED_PROXY`, `CACHE_ENABLED`, `CACHE_TTL_SECONDS`, `CACHE_MAX_ITEMS`, `LOG_LEVEL`, `INTERNAL_API_KEY`; `PYTHON_VERSION` is Render-side | `.env.example`, `app/config.py` |
| Staging model (documented, not independently verified) | Render Free, native Python, single instance, manual deploy from `dev` | `docs/verification/runbook.md` |

### 5.3 Render dashboard facts (supplied or unverified)

- Actual build/start command and instance details: **not supplied**; the
  supplied evidence records only runtime Python 3 and the Free plan (§9.5).
- Source branch, Auto-Deploy state and current deployed commit SHA: **supplied
  evidence says `dev`, OFF and `eef7ac2` (§9.5–§9.7); not independently
  verified in this audit.**
- Health-check path setting, `$PORT` wiring and cold-start behavior: **not
  supplied or verified.**
- Live values of `USE_MOCK`, `LOG_LEVEL`, `TRUSTED_PROXY`, rate limits, cache
  settings and `PYTHON_VERSION` (name only for the last): **not supplied or
  independently verified.**
- Deploy Events, live logs, log retention and any log shipper: **not supplied
  or verified.**

## 6. Privacy audit

### 6.1 Completed

- Read `docs/verification/privacy-log-audit.md`, `docs/verification/monitoring.md`,
  `docs/api.md` §18/§22 and `tests/failure/test_log_privacy.py`.
- `pytest tests/failure/test_log_privacy.py -q` → **2 passed**.
- Full suite (including the container log-privacy test) → **324 passed**.
- `.env` is not tracked (`git ls-files .env` empty).
- Secret-pattern scan of tracked files (`sk-...`, `ghp_...`, `AKIA...`) returned
  no matches.
- Code inspection confirms the access line is limited to
  `request_id/method/path/status/latency_ms/cache/intent/stage/fallback_used`.

### 6.2 Not verified — needs Render logs/dashboard

- Sentinel-marker grep against **staging** logs (`PRIVACY-MARKER-*`,
  `privacy-marker-*`, `sk-PRIVACY-*`).
- Positive control that staging emits `http_request` lines.
- Confirmation that staging logs contain only the allowed fields.
- Live `LOG_LEVEL` value and whether any external log sink exists.
- Retention/sampling behavior on the Render plan.

No live-log claim is made. The bug tracker remains header-only; no new defect
was confirmed.

## 7. Monitoring status

Status: **requirements only; no monitoring stack in the repository.**

- No Prometheus/Grafana/Alertmanager/Datadog/Sentry/OpenTelemetry config exists.
- `docs/verification/monitoring.md` defines metrics M1–M8, thresholds and
  owners, but they are not implemented or charted.
- `docs/verification/runbook.md` documents these Render-native capabilities:
  outbound bandwidth / Network Metrics, the Events timeline, live logs,
  failed-deploy notifications and unhealthy-service notifications.
- It also records that HTTP request logs are a Pro-workspace feature and that
  no custom dashboard or metrics exporter exists on the current Free service.
- Notification destinations are **not configured or verified**.

## 8. Release readiness

**Update note (2026-11-05, release verification).** At the original audit start
the repository had no tags, no frozen SHA and no Render deployment evidence.
Those observations were accurate at that time and remain in §2.1 and §3. The
table below records the later `v0.1` evidence from §9 and marks each superseded
item explicitly. PR #33 approval, live-log checks, health-check configuration,
notification delivery, runtime settings and branch protection remain pending.

| Item | Status |
|---|---|
| Release tags | **`v0.1` published** — annotated tag object `182401b`, peeled commit `eef7ac2`. *Historical: no tags existed at audit start; superseded by §9.* |
| GitHub releases | None — a Git tag is not a GitHub Release |
| Frozen SHA from project lead | **Verified:** `eef7ac24b11c0bec5f682b121cb37eeec1a192a3`, ancestor of `origin/dev`. *Historical: not provided at audit start; superseded by §9.* |
| Release approval | **No explicit written approval record** in PR #33 or the repository; tag and deployment evidence were supplied separately |
| PR #33 description | Updated 2026-11-05; refreshed again after release verification |
| PR #33 review/approval | **Not approved** (no reviews) |
| PR #33 merge | **Not merged** (not an ancestor of `origin/dev`) |
| Staging deployed SHA | **`eef7ac2`** per supplied Render dashboard evidence; matches the tag. *Historical: unknown at audit start; superseded by §9.* |
| Render deployment | **Live** — manual dashboard deploy, 54.4 s, 2026-11-05 (§9.5) |
| Auto-Deploy | **OFF** per supplied Render dashboard evidence (§9.7) |
| Pull Request Previews | **OFF** per supplied Render dashboard evidence (§9.7) |
| Approval to deploy/tag | **Evidence supplied** — tag published and deployment live; no separate approval record in the repository |
| Branch protection | **Unconfirmed** — branch-rules API returns no rules; classic protection API returns 404 with a non-admin token |
| Open release-scope PRs | 6, including #35 targeting `main` |

### 8.1 Information still required from the project lead

1. Explicit approval to merge **PR #33**, and a decision on the other open PRs.
2. Release scope: whether `main` also receives the release (PR #35 targets `main`).
3. Confirmation that `v0.1` at `eef7ac2` and the supplied Render deployment are
   the intended release artifacts, plus a durable record of that approval.
4. Confirmation of staging `USE_MOCK` mode, `LOG_LEVEL`, `TRUSTED_PROXY`, rate
   limits and whether real-mode validation is in scope.
5. A repo admin to configure/confirm branch protection or rulesets on `main`
   and `dev`.
6. A Render platform admin to provide independent evidence for health-check
   configuration, notification delivery and logs, and to configure the
   failed-deploy/unhealthy-service notifications.

## 9. Release Verification — Setu Guide v0.1

Verification date: **2026-11-05**. All Git commands below were run in
`~/setu-guide`; Render facts are the supplied dashboard evidence, not an
independent dashboard session.

### 9.1 Frozen commit

| Field | Value |
|---|---|
| Frozen SHA | `eef7ac24b11c0bec5f682b121cb37eeec1a192a3` |
| Short SHA | `eef7ac2` |
| Commit subject | `Fix/handle chat alias (#37)` |
| Commit date | 2026-11-01 12:39:06 +0530 |
| Branch containment | `origin/dev` and `origin/HEAD` contain the commit |

### 9.2 Annotated tag

| Field | Value |
|---|---|
| Tag name | `v0.1` |
| Local tag object | `182401b24f522713af6bd2c55315b8cca2f330fe` |
| Object type | `tag` (annotated, not lightweight) |
| Tagger | `25-Ankit <ankitmishra200625@gmail.com>` |
| Tagger date | 2026-11-05 12:38:28 +0530 |
| Tag message | `Setu Guide v0.1` |
| Peeled commit | `eef7ac24b11c0bec5f682b121cb37eeec1a192a3` |
| Local tag ref | `refs/tags/v0.1` |

This documentation update did not create, move, delete or force-push the tag.

### 9.3 Publication to origin

| Ref | Value |
|---|---|
| `refs/tags/v0.1` | `182401b24f522713af6bd2c55315b8cca2f330fe` |
| `refs/tags/v0.1^{}` | `eef7ac24b11c0bec5f682b121cb37eeec1a192a3` |
| GitHub tags API | `v0.1` → `eef7ac24b11c0bec5f682b121cb37eeec1a192a3` |

The annotated tag object and its peeled commit are both published on `origin`.

### 9.4 Local and remote verification

| Check | Command | Result |
|---|---|---|
| Local tag exists | `git show --no-patch --format=fuller v0.1` | Annotated tag; tagger and message shown |
| Tag is annotated | `git cat-file -t v0.1` | `tag` |
| Peeled local tag | `git rev-parse 'v0.1^{commit}'` | `eef7ac24b11c0bec5f682b121cb37eeec1a192a3` |
| Remote tag refs | `git ls-remote --tags origin 'refs/tags/v0.1*'` | `refs/tags/v0.1` = `182401b...`; `refs/tags/v0.1^{}` = `eef7ac2...` |
| Commit on integration branch | `git merge-base --is-ancestor eef7ac2... origin/dev` | Exit 0 |

### 9.5 Render deployment evidence (supplied)

The following facts were supplied from the Render dashboard. They were not
independently re-read from Render during this documentation update.

| Field | Value |
|---|---|
| Service | `setu-guide` |
| Platform | Render |
| Runtime | Python 3 |
| Plan | Free |
| Git branch | `dev` |
| Staging URL | `https://setu-guide-1wiy.onrender.com` |
| Active deployment SHA | `eef7ac2` |
| Deployment method | Manual Dashboard deployment |
| Deployment result | Deploy succeeded / Live |
| Deployment duration | 54.4 seconds |
| Deployment date | 2026-11-05 |
| Auto-Deploy | OFF |
| Pull Request Previews | OFF |

The dashboard showed the successful deployment using the same commit as the
frozen `v0.1` release tag.

### 9.6 Deployment SHA and release-tag SHA match

| Evidence | SHA |
|---|---|
| `v0.1` peeled commit | `eef7ac24b11c0bec5f682b121cb37eeec1a192a3` |
| Render active deployment (short) | `eef7ac2` |
| Match | **Yes** — Render's short SHA matches the first 7 characters of the peeled tag commit |

### 9.7 Auto-Deploy and PR Previews

The supplied dashboard evidence records **Auto-Deploy OFF** and **Pull Request
Previews OFF**. This matches the runbook's documented staging model (manual
deployment only). No Render setting was changed during this update.

### 9.8 Release verification limitations and remaining external checks

- Render facts are supplied dashboard evidence; no independent Render session
  or API access was available in this update.
- No live Render privacy-log audit was performed. Sentinel-marker greps and
  access-line inspection still require Render log access.
- Health-check configuration evidence (the dashboard health-check setting and
  probe behavior) was not supplied; the HTTP `GET /health` checks in §5 prove
  liveness only.
- Notification delivery was not verified.
- Runtime environment settings (`USE_MOCK`, `LOG_LEVEL`, `TRUSTED_PROXY`, rate
  limits, cache settings, `PYTHON_VERSION`) were not independently verified.
- Branch protection/rulesets remain unconfirmed.
- PR #33 still needs team-lead approval and has not been merged.
- The full staging POST smoke suite was not run; no POST requests were sent.
- No release approval record exists in the repository or PR #33 reviews.

## 10. External dependencies and blockers

| Blocker | Impact | Owner |
|---|---|---|
| Render evidence is supplied dashboard evidence; no independent Render session or API access in this audit | Cannot independently verify deployed SHA, health-check configuration, notifications or logs | Project lead / platform admin (`ujala100`) |
| PR #33 has no approving review | Cannot merge or treat the runbook PR as approved | Project lead |
| Release approval not recorded | Tag and deployment evidence exist, but there is no durable approval record in the repository or PR | Project lead |
| Release scope (`main` vs `dev`) not confirmed | PR #35 targets `main`; final release scope is unresolved | Project lead |
| Health-check configuration evidence not supplied | Dashboard health-check setting and probe behavior unverified | Platform admin |
| Notification delivery not verified | Failed-deploy/unhealthy-service alerts may not reach owners | Platform admin + DevOps 2 |
| Runtime environment settings not independently verified | Mode, log level, proxy trust and limits are unknown for the live service | Platform admin / DevOps 2 |
| Live Render privacy-log audit not run | Staging log privacy remains unverified | DevOps 2, after access/approval |
| Branch protection/rulesets unconfirmed | Merge-gating policy unknown; DevOps 2 Day 1 item still open | Repo admin |
| Repo API reports visibility **public** while the old handover says private | Privacy/access-policy discrepancy to confirm | Project lead |
| Full staging POST smoke not run | Staging behavior beyond `/health` is unverified | DevOps 2, after approval |
| CI skips the 3 container tests | Green CI means unit/failure tests only | DevOps 2/DevOps 1 decision |
| Real-LLM p95 (12s target) unvalidated | Real-mode performance unknown | Project lead / AI-ML |

## 11. Outstanding-action register

### 11.1 Completed by release verification (2026-11-05)

| Action | Evidence |
|---|---|
| Frozen SHA identification and verification | `eef7ac24b11c0bec5f682b121cb37eeec1a192a3`; ancestor of `origin/dev` (§9.1) |
| Annotated `v0.1` tag creation and publication | Local tag object `182401b`; remote `refs/tags/v0.1` and peeled `eef7ac2` (§9.2–§9.4) |
| Render deployment verification for `eef7ac2` | Supplied dashboard evidence: Live, manual deploy, 54.4 s, 2026-11-05 (§9.5) |
| Auto-Deploy verification | Supplied dashboard evidence: OFF; PR Previews OFF (§9.7) |

### 11.2 Remaining actions

| Action | Owner | Precondition |
|---|---|---|
| Review and approve PR #33 | Project lead | Current report; no reviews yet |
| Merge PR #33 after approval | Project lead | Approval complete |
| Confirm release scope (`main` vs `dev`) and record release approval | Project lead | §9 evidence |
| Run live Render privacy-log audit | DevOps 2 | Render access + approval |
| Obtain health-check configuration evidence | Platform admin + DevOps 2 | Render dashboard access |
| Verify notification delivery | Platform admin + DevOps 2 | Render dashboard access |
| Confirm runtime environment settings without exposing values | Platform admin / DevOps 2 | Render dashboard access |
| Confirm branch-protection/ruleset policy on `main` and `dev` | Repo admin | Admin access |
| Confirm repository visibility intent | Project lead | — |
| Run approved staging POST smoke suite | DevOps 2 | Render access + approval |
| Decide whether CI should build the Docker image | DevOps 2 + DevOps 1 | — |
| Validate real-LLM p95 | Project lead / AI-ML | — |

Do not merge, redeploy, restart, roll back, or create/move/delete a tag on the
basis of this document alone.
