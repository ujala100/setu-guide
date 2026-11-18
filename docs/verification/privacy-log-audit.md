# Privacy log audit procedure

Owner: DevOps 2. Purpose: a repeatable check that the service never writes
private data or secrets to its logs, so a leak is caught before release rather
than by luck. Companion to `bug-tracker.csv`: if an audit finds a leak, file it
as a bug there.

This is a documentation/procedure change only. It does not alter code, CI or
configuration.

## 1. What is allowed in logs

The service emits one structured access line per request on logger `setu.guide`
(`app/api/main.py:121-130`). Allowed fields (`app/api/main.py:121-130` and
`app/api/chat.py:94-99`):

| Field | Always | Source |
|---|---|---|
| `request_id` | yes | `main.py:123` (== response `X-Request-Id`) |
| `method` | yes | `main.py:124` |
| `path` | yes | `main.py:125` (`request.url.path` only) |
| `status` | yes | `main.py:126` |
| `latency_ms` | yes | `main.py:127` |
| `cache` | chat only | `chat.py:95` |
| `intent` | chat only | `chat.py:96` (response intent) |
| `stage` | chat only | `chat.py:97` (enum value) |
| `fallback_used` | chat only | `chat.py:98` |

Other permitted lines (no user data):

- `rate_limited scope=user|ip retry_after=N` - scope only, never the id
  (`app/api/chat.py:58`).
- `orchestrator_failed mode=real type=<ExcName> fallback_used=true` - exception
  type only (`app/api/chat.py:87`).
- `unhandled <ExcName> -> 500 internal_error` + traceback frames; `str(exc)` is
  never sent to the log (`app/api/main.py:95-97`).
- `llm_failed type=...` / `generation_failed type=...` (`app/core/orchestrator.py:205,246`).

Log format is `%(asctime)s %(levelname)s %(name)s %(message)s`
(`app/api/main.py:25-27`).

## 2. What must NEVER appear

`message`, `topic`, `user_id`, `match_id`, `context` (any nested PII), request
body/query string, and any API key (`LLM_API_KEY`, `INTERNAL_API_KEY`). Defined
in `docs/api.md` section 18 and asserted by `tests/failure/test_log_privacy.py`.

## 3. Sentinel technique

Send values that are meaningless to a user but greppable, then prove they are
absent from logs. Reuse the markers already in `tests/failure/test_log_privacy.py:13-21`:

```
message   = PRIVACY-MARKER-MESSAGE private thoughts about my match
topic     = PRIVACY-MARKER-TOPIC
user_id   = privacy-marker-user-77
match_id  = privacy-marker-match-77
LLM_API_KEY = sk-PRIVACY-MARKER-API-KEY-88
```

Never substitute real user data, phone numbers or a genuine key.

## 4. Automated audit (every PR / CI)

Runs as part of the normal suite; no separate CI change is needed.

```bash
python -m pytest tests/failure/test_log_privacy.py -q
```

`test_no_private_data_in_logs_from_any_path` drives 200, 422, 404, 429 and 500
in one process (`test_log_privacy.py:36-61`) so "no leak" is not an accident of
a path that did not run, then asserts none of the markers is in `caplog`
(`test_log_privacy.py:63-67`). `test_response_bodies_never_carry_the_api_key`
covers the response path (`:70-77`).

Pass = the whole file green. Any failure is a Critical/High bug: see section 7.

Provider failure paths are covered separately by
`tests/failure/test_llm_provider_log_privacy.py` (see section 10):

```bash
python -m pytest tests/failure/test_llm_provider_log_privacy.py -q
```

## 5. Manual / container audit

For a built image or a running container (`docker/Dockerfile`):

