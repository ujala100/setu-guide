# Final DevOps 2 handover — audit and release readiness

Owner: DevOps 2. Audit date: **2026-11-05** (UTC).
Repository: `/home/kali/setu-guide`, remote `https://github.com/ujala100/setu-guide.git`.
Code audit ref: `feature/devops2-deploy-runbook` at
`7ebf17d6c11d3d442433c11e401f96af1eacb700`. This handover is added by a
docs-only finalization commit on the same branch; that commit does not change
application code or CI. Every result below was produced during this audit. Old
runbook/PR numbers are not reused as current evidence.

## 1. Completed tasks

| # | Task | Result |
|---|---|---|
| 1 | Repository and PR audit | Done — working tree clean, remote refs fetched, PR #33 and #13 inspected. |
| 2 | CI verification | Done — PR #33 run `41604222814` green; intentional failure run `41601173424` confirmed. |
| 3 | Test verification | Done — full suite via `.venv`, `git diff --check` clean. |
| 4 | Staging verification | Partial — live `GET /health` verified; dashboard facts remain unverified. No POST, no mutation. |
| 5 | Privacy and monitoring audit | Repository/automated checks done; live Render log checks not done. |
| 6 | Release readiness | Blocked — no frozen SHA, no approval, no tags, no deployed-SHA evidence. |
| 7 | Final handover | This document. |
| 8 | Finalization | Handover cross-checked; PR #33 description updated; docs-only commit created on the same branch. |

No application code, CI workflow, dependency, tag, branch, merge state or
staging setting was changed. The only metadata change is the PR #33 description
update described in §2.2.

## 2. Repository and PR status

### 2.1 Git state (at audit start, before the finalization commit)

| Item | Value |
|---|---|
| Current branch | `feature/devops2-deploy-runbook` |
| Code audit HEAD | `7ebf17d` — `docs(devops2): clarify orchestrator entry-point wording` (2026-11-03 14:03:51 +0530) |
| Upstream at audit start | `origin/feature/devops2-deploy-runbook` (same commit) |
| vs `origin/dev` at audit start | 7 ahead, 0 behind (8 ahead after the finalization commit) |
| `origin/dev` tip | `eef7ac2` — `Fix/handle chat alias (#37)` |
| Working tree | Clean before the finalization commit; only this new file is untracked until committed |
| Preserved stash | `stash@{0}: On feature/devops2-deploy-runbook: WIP runbook before syncing with origin/dev` |
| Local `dev` | `5f91a1a`, behind `origin/dev` by 3 |
| Finalization commit | Docs-only commit on this branch containing this document; see PR #33 head |

### 2.2 PR #33

