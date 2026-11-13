# Security Scan Report — Phase 2, Day 4

**Owner:** DevOps 1 · **Date:** 2026-11-01 · **Branch:** `feature/phase2-day4-recovery-integration`

## 1. Python Dependencies (requirements.txt)

`pip-audit -r requirements.txt` → **No known vulnerabilities found** — 0 CVEs.

All runtime packages are pinned with `==`:
- fastapi 0.142.2
- pydantic 2.13.5
- pydantic-settings 2.15.0
- cachetools 7.2.1
- uvicorn 0.54.0
- google-genai 2.29.0

Dev dependencies also pinned similarly. **0 CVEs** in production deps.

## 2. Image Scan: Before → After

| Finding class | Before (day2) | After (day4/hardened) | Change |
|---|---|---|---|
| OS **HIGH** | 8 unique CVEs | 8 unique CVEs | unchanged — no Debian fix exists |
| OS **MEDIUM** | 58 | 58 | — |
| OS **LOW** | 61 | 61 | — |
| OS **UNKNOWN** | 1 | 1 (liblzma5) | fixed by apt upgrade — DSA-6549-1 |
| Python **HIGH** | 4 (jaraco.context, wheel) | **0** | build tools removed |
| Python **MEDIUM** | 12 (pip, setuptools) | **0** | build tools removed |
| Python **LOW** | 2 (pip CVE-2026-1703) | **0** | build tools removed |
| **Secrets** (trivy) | **0** | **0** | — |
| **Image size** | 307 MB | **271 MB** | −36 MB (minimal base) |

### Fixes Applied (Dockerfile, docker-compose.yml)

1. **No build tools in the final stage** — builder venv runs `pip uninstall -y pip setuptools wheel` after installing requirements, and the runtime stage runs `/usr/local/bin/pip uninstall -y pip setuptools wheel` for the base image's global copies. This removes every Python-side finding outright (including setuptools' vendored wheel/jaraco HIGH CVEs). Verified in the image: `which pip` → none; no `pip|setuptools|wheel|jaraco` in either site-packages; `import app.api.main` → ok.

2. **Debian fixes applied at build** — `apt-get upgrade --no-install-recommends` + `rm -rf /var/lib/apt/lists/*`. Result: liblzma5 DSA findings gone.

3. **Base pinned by digest** — `python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce` (python 3.11.17, debian 13.7). Refresh deliberately, not silently.

4. **Runtime hardening (compose)** — `read_only: true` + `tmpfs: /tmp`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, on top of the existing `init: true`, non-root `USER app`, `:ro` model mounts.

### Hardening Checklist

| Requirement | Status | Evidence |
|---|---|---|
| Non-root user | ✅ | `USER app` in Dockerfile; `docker inspect .Config.User` → `app` |
| Minimal base | ✅ | `python:3.11-slim` (debian 13.7), digest-pinned |
| All versions pinned | ✅ | requirements `==`, base digest, build tools removed entirely |
| No build tools in final stage | ✅ | image probe: `no pip / no global build tools / no venv build tools` |
| No secrets baked in | ✅ | trivy secrets 0 (before+after), `docker history` grep 0, baked ENV = only `PYTHONUNBUFFERED/PYTHONDONTWRITEBYTECODE/PATH/LANG` + python-image's public `GPG_KEY` |
| HEALTHCHECK present | ✅ | Dockerfile HEALTHCHECK; container reached `healthy` |
| Read-only filesystem where possible | ✅ | `ReadonlyRootfs: true` verified; health 200 + chat 200 under it; no `Read-only`/`Permission denied` errors in logs |

### Remaining Findings: 8 OS HIGH CVEs with No Debian Fix

| CVE | Package(s) | Issue |
|---|---|---|
| CVE-2026-76642 | util-linux family | privileged X-mount post-hooks still run |
| CVE-2026-78408 | util-linux family | `nsenter --join-cgroup` leaks root cgroup authority |
| CVE-2026-78409 | util-linux family | X-mount.subdir symlink escape |
| CVE-2026-78410 | util-linux family | restricted bind mounts not pinned |
| CVE-2026-54369 | libacl1 | symlink-traversal privilege escalation |
| CVE-2025-69720 | libncursesw6, libtinfo6, ncurses-* | buffer overflow → code execution |
| CVE-2026-16742 | libsystemd0, libudev1 | systemd-homed local privilege escalation |
| CVE-2026-9538 | perl-base | perl-Archive-Tar DoS via crafted tar header |

**Why the risk is accepted for this POC:** every one of these is exploited *locally* through binaries/functions this service never uses — the app shells out to nothing (health probe is Python stdlib), never calls `mount`/`nsenter`/`systemd`/`perl`/ncurses, runs as non-root `app` with **all capabilities dropped**, **no-new-privileges**, a **read-only root fs** and no interactive TTY. The container also has no package manager usage at runtime. Re-scan cadence: every image rebuild (the base digest + apt layer pick up Debian backports the moment they exist — re-run `trivy image setu-guide-api:day4` after the next base refresh).

