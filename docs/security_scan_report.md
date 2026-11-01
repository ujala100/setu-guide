# Security Scan Report — Phase 2, Day 3

**Date:** 2026-10-20 · **Owner:** DevOps 1 · **Branch:** `feature/phase2-day3-security`
**Tools:** `pip-audit 2.10.1` (Python deps), `trivy 0.76.0` (image: CVEs + secrets)

Baseline image = `setu-guide-api:day2` built 2026-10-18, image ID
`sha256:27f6e178df7b4b335c7e3d540bb5c11dc1ebdf2d0ae42e48e0151e42d43ae1ac`.
Hardened image = `setu-guide-api:day3` built 2026-10-20, image ID
`sha256:3454b30ea5ffae3c201147ce891261f050ab02353035210c7b1ba99578598b05`
(both tags `day2`+`day3` now point at the hardened build, so compose/README
commands and the container tests use the same image).

## 1. Python dependencies (requirements.txt / requirements.txt in the image)

`pip-audit -r requirements.txt` → **"No known vulnerabilities found"** — 0 CVEs,
before any change. All six runtime packages were already pinned with `==`
(fastapi 0.142.2, pydantic 2.13.5, pydantic-settings 2.15.0, cachetools 7.2.1,
uvicorn 0.54.0, google-genai 2.29.0), as are the dev pins.

The Python CVEs the image scan found were **not** in requirements.txt — they
were the base image's/venv's *build tools* (see §2). Trivy's language scan of
the image: **before 4 HIGH + 12 MEDIUM + 2 LOW → after 0** (tools removed).

## 2. Image scan: before → after

| Finding class | Before (day2, Oct-18) | After (day3, hardened) | Change |
|---|---|---|---|
| OS **HIGH** | 44 rows / **8 unique CVEs** | 44 rows / 8 unique CVEs | unchanged — no Debian fix exists (§3) |
| OS MEDIUM | 58 | 58 | — |
| OS LOW | 61 | 61 | — |
| OS UNKNOWN | 3 | **1** | liblzma5 `DSA-6549-1` + `TEMP-1147318` fixed by apt upgrade |
| Python **HIGH** | **4** (jaraco.context 5.3.0, wheel 0.45.1 — both vendored inside setuptools, found in venv **and** globally) | **0** | build tools removed |
| Python MEDIUM | **12** (pip 24.0 ×6 CVEs, setuptools 79.0.1, ×2 copies) | **0** | build tools removed |
| Python LOW | 2 (pip CVE-2026-1703) | **0** | build tools removed |
| Secrets (trivy) | **0** | **0** | — |
| Image size | 307 MB | **271 MB** | −36 MB |

### Fixes applied (docker/Dockerfile, docker-compose.yml)

