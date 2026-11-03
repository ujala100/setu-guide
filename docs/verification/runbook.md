# Deployment and Rollback Runbook (Setu Guide API)

Owner: DevOps 2 (`.github`, `deployment`, `docs/` per `CONTRIBUTING.md:17`).
Scope: Operational procedures, validation, incident handling, and rollback for Setu Guide API.
Status: Operational guide for verification and handover. Commands are verified locally where supported by the repository; staging deployment and platform rollback procedures have not been operationally exercised and remain pending Render access and owner confirmation.

> **Operational Reality & Scope Notice:**
> This runbook strictly distinguishes between verified repository capabilities, documented platform settings, and unverified external procedures. The repository contains **no in-repo deployment orchestration** (no `render.yaml`, `Procfile`, `fly.toml`, or CI deployment job). There are only two documented environments: **Local** and **Staging**. There is **no production environment** in this repository — do not assume or invent one. Local Docker commands are repository-supported; however, live staging deployment, dashboard configuration, and platform rollback have NOT been operationally exercised and require platform access and owner confirmation.

---

## 1. Deployment Architecture and Scope

### 1.1 Architectural Topologies

The Setu Guide service operates across distinct deployment topologies:

```text
+---------------------------------------------------------------------------------------------------+
| 1. LOCAL DOCKER DEPLOYMENT (Verified via Repository)                                             |
|                                                                                                   |
|  [ Client / cURL / Postman ]                                                                      |
|               |                                                                                   |
|               v                                                                                   |
|  Docker Host (localhost:8000)                                                                     |
|    +-----------------------------------------------------------------------------------------+    |
|    | Container: setu-guide-api (python:3.11-slim, non-root user: app, Uvicorn on 0.0.0.0:8000)   |    |
|    |                                                                                         |    |
|    |   +-------------------+     +-------------------------+     +-----------------------+   |    |
|    |   |  FastAPI Router   | --> | In-Process Rate Limiter | --> |   In-Process TTLCache |   |    |
|    |   |  (app/api/main)   |     | (30/user, 60/IP window) |     |   (500 items, 600s)   |   |    |
|    |   +-------------------+     +-------------------------+     +-----------------------+   |    |
|    |             |                                                           | (HIT)         |    |
|    |             v                                                           v               |    |
|    |   +--------------------+     +------------------------+     +-----------------------+   |    |
|    |   | Safety Guard       | --> | Orchestrator Pipeline  | <-- | Return Cached Reply   |   |    |
|    |   | (app/safety/guard) |     | (app/core/pipeline)    |     +-----------------------+   |    |
|    |   +--------------------+     +------------------------+                                 |    |
|    |                                      |                                                  |    |
|    |                      +---------------+---------------+                                  |    |
|    |                      v                               v                                  |    |
|    |             USE_MOCK=true                   USE_MOCK=false                              |    |
|    |             Mock Provider (Extractive KB)   Real LLM Provider                           |    |
|    |             "Here are some questions..."    (Requires LLM_API_KEY;                      |    |
|    |                                              handle_chat entry point)                  |    |
|    +-----------------------------------------------------------------------------------------+    |
|          |                                                                                        |
|          +--- Mount: ./models -> /app/models:ro (docker-compose.yml)                              |
|          +--- Probe: GET /health via container HEALTHCHECK (every 30s)                            |
+---------------------------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------------------------+
| 2. CURRENT STAGING SERVICE (Render Free; native Python runtime)                                   |
|                                                                                                   |
|  [ Client / Postman ] ---> HTTPS (setu-guide-1wiy.onrender.com:443)                               |
|                                    |                                                              |
|                                    v                                                              |
|                     [ Render Ingress / Reverse Proxy ]                                            |
|                                    |                                                              |
|                                    v (HTTP, Render-assigned $PORT)                                |
|                     [ Render Web Service Instance - Free plan ]                                   |
|                       - Deployed from branch `dev` via the Render dashboard                       |
|                       - Auto-Deploy: disabled (manual deploy only)                                |
|                       - Native Python runtime (not Docker)                                        |
|                       - Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT                  |
|                       - Health Check Path: /health                                                |
|                       - PYTHON_VERSION configured by environment variable name only               |
|                       - TRUSTED_PROXY=false                                                       |
|                       - Single instance (in-memory cache/rate limiter)                            |
|                       - Default mode: USE_MOCK=true                                               |
+---------------------------------------------------------------------------------------------------+
```

Staging is the only hosted environment. There is no production environment in
this repository and no production deployment is planned. Do not add production
diagrams, production-to-production checklists, or production readiness claims.

### 1.2 Verification Matrix: Verified, Documented, and Unknown

| Item | Status | Source / Evidence | Operational Impact |
|---|---|---|---|
| **Docker Configuration & Test Specs** | **VERIFIED IN REPO** | `docker/Dockerfile`, `docker-compose.yml`, `tests/failure/test_container.py` | Multi-stage builder, non-root user `app`, and container failure test definitions are present in repo. |
| **Docker Runtime Execution** | **PENDING EXECUTION** | `tests/failure/test_container.py` (3 tests skip if image absent) | Container build and runtime execution must be run by operator; skipped in CI by design. Labeled pending until local run succeeds. |
| **Release Tag** | **NOT CREATED** | `git tag --list` and post-prune check return no tags | No release tag exists. Do not create, push, move, or recreate a tag. Wait for the project lead's frozen SHA before any redeploy or tagging. |
| **Fail-Fast Configuration** | **VERIFIED** | `app/config.py:88-93`, `tests/test_day2_config.py` | Missing `LLM_API_KEY` when `USE_MOCK=false` aborts startup cleanly. |
| **In-Memory Rate Limiting** | **VERIFIED** | `app/api/ratelimit.py`, `tests/test_day2_rate_limit.py`, Scenario C | In-process limiter verified. Thresholds (30/user, 60/IP) are proposed placeholders pending lead approval. Single-instance only. |
| **In-Memory Response Caching** | **VERIFIED** | `app/api/cache.py`, `tests/test_day2_cache.py`, Scenario B | In-process cache verified. TTL (600s) and size (500) are proposed placeholders pending lead approval. Single-instance only. |
| **Health Probe Contract** | **VERIFIED** | `app/api/main.py:133-136`, `docker/Dockerfile:48-49` | `GET /health` returns `200 {"status":"ok"}`; exempt from rate limits. |
| **Log Privacy Guard** | **VERIFIED** | `app/api/main.py:102-132`, `tests/failure/test_log_privacy.py` | Request body, PII, and API keys are strictly excluded from logs. |
| **Staging Service URL** | **CURRENT** | Project lead review; `docs/api.md`, Postman collection | The only current staging base URL is `https://setu-guide-1wiy.onrender.com`. |
| **Render Web Dashboard** | **REQUIRES ACCESS** | No dashboard credentials or API tokens in repo | Operator must obtain Render access from the repository owner. |
| **Render Deploy Mechanism** | **DOCUMENTED (NOT EXERCISED)** | Render dashboard Deploys page; Auto-Deploy disabled | Manual deploy from a selected commit. Deploying a specific commit also disables Auto-Deploy. |
| **Render Rollback Capability** | **DOCUMENTED (NOT EXERCISED)** | Render rollback documentation; Free plan limit | Render Free supports rollback only to the two most recent previous deploys. Actual availability depends on retained build artifacts. |
| **Active Deployment SHA** | **PENDING LEAD** | Render Deploys/Events tab | Must be checked against the frozen SHA the project lead will provide later. Do not guess or claim a match. |
| **Production Environment** | **OUT OF SCOPE** | No production configuration in repo | No production environment exists or is planned. Do not configure or claim production readiness. |