| Field | Value |
|---|---|
| Title | `docs(devops2): expand deployment and rollback runbook` |
| State | **OPEN**, not draft |
| Base / head | `dev` / `feature/devops2-deploy-runbook` |
| Head commit at audit start | `7ebf17d6c11d3d442433c11e401f96af1eacb700` |
| PR head after finalization | Docs-only commit on this branch (see PR #33) |
| Mergeability | `MERGEABLE` / `CLEAN` |
| Review decision | Empty — **no approving review submitted** |
| Reviews / review requests | None / none |
| Review comments / issue comments | 0 / 0 |
| Changed files | 6 files before this handover (+1002 / −60); this document adds a 7th file |
| Checks at audit start | `test` pass, `GitGuardian Security Checks` pass |
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
| `41601173424` | `workflow_dispatch`, `demo/ci-intentional-failure-20261103133902`, `8e5e5e3` | **failure (intentional)** | 1 failed, 321 passed, 3 skipped, 1 warning in 3.96s |

The finalization commit triggers a new `ci / test` run; check PR #33's Checks
tab for its result rather than treating the `7ebf17d` run as the final head.

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
| **Full suite, latest finalization run** | **324 passed, 0 skipped, 1 warning in 28.67s** |
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

### 5.3 Requires Render dashboard access (not verified)

- Actual build/start command, runtime and instance type.
- Source branch, Auto-Deploy state and current deployed commit SHA.
- Health-check path setting, `$PORT` wiring and cold-start behavior.
- Live values of `USE_MOCK`, `LOG_LEVEL`, `TRUSTED_PROXY`, rate limits, cache
  settings and `PYTHON_VERSION` (name only for the last).
- Deploy Events, live logs, log retention and any log shipper.

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

| Item | Status |
|---|---|
| Release tags | **None** — `git tag -l` empty, `git ls-remote --tags` empty, GitHub tags API empty |
| GitHub releases | None |
| Frozen SHA from project lead | **Not provided** |
| Release approval | **Not recorded** — no approval in PR #33 reviews or repository evidence |
| PR #33 description | Updated 2026-11-05 to current state (no frozen SHA, no live Render verification) |
| PR #33 review/approval | **Not approved** (no reviews) |
| PR #33 merge | **Not merged** (not an ancestor of `origin/dev`) |
| Staging deployed SHA | **Unknown** — requires Render Deploys page |
| Approval to deploy/tag | **Not provided** |
| Branch protection | **Unconfirmed** — branch-rules API returns no rules; classic protection API returns 404 with a non-admin token |
| Open release-scope PRs | 6, including #35 targeting `main` |

### 8.1 Exact information required from the project lead

1. The **full 40-character frozen SHA**, with confirmation it is on `origin/dev`.
2. Explicit approval to merge **PR #33**, and a decision on the other open PRs.
3. Release scope: is the release cut from `dev` or `main` (PR #35 targets `main`)?
4. Whether a release tag is authorized; if yes, the exact tag name and who may
   create/push it. No tag will be created without that instruction.
5. Approval to deploy staging and the target commit; confirmation that
   Auto-Deploy remains off.
6. Confirmation of staging `USE_MOCK` mode, `LOG_LEVEL`, `TRUSTED_PROXY`, rate
   limits and whether real-mode validation is in scope.
7. A repo admin to configure/confirm branch protection or rulesets on `main`
   and `dev`.
8. A Render platform admin to configure failed-deploy and unhealthy-service
   notifications and to provide read access or log/Deploy evidence.

## 9. External dependencies and blockers

| Blocker | Impact | Owner |
|---|---|---|
| No Render dashboard session or API credentials available in this audit; GitHub repo permission is `admin: false` | Cannot verify deployed SHA, settings or logs; cannot configure notifications | Project lead / platform admin (`ujala100`) |
| PR #33 has no approving review | Cannot merge or treat as release-ready | Project lead |
| Frozen SHA not supplied | Cannot compare staging to an approved commit | Project lead |
| Staging deploy/tag authorization not supplied | Cannot deploy, restart or tag | Project lead |
| Branch protection/rulesets unconfirmed | Merge-gating policy unknown; DevOps 2 Day 1 item still open | Repo admin |
| Repo API reports visibility **public** while the old handover says private | Privacy/access-policy discrepancy to confirm | Project lead |
| Full staging smoke and live log audit not run | Staging behavior beyond `/health` is unverified | DevOps 2, after approval |
| CI skips the 3 container tests | Green CI means unit/failure tests only | DevOps 2/DevOps 1 decision |
| Real-LLM p95 (12s target) unvalidated | Real-mode performance unknown | Project lead / AI-ML |

## 10. Next actions

| Action | Owner | Precondition |
|---|---|---|
| Review and approve PR #33 (description updated 2026-11-05) | Project lead | Current audit evidence |
| Provide frozen SHA, release scope and tag authorization | Project lead | — |
| Confirm repo visibility intent and branch-protection policy | Project lead / repo admin | — |
| Grant Render access or supply Deploy SHA, settings and log excerpts | Platform admin | — |
| Run approved staging POST smoke suite and live log privacy greps | DevOps 2 | Render access + approval |
| Configure Render failed-deploy/unhealthy notifications | Platform admin + DevOps 2 | Render access |
| Decide whether CI should build the Docker image | DevOps 2 + DevOps 1 | — |
| Record deployed SHA and match it to the frozen SHA | DevOps 2 | Frozen SHA + Render access |
| Merge PR #33 only after approval | Project lead | Review complete |
| Create/push a release tag only if explicitly authorized | Project lead | Frozen SHA + written authorization |

Do not merge, deploy, restart staging, or create/move/delete a tag on the basis
of this document alone.
