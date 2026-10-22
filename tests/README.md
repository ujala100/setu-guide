# Load and failure tests (owner: DevOps 1)

Two suites live here:

| Folder        | Tool               | Needs a server?        |
|---------------|--------------------|------------------------|
| `tests/failure/` | pytest + httpx  | no (TestClient), except `test_container.py` |
| `tests/load/`    | Locust          | yes (container on :8000) |
| `tests/ratelimit/` | pytest        | no (TestClient) |
| `tests/cache/`    | pytest        | no (TestClient) |
| `tests/recovery/` | pytest        | yes (container, Docker required) |
| `tests/integration/` | pytest     | no (TestClient) |

Setup (once):

```bash
pip install -r requirements-dev.txt      # pytest, httpx, locust (all pinned)
```

---

## 1. Failure tests

```bash
python -m pytest tests/failure -q
```

`test_container.py` needs Docker **and** the image:

```bash
docker build -t setu-guide-api:day3 -f docker/Dockerfile .
python -m pytest tests/failure/test_container.py -q
```

Without them the file skips itself (CI stays green without a built image).
Overrides: `SETU_TEST_IMAGE`, `SETU_TEST_PORT` (default 8010), `DOCKER_EXE`.

The whole suite (Day 1 + Day 2 + Day 3) is just `python -m pytest -q`.

### Day 2 provider drills

`test_provider_drills.py` covers the Day 2 drill set (LLM down / connection
refused, LLM slow / beyond `LLM_TIMEOUT_SECONDS`, provider 429, and garbage
replies: empty, whitespace, invalid JSON, wrong schema). Every drill asserts the
same contract: HTTP 200, template reply, `fallback_used=true`,
`safety.status="pass"`, `flags=[]`, never a 500, fallback never cached.

```bash
python -m pytest tests/failure/test_provider_drills.py -q   # 7 drills
python -m pytest tests/failure -q                           # all failure tests
```

The Day 3 file `test_llm_failures.py` keeps its original coverage (timeout,
invalid JSON/schema, wrong type, fallback-not-cached, recovery, 500); the two
files do not duplicate a case. Results:
[`docs/failure_drill_results.md`](../docs/failure_drill_results.md).

---

## 2. Load tests (Locust)

**Never** point a load run at a real LLM provider (free-tier quota): the
main runs below use `USE_MOCK=true`. All knobs are placeholders at the top of
`tests/load/common.py` (`TARGET_URL`, `LOAD_USERS=20`,
`RAMP_UP_SECONDS=30`, `DURATION=5m`).

### Start a container for the scenario

Rate limits are raised **for these runs only** so the limiter does not distort
the latency numbers (Scenario C lowers them again on purpose):

```bash
docker rm -f setu-day3-load 2>/dev/null
docker run -d --name setu-day3-load -p 8000:8000 \
  -e USE_MOCK=true \
  -e RATE_LIMIT_PER_USER=100000/minute \
  -e RATE_LIMIT_PER_IP=100000/minute \
  setu-guide-api:day3
```

### Run a scenario

```bash
# Scenario D - /health under load (start the container with DEFAULT limits
# first, so the "never rate limited" claim is meaningful):
docker rm -f setu-day3-load && docker run -d --name setu-day3-load -p 8000:8000 \
  -e USE_MOCK=true setu-guide-api:day3
locust -f tests/load/scenario_d.py --headless \
  -u 20 -r 0.67 -t 60s --csv tests/load/results/d_health

# Scenario A - mixed traffic (the profile from the brief: 20 users, 5 min, 30 s ramp)
locust -f tests/load/scenario_a.py --headless \
  -u 20 -r 0.67 -t 5m --csv tests/load/results/a_mixed

# Scenario B - cache HIT vs MISS
locust -f tests/load/scenario_b.py --headless \
  -u 20 -r 4 -t 60s --csv tests/load/results/b_cache

# Scenario C - rate limit (restart the container with the user limit back at
# the default 30/minute and only the IP limit raised):
docker rm -f setu-day3-load && docker run -d --name setu-day3-load -p 8000:8000 \
  -e USE_MOCK=true -e RATE_LIMIT_PER_USER=30/minute \
  -e RATE_LIMIT_PER_IP=100000/minute setu-guide-api:day3
locust -f tests/load/scenario_c.py --headless \
  -u 6 -r 1 -t 90s --csv tests/load/results/c_ratelimit
```

### Day 2 load runs (same Scenario A traffic, three profiles)

Placeholders live at the top of `tests/load/common.py` (`TARGET_URL`,
`LOAD_USERS`, `RAMP_UP_SECONDS`, `DURATION`). Each run keeps its own `--csv`
prefix so the raw numbers stay separate under `tests/load/results/`:

