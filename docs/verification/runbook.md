# Deployment and rollback runbook (Setu Guide API)

Owner: DevOps 2 (`.github`, `deployment`, `docs/` per `CONTRIBUTING.md:17`).
Scope: documentation only. This file changes no application code, CI,
dependencies or configuration.

Verification status: every command, path, port, endpoint and environment
variable below was checked against the current repository. Anything that
depends on the hosting dashboard (Render) or on permissions we do not hold is
explicitly marked **UNVERIFIED** or **NEEDS RENDER ACCESS**. Do not treat those
as confirmed capabilities.

> There is **no in-repo deployment configuration**: the repository contains no
> `render.yaml`, `Procfile`, `fly.toml`, `app.yaml` or CI deploy job. Staging is
> configured on the platform, not in this repo. Only two environments are
> documented anywhere: **Local** and **Staging**. There is no documented
> production environment — do not invent one.

---

## 1. Purpose, scope, and prerequisites

### 1.1 Purpose
Give a single operator (DevOps 2) a repeatable, evidence-producing procedure to
build, run, deploy, verify and (where the platform allows) roll back the Setu
Guide API, without guessing at undocumented platform features.

### 1.2 Scope
- Local Docker build and run of the API image.
- Staging deploy on the platform (Render) and its health/smoke verification.
- Rollback **only** if the platform supports it and only with authorized
  access.
- Recording a deployment/rollback for later auditing.

Out of scope: application behaviour (owned by the lead / AI-ML owners),
benchmark numbers (`docs/load_and_failure_test_notes.md`) and the CI pipeline
(`.github/workflows/ci.yml`, owned by DevOps 2 but unchanged here).

### 1.3 Prerequisites
| Need | Notes |
|---|---|
| Git | To fetch and identify the commit to ship. |
| Docker + Docker Compose | For the local container path. `docker compose` (v2 syntax) is what `docker-compose.yml` assumes. |
| Python 3.11 | What CI pins (`.github/workflows/ci.yml:15`, `Dockerfile:7`). Only needed for the non-container local run. |
| Repo access | Private repo: `https://github.com/ujala100/setu-guide.git`. Clone access must be granted by an admin. |
| `.env` file | Copy of `.env.example`. **Never committed** (`.gitignore:6`). |
| Render access | **NEEDS RENDER ACCESS.** Required for any staging deploy, deploy record, env-var change, restart or rollback. We do not have it during this handover. |
| Lead confirmation | Required before any release tag or any claim that staging runs a release commit (see §7). |

---

## 2. Environment and secret-handling requirements

### 2.1 Environments
| Environment | Base URL | Source |
|---|---|---|
| Local | `http://localhost:8000` | `docs/api.md:24` |
| Staging | `https://setu-guide.onrender.com` | `docs/api.md:25`, `docs/verification/devops2-handover.md` §6.1 |

No production URL exists in the repository.

### 2.2 Configuration variables (names verified in `.env.example`)
All configuration is read from the environment by `app/config.py`
(pydantic-settings); nothing is hardcoded (`README.md:48-52`).

| Variable | Purpose | Default in `.env.example` |
|---|---|---|
| `USE_MOCK` | `true` = Day-1 mock reply; `false` = real orchestrator path | `true` |
| `LLM_PROVIDER` | Provider name (still a placeholder) | `placeholder` |
| `LLM_API_KEY` | **Secret.** Required only when `USE_MOCK=false` | `placeholder-not-a-real-key` |
| `LLM_TIMEOUT_SECONDS` | Call budget = this + 1s margin | `10` |
| `RATE_LIMIT_PER_USER` | Per-user limit `<count>/<period>` | `30/minute` |
| `RATE_LIMIT_PER_IP` | Per-IP limit | `60/minute` |
| `TRUSTED_PROXY` | Honor `X-Forwarded-For` only behind a proxy we control | `false` |
| `CACHE_ENABLED` | `false` forces `MISS` | `true` |
| `CACHE_TTL_SECONDS` | Cache TTL | `600` |
| `CACHE_MAX_ITEMS` | Cache size | `500` |
| `LOG_LEVEL` | `CRITICAL/ERROR/WARNING/INFO/DEBUG/NOTSET` | `INFO` |
| `INTERNAL_API_KEY` | Present for the shared setup; **not read by this service yet** | empty |

### 2.3 Secret-handling rules
- `.env` is ignored by **git** (`.gitignore:6`) **and** by **Docker**
  (`.dockerignore:20-22`); the build context therefore carries no secrets.
- The image bakes in no secrets — every setting arrives at runtime
  (`Dockerfile:3-4`, `Dockerfile:33-34`).
- Never commit a real key, and never paste one into a ticket, PR, chat or a
  deploy record. The API key is never logged and never appears in an error
  message (`README.md:68`, `docs/api.md:289-299`).
