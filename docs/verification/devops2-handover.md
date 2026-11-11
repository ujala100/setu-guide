# DevOps 2 — Day 1 handover

Owner: DevOps 2. Audience: a new intern picking up repository, CI, deployment
and documentation duties for the Setu Guide POC. Every fact below was verified
against the repository on **2026-10-17** (branch `feature/devops2-ci-hardening`,
tip `531cb6e`). Where something is not verified or not yet implemented, it says
so explicitly — do not treat a gap as a working feature.

---

## 1. Repository structure and important files

Remote: `https://github.com/ujala100/setu-guide.git` (`git remote -v`).
The repository is **private** — access is by invitation only.

```
setu-guide/
├── .env.example               # every env var with dummy values; copy to .env
├── .gitignore                 # ignores .env, __pycache__/, .pytest_cache/
├── .dockerignore              # keeps secrets/caches out of the image
├── CONTRIBUTING.md            # branch rules + folder ownership (authoritative)
├── README.md                  # run instructions, Day 2/3 notes, layout map
├── requirements.txt           # runtime deps only (installed in the image)
├── requirements-dev.txt       # -r requirements.txt + pytest, httpx, locust
├── pytest.ini                 # pythonpath=.
├── docker-compose.yml         # local container run (mounts ./models read-only)
├── .github/
│   ├── CODEOWNERS             # placeholder — all handles commented out
│   ├── pull_request_template.md
│   └── workflows/ci.yml       # the only CI workflow
├── app/
│   ├── api/                   # FastAPI routes, rate limiter, cache (DevOps 1)
│   ├── config.py              # pydantic-settings, all env reads
│   ├── schemas/               # frozen request/response models (lead)
│   ├── core/                  # orchestrator, prompts (lead / AI-ML 3)
│   ├── rag/                   # knowledge base + retrieval (AI-ML 2)
│   └── safety/                # safety guard (lead)
├── data/                      # synthetic profiles + test conversations (AI-ML 1)
├── deploy/                    # README only — staging deploy is DevOps 2's area
├── docker/Dockerfile          # multi-stage, non-root, HEALTHCHECK on /health
├── docs/
│   ├── api.md                 # integration doc; §22 is the staging checklist
│   ├── load_and_failure_test_notes.md   # Day 3 numbers, bug list, known limits
│   ├── postman/               # Setu-Guide.postman_collection.json
│   ├── team/<role>.md         # one file per role, day-by-day tasks
│   └── verification/          # DevOps 2 verification artifacts (see §5)
├── eval/                      # retrieval eval script + dev/heldout cases
└── tests/                     # unit + failure + load suites (see §4)
```

Most important files for a new DevOps intern:

| File | Why it matters |
|---|---|
| `CONTRIBUTING.md` | Branch/review/merge rules and who owns what. |
| `.github/workflows/ci.yml` | The entire CI pipeline (18 lines). |
| `docs/api.md` | Source of truth for the API contract; §22 = staging checklist. |
| `.env.example` | Full list of environment variables (never commit `.env`). |
| `tests/README.md` | How to re-run the Day 3 load/failure suites. |
| `docs/verification/` | Bug tracker, privacy-log audit, monitoring requirements. |

---

## 2. Clone the private repo and set up the environment

### 2.1 Get access and clone

1. Ask the team lead to invite your GitHub account as a collaborator on
   `ujala100/setu-guide` (the repo is private; you cannot fork or clone without
   an invite).
2. Clone over HTTPS with your GitHub credentials:

   ```bash
   git clone https://github.com/ujala100/setu-guide.git
   cd setu-guide
   ```

   If your remote URL is `https://...`, Git will prompt for credentials on the
   first push. Use a Personal Access Token (PAT) or SSH — do **not** paste your
   GitHub password into the repo or any script.

3. Confirm you are on the integration branch:

   ```bash
   git status          # On branch dev
   git log --oneline -3
   ```

### 2.2 Install dependencies

```bash
python -m pip install -r requirements-dev.txt
```

- `requirements-dev.txt` includes `requirements.txt` (runtime) plus
  `pytest==9.1.1`, `httpx==0.28.1`, `locust==2.46.7` — all pinned.
- CI uses the same install step (`.github/workflows/ci.yml:17`), so a green
  local install means a green CI install.
- Python **3.11** is what CI pins (`ci.yml:15`); use the same version locally.

### 2.3 Environment file (never committed)

```bash
cp .env.example .env
```

- `.env` is ignored by git **and** by docker (`.env.example:3`), so secrets
  never leave your machine. Never commit a real key.
- Defaults work without editing. `USE_MOCK=true` uses knowledge-base/template
  mock replies. `app.core.orchestrator.handle_chat` exists; flipping to `false`
  requires a real `LLM_API_KEY`, and provider failures answer a safe 200 with
  `fallback_used=true` (README.md:92-96).
