# Load and failure tests (owner: DevOps 1)

Two suites live here:

| Folder        | Tool               | Needs a server?        |
|---------------|--------------------|------------------------|
| `tests/failure/` | pytest + httpx  | no (TestClient), except `test_container.py` |
| `tests/load/`    | Locust          | yes (container on :8000) |

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

## 3. Results

Filled-in numbers, bug list and known limits: see

- [`docs/load_test_report.md`](../docs/load_test_report.md) - Day 2 load runs
  (20 users, 50 users, 10-minute sustained) with real numbers.
- [`docs/failure_drill_results.md`](../docs/failure_drill_results.md) - Day 2
  failure drills (Drill / Setup / Expected / Actual / Pass-Fail).
- [`docs/load_and_failure_test_notes.md`](../docs/load_and_failure_test_notes.md) -
  the earlier Day 3 scenarios (A-D) and their numbers.