- On staging, secrets live in the platform's environment settings — **NEEDS
  RENDER ACCESS** to view or change, and they are not in this repo.
- Startup fails fast with one clear line if the environment cannot work (e.g.
  `USE_MOCK=false` without `LLM_API_KEY`) — `README.md:66-68`.

---

## 3. Local Docker build and run (repository-supported)

### 3.1 Build the image
```bash
docker build -f docker/Dockerfile -t setu-guide-api:day2 .
```
- Source: `README.md:28`, `docs/verification/devops2-handover.md` §2.4.
- The image is multi-stage (`python:3.11-slim`), installs with `--no-cache-dir`,
  runs as non-root user `app` (`Dockerfile:29`, `Dockerfile:43`), exposes port
  **8000** (`Dockerfile:45`) and defines a `HEALTHCHECK` on `/health`
  (`Dockerfile:48-49`).
- The test suite expects the tag `setu-guide-api:day3`
  (`tests/README.md:27`). Both tags point at the same Dockerfile; `day2` is the
  README/compose tag, `day3` is the test tag. Pick one and stay consistent.
- Model / knowledge-base files are **not** baked into the image
  (`Dockerfile:36-41`).

### 3.2 Run the container
```bash
# optional: create .env first (defaults work without it)
cp .env.example .env
docker run --rm -p 8000:8000 --env-file .env setu-guide-api:day2
```
- Source: `README.md:27-29`, `docs/verification/devops2-handover.md` §2.4.
- Port mapping `8000:8000` matches `EXPOSE 8000` and the documented local URL.

### 3.3 Run with Compose (adds the model volume mount)
```bash
docker compose up --build
```
- Source: `README.md:31`, `docker-compose.yml`.
- Compose builds `docker/Dockerfile` and tags `setu-guide-api:day2`
  (`docker-compose.yml:12-15`), publishes `8000:8000`
  (`docker-compose.yml:17-18`), reads an optional `.env`
  (`docker-compose.yml:24-26`) and mounts `./models:/app/models:ro`
  (`docker-compose.yml:36-37`). Create `./models` first if you use that mount.
- Per-run env override example (documented, commented out in the file):
  `USE_MOCK=false docker compose up` (`docker-compose.yml:28-29`).

### 3.4 Local health check
```bash
curl localhost:8000/health
# -> {"status":"ok"}
```
- Source: `README.md:35`, `docs/api.md:69-74`.
- Swagger UI: `http://localhost:8000/docs` (`README.md:9`).

---

## 4. Staging deployment procedure (Render)

Staging host: `https://setu-guide.onrender.com`. The service is deployed by the
platform from a branch/commit on the remote
(`docs/verification/devops2-handover.md` §7.2). There is **no deploy script in
this repo**, so these steps mix repo commands (verified) with dashboard actions
(**NEEDS RENDER ACCESS**, unverified details).

### 4.1 Steps that are verified from the repo
1. Ensure you are shipping the intended commit:
   ```bash
   git fetch origin
   git rev-parse --short HEAD          # e.g. 531cb6e
   git log --oneline -1
   ```
2. After the platform reports a live deploy, confirm the commit exists here:
   ```bash
   git branch -r --contains <deployed-short-sha>   # which branches contain it
   git log --oneline -1 <deployed-short-sha>       # what the commit is
   git tag --contains <deployed-short-sha>         # empty until a tag exists
   ```

### 4.2 Steps that require authorized Render access (UNVERIFIED)
- **Triggering the deploy.** The handover says a deploy is "created from a
  branch/commit on the remote" but does **not** document a deploy hook, a CLI
  command, or an auto-deploy setting. **Confirm the exact mechanism with the
  platform admin** — do not assume push-to-deploy or manual deploy.
- **Reading the deployed commit.** On the platform, open the service's
  **Deploys** page and read the commit SHA and branch for the live deploy
  (documented in `docs/verification/devops2-handover.md` §7.2 step 3). The
  navigation itself is **NEEDS RENDER ACCESS**.
- **Viewing/changing environment variables and secrets**, service settings, and
  logs.
- **Restarting the service.**

### 4.3 Order of operations
1. Complete §4.1 step 1 (note the commit to ship).
2. Deploy via the platform (**NEEDS RENDER ACCESS**; mechanism UNVERIFIED).
3. Read the deployed commit SHA + branch from the platform (§4.2).
4. Confirm the SHA exists in this repo (§4.1 step 2).
5. Run health verification (§5) then the smoke tests (§6).
6. Record the deploy (§9).

> Staging health was **not** confirmed during the handover — treat it as
> "unverified" until you personally run §5 and §6
> (`docs/verification/devops2-handover.md` §6.3 note).