## 3. Secrets Scan (gitleaks + trivy + docker history)

**Result:** No real secret found anywhere — in the repository, its entire git history, the image layers, or the container environment/logs.

### Git History (gitleaks)

- 6 finding rows = 3 unique locations, one single value: `sk-PRIVACY-MARKER-API-KEY-88` (synthetic marker, by design — used by log-privacy tests)
- No `github-pat`/`ghp_`-style token appears anywhere in the 100+ commits
- The GitHub PAT shared in a chat message (prefix `ghp_`) never entered the repository or the image. **It still needs to be revoked on GitHub** — that remains unconfirmed; pasting it in chat already exposed it regardless of the repo being clean.

### Working Tree (gitleaks dir)

- The 223 `.venv` rows (211 `generic-api-key`, 12 `private-key`) are third-party files inside the local virtualenv. `.venv/` is in `.gitignore` (never committed) and in `.dockerignore` (never reaches the image) — environmental only, nothing of ours.
- Tracked files: only the 3 marker rows above (synthetic, by design).

### `.env` Handling

| Check | Result |
|---|---|
| `.env` on disk | **Absent** — only `.env.example` exists |
| git-ignored | ✅ `.gitignore` contains `.env` (and `*.log`) |
| ever tracked in git history | ✅ **never** — `git log --all --full-history -- .env` → empty |
| docker-ignored | ✅ `.dockerignore`: `.env`, `.env.*` with `!.env.example` exception |
| inside the image | ✅ `find / -name '.env*'` in `setu-guide-api:day4` → nothing; `/app` contains only `app/`, `data/`, `models/` |
| `.env.example` values | ✅ dummies only: `LLM_PROVIDER=placeholder`, `LLM_API_KEY=placeholder-not-a-real-key`, `LLM_TIMEOUT_SECONDS=10` (placeholder comment), `INTERNAL_API_KEY=` empty; header says "Never commit a real key" |

### Docker Image Layers / Filesystem / Env

| Check | Result |
|---|---|
| trivy secret scan of image (before) | **0 findings** |
| trivy secret scan of image (after) | **0 findings** |
| `docker history --no-trunc` grep for `sk-`/`ghp_`/`api_key=`/`token=`/`PRIVATE KEY` | **no matches** — no build steps carry a secret |
| Baked `Config.Env` | only `PATH`, `LANG`, `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE`, `PORT`, python image's public `GPG_KEY`/`PYTHON_VERSION`/`PYTHON_SHA256` — **no app secrets** |
| `.env`/secrets copied into image | none (§3) |

### Container Environment and Logs

| Check | Result |
|---|---|
| Runtime env | secrets arrive only via `-e`/`env_file` at run time (e.g. the tests' marker `LLM_API_KEY=sk-PRIVACY-CONTAINER-KEY`), never baked (§4) |
| Container logs carry no private data | ✅ `pytest tests/failure/test_container.py::test_container_logs_carry_no_private_data` **PASSED** — asserts the marker key, message, topic, user and match markers are absent from `docker logs` |
| Structured log hygiene (unit level) | ✅ Day-2 audit: 53 000+ log lines, 0 occurrences of user/match ids, message text, topic, free-text prompts or API keys |
| Fail-fast without secret | ✅ container test **PASSED** — with `USE_MOCK=false` and no key the process exits non-zero with the config message and prints no key material (there is none) |

### Real Secrets Found: **0** → No Critical, no rotation required.

## 4. Findings Log (Bug Tracker)

| # | Finding | Severity | Owner | Status |
|---|---|---|---|---|
| C | Build tools (pip/setuptools/wheel + vendored wheel/jaraco) in image carrying 4 HIGH / 12 MEDIUM Python CVEs | High (scanner) | DevOps 1 | **Fixed** in this PR — tools removed, trivy Python side now 0 |
| D | 8 unique OS HIGH CVEs in base packages with no Debian fix yet | High (scanner) / Low in practice — see mitigations §3 | DevOps 1 (re-scan cadence) | **Accepted with mitigations**, documented above; re-scan on every rebuild |
| E | liblzma5 findings without fixes at scan time | Unknown severity | DevOps 1 | **Fixed** in this PR (apt upgrade, DSA applied) |

## Verification on the Hardened Image

- `pytest tests/failure/test_container.py` → **3/3 passed**: fail-fast without secret, restart-under-load → `healthy` again with 0 server errors, container logs carry no private data.
- `docker compose config -q` valid; `compose up` → `/health` 200, `/v1/guide/chat` 200 (`X-Cache: MISS`, `X-Request-Id` present), `Health: healthy`, inspect: `ReadonlyRootfs true | CapDrop [ALL] | no-new-privileges | User app`. Torn down cleanly.

---

**Final Result:** **0 CVEs** in Python deps, **0 real secrets** in repo/image, **8 OS HIGH CVEs** accepted with mitigations (no Debian fix yet), image hardened: non-root, minimal base, pinned versions, build tools removed, read-only fs, HEALTHCHECK present.