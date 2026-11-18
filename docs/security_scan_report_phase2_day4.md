# Security Scan Report — Phase 2, Day 4 (2026-11-01)

**Owner:** DevOps 1 · **Branch:** `feature/phase2-day4-recovery-integration`
**Tools:** `pip-audit 2.10.1` (Python deps), `detect-secrets 1.5.0` (repo + history)

---

## 1. Python dependencies (requirements.txt — what the image ships)

`pip-audit -r requirements.txt` → **No known vulnerabilities found** — 0 CVEs.

All runtime packages pinned with `==`:
- fastapi==0.142.2, pydantic==2.13.5, pydantic-settings==2.15.0, cachetools==7.2.1, uvicorn==0.54.0, google-genai==2.29.0
- certifi==2026.10.18, pyasn1==0.6.5 — transitive security floors added 2026-11-10 (see §6)

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
| Image shipped CVEs | ✅ 0 Python CVEs (Day 3 hardening); OS HIGH accepted with mitigations — 8 at Day 4, 11 after the 2026-11-11 DB refresh, 0 fixable (see §6) |
| Secrets in repo/history | ✅ 0 real secrets; all markers are synthetic test values |
| Secrets in image | ✅ 0 (Day 3 trivy scan) |
| Container hardening | ✅ Non-root, digest-pinned, build tools removed, HEALTHCHECK, graceful shutdown |
| **Critical findings** | **0** — nothing to escalate |

**Re-scan cadence:** Run `pip-audit -r requirements.txt` and `pip-audit -r requirements-dev.txt` on every dependency update. Run `trivy image` on every image rebuild. The base image digest pins the Debian version; refresh the digest deliberately when a new base is wanted.

---

## 6. Re-verification — 2026-11-11 (transitive pins + deliberate base refresh)

This report was re-verified on this branch with a fresh scan (`trivy 0.76.0`
with a current vulnerability DB, image rebuilt from this branch's
`docker/Dockerfile` + `requirements.txt`). A re-scan with a *newer DB* is
expected to surface CVEs published since the last one — that is the re-scan
cadence working, not a regression. Three things were found and fixed:

**1. Transitive Python CVEs ship in the image — §2 above classed them as
local-venv-only, which was incomplete.** `pip-audit -r requirements.txt`
only audits the direct pins, so the runtime venv's transitive tree was
unaudited. A trivy language scan of the rebuilt image found:

| Package | Finding | Fix |
|---|---|---|
| certifi 2026.7.22 | **GHSA-6q48-6c7w-9gw2 (CRITICAL)** — bundles emSign root CAs with compromised intermediate CA keys | pinned `certifi==2026.10.18` in requirements.txt |
| pyasn1 0.6.4 | CVE-2026-119194..119197 (4x HIGH) — DoS via ASN.1 decoding | pinned `pyasn1==0.6.5` in requirements.txt |

Both arrive in the runtime venv via the `google-genai` dependency tree
(google-genai -> requests -> certifi; google-genai -> google-auth ->
pyasn1). After the pins: **trivy Python findings 0**;
`pip-audit -r requirements.txt` still reports "No known vulnerabilities
found" — and it now audits the two new pins as direct requirements.

**2. The pinned 2026-10-22 base had fallen behind Debian.** Re-scanned
with the current DB, the old digest's package set still carried OS HIGH
CVEs with a Debian fix available (e.g. CVE-2026-109518, CVE-2026-76844,
CVE-2026-85091 at the 2026-11-11 scan) that `apt-get upgrade` inside the
old point release could not reach. The base digest was **deliberately
refreshed** — the Dockerfile pin exists exactly so this is a decision, not
a silent drift:

- `python:3.11-slim@sha256:e88e9763...` (2026-10-22, python 3.11.17 / debian 13.7)
- -> `python:3.11-slim@sha256:07d48240...` (2026-11-10 manifest, same debian 13.7 line)

`apt-get upgrade` in the runtime stage then applied the point-release
fixes. Result on the refreshed image: **fixable HIGH 0**.

**3. Remaining OS HIGH after the refresh: 11 unique CVEs, all with no
Debian fix available** — the same set Day-3/Day-4 documented (util-linux
family: CVE-2026-76642/78408/78410, login/liblastlog2-2, libacl1
CVE-2026-54369, ncurses-base CVE-2025-69720, libudev1 CVE-2026-16742,
perl-base CVE-2026-9538) plus the 3 libsqlite3-0 rows
(CVE-2026-119373/74/79). Same acceptance rationale as before: local
attack vectors through binaries this service never invokes; the app
shells out to nothing, runs as non-root `app`, all capabilities dropped,
`no-new-privileges`, read-only root fs, no TTY, no runtime package
installs. sqlite is linked into the base's Python but the app opens no
database.

| Metric | Day-4 scan (2026-11-01 DB) | Re-scan after fixes (2026-11-11 DB) |
|---|---|---|
| Python CRITICAL | 0 | **0** (certifi CRITICAL fixed by pin) |
| Python HIGH | 0 | **0** (pyasn1 HIGHs fixed by pin) |
| Python findings total | 0 | **0** |
| OS HIGH unique / fixable | 8 / 0 | 11 / **0** |
| OS MEDIUM / LOW | 58 / 61 | 74 / 65 (newer DB reports more; nothing fixable at HIGH+) |
| UNKNOWN | 1 | 15 rows / **5 unique** — unrated openssl-family rows (CVE-2026-107496, CVE-2026-88822/823, CVE-2026-95691/2) newly listed by the 2026-11-11 DB, no Debian fix; same mitigations as the HIGH set above |
| Secrets (image) | 0 | **0** |
| Image size | 271 MB | **271 MB** |

Verification on this branch's rebuilt image: `docker compose up` -> health
`healthy`; `/health` 200; chat 200 with `safety: pass` under
`read_only` / `cap_drop ALL` / `no-new-privileges` (docker inspect
confirmed, user `app`); image venv probes: `certifi 2026.10.18`,
`pyasn1 0.6.5`; full suite `python -m pytest -q` -> **401 passed, 0
failed** (including the container and recovery suites that assert these
Dockerfile/compose flags); `pip-audit` -> "No known vulnerabilities
found".

**Final Result:** **0 CVEs** in Python deps (direct + pinned transitive),
**0 real secrets** in repo/image, **11 OS HIGH + 5 unrated openssl rows**
accepted with documented mitigations (no Debian fix exists), image
hardened: non-root, minimal digest-pinned base, pinned versions, build
tools removed, read-only fs, HEALTHCHECK present.