```bash
# Run 1 - 20 users
locust -f tests/load/scenario_a.py --headless \
  -u 20 -r 1.0 -t 2m --csv tests/load/results/day2_20u --only-summary

# Run 2 - 50 users
locust -f tests/load/scenario_a.py --headless \
  -u 50 -r 2.0 -t 2m --csv tests/load/results/day2_50u --only-summary

# Run 3 - 10-minute sustained (20 users)
locust -f tests/load/scenario_a.py --headless \
  -u 20 -r 0.5 -t 10m --csv tests/load/results/day2_10min --only-summary
```

Pass criteria (placeholders until the lead confirms): 5xx error rate < 1 %,
p95 < 2 s with mock/cached replies (< 12 s with the real LLM).

Small **real-mode** run (5 users, 1 min) - `USE_MOCK=false` goes through the
LLM safety net; no provider key is used and no provider is contacted:

```bash
docker rm -f setu-day3-load && docker run -d --name setu-day3-load -p 8000:8000 \
  -e USE_MOCK=false -e LLM_API_KEY=placeholder-not-a-real-key \
  -e RATE_LIMIT_PER_USER=100000/minute -e RATE_LIMIT_PER_IP=100000/minute \
  setu-guide-api:day3
locust -f tests/load/scenario_a.py --headless \
  -u 5 -r 1 -t 60s --csv tests/load/results/real_small
```

### Record while a run is active