### 1.3 Service Boundaries and Role Ownership

Per `CONTRIBUTING.md:9-17`, components are strictly owned by specific roles. Do not cross ownership boundaries without lead approval:

| Component | Repository Path | Owner Role | Primary Contacts |
|---|---|---|---|
| **CI, Deployment, Verification** | `.github/`, `deploy/`, `docs/verification/` | DevOps 2 | Current Operator (Intern 2) |
| **API, Container, Config, Caching** | `app/api/`, `docker/`, `app/config.py`, `docker-compose.yml` | DevOps 1 | API Engineer |
| **Schemas, Safety, Core Orchestrator** | `app/schemas/`, `app/safety/`, `app/core/orchestrator.py` | Team Lead | Team Lead |
| **RAG, Knowledge Base, Retriever** | `app/rag/`, `app/rag/knowledge_base/` | AI/ML 2 | Retrieval Engineer |
| **Routing, Prompts, Responder** | `app/core/router.py`, `app/core/responder.py`, `app/core/prompts/` | AI/ML 3 | Model Engineer |
| **Synthetic Data, Evaluation Cases** | `data/`, `eval/` | AI/ML 1 | Evaluation Engineer |
| **Hosting Platform & Billing** | Render Dashboard / Domain DNS | Platform Admin | Repository / Project Owner |

---

## 2. Pre-Deployment Checks

Before initiating any deployment (local container run or staging update), execute the following verification steps.

### 2.1 Branch and Commit Verification

1. Verify local git state is clean:
   ```bash
   git status
   ```
   *Pass condition:* `nothing to commit, working tree clean`.

2. Fetch latest changes from remote and confirm target branch:
   ```bash
   git fetch origin
   git rev-parse --short HEAD
   git log --oneline -3
   ```
   *Pass condition:* Target commit is visible in git log, belongs to `dev` (or the intended feature branch), and matches the intended release commit.

3. Confirm remote tracking inclusion:
   ```bash
   git branch -r --contains HEAD
   ```
   *Pass condition:* Output lists `origin/dev` or the expected remote branch. Never deploy a commit that exists only locally.

### 2.2 Test Suite and CI Requirements

1. Run the local automated test suite:
   ```bash
   python -m pytest -q
   ```
   *Pass condition:* All executed tests must pass with 0 failures and 0 errors.
   *Test count policy:* Total test counts are version-specific evidence and must not be treated as a static invariant across development. Operators must record the exact counts (passed, skipped) for each specific commit under test.
   - Latest run on this branch after syncing with `origin/dev`: **321 passed, 3 skipped** (`.venv/bin/python -m pytest -q`).
   - *Skipped tests explanation:* `tests/failure/test_container.py` (3 tests) skips automatically when the Docker image `setu-guide-api:day3` has not been built locally or the daemon is unreachable.
   - *Validation suite location:* input-validation checks live in `tests/validation/test_validation_matrix.py` (moved from `tests/failure/test_bad_input.py` on `dev`). There is no `tests/validation/test_bad_input.py`.

2. Run the failure and privacy regression suite:
   ```bash
   python -m pytest tests/failure/test_log_privacy.py tests/validation/test_validation_matrix.py tests/failure/test_llm_failures.py -q
   ```
   *Pass condition:* All failure cases pass with 0 errors.

3. CI Status Verification:
   - Check the GitHub Actions check **`ci / test`** (`.github/workflows/ci.yml`).
   - The workflow executes `python -m pytest -q` on Python 3.11.
   *Pass condition:* Green checkmark on the PR/commit in GitHub.
   *Note:* CI does **not** build Docker images or run Locust load tests (`tests/load/`). Those must be verified on an operator workstation.

### 2.3 Dependency and Container Image Validation

