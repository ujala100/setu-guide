# Validation Review — Test Results

**Phase 2, Day 1 · DevOps Intern 1 (API service)**
**Date:** 17 October 2026 · **Base:** `dev` @ `531cb6e`

## Scope

Review of how the API handles bad input: every malformed request must come back
as a clean 4xx in the standard error contract

```json
{"error": {"code": "...", "message": "...", "details": [...]}}
```

— never a 500, never a stack trace, and the caller's input is **never echoed**
back. This is a verification task; no API behaviour was changed.

## Test suite

- Tests live in **`tests/validation/test_validation_matrix.py`**.
- The validation cases that previously lived in
  `tests/failure/test_bad_input.py` were **moved** here so there is a single
  home for input-validation checks (no duplicate suites). Failure-drill,
  privacy and container tests remain in `tests/failure/`.

## Environment

| Item | Value |
|---|---|
| Python | 3.14.7 (local; CI runs 3.11) |
| FastAPI | 0.142.2 |
| pydantic | 2.13.5 |
| pytest | 9.1.1 |
| Command | `pytest -q` and `pytest tests/validation -q` |

## Summary

| Run | Result |
|---|---|
| `tests/validation` | **31 passed** |
| Full suite | **313 passed, 3 skipped** (3 Docker tests skipped — no local image) |
| Bugs found in the API layer | **0** |

## Results table

| # | Test | Input | Expected | Actual | Pass/Fail |
|---|---|---|---|---|---|
| 1 | bad stage | `stage="teleport"` | 422 `invalid_request` | 422, `details=["stage: enum"]` | PASS |
| 2 | bad intent | `intent="make_me_rich"` | 422 `invalid_request` | 422, `details=["intent: enum"]` | PASS |
| 3 | missing user_id | body without `user_id` | 422 `invalid_request` | 422, `details=["user_id: missing"]` | PASS |
| 4 | missing match_id | body without `match_id` | 422 `invalid_request` | 422, `details=["match_id: missing"]` | PASS |
| 5 | neither intent nor message | only ids + stage | 422 `invalid_request` | 422, `details=["value_error"]` | PASS |
| 6 | empty JSON object | `{}` | 422 `invalid_request` | 422, `details=["user_id: missing","match_id: missing","stage: missing"]` | PASS |
| 7 | whitespace-only message | `message="   "` | 422 `invalid_request` | 422, `details=["value_error"]` | PASS |
| 8 | empty body | `""` | 422 `invalid_request` | 422, `details=["missing"]` | PASS |
| 9 | null body | literal `null` | 422 `invalid_request` | 422, `details=["missing"]` | PASS |
| 10 | wrong type user_id | `user_id=12345` | 422 `invalid_request` | 422, `details=["user_id: string_type"]` | PASS |
| 11 | wrong type match_id | `match_id=999` | 422 `invalid_request` | 422, `details=["match_id: string_type"]` | PASS |
| 12 | wrong type stage | `stage=7` | 422 `invalid_request` | 422, `details=["stage: enum"]` | PASS |
| 13 | wrong type intent | `intent=["next_steps"]` | 422 `invalid_request` | 422, `details=["intent: enum"]` | PASS |
| 14 | null values | all fields `null` | 422 `invalid_request` | 422, `details=["user_id: string_type"]` | PASS |
| 15 | message over 500 chars | `message="x"*501` | 422 `invalid_request` | 422, `details=["message: string_too_long"]` | PASS |
| 16 | topic over 100 chars | `topic="x"*101` | 422 `invalid_request` | 422, `details=["topic: string_too_long"]` | PASS |
| 17 | very large body (~1 MB) | `message` = 1,000,000 chars | 422 `invalid_request` | 422, `details=["message: string_too_long"]` | PASS |
| 18 | malformed JSON | `{"user_id": ` (truncated) | 422 `invalid_request` | 422, `details=["json_invalid"]` | PASS |
| 19 | wrong Content-Type | `text/plain` with JSON body | 422 `invalid_request` | 422, `details=["model_attributes_type"]` | PASS |
| 20 | wrong HTTP method | `GET`/`DELETE /v1/guide/chat` | 405 `method_not_allowed` | 405, `details=[]` | PASS |
| 21 | unknown route | `GET /nope/such/path`, `POST /v1/guide/unknown` | 404 `not_found` | 404, `details=[]` | PASS |
| 22 | unicode / emoji / Hindi / RTL | Hindi text, emoji-only, RTL, zero-width | 200, valid reply, no crash | 200, valid reply, `fallback_used=false` | PASS |
| 23 | message exactly 500 chars (boundary) | `message="a"*500` | 200 accepted | 200 | PASS |
| 24 | message 501 chars (boundary) | `message="a"*501` | 422 | 422, `details=["message: string_too_long"]` | PASS |
| 25 | topic exactly 100 chars (boundary) | `topic="t"*100` | 200 accepted | 200 | PASS |
| 26 | newlines / tabs in message | `"line one\nline two\tend 🙂"` | 200 accepted | 200 | PASS |

### Format checks (asserted on every error response)

- Top-level body has exactly one key: `error`.
- `error` has exactly `code`, `message`, `details`.
- `Content-Type: application/json` and an `X-Request-Id` header are present.
- No `Traceback` text and no echo of the caller's input (canary value) anywhere.

## Other status codes

The validation inputs above cover 422 / 404 / 405. The remaining statuses are
proven by existing tests:

- **429** (`rate_limited` + `Retry-After`) — `tests/test_day2_rate_limit.py`
  and `tests/failure/test_log_privacy.py`.
- **500** (`internal_error`, empty details, no traceback) —
  `tests/failure/test_llm_failures.py::test_unexpected_exception_is_500_without_internal_details`.

## Bugs

**No bugs were found in the API layer.** Every bad input returned a clean 4xx in
the standard error format; no 500, no stack trace, no input echo. Two new cases
were added beyond the previous suite (`null` body and whitespace-only message)
and both behave correctly.

## How to reproduce

```bash
pip install -r requirements-dev.txt
pytest tests/validation -q     # 31 passed
pytest -q                      # full suite: 313 passed, 3 skipped
```