- Startup fails fast with one clear line if the environment cannot work
  (README.md:66-68).

### 2.4 Run the service locally

```bash
uvicorn app.main:app --reload --port 8000   # app.api.main:app is the same app
curl localhost:8000/health                  # -> {"status": "ok"}
```

Swagger UI: `http://localhost:8000/docs`.

Container alternative (see §1 for the multi-stage, non-root image):

```bash
docker build -f docker/Dockerfile -t setu-guide-api:day2 .
docker run --rm -p 8000:8000 --env-file .env setu-guide-api:day2
# or, with the model volume mount:
docker compose up --build
```

---

## 3. Branch naming, pull requests, review and merge

All rules below are from `CONTRIBUTING.md` (the authoritative source).

### 3.1 Branch model

- `main` is **protected**. `dev` is the **integration branch**.
- Open all PRs **into `dev`** (`CONTRIBUTING.md:2`).
- Branch naming: `feature/<area>-<short-description>` — e.g.
  `feature/api-mock-endpoint` (`CONTRIBUTING.md:3`). Example in the wild:
  `feature/devops2-ci-baseline`.

### 3.2 Work on a feature branch

```bash
git checkout dev
git pull origin dev
git checkout -b feature/<area>-<short-description>
# ... edit, commit ...
git push -u origin feature/<area>-<short-description>
```

### 3.3 Open the PR

- Fill in `.github/pull_request_template.md`: What changed, How to test, and
  the checklist (schema change approved? tests updated and `pytest -q`
  passes? no secrets or real user data?). Template at `.github/pull_request_template.md`.
- The team lead approves **every** PR (`CONTRIBUTING.md:4`).
- CI (`.github/workflows/ci.yml`) runs automatically on every PR targeting
  `dev` or `main` (`ci.yml:3-4`).

### 3.4 Review and merge

- Author **squash-merges** after the lead's approval (`CONTRIBUTING.md:4`).
- The lead merges `dev` into `main` once, after the Day 3 integration test
  (`CONTRIBUTING.md:5`).
- **Caveat (unverified):** whether a red CI actually *blocks* a merge depends
  on GitHub branch-protection / rulesets configured on the remote. The workflow
  only *runs* tests and reports status; it does not itself prevent merging.
  The current settings were not verifiable from the repo (no `gh` CLI
  available; the GitHub protection API needs auth we do not have). Confirm with
  a repo admin before assuming a failed test stops a merge.

### 3.5 CODEOWNERS

`.github/CODEOWNERS` exists but every rule is **commented out** with placeholder
handles (`@lead`, `@aiml2`, …). Review assignment is therefore not enforced by
CODEOWNERS today; the lead reviews by convention. Activating it is an open
action item for DevOps 2.

---

## 4. Run the test suite and check CI

### 4.1 Local test run

```bash
python -m pytest -q          # whole suite: Day 1 + Day 2 + Day 3
```

Useful subsets (`tests/README.md`):

```bash
python -m pytest tests/failure -q        # Day 3 failure suite (TestClient)
python -m pytest tests/test_retriever.py -q
```

- `tests/failure/test_container.py` needs Docker **and** a locally built image;
  without them it **skips itself** so CI stays green (`tests/README.md:24-31`).
  To run it: `docker build -t setu-guide-api:day3 -f docker/Dockerfile .` then
  `python -m pytest tests/failure/test_container.py -q`.
- Last recorded full-suite result: **179 passing** (README.md:141), Day 3.
- Load tests (`tests/load/`) are Locust, **not** collected by pytest. See
  `tests/README.md:38-96`. Never point a load run at a real LLM provider.

### 4.2 What CI runs

`.github/workflows/ci.yml` (the whole file):

- **Triggers:** every PR to `dev` or `main`, every push to `dev`, and manual
  `workflow_dispatch` (`ci.yml:2-7`).
- **Job `test`** on `ubuntu-latest`, Python 3.11: checkout → setup-python →
  `pip install -r requirements-dev.txt` → `python -m pytest -q`
  (`ci.yml:8-18`).
- That is the **only** job. There is no lint, type-check, coverage or separate
  regression gate in CI today.

### 4.3 Check CI status for a PR

CI produces a status check named **`ci / test`** (workflow `ci` + job `test`).

- GitHub web UI: open your PR → the **Checks** tab (or the green/red tick next
  to the commit) shows `ci / test`.
- API / CLI: `gh` is not installed in this environment; with `gh` installed you
  would run `gh run list --workflow=ci.yml` or `gh pr checks <number>`.
- To re-run a failed job: **Actions** tab → `ci` workflow → **Re-run failed
  jobs**, or trigger it manually via **Run workflow** (`workflow_dispatch`).