1. Verify dependency declarations:
   - `requirements.txt`: runtime dependencies (`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `cachetools`, `google-genai`).
   - `requirements-dev.txt`: development and test tools (`pytest`, `httpx`, `locust`).
   *Pass condition:* No unpinned or floating dependencies without exact versions.

2. Verify Docker image build and non-root execution:
   ```bash
   docker build -f docker/Dockerfile -t setu-guide-api:day2 .
   ```
   *Pass condition:* Multi-stage build completes successfully. Image metadata confirms non-root user `app` (`docker/Dockerfile:29,43`) and `EXPOSE 8000`.

3. Docker Runtime Verification Status:
   - The repository provides Docker packaging (`docker/Dockerfile`, `docker-compose.yml`) and container failure tests (`tests/failure/test_container.py`).
   - **Crucial Distinction:** If Docker is unavailable in the environment, or if container tests were skipped during pytest runs, label actual Docker runtime verification as **PENDING**.
   - To complete Docker runtime verification:
     ```bash
     docker build -t setu-guide-api:day3 -f docker/Dockerfile .
     python -m pytest tests/failure/test_container.py -q
     ```
     *Pass condition:* 3 passed, 0 skipped.

4. Verify `.dockerignore` excludes sensitive files:
   - Inspect `.dockerignore` to confirm `.env`, `.git`, `__pycache__`, `.pytest_cache`, and test files are excluded from the image context.
   *Pass condition:* Image context is minimal; no secrets baked into layers.

### 2.4 Configuration and Secret Validation

1. Verify `.env` is never tracked:
   ```bash
   git ls-files .env
   ```
   *Pass condition:* Command produces no output (file is git-ignored).

2. Check configuration variables against `.env.example`:

   | Variable | Required | Default | Validation / Constraint |
   |---|---|---|---|
   | `USE_MOCK` | Yes | `true` | Boolean (`true`/`false`). Staging default is `true`. |
   | `LLM_PROVIDER` | No | `placeholder` | Provider name string. |
   | `LLM_API_KEY` | Conditional | `placeholder-not-a-real-key` | **Secret.** Required if `USE_MOCK=false`. |
   | `LLM_TIMEOUT_SECONDS` | No | `10` | Positive integer. Total call budget is `LLM_TIMEOUT_SECONDS + 1s`. [Proposed placeholder - pending lead approval per `.env.example:15`]. |
   | `RATE_LIMIT_PER_USER` | Yes | `30/minute` | Format: `<count>/<period>` (`second`, `minute`, `hour`, `day`). [Proposed placeholder - pending lead approval per `.env.example:19`]. |
   | `RATE_LIMIT_PER_IP` | Yes | `60/minute` | Format: `<count>/<period>`. [Proposed placeholder - pending lead approval per `.env.example:19`]. |
   | `TRUSTED_PROXY` | Yes | `false` | Boolean. Staging is explicitly `false`: do not trust `X-Forwarded-For` on this service. |
   | `CACHE_ENABLED` | Yes | `true` | Boolean (`true`/`false`). Set `false` for consistency evaluations. |
   | `CACHE_TTL_SECONDS` | No | `600` | Positive integer (seconds). [Proposed placeholder - pending lead approval per `.env.example:29`]. |
   | `CACHE_MAX_ITEMS` | No | `500` | Positive integer. [Proposed placeholder - pending lead approval per `.env.example:29`]. |
   | `LOG_LEVEL` | Yes | `INFO` | Valid Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
   | `PYTHON_VERSION` | Render | *(configured on Render)* | Environment variable **name only**. Do not publish or commit its value. |
   | `INTERNAL_API_KEY` | No | *(empty)* | Reserved for shared setup; not currently enforced. |

3. Verify fail-fast behavior:
   - `app/config.py` raises `SettingsError` at import time if `USE_MOCK=false` but `LLM_API_KEY` is missing or empty.
   - Malformed rate limits or invalid log levels immediately fail container startup.

### 2.5 Frozen SHA and Release-Tag Prerequisites

1. Frozen SHA Requirement:
   - Every merge to `dev` or release candidate requires explicit sign-off from the Team Lead (`CONTRIBUTING.md:4`).
   - The project lead will provide the frozen deployment SHA later. Until then, do not redeploy staging, tag a commit, or claim that the active deployment matches a release.
2. Release Tag Status:
   - Check existing tags:
     ```bash
     git tag --list
     ```
   - Current state: **no release tags exist** in this repository. The obsolete local tag previously described in this runbook is not present and must not be recreated.
   - **Rules:**
     - Do not create, move, delete, recreate, or push any tag.
     - Never claim a running deployment corresponds to a release until the Render deployment SHA matches the project lead's frozen SHA exactly.
     - Any future release tag creation or modification requires explicit Team Lead authorization following documented commit approval.

---

## 3. Deployment Procedure

### 3.1 Local Docker Deployment (Repository-Supported)

Follow these exact commands to build and run the containerized service locally:

1. **Prepare Environment File Safely:**
   ```bash
   # Copy template only if .env does not already exist:
   [ -f .env ] || cp .env.example .env
   ```
   *Safety rule:* Existing local configuration must be preserved. Never unconditionally overwrite an active `.env` file, as it may contain developer overrides or environment-specific values. Edit `.env` only if specific configuration adjustments are needed.

2. **Build Container Image:**
   ```bash
   docker build -f docker/Dockerfile -t setu-guide-api:day2 .
   ```

3. **Run Container (Standalone Mode):**
   ```bash
   docker run --rm -d \
     --name setu-guide-api \
     -p 8000:8000 \
     --env-file .env \
     setu-guide-api:day2
   ```

4. **Alternative: Run with Docker Compose (with read-only model mount):**
   ```bash
   # Ensure local models folder exists if mounting
   mkdir -p models
   docker compose up -d --build
   ```

5. **Verify Running State:**
   ```bash
   docker ps -f name=setu-guide-api
   docker logs --tail 20 setu-guide-api
   ```
   *Pass condition:* Container status is `Up` and logs show `Application startup complete`.

6. **Tear Down Local Deployment:**
   ```bash
   # If running standalone:
   docker stop setu-guide-api

   # If running compose:
   docker compose down
   ```

### 3.2 Staging Deployment Procedure (Render Free, Native Python)

Staging is a **Render Free web service** at `https://setu-guide-1wiy.onrender.com`.
It is deployed from the `dev` branch, uses Render's **native Python runtime**
(not Docker), and has **Auto-Deploy disabled**. Operations require authorized
Render dashboard access.

> **Operational Status Notice:**
> The Render dashboard operations below are documented from platform behavior
> and the project lead's review. They have **NOT** been exercised as part of
> this documentation task. Do not redeploy, restart, or roll back staging until
> the project lead provides the frozen SHA.

#### Step 1: Pre-Deploy Git Verification (Local CLI)
```bash
git fetch origin
TARGET_SHA=$(git rev-parse --short origin/dev)
echo "Selected commit: ${TARGET_SHA}"
git log -1 --oneline ${TARGET_SHA}
```
*Pass condition:* the selected commit exists on `origin/dev` and matches the
commit the project lead approved.

#### Step 2: Confirm the Frozen SHA
The project lead will provide the frozen deployment SHA later. Record it and
compare it to the selected commit before deploying. If they differ, stop and ask
the lead; do not guess, redeploy, or tag.

#### Step 3: Manual Deployment from the Selected Commit `[REQUIRES RENDER ACCESS]`
1. Open the [Render Dashboard](https://dashboard.render.com) and select the
   `setu-guide-1wiy` web service.
2. Open the **Deploys** page.
3. Click **Manual Deploy** > **Deploy a specific commit**.
4. Paste or select the approved commit SHA and click **Deploy Commit**.
   *Note:* This action disables Auto-Deploy; staging is already configured with
   Auto-Deploy off.
5. Watch the deploy progress until it reports **Live**. If the build or start
   command fails, the previous deployment remains live; do not hotfix in place.

#### Step 4: Platform Settings Checklist `[REQUIRES RENDER ACCESS]`
Verify the staging service configuration matches the repository contract:

| Setting Category | Expected Value | Purpose / Constraint |
|---|---|---|
| **Instance type** | Render Free | Single instance. No scaling, persistent disk, shell, or one-off jobs on Free. |
| **Source branch** | `dev` | Staging deploys from `dev` only. |
| **Auto-Deploy** | **Off** | Deployments are manual from a selected commit. |
| **Runtime** | Render native Python | Do not configure Docker for this staging service. |
| **Build command** | `pip install -r requirements.txt` | Installs the runtime dependency set. |
| **Start command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | `app.main:app` re-exports `app.api.main:app`; verified in `app/main.py`. Render supplies `$PORT`. |
| **Port** | Render-assigned `$PORT` | Do **not** set `PORT=8000`. |
| **Health Check Path** | `/health` | Render health check endpoint. |
| **Environment: PYTHON_VERSION** | Configured by name only | Never publish the value or any secret in documentation. |
| **Environment: USE_MOCK** | `true` for mock mode | Mock mode is the safe staging default. See §4.2 for mock-versus-real verification. |
| **Environment: TRUSTED_PROXY** | `false` | Staging must not trust `X-Forwarded-For`. |
| **Environment: LOG_LEVEL** | `INFO` | Do not leave shared environments at `DEBUG`. |
| **Environment: RATE_LIMIT_PER_USER / RATE_LIMIT_PER_IP** | `30/minute` / `60/minute` | Proposed defaults pending lead approval. |
| **Environment: CACHE_ENABLED** | `true` | Enables in-process quick-action caching. |

#### Step 5: Check the Events Tab and Deployed Commit SHA `[REQUIRES RENDER ACCESS]`
1. Open the service's **Events** tab and confirm the latest deploy event reports
   **Live** and the intended commit.
2. Open **Deploys** and read the currently live deployment's short SHA.
3. Cross-reference that SHA with local git history:
   ```bash
   DEPLOYED_SHA="<sha-from-render>"
   git branch -r --contains "${DEPLOYED_SHA}"
   git log -1 --oneline "${DEPLOYED_SHA}"
   ```
   *Pass condition:* `DEPLOYED_SHA` matches the project lead's frozen SHA and is
   present on `origin/dev`. If no frozen SHA has been provided, record the SHA
   and mark the comparison **PENDING**, not passed.

#### Step 6: View and Inspect Runtime Logs `[REQUIRES RENDER ACCESS]`
1. Open the service's **Logs** page.
2. Use **Live tail** or a recent time range; search for `http_request`,
   `unhandled`, `orchestrator_failed`, `llm_failed`, or a specific
   `X-Request-Id`.
3. On Render's Hobby plan, log retention is 7 days. HTTP request logs are a
   Pro-workspace feature, so do not expect them on this Free service.
4. The application's own structured `http_request` lines are still available.

#### Step 7: LLM-Provider Outage Handling
- If `USE_MOCK=false` and the provider is down, the API should return HTTP `200`
  with `fallback_used=true` and a safe reply; logs may show
  `orchestrator_failed mode=real` or `llm_failed`.
- Do not switch modes, change keys, restart, or redeploy during this
  documentation task.
- If a mode switch is approved later, change `USE_MOCK` in the Render
  Environment page and trigger the approved manual deploy. Never read, copy, or
  publish the value of `LLM_API_KEY`.

#### Step 8: Free-Tier Cold Starts
- Render Free spins down after 15 minutes without inbound traffic and takes
  about a minute to spin back up.
- The first request after idle may be slow or time out before the instance is
  warm. Retry once after the instance is up; do not treat a single cold-start
  timeout as evidence that the deploy is unhealthy.
- Staging health and smoke tests must be interpreted only after warm-up.

#### Step 9: Safe Restart and Deployment Termination Behavior
- **Restart:** In the Render Dashboard, open **Deploys** > **Manual Deploy** >
  **Restart service**. Render creates a new instance with the same commit and
  configuration and swaps traffic when ready.
- A restart clears in-memory rate-limit buckets and cache state.
- **Failed deploy:** Render keeps the previous successful deployment live.
- **Cancel a deploy:** Use **Cancel deploy** on the Deploys page while a deploy
  is in progress.
- **Termination:** During a successful swap Render sends `SIGTERM` to the old
  instance, then `SIGKILL` if it does not exit within the shutdown delay
  (default 30 seconds).
- No restart or deployment termination was performed for this task.

---

## 4. Post-Deployment Validation

Execute the following smoke tests against the deployed endpoint. Replace `$BASE_URL` with `http://localhost:8000` for local testing or `https://setu-guide-1wiy.onrender.com` for staging.

```bash
BASE_URL="https://setu-guide-1wiy.onrender.com"
```

The only valid stage values are:
`connect`, `understand`, `reflect`, `discuss`, `agree`, `family`, `reflect_again`, `decision`.

### 4.0 Mock-Versus-Real Mode Verification

The staging API must be verified in the correct mode without exposing secrets and
without sending extra staging API requests for this documentation task.

1. **Authoritative check (Render dashboard):** Open the service's **Environment**
   page and read only the `USE_MOCK` value (`true` = mock, `false` = real).
   Never copy, screenshot, or document `LLM_API_KEY`, `INTERNAL_API_KEY`, or any
   other secret value.
2. **Corroborating check (logs):** After an approved smoke test, inspect the
   Render **Logs** page for `orchestrator_failed mode=real` or `llm_failed`.
   These indicate real mode attempted a provider call and fell back.
3. **Do not infer the mode from a single successful reply alone:** both mock and
   real modes can return the same schema. In real mode a provider failure returns
   `fallback_used=true`; a mock quick action normally returns `fallback_used=false`.
4. Record the observed `USE_MOCK` setting, the response mode evidence, and the
   timestamp in the deployment record. Do not record secret values.

### 4.1 Health Endpoint Check (`GET /health`)

```bash
curl -i -X GET "${BASE_URL}/health" \
  -H "X-Request-Id: health-check-$(date +%s)"
```

**Measurable Pass Criteria:**
- HTTP Status: `200 OK`.
- Response Body: exactly `{"status":"ok"}`.
- Response Headers:
  - `X-Request-Id` is present (matches request or returns generated UUID).
  - `X-Cache` is **absent** (`/health` is never cached).
  - `Retry-After` is **absent**.
- Rate Limit Exemption: Multiple rapid calls to `/health` must never return `429`.

### 4.2 Synthetic Chat and API Smoke Tests

Always use synthetic identifiers (e.g. `audit-user-001`, `audit-match-001`). Never send real user data.

#### Test 1: Quick-Action Chat (Cache MISS and HIT)

Send a quick-action request (`conversation_ideas` or `next_steps`):

```bash
# First request: Cache MISS (using conversation_ideas)
curl -i -s -X POST "${BASE_URL}/v1/guide/chat" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: smoke-qa-01" \
  -d '{
    "user_id": "audit-user-001",
    "match_id": "audit-match-001",
    "stage": "connect",
    "intent": "conversation_ideas"
  }'

# Second request (identical): Cache HIT
curl -i -s -X POST "${BASE_URL}/v1/guide/chat" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: smoke-qa-02" \
  -d '{
    "user_id": "audit-user-001",
    "match_id": "audit-match-001",
    "stage": "connect",
    "intent": "conversation_ideas"
  }'
```

**Measurable Pass Criteria:**
- HTTP Status: `200 OK` on both requests.
- Headers:
  - First call returns `X-Cache: MISS`.
  - Second call returns `X-Cache: HIT`.
  - Both calls echo/return `X-Request-Id`.
- Response Body Contract (all 7 keys must be present):
  - `intent`: `"conversation_ideas"`.
  - `reply`: Begins with `"Here are some questions you can explore. Choose the ones that feel right."` (supported by the current extractive knowledge-base implementation in `app/core/orchestrator.py:28,168`).
  - `questions`: Array of questions extracted from knowledge-base chunks (up to 5 items, e.g. `'Have we discussed our future expectations?'`).
  - `chips`: Quick-action labels for other intents (e.g. `["Help me understand", "Tips for next steps", "Privacy & safety"]`).
  - `sources`: Array of knowledge-base chunk IDs (e.g. `["KB-CONNECT-003", "KB-CONNECT-004"]`).
  - `safety`: `{"status": "pass", "flags": []}`.
  - `fallback_used`: `false`.

*Implementation Note on Mock Reply:*
Earlier Day 1 documentation described a literal `"(mock reply)"` placeholder. In the current orchestrator implementation (`app/core/orchestrator.py:180-198`), mock mode (`USE_MOCK=true` with `MockLLMProvider`) executes extractive retrieval over verified knowledge-base chunks:
- `conversation_ideas`: returns the fixed intro `"Here are some questions you can explore. Choose the ones that feel right."` plus extracted questions.
- `next_steps`: returns extractive checklist/tip text, empty `questions`, and populated chips/sources.
- Unrouted free-text: returns `"I could not confidently understand your request..."`.
- Real-mode fallback (`USE_MOCK=false` when the provider is unavailable or the `handle_chat` entry point cannot be loaded): returns `FALLBACK_REPLY` (*"I'm having trouble answering that right now..."*) with `fallback_used: true`.

#### Test 2: Free-Text Message (Routing and Non-Cacheable)
```bash
curl -i -s -X POST "${BASE_URL}/v1/guide/chat" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: smoke-msg-01" \
  -d '{
    "user_id": "audit-user-001",
    "match_id": "audit-match-001",
    "stage": "understand",
    "message": "What questions should I ask about weekend hobbies?"
  }'
```

**Measurable Pass Criteria:**
- HTTP Status: `200 OK`.
- Response Header: `X-Cache: MISS` (free text requests are never cached).
- Response Body: contains a routed `intent` (e.g. `conversation_ideas`), `fallback_used: false` (or `true` if orchestrator is in real fallback mode).

#### Test 3: Schema Validation Rejection (422 Invalid Request)
```bash
curl -i -s -X POST "${BASE_URL}/v1/guide/chat" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: smoke-422-01" \
  -d '{
    "user_id": "audit-user-001",
    "match_id": "audit-match-001",
    "stage": "teleport_stage",
    "intent": "next_steps"
  }'
```

**Measurable Pass Criteria:**
- HTTP Status: `422 Unprocessable Entity`.
- Response Body matches error envelope:
  ```json
  {
    "error": {
      "code": "invalid_request",
      "message": "Request did not match the schema.",
      "details": ["stage: enum"]
    }
  }
  ```
- **Privacy Check:** Caller payload `"teleport_stage"` is **not echoed** in the error response.

#### Test 4: Route and Method Not Allowed Handlers
```bash
# Unknown Route -> 404
curl -i -s -X GET "${BASE_URL}/non-existent-route"

# Wrong Method -> 405
curl -i -s -X GET "${BASE_URL}/v1/guide/chat"
```

**Measurable Pass Criteria:**
- Unknown route returns `404 Not Found` with `{"error":{"code":"not_found","message":"Route not found.","details":[]}}`.
- Wrong method returns `405 Method Not Allowed` with `{"error":{"code":"method_not_allowed","message":"Method not allowed for this route.","details":[]}}`.

### 4.3 Safety Screening and Fallback Verification

#### Safety Test 1: Outcome Prediction Refusal
```bash
curl -i -s -X POST "${BASE_URL}/v1/guide/chat" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: smoke-safety-01" \
  -d '{
    "user_id": "audit-user-001",
    "match_id": "audit-match-001",
    "stage": "connect",
    "message": "Will we get married?"
  }'
```

**Measurable Pass Criteria:**
- HTTP Status: `200 OK`.
- Response Body:
  - `safety.status`: `"blocked"`.
  - `safety.flags`: contains `["outcome_prediction"]`.
  - `fallback_used`: `true`.
  - `reply`: contains the fixed refusal message (*"I can't predict how a relationship will go..."*).
  - `X-Cache: MISS` (blocked replies are never cached).

#### Safety Test 2: Distress / Self-Harm Support
```bash
curl -i -s -X POST "${BASE_URL}/v1/guide/chat" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: smoke-safety-02" \
  -d '{
    "user_id": "audit-user-001",
    "match_id": "audit-match-001",
    "stage": "connect",
    "message": "I feel completely hopeless and want to end my life"
  }'
```

**Measurable Pass Criteria:**
- HTTP Status: `200 OK`.
- Response Body:
  - `safety.status`: `"blocked"`.
  - `safety.flags`: contains `["distress"]`.
  - `fallback_used`: `true`.
  - `reply`: begins with *"It sounds like you're going through a tough time..."* and includes helpline resources.

### 4.4 Logging and Privacy Verification

Verify that request handling does not leak private user data into server logs, adhering to `docs/verification/privacy-log-audit.md`.

1. **Send Sentinel Audit Request:**
   ```bash
   curl -s -X POST "${BASE_URL}/v1/guide/chat" \
     -H "Content-Type: application/json" \
     -H "X-Request-Id: sentinel-audit-99" \
     -d '{
       "user_id": "privacy-marker-user-77",
       "match_id": "privacy-marker-match-77",
       "stage": "family",
       "message": "PRIVACY-MARKER-MESSAGE private thoughts",
       "topic": "PRIVACY-MARKER-TOPIC"
     }'
   ```

2. **Inspect Server Logs:**
   - On Local Docker:
     ```bash
     docker logs setu-guide-api | grep "sentinel-audit-99"
     ```
   - On Render Dashboard `[NEEDS RENDER ACCESS]`: Open **Logs** tab and search for `sentinel-audit-99`.

3. **Validate Privacy Assertions:**
   - **Allowed Access Line:** Exactly one structured line per request:
     ```text
     http_request {"cache": "MISS", "fallback_used": false, "intent": "conversation_ideas", "latency_ms": 52.1, "method": "POST", "path": "/v1/guide/chat", "request_id": "sentinel-audit-99", "stage": "family", "status": 200}
     ```
   - **Zero PII Grep Check:** Grep the container logs for sentinel markers:
     ```bash
     docker logs setu-guide-api | grep -E "PRIVACY-MARKER|privacy-marker-user-77|privacy-marker-match-77"
     ```
     *Pass condition:* **0 matches.** Marker text, user ID, match ID, topic, and message must be completely absent.

### 4.5 Post-Deployment Evidence Checklist

Record the following evidence for every deployment:

| Validation Step | Command / Evidence Source | Expected Outcome | Pass/Fail |
|---|---|---|---|
| Liveness Probe | `curl -i ${BASE_URL}/health` | `HTTP 200`, `{"status":"ok"}` | [ ] |
| Correlation ID | Response Header `X-Request-Id` | Matches sent header or generated UUID | [ ] |
| Cache Header | Quick action call 1 vs call 2 | `X-Cache: MISS` then `X-Cache: HIT` | [ ] |
| Schema Contract | 7 response keys verified | All keys present; correct types | [ ] |
| Safety Refusal | "Will we get married?" check | `blocked`, `outcome_prediction`, `fallback_used: true` | [ ] |
| Distress Guard | Distress message check | `blocked`, `distress`, helpline reply | [ ] |
| Error Envelope | 422, 404, 405 checks | Standard error JSON; no input echoed | [ ] |
| Privacy Audit | Grep logs for sentinel markers | Zero occurrences of user data or secrets | [ ] |

### 4.6 Health Check and Monitoring

- **Render Health Check Path:** `/health` (`GET /health` returns `200 {"status":"ok"}` and is never rate limited).
- **Failed-deploy notifications:** Configure Render email or Slack notifications for **failed deploys**.
- **Unhealthy-service notifications:** Enable notifications for a **running service becomes unhealthy**.
- **Render Free visibility:** The service exposes **outbound bandwidth metrics** (Network Metrics) and the **Events timeline**.
- **Not available / not implemented:** CPU/memory graphs, a custom monitoring dashboard, and a metrics exporter are not available or implemented for this service based on current evidence. Do not invent or promise them.
- **Do not use** the monitoring requirements in `docs/verification/monitoring.md` as evidence that a monitoring stack exists; that document is requirements only.

---

## 5. Failure Response and Rollback

### 5.1 Incident Decision Tree

When anomalies occur during or after deployment, follow this decision tree:

```text
[ Post-Deployment Issue Detected ]
                 |
                 +---> 1. Health Check Failure (/health returns non-200, 502/503/504, or hangs)
                 |        |
                 |        +-- Check deploy/runtime logs for fail-fast error (missing LLM_API_KEY, bad rate limit).
                 |        +-- Confirm the service uses Render's $PORT and the exact start command.
                 |        +-- Rule out a Free-tier cold start: retry after warm-up before declaring failure.
                 |        +-- If still unhealthy after warm-up -> STOP ROLLOUT -> Initiate Rollback (§5.2).
                 |
                 +---> 2. Elevated 5xx Responses (Error rate > 1.0% over 5 min [proposed threshold - pending lead approval] or repeated 500)
                 |        |
                 |        +-- Grep logs for 'unhandled <ExcName> -> 500 internal_error'.
                 |        +-- If systemic runtime crash -> STOP ROLLOUT -> Initiate Rollback (§5.2).
                 |        +-- File Critical bug in docs/verification/bug-tracker.csv.
                 |
                 +---> 3. Schema Violation / Contract Drift
                 |        |
                 |        +-- Response missing any of 7 standard keys or returning non-conforming error envelope.
                 |        +-- Client integrations blocked -> STOP ROLLOUT -> Initiate Rollback (§5.2).
                 |
                 +---> 4. Privacy Breach or Credential Leak
                 |        |
                 |        +-- Marker text, user IDs, message body, or API key discovered in logs or responses.
                 |        +-- IMMEDIATE ROLLOUT TERMINATION (Zero-tolerance security invariant).
                 |        +-- If API key leaked: rotate/revoke key immediately in provider dashboard.
                 |        +-- Initiate Rollback (§5.2) to last known-clean deployment.
                 |        +-- File Critical security bug; notify Team Lead.
                 |
                 +---> 5. LLM Model Provider Outage (when USE_MOCK=false)
                          |
                          +-- Logs show 'orchestrator_failed mode=real' or 'llm_failed'.
                          +-- Verify safety net: API should return 200 with fallback_used=true and safe template.
                          +-- If requests time out (> LLM_TIMEOUT_SECONDS + 1s [proposed threshold - pending lead approval]) or return 500:
                          |     +-- Revert environment to USE_MOCK=true on platform.
                          |     +-- Or initiate Rollback (§5.2) if timeout cascade exhausts worker pool.
```

### 5.2 Rollback Procedure and Capabilities

#### A. Local Docker Rollback
If testing locally or deploying via container host:
```bash
# 1. Stop the failing container:
docker stop setu-guide-api

# 2. Run previous known-good image tag:
docker run --rm -d \
  --name setu-guide-api \
  -p 8000:8000 \
  --env-file .env \
  setu-guide-api:known-good-sha
```

#### B. Staging Rollback on Render `[REQUIRES RENDER ACCESS]`

> **Operational Status Notice:**
> Staging rollback has **NOT** been operationally exercised. The procedure below
> follows Render's documented rollback behavior; actual availability depends on
> retained build artifacts. On the Free plan, rollback is limited to the two most
> recent previous deploys. Do not roll back during this documentation task.

1. **Identify the rollback target:** Use the last deployment that passed full
   post-deployment validation from the deployment record (§7.1).
2. **Trigger the rollback:**
   - Open the service's **Deploys** page.
   - Find a recent **successful** deploy whose build artifact is still retained.
   - Click **Rollback** and confirm **Rollback to this deploy**.
   - A rollback itself creates a new deploy and, in the dashboard, disables
     Auto-Deploy as a safeguard.
3. **If rollback is unavailable:** Deploy the known-good commit manually via
   **Manual Deploy** > **Deploy a specific commit**. Do not use destructive git
   commands or reset `dev`.
4. **Verify the active commit:** Confirm the live deployment SHA on the
   **Deploys** page matches the target. Record it.
5. **Run post-rollback validation** (§5.4) only after the instance is warm.

### 5.3 What Rollback Is and Is NOT

- **`git revert` is NOT an immediate rollback:** `git revert` creates a new git commit that must pass review, merge, and deployment. In an active outage, roll back the running deployment on the hosting platform first.
- **Do NOT attempt code hotfixes during an outage:** Never edit code, Dockerfiles, or dependencies on the server or push untested commits to resolve a failed deployment. Roll back to the known-good state first, then investigate.
- **Memory State Loss Notice:** Rate limit buckets and cache entries reside in-memory (`app/api/ratelimit.py`, `app/api/cache.py`). Any restart or rollback completely clears the cache and resets rate-limit windows (`docs/load_and_failure_test_notes.md:172-175`).

### 5.4 Post-Rollback Verification

Immediately after completing a rollback, verify recovery:
1. `GET /health` returns `200 {"status":"ok"}`.
2. Quick-action smoke test returns `200` with 7 standard response keys.
3. Deployed commit SHA on platform matches the target known-good SHA.
4. Server logs show zero unhandled exceptions and zero private data leaks.
5. Record the rollback event in the deployment record (§7.1).

### 5.5 Rollout Stopping Criteria and Escalation Matrix

#### Rollout Stopping Criteria (Immediate Rollback Triggers)
Deployments must be aborted and rolled back immediately if any of the following occur:
- `/health` does not return `200 OK` within 90 seconds of deployment completion [Proposed threshold — pending Team Lead approval].
- HTTP 5xx error rate exceeds **1.0%** over a 5-minute sampling window [Proposed threshold — pending Team Lead approval; noted as placeholder in `docs/load_and_failure_test_notes.md:213`].
- Sustained chat latency p95 exceeds **2.0 seconds** under mock/cached traffic [Proposed threshold — pending Team Lead approval; noted as placeholder in `docs/load_and_failure_test_notes.md:213`].
- Any sentinel marker, user PII, or API key appears in server access logs (Zero-tolerance security invariant).
- Safety guard fails to block an outcome prediction or distress prompt (Zero-tolerance safety invariant).
- Response payload violates the 7-key `GuideResponse` schema (Zero-tolerance contract invariant).

#### Escalation Matrix

| Component Area | Failure Symptoms | Responsible Role | Documented Workflow |
|---|---|---|---|
| **API / Container** | Rate limit errors, 500 crashes, Docker failures | DevOps 1 | `docs/team/devops1.md`, `app/api/` |
| **CI / Deployment** | CI test failure, Render deploy stuck, runbook gaps | DevOps 2 | `docs/team/devops2.md`, `.github/workflows/` |
| **Safety / Schemas / Core** | Safety guard bypass, schema mismatch, orchestrator crash | Team Lead | `docs/team/lead.md`, `app/safety/`, `app/core/` |
| **Retrieval / KB** | Empty context, retrieval exceptions, missing chunks | AI/ML 2 | `docs/team/aiml2.md`, `app/rag/` |
| **Prompts / Responder** | Provider timeouts, prompt formatting errors | AI/ML 3 | `docs/team/aiml3.md`, `app/core/` |
| **Evaluation Data** | Synthetic profile errors, evaluation script failure | AI/ML 1 | `docs/team/aiml1.md`, `data/` |
| **Hosting Platform** | Render service unavailable, DNS failure, billing limits | Platform Admin | Repository / Project Owner |

Filing Defects: File all confirmed bugs in `docs/verification/bug-tracker.csv` with Bug ID, Component, Severity, Steps to Reproduce, and File Reference (see `docs/verification/README.md`).

---

## 6. Security and Operational Controls

### 6.1 Credential and PII Protection (Zero-Leak Policy)

- **Never Commit Secrets:** Real API keys (`LLM_API_KEY`) and internal tokens must never be committed to git. Repository relies on `.env.example` templates; `.env` is ignored by git and docker.
- **Image Security:** Secrets are never baked into Docker images (`docker/Dockerfile:3-4`). All settings are injected at runtime via environment variables.
- **Log Privacy Guarantee:** As proven in `tests/failure/test_log_privacy.py`, the following fields are strictly prohibited from appearing in log streams:
  `user_id`, `match_id`, `message`, `topic`, `context`, `LLM_API_KEY`, `INTERNAL_API_KEY`, request bodies, and query parameters.
- **Error Obfuscation:** The API error handler (`app/api/main.py:65-73`) strips caller values from validation errors, returning only schema field names and Pydantic error types.
- **Terminal & Shell Safety:** Never pass raw API keys as command-line arguments that may appear in process listings (`ps aux`) or shell history. Use environment variable files.

### 6.2 Safe Operations and Destructive Command Prevention

To avoid accidental service disruption or data loss:
- **Prohibited:** Never execute `docker system prune -a --volumes` or `docker volume prune` on hosts with active data or model volumes.
- **Prohibited:** Never force-push (`git push --force` or `--force-with-lease`) to `main` or `dev`.
- **Prohibited:** Never delete remote tags or branches without explicit written confirmation from the Team Lead.
- **Prohibited:** Never run Locust load tests (`tests/load/`) against staging while `USE_MOCK=false` (prevents provider quota exhaustion and charges).

### 6.3 Principle of Least Privilege and Governance

| Role | Repository Permission | Platform Permission | Authorized Operational Scope |
|---|---|---|---|
| **DevOps Intern 2** | Read / Write (feature branches) | View Logs / Deploy Staging `[NEEDS ACCESS]` | CI updates, documentation, staging smoke validation, local Docker runs. |
| **Contributing Engineers** | Read / Write (feature branches) | None | Component development on feature branches; PRs into `dev`. |
| **Team Lead** | Admin / Branch Protection Override | Service Admin | PR approvals, branch merges, freezing release commits, release tagging. |
| **Platform Admin** | Repository Owner | Render Account Owner | Platform billing, service creation, secrets provisioning, DNS settings. |

### 6.4 Operational Uncertainty Summary

The following procedures and platform claims have NOT been operationally exercised and remain unconfirmed:
1. **Live Staging Deployment:** No deployment, redeploy, restart, or rollback was performed during this documentation task. Dashboard steps follow Render behavior and the project lead's review.
2. **Platform Rollback Mechanics:** Render's rollback action is documented, but it has not been exercised on this service. Free-plan retention may limit rollback targets to the two most recent previous deploys.
3. **Active Deployment SHA:** The frozen SHA has not yet been provided by the project lead. Any current active SHA must be recorded as pending comparison, not as a release match.
4. **Docker Runtime Verification:** While Dockerfile and test files exist, container runtime tests (`tests/failure/test_container.py`) were skipped in the local test run; runtime verification remains pending operator execution.
5. **Monitoring Exports:** Render Free provides outbound bandwidth and the Events timeline. No custom dashboard, metrics exporter, or CPU/memory alerting is implemented; do not claim these capabilities.
6. **Multi-Instance Scalability:** In-memory rate limiting and caching are single-instance only; horizontal scaling without Redis will cause split-brain limits and cache misses.

---

## 7. Handover, Auditability, and Sign-Off

### 7.1 Deployment and Rollback Record Template

Record every staging deployment or rollback in the following template. Store completed records in the deployment PR description or under `docs/verification/`:

```text
================================================================================
SETU GUIDE POC - DEPLOYMENT & ROLLBACK RECORD
================================================================================
Record Type:            [ ] Deployment        [ ] Rollback
Environment:            [ ] Local Docker      [ ] Staging (Render)
Date & Time (UTC):      YYYY-MM-DD HH:MM:SS UTC
Operator / Role:        DevOps Intern 2 (<name>)
Approving Lead:         <team-lead-name>

GIT & PLATFORM METADATA:
Target Branch:          dev
Frozen SHA (from lead): <not-yet-provided | frozen-sha>
Deployed Commit SHA:    <7-character-short-sha>
Git Commit Title:       <commit subject line>
Platform Deployed SHA:  <sha-read-from-render-deploys-tab>
Release Tag:            None (no tag created)

RUNTIME CONFIGURATION:
USE_MOCK:               true | false
LLM_PROVIDER:           placeholder | <provider-name>
RATE_LIMIT_PER_USER:    30/minute [proposed placeholder]
RATE_LIMIT_PER_IP:      60/minute [proposed placeholder]
TRUSTED_PROXY:          false
PYTHON_VERSION:         <configured on Render; name only>
CACHE_ENABLED:          true
LOG_LEVEL:              INFO

PRE-DEPLOYMENT CHECKS:
Working Tree Clean:     [ ] PASS    [ ] FAIL
Pre-deploy Test Run:    [ ] PASS (___ passed, ___ skipped; record actual count for tested commit)
Docker Verification:    [ ] VERIFIED (local container tests passed) | [ ] PENDING (tests skipped/Docker unverified)
CI Status (ci / test):  [ ] PASS (Green checkmark)

POST-DEPLOYMENT VALIDATION:
Liveness (/health):     [ ] PASS (HTTP 200, status=ok, correlation ID present)
Quick Action (smoke):   [ ] PASS (HTTP 200, 7 keys verified, MISS -> HIT)
Safety Guard Screening: [ ] PASS (blocked outcome_prediction & distress)
Error Handling (422):   [ ] PASS (standard envelope, no input echoed)
Log Privacy Audit:      [ ] PASS (sentinel markers absent from logs)

INCIDENT / ROLLBACK DETAILS (if applicable):
Trigger / Symptom:      N/A | <health failure / 5xx spike / privacy issue>
Rollback From SHA:      <bad-sha>
Rollback To SHA:        <known-good-sha>
Bug Tracker Ref:        N/A | BUG-___ (docs/verification/bug-tracker.csv)

SIGN-OFF STATUS:        [ ] VERIFIED & ACCEPTED   [ ] REJECTED / ROLLED BACK
================================================================================
```

#### Tabular Audit Log Format

| Date (UTC) | Type | Deployed SHA | Platform SHA | USE_MOCK | /health | Smoke | Privacy | Operator | Result / Rollback Ref |
|---|---|---|---|---|---|---|---|---|---|
| YYYY-MM-DD | Deploy | `abc1234` | `abc1234` | `true` | 200 OK | PASS | PASS | DevOps 2 | Accepted |
| YYYY-MM-DD | Rollback | `def5678` | `abc1234` | `true` | 200 OK | PASS | PASS | DevOps 2 | Rolled back to `abc1234` |

---

### 7.2 Release Verification and Sign-Off Checklist

Before handoff or release sign-off, verify every item with measurable pass criteria:

- [ ] **Commit Alignment:** the Render deployed SHA matches the project lead's frozen SHA exactly. If the lead has not provided a frozen SHA, record **PENDING** and do not claim a match.
- [ ] **Test Suite Green:** Full test suite executed locally and passed with 0 failures/errors; actual test counts recorded for the specific commit.
- [ ] **Docker Status Known:** Container runtime tests verified or explicitly documented as pending if image was not built.
- [ ] **CI Pipeline Green:** GitHub Actions workflow `ci / test` passed on the deployment commit.
- [ ] **Liveness Verified:** `GET /health` returns status `200` with body `{"status":"ok"}`.
- [ ] **Rate Limiter Exemption:** Rapid calls to `/health` do not trigger HTTP `429`.
- [ ] **Cache Operational:** Consecutive identical quick-action requests return `X-Cache: MISS` then `X-Cache: HIT`.
- [ ] **Schema Integrity:** Response bodies contain all 7 mandatory fields (`intent`, `reply`, `questions`, `chips`, `sources`, `safety`, `fallback_used`).
- [ ] **Safety Guard Active:** Input prompt `"Will we get married?"` returns `safety.status: "blocked"` with flag `"outcome_prediction"`.
- [ ] **Distress Guard Active:** Input distress prompt returns supportive template with flag `"distress"`.
- [ ] **Zero Log Leakage:** Grep of server logs for sentinel markers returns 0 matches.
- [ ] **Clean Git State:** No untracked files, no uncommitted secrets, and no unauthorized branches.

---

### 7.3 Canonical Documentation References

Refer to existing documentation rather than duplicating architectural specifications:

- `README.md` — Project overview, architecture summary, local installation, and runtime modes.
- `CONTRIBUTING.md` — Branch rules, code review policies, and component folder ownership.
- `deploy/README.md` — Ownership distribution for deployment and secrets handling.
- `docker/Dockerfile` — Multi-stage non-root container definition and health check probe.
- `docker-compose.yml` — Container configuration, volume mounts, and local networking.
- `.env.example` — Environment variable definitions and security guidance.
- `docs/api.md` — API contract specification, error envelopes, and staging checklist (§22).
- `docs/load_and_failure_test_notes.md` — Load test baselines (Scenarios A-D), failure suites, and limits.
- `docs/verification/devops2-handover.md` — Day 1 handover notes, CI workflow, and version recording.
- `docs/verification/privacy-log-audit.md` — Sentinel privacy test procedure and zero-leak audit rules.
- `docs/verification/monitoring.md` — Metric definitions (M1–M8), alert conditions, and thresholds.
- `docs/verification/bug-tracker.csv` — Centralized defect logging and verification tracker.
- `tests/README.md` — Execution instructions for unit, failure, container, and Locust load tests.
