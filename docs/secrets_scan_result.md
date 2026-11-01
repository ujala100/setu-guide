# Secrets Scan Result — Phase 2, Day 4

**Owner:** DevOps 1 · **Date:** 2026-11-01 · **Branch:** `feature/phase2-day4-recovery-integration`

**Result:** no real secret found anywhere — in the repository, its entire git
history, the image layers, or the container environment/logs. Nothing to
rotate, nothing to escalate as Critical.

## 1. Full Git History (gitleaks v8.30.1)

```bash
gitleaks git . -r gitleaks_history.json -f json --redact
→ 6 finding rows = 3 unique locations, one single value
```

| Location | Commits | Value (redacted pattern) | Classification |
|---|---|---|---|
| `tests/failure/test_log_privacy.py:17` | `d4607d6`, `31cb348` | `sk-PRIVACY-MARKER-API-KEY-88` (entropy 3.6245186 — identical in all 6 rows) | **synthetic marker, by design** |
| `docs/verification/privacy-log-audit.md:58` | `4b48e5b`, `d7baf25` | same marker (shown as the audit's sample env value) | **synthetic marker, by design** |
| `docs/verification/privacy-log-audit.md:86` | `4b48e5b`, `d7baf25` | same marker (in the audit's sample `docker run -e` line) | **synthetic marker, by design** |

**Why this is accepted:** the marker is the *probe* the log-privacy tests grep for
in container/log output — it must exist in the test source and audit doc so
the tests can prove it never appears in logs. It is not a credential, is not
accepted by any service, and never entered any environment as a real key.

**No `github-pat`/`ghp_`-style token appears anywhere in the repository or its
41+ commits.** The GitHub PAT shared in a chat message (prefix `ghp_`) never
entered the repository or the image. **It still needs to be revoked on GitHub** —
that remains unconfirmed; pasting it in chat already exposed it regardless of
the repo being clean.

## 2. Working Tree (gitleaks dir, 118 MB scanned)

```bash
gitleaks dir . -r gitleaks_worktree.json -f json --redact
→ 226 rows = 223 rows inside .venv/ + 3 tracked-file rows (the same marker as §1)
```

- The **223 `.venv` rows** (211 `generic-api-key`, 12 `private-key`) are
  third-party files inside the local virtualenv. `.venv/` is in `.gitignore`
  (never committed) **and** in `.dockerignore` (never reaches the image) —
  environmental only, nothing of ours. Filter with
  `File -notmatch '^.venv'` when reviewing reports.
- Tracked files: only the 3 marker rows above (synthetic, by design).

## 3. `.env` Handling

| Check | Result |
|---|---|
| `.env` on disk | **Absent** (`Test-Path .env` → False — only `.env.example` exists) |
| git-ignored | ✅ `.gitignore` contains `.env` (and `*.log`) |
| ever tracked in git history | ✅ **never** — `git log --all --full-history -- .env` → empty |
| docker-ignored | ✅ `.dockerignore`: `.env`, `.env.*` with `!.env.example` exception |
| inside the image | ✅ `find / -name '.env*'` in `setu-guide-api:day4` → nothing; `/app` contains only `app/`, `data/`, `models/` |
| `.env.example` values | ✅ dummies only: `LLM_PROVIDER=placeholder`, `LLM_API_KEY=placeholder-not-a-real-key`, `LLM_TIMEOUT_SECONDS=10` (placeholder comment), `INTERNAL_API_KEY=` empty; header says "Never commit a real key" |

## 4. Docker Image Layers / Filesystem / Env

| Check | Result |
|---|---|
| trivy secret scan of image (before) | **0 findings** (`setu-guide-api:day2`) |
| trivy secret scan of image (after) | **0 findings** (`setu-guide-api:day4` hardened) |
| `docker history --no-trunc` grep for `sk-`/`ghp_`/`api_key=`/`token=`/`PRIVATE KEY` | **no matches** — no build steps carry a secret |
| Baked `Config.Env` | only `PATH`, `LANG`, `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE`, `PORT`, python image's public `GPG_KEY`/`PYTHON_VERSION`/`PYTHON_SHA256` — **no app secrets** |
| `.env`/secrets copied into image | none (§3) |

## 5. Container Environment and Logs

| Check | Result |
|---|---|
| Runtime env | secrets arrive only via `-e`/`env_file` at run time (e.g. the tests' marker `LLM_API_KEY=sk-PRIVACY-CONTAINER-KEY`), never baked (§4) |
| Container logs carry no private data | ✅ `pytest tests/failure/test_container.py::test_container_logs_carry_no_private_data` **PASSED** — asserts the marker key, message, topic, user and match markers are absent from `docker logs` |
| Structured log hygiene (unit level) | ✅ Day-2 audit: 53 000+ log lines, 0 occurrences of user/match ids, message text, topic, free-text prompts or API keys |
| Fail-fast without secret | ✅ container test **PASSED** — with `USE_MOCK=false` and no key the process exits non-zero with the config message and prints no key material (there is none) |

## Reproduce

```powershell
gitleaks git . -r history.json -f json --redact     # full git history
gitleaks dir . -r worktree.json -f json --redact    # files on disk
trivy image --scanners vuln,secret setu-guide-api:day4
docker history setu-guide-api:day4 --no-trunc       # manual grep
docker inspect setu-guide-api:day4 --format '{{json .Config.Env}}'
```

## Findings Log (Bug Tracker)

| # | Finding | Severity | Owner | Status |
|---|---|---|---|---|
| F | gitleaks flags the synthetic privacy-test marker `sk-PRIVACY-MARKER-…` (3 tracked locations,4 commits) | Info (false positive by design) | DevOps 1 (test) / DevOps 2 (audit doc) | **Accepted** — required by the log-privacy tests; documented here so future scans do not treat it as a leak |

**Real secrets found: 0** → no Critical, no rotation required.