```bash
docker build -t setu-guide-api:audit -f docker/Dockerfile .
docker run -d --name setu-privacy-audit -p 8000:8000 \
  -e USE_MOCK=true -e LLM_API_KEY=sk-PRIVACY-MARKER-API-KEY-88 \
  -e RATE_LIMIT_PER_USER=100000/minute setu-guide-api:audit

# 1. Drive every status path with sentinel payloads (same values as section 3).
curl -s localhost:8000/health
curl -s -X POST localhost:8000/v1/guide/chat -H 'content-type: application/json' \
  -d '{"user_id":"privacy-marker-user-77","match_id":"privacy-marker-match-77","stage":"family","message":"PRIVACY-MARKER-MESSAGE","topic":"PRIVACY-MARKER-TOPIC"}'
curl -s -X POST localhost:8000/v1/guide/chat -H 'content-type: application/json' \
  -d '{"user_id":"privacy-marker-user-77","match_id":"privacy-marker-match-77","stage":"nope","topic":"PRIVACY-MARKER-TOPIC"}'
curl -s localhost:8000/does-not-exist

# 2. Grep the container logs for every marker - ALL must print nothing.
docker logs setu-privacy-audit | grep -E \
  'PRIVACY-MARKER|privacy-marker-user|privacy-marker-match|sk-PRIVACY'
# expected: empty

# 3. Positive control - the allowed fields MUST be present, proving logging ran.
docker logs setu-privacy-audit | grep -c http_request
```

If the access log ever contains the path or query string, grep for the URL of a
chat request: `docker logs setu-privacy-audit | grep 'v1/guide/chat?'` must be
empty (only `path` is logged, not the query string - `main.py:125`).

## 6. Staging audit

Run the same sentinel sequence against the staging base URL (`docs/api.md`
section 22) with synthetic ids only. Then verify the platform's log viewer (and
any shipping sink) shows the same greps returning nothing. Record the date, the
`request_id`s used, and the greps run in the audit record (section 8).

Because staging is remote and logs may be sampled, treat "marker absent" as the
only acceptable result; if logs are unavailable, mark the check "Not verified"
rather than "Pass".

## 7. Filing a leak found by the audit

Add a row to `docs/verification/bug-tracker.csv` (see its README):

- `Severity` = Critical (private data or key in logs) or High (message/topic/id).
- `Component` = API (or CI/CD if the leak is in the pipeline).
- `Steps to Reproduce` = the sentinel request + the grep that matched.
- `Evidence / File Reference` = the matching log line, with the secret
  redacted; reference the marker name, not the value.
- Never paste a real key or real user data into the tracker.

## 8. Audit record

Log every run so the evidence is auditable. One line per run:

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Auditor | name |
| Target | local container / staging URL |
| Suite | `pytest tests/failure/test_log_privacy.py` = pass/fail |
| Greps | markers absent = yes/no |
| Result | Pass / Fail / Not verified |
| Bug ID | `BUG-...` if anything was filed |

Store records under `docs/verification/` (or paste into the PR description).

## 9. Sign-off checklist

- [ ] `pytest tests/failure/test_log_privacy.py -q` passes.
- [ ] Container audit: all sentinel greps empty; `http_request` lines present.
- [ ] Staging audit (if applicable) with synthetic data only.
- [ ] No secrets in any report, screenshot or bug row.
- [ ] Any finding filed in `bug-tracker.csv` with severity and owner.
- [ ] `LOG_LEVEL` never raised above `INFO` in shared environments.

## 10. D2-24 follow-up: provider failure paths

Audited the two places that handled a failing LLM provider with `print(...)`.
Both wrote the exception text to stdout, and provider errors can echo the
prompt, so they were a leak path that the request-path test above did not
exercise.

| File | Before | After |
|---|---|---|
| `app/core/llm_provider.py` | `print(f"Gemini provider unavailable: {error}")` and three similar prints | `logger.warning("gemini_request_failed type=%s", type(error).__name__)` and `gemini_output_failed`, `gemini_invalid_json`, `gemini_request_interrupted` |
| `app/core/pipeline.py` (`run_pipeline`) | `print(f"LLM provider failed: {error}")` | `logger.warning("llm_provider_failed type=%s", type(error).__name__)` |

New test `tests/failure/test_llm_provider_log_privacy.py`:

1. Makes the Gemini provider raise an error containing a sentinel and asserts
   the sentinel is absent from `caplog`, stdout and stderr.
2. Makes `run_pipeline`'s provider lookup fail the same way, asserts the same,
   and asserts the template fallback still answers.
3. Asserts the `type=<ExcName>` line is present, so the test cannot pass
   because nothing was logged.

The `print(...)` calls inside `if __name__ == "__main__"` blocks are developer
demos and do not run while serving a request.

