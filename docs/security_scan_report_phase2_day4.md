# Security Scan Report — Phase 2, Day 4 (2026-11-01)

**Owner:** DevOps 1 · **Branch:** `feature/phase2-day4-recovery-integration`
**Tools:** `pip-audit 2.10.1` (Python deps), `detect-secrets 1.5.0` (repo + history)

---

## 1. Python dependencies (requirements.txt — what the image ships)

`pip-audit -r requirements.txt` → **No known vulnerabilities found** — 0 CVEs.

All runtime packages pinned with `==`:
- fastapi==0.142.2, pydantic==2.13.5, pydantic-settings==2.15.0, cachetools==7.2.1, uvicorn==0.54.0, google-genai==2.29.0

`pip-audit -r requirements-dev.txt` → **No known vulnerabilities found** — 0 CVEs in the declared dev deps.

---

## 2. Local .venv transitive dependencies (NOT shipped in image)

`pip-audit` against the local `.venv` (which includes dev tools + transitive deps) → **16 known vulnerabilities in 5 packages**:

| Package | Version | IDs | Fix Available | Origin |
|---------|---------|-----|---------------|--------|
| brotli | 1.2.0 | PYSEC-2026-4322 | 1.2.1 | geventhttpclient → locust (load test tool) |
| certifi | 2026.7.22 | PYSEC-2026-4320 | 2026.10.18 | geventhttpclient/httpcore/httpx/requests |
| opentelemetry-api | 1.45.0 | CVE-2026-114603 | 1.45.1 | fastapi (transitive) |
| pyasn1 | 0.6.4 | CVE-2026-119194/195/196/197 | 0.6.5 | pyasn1_modules → google-auth (transitive) |
| pypdf | 6.21.2 | CVE-2026-119203/04/05/06/07/08/09 | 6.21.3/4 | standalone (not required by our deps) |

**These are NOT in the production Docker image.** The Dockerfile only installs `requirements.txt`:
```
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

The vulnerabilities come from:
- `locust` (load testing, not in runtime image)
- Transitive deps of `fastapi`, `google-auth` (some may be in image but are already scanned clean by trivy in Day 3)
- `pypdf` (not required by any of our declared dependencies)

**Action:** Not Critical for production. The image was already hardened in Day 3 (build tools removed, trivy Python CVEs → 0). The remaining OS-level CVEs (8 HIGH, no Debian fix) are accepted with mitigations (non-root, all caps dropped, read-only rootfs, no-new-privileges).

---

## 3. Secrets scan (detect-secrets 1.5.0 + git history review)

**Result: 0 real secrets found.**

### What was scanned
- Full git history (all branches, all commits)
- Working tree (excluding `.venv/`, `.pytest_cache/`, `__pycache__/`)
- `git log --all --oneline --name-only` reviewed for any secret-bearing files

### Findings
All detections are **synthetic test markers** or **documentation references**, not real credentials:

| Location | Type | Classification |
|----------|------|---------------|
| `tests/failure/test_log_privacy.py:17` | `sk-PRIVACY-MARKER-API-KEY-88` | Synthetic marker for log-privacy tests (by design) |
| `tests/failure/test_container.py:34` | `sk-PRIVACY-CONTAINER-KEY` | Synthetic marker for container tests (by design) |
| `tests/failure/test_provider_drills.py:151` | `sk-DRILL-MARKER-KEY-42` | Synthetic marker for provider drills (by design) |
| `tests/test_day2_resilience.py:83` | `sk-SECRET-MUST-NOT-APPEAR` | Synthetic marker — name literally says "must not appear" |
| `tests/test_day2_config.py` | `sk-SUPER-SECRET-VALUE`, `sk-HIDDEN-VALUE` | Synthetic markers for config tests (by design) |
| `tests/integration/test_auth.py` | `integration-dummy-key` | Synthetic marker for integration tests |
| `tests/recovery/test_timeouts_shutdown.py` | `recovery-dummy-key` | Synthetic marker for recovery tests |

**No `github-pat`/`ghp_`/AWS key/Private key/real API key** appears anywhere in the repo or its history.

### .env handling
- `.env` does not exist on disk (`.env.example` only)
- `.env` is git-ignored and docker-ignored
- `.env` has never been tracked in git history
- `.env.example` contains only dummies: `LLM_API_KEY=placeholder-not-a-real-key`

---

## 4. Container image hardening (Dockerfile review)

The Dockerfile at `docker/Dockerfile` already implements Day 3 hardening:

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Non-root user | ✅ | `USER app` (system user, no login shell) |
| Minimal base | ✅ | `python:3.11-slim@sha256:...` (Debian 13.7, digest-pinned) |
| All versions pinned | ✅ | requirements `==`, base digest pinned |
| Build tools removed | ✅ | `pip uninstall -y pip setuptools wheel` in both stages |
| No secrets baked in | ✅ | `.dockerignore` excludes `.env`; `docker history` clean |
| HEALTHCHECK | ✅ | Python stdlib health probe on `/health` |
| Graceful shutdown | ✅ | `--timeout-graceful-shutdown 30` (Day 4 addition) |
| Keep-alive timeout | ✅ | `--timeout-keep-alive 5` (Day 4 addition) |

---

## 5. Summary

| Check | Result |
|-------|--------|
| Runtime deps (requirements.txt) | ✅ 0 CVEs |
| Dev deps (requirements-dev.txt) | ✅ 0 CVEs |
| Image shipped CVEs | ✅ 0 Python CVEs (Day 3 hardening); 8 OS HIGH accepted with mitigations |
| Secrets in repo/history | ✅ 0 real secrets; all markers are synthetic test values |
| Secrets in image | ✅ 0 (Day 3 trivy scan) |
| Container hardening | ✅ Non-root, digest-pinned, build tools removed, HEALTHCHECK, graceful shutdown |
| **Critical findings** | **0** — nothing to escalate |

**Re-scan cadence:** Run `pip-audit -r requirements.txt` and `pip-audit -r requirements-dev.txt` on every dependency update. Run `trivy image` on every image rebuild. The base image digest pins the Debian version; refresh the digest deliberately when a new base is wanted.