- **Container CPU/memory** - start the sampler before locust, stop it after.
  Use **absolute paths** (a `Start-Job` runs in its own working directory, so a
  relative `--csv` path silently writes nowhere):

  ```powershell
  Start-Job -FilePath "$PWD\tests\load\collect_docker_stats.ps1" -ArgumentList `
      "setu-day3-load", "$PWD\tests\load\results\a_docker_stats.csv"
  # ... locust ...
  Get-Job | Stop-Job; Remove-Job $job -Force
  ```

- **Cache hit ratio + 429 count** - from the container's own access log for
  the run window:

  ```bash
  docker logs --since <run-start-rfc3339> setu-day3-load | grep -c '"cache": "HIT"'
  docker logs --since <run-start-rfc3339> setu-day3-load | grep -c '"cache": "MISS"'
  docker logs --since <run-start-rfc3339> setu-day3-load | grep -c 'rate_limited scope='
  ```

- **p50/p95/p99, RPS, failures** - from `<name>_stats.csv` and
  `<name>_failures.csv` that locust writes into `tests/load/results/`.

### Log hygiene check after a run

```bash
docker logs setu-day3-load | grep -E 'load_user_|load_match_|How do I start'   # must print nothing
```

---

## 3. Day 3 review suites (rate limit + cache isolation)

`tests/ratelimit/test_rate_limit_review.py` (9 tests) pins the rate-limit
audit: N+1 behaviour per user and per IP with `Retry-After`, isolation between
users, `/health` never limited, the bypass attempts (forged
`X-Forwarded-For` with `TRUSTED_PROXY=false`, rotating `user_id`s,
`user_id` case/whitespace variants), a 200-request burst staying up, and the
limiter's memory staying bounded. `tests/cache/test_cache_isolation.py`
(13 tests) proves two users can never receive each other's cached reply: the
fake orchestrator encodes the request into the reply, so isolation is asserted
on **response bodies**, not just call counts, plus the never-cached set
(free text, 500s, fallback, safety modified/blocked, flags) and
`CACHE_ENABLED=false`.

```bash
python -m pytest tests/ratelimit tests/cache -q     # 22 tests, TestClient only
```

Both suites reset counters/cache between tests (autouse fixture) and use
synthetic ids only. Results and the two fixed gaps:
[`docs/rate_limit_check.md`](../docs/rate_limit_check.md),
[`docs/cache_isolation_test.md`](../docs/cache_isolation_test.md).

### Day 3 security scans (report: docs/security_scan_report.md)

```bash
pip install pip-audit
pip-audit -r requirements.txt                        # Python dependencies
trivy image --scanners vuln,secret setu-guide-api:day3   # image CVEs + secrets
gitleaks git . -f json -r history.json --redact      # full git history
gitleaks dir . -f json -r worktree.json --redact     # files on disk (filter .venv/)
```

---

## 4. Day 4 suites (recovery + integration + auth)

### Recovery: timeouts, graceful shutdown, restart (Docker required)

`tests/recovery/test_timeouts_shutdown.py` (8 tests) runs against a real
container, because a TestClient cannot show a SIGTERM drain:

```bash
docker build -t setu-guide-api:day3 -f docker/Dockerfile .
python -m pytest tests/recovery -q
```

It covers the LLM timeout budget (the fallback answer, never a hang), a
request inside the budget (a real reply, not the fallback), one and three
concurrent in-flight requests surviving `docker stop`, the idle keep-alive
connection being released, `docker restart` under load recovering on its
own, and the API key being enforced in a real container (`AUTH_METHOD=api_key`
-> 401 without the key, 200 with it, `/health` open, the key absent from the
logs). Two of the tests are config guards: they fail if the image CMD loses
`--timeout-graceful-shutdown` / `--timeout-keep-alive`, or if
`stop_grace_period` in `docker-compose.yml` stops being larger than the
graceful window. Without Docker or the image the file skips itself. Overrides:
`SETU_TEST_IMAGE` (default `setu-guide-api:day3`), `SETU_TEST_PORT` (default
8011), `DOCKER_EXE`.

The suite runs the image with a mounted launcher
(`tests/recovery/slow_orchestrator.py`) that installs a slow
`app.core.orchestrator.handle_chat` - the real-mode entry does not exist yet
(lead follow-up, issue #15), so without it a request would fall back
instantly and never stay in flight. **No file under `app/core` is modified.**

### Integration: the contract a backend codes against

`tests/integration/test_contract.py` (20 tests, TestClient only) pins what an
external backend needs: the full response field set, the shared error
envelope for 401 / 422 / 429 / 500 / 404, `Retry-After` as an integer number of
seconds on 429, `fallback_used` as a 200 (not an error), `X-Request-Id` on
every status including 500, a latency budget, and the **frozen request
schema** (all 8 stage values, the 4 intent values, the field names and the
length limits).

```bash
python -m pytest tests/integration -q
```

### Auth: the API key the lead asked for

`tests/integration/test_auth.py` (25 tests, TestClient only) covers the
inbound authentication added on Day 4:

- the default (`AUTH_METHOD=none`) changes nothing - every other suite still
  works;
- `api_key` mode: the right key works, a missing / wrong / truncated / empty
  key is a 401 with the standard envelope, and the `Authorization` header is
  not accepted;
- `bearer` mode: `Bearer <token>` works, a wrong scheme / token is a 401, the
  response carries `WWW-Authenticate: Bearer`, and `X-API-Key` is not
  accepted - switching method is a configuration change, so only one
  credential may work at a time;
- `/health` never needs a credential (the container `HEALTHCHECK` calls it);
- startup fails fast when a method is on but no key is set, and the
  placeholder value from `.env.example` is refused as a live credential;
- the key never appears in a response body, a header, a log line or the
  settings `repr`, and `.env.example` holds only a placeholder.

```bash
python -m pytest tests/integration -q
```

Results and the handover notes for the backend engineer and DevOps 2:
[`docs/recovery_test_notes.md`](../docs/recovery_test_notes.md),
[`docs/integration_check.md`](../docs/integration_check.md).

---

## 5. Results

Filled-in numbers, bug list and known limits: see

- [`docs/load_test_report.md`](../docs/load_test_report.md) - Day 2 load runs
  (20 users, 50 users, 10-minute sustained) with real numbers.
- [`docs/failure_drill_results.md`](../docs/failure_drill_results.md) - Day 2
  failure drills (Drill / Setup / Expected / Actual / Pass-Fail).
- [`docs/rate_limit_check.md`](../docs/rate_limit_check.md) - Day 3 rate-limit
  review (checklist, 2 gaps found and fixed).
- [`docs/cache_isolation_test.md`](../docs/cache_isolation_test.md) - Day 3
  cache isolation (cross-user check: none found).
- [`docs/security_scan_report.md`](../docs/security_scan_report.md) - Day 3
  dependency/image scan with before-after findings and hardening checklist.
- [`docs/secrets_scan_result.md`](../docs/secrets_scan_result.md) - Day 3
  secrets scan of repo, git history, image layers and container logs.
- [`docs/load_and_failure_test_notes.md`](../docs/load_and_failure_test_notes.md) -
  the earlier Day 3 scenarios (A-D) and their numbers.
- [`docs/recovery_test_notes.md`](../docs/recovery_test_notes.md) - Day 4
  timeout, graceful-shutdown and restart scenarios (Scenario / Steps /
  Expected / Actual / Recovery time / Pass-Fail) and the SIGKILL finding.
- [`docs/integration_check.md`](../docs/integration_check.md) - Day 4 contract
  check for the backend team: schemas, error codes, timings, the API-key
  authentication and the open questions.