---

## 5. Health verification using `GET /health`

```bash
curl -i https://setu-guide.onrender.com/health
```

Expected (`docs/api.md:65-78`, `docs/verification/devops2-handover.md` §6.2):
- Status **200** with body `{"status": "ok"}`.
- Header **`X-Request-Id`** present (send your own `X-Request-Id` to have it
  echoed back — that value is the `request_id` in the server log).
- **No `X-Cache`** header and **no `Retry-After`** header.
- `/health` is **never rate limited**, even while chat is returning `429`.

Local equivalent: `curl -i http://localhost:8000/health` — same expectations.

Container liveness: the image's `HEALTHCHECK` polls `http://127.0.0.1:8000/health`
every 30s (timeout 5s, start period 15s, 3 retries) — `Dockerfile:48-49`.

---

## 6. Post-deployment smoke tests and evidence to record

Run the authoritative checklist in `docs/api.md` §22 (lines 430-443). Beyond
`/health`:

- Quick-action chat (`connect`/`next_steps`, synthetic ids) → `200`, 7-key body,
  `safety.status=="pass"`, `fallback_used==false`, `X-Cache: MISS` then `HIT`.
- Message-only request → `200` with a routed `intent`.
- Unknown `stage` → `422 invalid_request`; caller text absent from the body.
- Unknown route → `404 not_found`; `GET /v1/guide/chat` → `405 method_not_allowed`.
- Safety: `"Will we get married?"` → `200 blocked/outcome_prediction`,
  `fallback_used=true`; a distress message → supportive reply.
- Request-id correlation: send `X-Request-Id: staging-<uuid>`, assert the same
  value returns.
- Log privacy: the access line contains only
  `request_id/method/path/status/latency_ms/cache/intent/stage/fallback_used`;
  grep for the synthetic `message`/`topic`/ids returns nothing
  (`docs/api.md:440`, `docs/verification/privacy-log-audit.md`).
- Confirm no secrets in responses/logs and confirm the `USE_MOCK` mode with the
  lead before sign-off (`docs/api.md:443`).

Example quick-action call (synthetic ids only):
```bash
curl -s -X POST https://setu-guide.onrender.com/v1/guide/chat \
  -H "content-type: application/json" -H "X-Request-Id: staging-<uuid>" \
  -d '{"user_id":"u1","match_id":"m1","stage":"connect","intent":"next_steps"}'
```

### 6.1 Evidence to record
- The exact commands you ran and their output (status codes, headers).
- The `X-Request-Id` used and returned.
- The deployed commit SHA read from the platform.
- `X-Cache` values observed (MISS/HIT) for the quick-action check.
- Timestamp (date + time, with timezone).
- Any deviation from the expected results, filed in
  `docs/verification/bug-tracker.csv`.

**Never** store secrets, real user data, full request bodies of real users, or
the API key in the evidence. Use synthetic ids and the sentinel markers only.

---

## 7. Rollback prerequisites and procedure

> **Repo reality:** no rollback script, hook, or platform rollback procedure is
> documented anywhere in this repository. The steps below are therefore
> **UNVERIFIED** and **permission-dependent**. Do **not** promise a rollback
> time or a zero-downtime rollback. If the platform does not expose a
> redeploy-previous-deploy / revert feature, a "rollback" means redeploying a
> known-good commit — which is still the platform's job, not a repo script.

### 7.1 Prerequisites
- **NEEDS RENDER ACCESS**: permission to deploy/redeploy on the staging service.
- A **known-good commit SHA** (the last deploy that passed §5 and §6), recorded
  per §9. Without this, there is nothing to roll back to.
- Confirmation from the platform admin that the platform supports rolling back
  to a previous deploy (or redeploying an arbitrary commit).
- Awareness that rate limiter and cache are **in-memory / single instance**
  (`docs/load_and_failure_test_notes.md:172-175`); a restart clears them.

### 7.2 Procedure (platform-dependent — verify each step)
1. Decide the target: the last-known-good SHA from a previous deploy record.
2. On the platform (Deploys page), roll back to that deploy **if** the platform
   offers it; otherwise create a new deploy from that commit.
   **NEEDS RENDER ACCESS.** Mechanism UNVERIFIED.
3. Read the new live commit SHA from the platform and confirm it equals the
   target:
   ```bash
   git rev-parse --short <target-sha>
   git branch -r --contains <target-sha>
   ```
4. Re-run health verification (§5) and the smoke tests (§6).
5. Record the rollback (§9), including the SHA you rolled back **from** and
   **to**.

### 7.3 What a rollback is NOT
- `git revert` alone does not roll back a running deployment — it only changes
  the branch, which then still has to be deployed.