1. **No build tools in the final stage** — the builder venv now runs
   `pip uninstall -y pip setuptools` after installing requirements, and the
   runtime stage runs `/usr/local/bin/pip uninstall -y pip setuptools wheel`
   for the base image's global copies. This removes every Python-side finding
   outright (including setuptools' vendored wheel/jaraco HIGH CVEs).
   Verified in the image: `which pip` → none; no `pip|setuptools|wheel|jaraco`
   in either site-packages; `import app.api.main` → ok.
2. **Debian fixes applied at build** — `apt-get upgrade --no-install-recommends`
   + `rm -rf /var/lib/apt/lists/*`. Result: liblzma5 DSA findings gone.
3. **Base pinned by digest** — both stages:
   `python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce`
   (python 3.11.17, debian 13.7). Refresh deliberately, not silently.
4. **Runtime hardening (compose)** — `read_only: true` + `tmpfs: /tmp`,
   `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, on top of the
   existing `init: true`, non-root `USER app`, `:ro` model mounts.

### Hardening checklist (task requirements)

| Requirement | Status | Evidence |
|---|---|---|
| Non-root user | ✅ | `USER app` in Dockerfile; `docker inspect .Config.User` → `app` |
| Minimal base | ✅ | `python:3.11-slim` (debian 13.7), digest-pinned |
| All versions pinned | ✅ | requirements `==`, base digest, build tools removed entirely |
| No build tools in final stage | ✅ | image probe: `no pip / no global build tools / no venv build tools` |
| No secrets baked in | ✅ | trivy secrets 0 (before+after), `docker history` grep 0, baked ENV = only `PYTHONUNBUFFERED/PYTHONDONTWRITEBYTECODE/PATH/PORT/LANG` + python-image's public `GPG_KEY` |
| HEALTHCHECK present | ✅ | Dockerfile HEALTHCHECK; compose container reached `healthy` |
| Read-only filesystem where possible | ✅ | `ReadonlyRootfs: true` verified; health 200 + chat 200 under it; no `Read-only`/`Permission denied` errors in logs |

### Verification on the hardened image

- `pytest tests/failure/test_container.py` → **3/3 passed**: fail-fast without
  secret, restart-under-load → `healthy` again with 0 server errors, container
  logs carry no private data.
- `docker compose config -q` valid; `compose up` → `/health` 200,
  `/v1/guide/chat` 200 (`X-Cache: MISS`, `X-Request-Id` present),
  `Health: healthy`, inspect: `ReadonlyRootfs true | CapDrop [ALL] |
  no-new-privileges | User app`. Torn down cleanly.

## 3. Remaining findings: 8 OS HIGH CVEs with no Debian fix

Debian has not backported fixes for these (trivy fix column: empty before and
after the apt upgrade — there is nothing to upgrade to today):

| CVE | Package(s) | Issue |
|---|---|---|
| CVE-2026-76642 | util-linux family (bsdutils, libblkid1, libmount1, libuuid1, mount, login…) | privileged X-mount post-hooks still run |
| CVE-2026-78408 | util-linux family | `nsenter --join-cgroup` leaks root cgroup authority |
| CVE-2026-78409 | util-linux family | X-mount.subdir symlink escape |
| CVE-2026-78410 | util-linux family | restricted bind mounts not pinned |
| CVE-2026-54369 | libacl1 | symlink-traversal privilege escalation |
| CVE-2025-69720 | libncursesw6, libtinfo6, ncurses-* | buffer overflow → code execution |
| CVE-2026-16742 | libsystemd0, libudev1 | systemd-homed local privilege escalation |
| CVE-2026-9538 | perl-base | perl-Archive-Tar DoS via crafted tar header |

**Why the risk is accepted for this POC (mitigations):** every one of these is
exploited *locally* through binaries/functions this service never uses — the
app shells out to nothing (health probe is Python stdlib), never calls
`mount`/`nsenter`/`systemd`/`perl`/ncurses, runs as non-root `app` with
**all capabilities dropped**, **no-new-privileges**, a **read-only root fs**
and no interactive TTY. The container also has no package manager usage at
runtime. Re-scan cadence: every image rebuild (the base digest + apt layer
pick up Debian backports the moment they exist — re-run
`trivy image setu-guide-api:day3` after the next base refresh).

## Findings log (bug tracker)

| # | Finding | Severity | Owner | Status |
|---|---------|----------|-------|--------|
| C | Build tools (pip/setuptools/wheel + vendored wheel/jaraco) in image carrying 4 HIGH / 12 MEDIUM Python CVEs | High (scanner) | DevOps 1 | **Fixed** in this PR — tools removed, trivy Python side now 0 |
| D | 8 unique OS HIGH CVEs in base packages with no Debian fix yet | High (scanner) / Low in practice — see mitigations §3 | DevOps 1 (re-scan cadence) | **Accepted with mitigations**, documented above; re-scan on every rebuild |
| E | liblzma5 findings without fixes at scan time | Unknown severity | DevOps 1 | **Fixed** in this PR (apt upgrade, DSA applied) |

Pip-audit findings: **none** (0 CVEs — nothing to file).