- If CI is red, read the failing pytest output, fix locally, push again — CI
  re-runs automatically on each push to the feature branch's PR.

### 4.4 Current CI limitation (honest note)

The container/real-image tests (`tests/failure/test_container.py`) are
**skipped in CI** because the workflow does not build the Docker image
(`tests/README.md:31`, `docs/load_and_failure_test_notes.md:186-187`). They run
on the dev machine, not in CI. Treat a green CI run as "unit + failure
(TestClient) passed", not "container verified".

---

## 5. Bug tracker: where it is and how to report

### 5.1 Location

| File | What it is |
|---|---|
| `docs/verification/bug-tracker.csv` | The tracker itself — plain UTF-8 CSV, open in Excel / Google Sheets / LibreOffice. |
| `docs/verification/README.md` | Full guide: columns, severity, status workflow, privacy rules. |

The tracker is currently **header-only** (no rows). As of the last test run no
defect had been confirmed (`docs/load_and_failure_test_notes.md`, §4). It is
intentionally empty — do not add a row you cannot back with evidence.

### 5.2 Reporting a bug

1. Open `docs/verification/bug-tracker.csv` and append **one row** on the next
   free line.
2. Assign the next free `Bug ID` (`BUG-001`, `BUG-002`, …) — never reuse an id.
3. Fill all 12 columns:
   `Bug ID, Title / Description, Severity, Component, Steps to Reproduce,
   Expected Result, Actual Result, Assigned Owner, Status, Evidence / File
   Reference, Date Reported, Notes`.
4. Severity: `Critical` (service down / privacy leak / wrong safety behaviour),
   `High` (core flow broken), `Medium` (degraded or workaround exists), `Low`
   (cosmetic).
5. Component: `API`, `CI/CD`, `deployment`, `AI/ML`, `safety`, `testing`,
   `documentation`, `other`.
6. Status starts at `New`. Workflow: `New → In Progress → Fixed → Verified`,
   with `Reopened` if verification fails. Only the **verifier** (someone other
   than the fixer) moves a bug to `Verified` — never without evidence.
7. Owner assignment follows `CONTRIBUTING.md` folder ownership (§3 table in
   `docs/verification/README.md`).

### 5.3 CSV editing rules

- Wrap a field in double quotes if it contains a comma, a double quote or a
  line break; escape inner quotes by doubling them (`""`).
- Save as **CSV UTF-8** if you use Excel, so Hindi/unicode text survives.
- Use synthetic ids/messages only. Never paste API keys, tokens, passwords or
  real user data; for a privacy bug reference the sentinel marker or line
  number instead (`docs/verification/README.md:106-114`).

### 5.4 Related verification docs

- `docs/verification/privacy-log-audit.md` — how to prove the logs contain no
  private data; file any leak in the tracker.
- `docs/verification/monitoring.md` — what to observe and at what thresholds
  (requirements only; **no monitoring stack is implemented** yet).

---

## 6. Staging URL and health verification

### 6.1 URLs

| Environment | Base URL |
|---|---|
| Local | `http://localhost:8000` |
| Staging | `https://setu-guide-1wiy.onrender.com` |

Source: `docs/api.md` §2 Base URLs. The Postman collection's `base_url`
defaults to the staging URL; override it to `http://localhost:8000` for local
runs (README.md).

### 6.2 Verify service health (liveness)

```bash
curl -i https://setu-guide-1wiy.onrender.com/health
```

Expected (`docs/api.md:65-78`):

- Status **200** with body `{"status": "ok"}`.
- Header **`X-Request-Id`** present (send your own `X-Request-Id` to get it
  echoed back — this is the correlation id you will find in the server log).
- **No `X-Cache`** header and **no `Retry-After`** header.
- `/health` is **never rate limited**, even when chat is already returning 429.

Local equivalent: `curl -i http://localhost:8000/health` — same expectations.

### 6.3 Full staging verification checklist

`docs/api.md` §22 (lines 430-443) is the authoritative checklist — run it before
any sign-off. Summary of the items beyond `/health`:

- Quick-action chat (`connect`/`next_steps`, synthetic ids) → 200, 7-key body,
  `safety.status=="pass"`, `fallback_used==false`, `X-Cache: MISS` then `HIT`.
- Message-only request → 200 with a routed `intent`.
- Unknown `stage` → 422 `invalid_request`; caller text absent from body.
- Unknown route → 404 `not_found`; `GET /v1/guide/chat` → 405
  `method_not_allowed`.
- Safety: `"Will we get married?"` → 200 `blocked`/`outcome_prediction`.
- Request-id correlation: send `X-Request-Id: staging-<uuid>`, assert the same
  value comes back.