- Do not edit application code, CI, dependencies or configuration to "fix" a
  bad deploy; those are owned by other people (`CONTRIBUTING.md:9-17`). File a
  bug (`docs/verification/README.md`) and coordinate instead.

---

## 8. Failure recovery, escalation, and post-rollback verification

### 8.1 If `/health` is not `200`
1. Re-run §5 and capture the full output (status, headers, body).
2. Read the platform's deploy status, logs and current commit SHA
   (**NEEDS RENDER ACCESS**).
3. Check that required env vars are set on the service (e.g. `USE_MOCK`,
   `LLM_API_KEY` if real mode) — a misconfiguration makes startup fail fast
   (`README.md:66-68`).
4. If the service is wedged, restart it on the platform (if supported) and
   re-check `/health`. Local evidence that a restart recovers the container:
   `tests/failure/test_container.py:146-187` ("restart under load → healthy").
5. If it does not recover, treat it as a failed deploy → roll back (§7) to the
   last-known-good SHA.

### 8.2 Escalation (ownership from `CONTRIBUTING.md:9-17`)
| Symptom area | Owner |
|---|---|
| `app/api`, Docker image/container | DevOps 1 |
| CI, deployment, docs | DevOps 2 |
| `app/core`, `app/schemas`, `app/safety` | Team lead |
| `app/rag` (retrieval/KB) | AI/ML 2 |
| route & generate in `app/core` | AI/ML 3 |
| `data/` (synthetic profiles, test convos) | AI/ML 1 |
| Platform account / access / billing | Platform admin (not in the repo) |

File any confirmed defect in `docs/verification/bug-tracker.csv` with evidence
(never secrets or real user data).

### 8.3 Post-rollback verification
- `/health` → `200 {"status":"ok"}` (§5).
- Full smoke checklist §6 passes.
- Platform's live commit SHA **equals** the rollback target SHA.
- Access log shows no private data (`docs/api.md:440`).
- The rollback is recorded (§9) and, if it was caused by a code defect, a bug
  row links to it.

---

## 9. Deployment record template

Copy this into the deploy PR description, or keep a durable log under
`docs/verification/` if the team wants one
(`docs/verification/devops2-handover.md` §7.2 step 5). One row per deploy or
rollback. Never put secrets or real user data here.

```text
Environment:            Local | Staging
Deployed commit SHA:    <short sha, read from the platform for staging>
Branch deployed from:   <branch, from the platform>
USE_MOCK mode:          true | false   (confirm with lead)
Deploy time (tz):       YYYY-MM-DDTHH:MM:SS±HH:MM
Deployer:               <name>
Health result:          200 {"status":"ok"} | <other>
Smoke-test result:      PASS | FAIL  (link to evidence / notes)
Rollback reference:     n/a | rolled back to <sha> at <time> (§7)
Notes / incident link:  <bug row in docs/verification/bug-tracker.csv>
```

| Field | Value |
|---|---|
| Environment | |
| Deployed commit SHA | |
| Branch deployed from | |
| `USE_MOCK` mode | |
| Deploy time (with timezone) | |
| Deployer | |
| Health result (`/health`) | |
| Smoke-test result | |
| Rollback reference | |
| Notes / incident link | |

---

## 10. Not verified / permission-dependent (explicit)

- Render deploy trigger mechanism, deploy hooks, auto-deploy — **not in repo**;
  confirm with the platform admin.
- Render "Deploys" page navigation, env-variable management, restart, and any
  rollback/rollback-to-deploy feature — **NEEDS RENDER ACCESS**, not documented
  in this repo.
- Whether staging currently runs a specific commit — **unverified**; no
  `/version` endpoint and no tags exist (`docs/verification/devops2-handover.md`
  §7.1).
- Release tagging (`v0.1`) — **blocked on the team lead**; do not create a tag
  or claim a staging/commit match until the lead freezes the commit and the
  deploy is verified (runbook §7, handover §7.3).
- No production environment exists in this repo.

## 11. References
- `docker/Dockerfile`, `docker-compose.yml`, `deploy/README.md`
- `.env.example`, `.gitignore`, `.dockerignore`
- `README.md` (Run, Docker, env, rate limiting, caching, fallback)
- `docs/api.md` §2 (Base URLs), §5 (`/health`), §15 (rate limiting),
  §18 (logging/privacy), §22 (staging checklist)
- `docs/verification/devops2-handover.md` §6-§7 (staging + version recording)
- `docs/verification/privacy-log-audit.md`, `docs/verification/monitoring.md`,
  `docs/verification/bug-tracker.csv`
- `docs/load_and_failure_test_notes.md` (single-instance limits, restart)
- `tests/README.md`, `tests/failure/test_container.py`
- `CONTRIBUTING.md` (branch rules, ownership)