- Log privacy: the access line contains only
  `request_id/method/path/status/latency_ms/cache/intent/stage/fallback_used`;
  grep for the synthetic `message`/`topic`/ids returns nothing (see
  `docs/verification/privacy-log-audit.md`).
- Confirm no secrets in responses/logs and confirm `USE_MOCK` mode with the
  lead before sign-off.

> **Not yet verified:** whether the currently deployed staging instance
> satisfies this checklist was not confirmed during this handover. Treat
> staging health as "unverified" until you run §6.2 and §6.3 yourself.

---

## 7. Record the deployed version and match it to a release commit

### 7.1 Current state (verified)

- **No release tags exist.** `git tag` returns nothing across the repository.
  No release tag has been created.
- **No `/version` endpoint or build metadata exists.** The service exposes only
  `GET /health` and `POST /v1/guide/chat` (`docs/api.md:11`); there is no
  version/build endpoint to query a running instance.
- Therefore the **only** reliable way to identify the deployed version is the
  hosting platform's deploy metadata (for staging on Render: the commit SHA
  Render records for the current deploy), cross-checked against the git history
  in this repo.

### 7.2 Record the deployed version (procedure)

Because there is no in-app version signal, record the version explicitly on
every deploy, using the platform's recorded commit SHA:

1. **Before deploying:** note the commit you intend to ship.

   ```bash
   git rev-parse --short HEAD       # e.g. 531cb6e
   git log --oneline -1
   ```

2. **Deploy** via the platform (staging on Render — the deploy is created from
   a branch/commit on the remote).
3. **Read the deployed commit from the platform.** On Render, open the
   service's **Deploys** page and read the commit SHA (and branch) shown for the
   currently live deploy. Record it:

   | Field | Value |
   |---|---|
   | Date | YYYY-MM-DD |
   | Deployer | name |
   | Deployed commit SHA (short) | from Render |
   | Branch deployed from | from Render |
   | `USE_MOCK` mode | true / false (confirm with lead) |
   | Health check (`/health`) | 200 / other |
   | Record keeper | name |

4. **Confirm the deployed commit exists in this repo** and matches what you
   intended:

   ```bash
   git fetch origin
   git branch -r --contains <deployed-short-sha>    # which branches contain it
   git log --oneline -1 <deployed-short-sha>        # what the commit is
   git tag --contains <deployed-short-sha>          # which release tag contains it
   ```

5. Store the record (in the deploy PR description, or a file under
   `docs/verification/` if the team wants a durable log). See also
   `deploy/README.md` (staging deploy is DevOps 2's area).

### 7.3 Matching a deployment to the frozen SHA (blocked on the project lead)

The intended release process is: the project lead freezes a commit, provides
that SHA, and a deploy is verified to be running exactly that commit. Tagging is
separate and is not authorized by this handover.

**This has not happened yet**, and this handover does not claim otherwise:

- Do **not** create or push any tag. The project lead has not provided the
  frozen SHA yet.
- Do **not** claim staging matches a release commit until the deployed version
  has been **verified** via the procedure in §7.2 (platform SHA recorded, the
  commit found in the repo, health check passing).

Once the lead provides the frozen SHA, the verification loop is:

```bash
# 1. Confirm the frozen commit exists in the repo:
git fetch origin
git log -1 --oneline <frozen-sha>

# 2. Compare the Render deployed SHA with the frozen SHA:
#    read the short SHA from Render's Deploys page and record it

# 3. They must match exactly. If they do not, the deploy is stale or from the
#    wrong commit. Stop and ask the lead; do not redeploy without approval.
```

Record the result (date, frozen SHA, Render SHA, match/mismatch) alongside the
deploy record from §7.2. Only after "frozen SHA == deployed SHA" may you state
that staging runs the approved commit.

---

## Quick-reference checklist for a new DevOps 2 intern

- [ ] Access granted; repo cloned; on `dev`.
- [ ] `pip install -r requirements-dev.txt` (Python 3.11).
- [ ] `cp .env.example .env` (never committed).
- [ ] `uvicorn app.main:app --reload --port 8000` + `curl /health` → 200.
- [ ] `python -m pytest -q` green locally.
- [ ] Open feature branches as `feature/<area>-<description>`; PR into `dev`.
- [ ] CI check to watch: **`ci / test`** (Checks tab).
- [ ] Read `docs/verification/README.md` before filing a bug.
- [ ] Staging: `https://setu-guide-1wiy.onrender.com/health` → 200 `{"status":"ok"}`.
- [ ] Do **not** create or push any tag, and do not claim a staging/commit match
      until the project lead provides the frozen SHA **and** the deploy is
      verified (§7).

---

*This handover is documentation only. It does not change application code, CI
workflows, dependencies or configuration. Facts were verified against the repo
on 2026-10-17; re-verify anything time-sensitive (CI settings, staging state)
before relying on it.*
