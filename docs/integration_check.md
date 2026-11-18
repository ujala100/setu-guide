# Integration check - Setu Guide API x backend (contract only)

**Date:** 2026-10-22 · **Owner:** DevOps 1 (`app/api/`) · **Branch:** `feature/phase2-day4-recovery-integration`
**Suites:** `tests/integration/test_contract.py` (20 tests) + `tests/integration/test_auth.py` (25 tests) · **Result: 45/45 PASS**

Audience: the new backend engineer (Shreya has left the team; a new software
engineer is reviewing the existing backend) and DevOps 2 (Postman collection
and docs).

> **Status change since the last version of this document.** The lead has
> confirmed that the backend integration has **not started**, so this document
> covers **our API contract only**. No test was run against the backend side,
> and none is planned until the backend exists. The end-to-end path
> "backend -> Setu Guide" is therefore **not verified** and is not claimed to be.

## What was tested, and what was not

**Verified here (local hardened container `setu-guide-api:day3`, real HTTP):**

- request/response schema
- error format and status codes (404 / 405 / 422 / 429 / 500 / 401)
- `Retry-After` semantics on 429
- `fallback_used` semantics
- timeout behaviour (bounded latency, fallback instead of a hang)
- response times
- `X-Request-Id` tracing
- cache behaviour
- inbound authentication (both supported methods)

**Not verified here, and why:**

| Not verified | Why |
|--------------|-----|
| The backend's own behaviour (retry policy, how it handles 429 / 422 / `fallback_used`) | the backend integration has not started - the lead confirmed this |
| Staging | **no staging endpoint has been confirmed by the lead** - see the staging section below |
| Authentication against a real issued credential | nobody issues the credential yet - see **Open items** |
| Real-LLM latency | `app.core.orchestrator.handle_chat` does not exist yet (lead-owned `app/core`, issue #15) |

## Backend-side assumptions (confirmed by the lead, 2026-10-22)

These are the lead's instructions for the backend side. The API side already
satisfies all four.

| # | Assumption (lead) | What the API does | Where it is verified |
|---|-------------------|-------------------|----------------------|
| 1 | **429:** the client must honour `Retry-After` | the API **always** sends `Retry-After` with a whole number of seconds on every 429 | `tests/integration/test_contract.py::test_429_carries_retry_after_as_an_integer` |
| 2 | **`fallback_used=true`:** the reply is still valid and must be shown normally; the client should log it as a metric | a fallback is returned as **HTTP 200** with a complete, safe reply body - it is **not** an error and must not be retried | `tests/integration/test_contract.py::test_fallback_answer_is_a_normal_200` |
| 3 | **422:** the frozen schema is the source of truth; whichever side deviates fixes its own code; schema changes go only through the lead | the request schema in `app/schemas/guide.py` is unchanged since Day 1; a 422 names the offending **field**, never the value | `tests/integration/test_contract.py::test_request_schema_is_unchanged`, `::test_422_uses_the_shared_error_envelope` |
| 4 | **Shared test window:** not available yet - load and restart tests run locally, a staging window is scheduled later | the load, timeout and restart-under-load runs were done against the local hardened container | `docs/recovery_test_notes.md`, scenarios 1-6 |

**For the backend engineer, in one line each:**

- **429** -> read `Retry-After` (seconds), wait that long, retry. A fixed
  backoff works but ignores the server's own hint.
- **`fallback_used: true`** -> show the reply to the user as a normal answer,
  and count it as a metric (for example a counter of fallback replies). Do not
  retry it and do not surface it as an error.
- **422** -> the field names in `details` are the only usable signal; the
  rejected value is never returned, so keep the original payload on your side.
- **Schema** -> frozen. If the backend needs a field that is not in the schema,
  it goes through the lead, not through a code change on either side.

## Authentication (implemented on Day 4, per the lead's instruction)

The lead asked for an API key in a header, read from the environment and never
committed, with the method configurable so it can be switched to Bearer later.
That is implemented and tested (25 unit tests + 1 container test).

| `AUTH_METHOD` | Credential the caller sends | Status |
|---------------|-----------------------------|--------|
| `none` (default) | none - the endpoint stays open | unchanged behaviour, nothing breaks |
| `api_key` | `X-API-Key: <key>` | the lead's working choice |
| `bearer` | `Authorization: Bearer <token>` | switchable, no code change |

| Setting | Required | Notes |
|---------|----------|-------|
| `AUTH_METHOD` | no | `none` / `api_key` / `bearer` |
| `API_KEY` | yes when the method is not `none` | secret from the environment; **never committed**; startup fails fast without it, and the placeholder value from `.env.example` is refused as a live credential |

Rules the backend can rely on:

- a missing key and a wrong key give the **same** `401` - the endpoint cannot
  be used to probe which keys exist;
- the 401 body is the standard envelope, `code = "unauthorized"`, `details: []`,
  and `X-Request-Id` is present, so a 401 is traceable like any other status;
- the key is compared in constant time and never appears in a response, a
  header or a log line;
- `GET /health` **stays open** - the container `HEALTHCHECK` and the
  load-balancer probe call it without a credential;
- in `bearer` mode the response carries `WWW-Authenticate: Bearer`;
- the method is strict - in `bearer` mode `X-API-Key` is rejected, so only one
  credential works at a time.

**Rollout status:** the code is done and tested (23 unit tests + 1 container
test), but the **default is still `none`** so nothing breaks for anyone
pointing at the current deployment. Turning it on needs the lead to confirm
the final method and who issues the credential.

## Staging - [PLACEHOLDER]

**The lead has not confirmed a staging endpoint** ("treat staging as not
ready"). No staging base URL, no access method, no deploy owner and no shared
test window exist yet. Every staging number in this document is therefore a
**placeholder**, and no staging result is claimed as verified.

| # | Check | Staging result | Verdict |
|---|-------|----------------|---------|
| 1 | `GET /health` | [PLACEHOLDER] | [PLACEHOLDER] |
| 2 | `POST /v1/guide/chat` happy path | [PLACEHOLDER] | [PLACEHOLDER] |
| 3 | Cache `MISS` -> `HIT` | [PLACEHOLDER] | [PLACEHOLDER] |
| 4 | 422 envelope | [PLACEHOLDER] | [PLACEHOLDER] |
| 5 | 404 envelope | [PLACEHOLDER] | [PLACEHOLDER] |
| 6 | `X-Request-Id` echo | [PLACEHOLDER] | [PLACEHOLDER] |
| 7 | 429 + `Retry-After` | [PLACEHOLDER] | [PLACEHOLDER] |
| 8 | Per-user isolation | [PLACEHOLDER] | [PLACEHOLDER] |
| 9 | Latency p50 / p95 | [PLACEHOLDER] | [PLACEHOLDER] |
| 10 | Mock mode confirmed | [PLACEHOLDER] | [PLACEHOLDER] |
| 11 | Day 3 fix A present | [PLACEHOLDER] | [PLACEHOLDER] |

Still needed from the lead / DevOps 2, and tracked as open items below:

- [PLACEHOLDER] staging base URL
- [PLACEHOLDER] who deploys (the lead says DevOps 2 via CI) and who may
  restart the service during a test window
- [PLACEHOLDER] access method (VPN or allowlist)
- [PLACEHOLDER] image tag deployed on staging - the Day 3 and Day 4 fixes are
  both still un-deployed
- [PLACEHOLDER] a shared test window for the load and restart runs

### Note for the lead - an unconfirmed public endpoint was reachable

While looking for the staging URL, one was found in the Postman collection
description (`docs/postman/Setu-Guide.postman_collection.json`):
`https://setu-guide.onrender.com` - a Render deployment behind Cloudflare. On
2026-10-21 it was reachable from this machine and answered the same contract
(happy path, 422, 404, 429 with `Retry-After`, per-user isolation, `X-Cache`
MISS/HIT, `X-Request-Id` echo).

It is **not** treated as staging here, because the lead has not confirmed it.
Two things need a decision (both are open items below):

1. **If it is ours**, it is currently **public and unauthenticated**, and it
   runs a build without the Day 3 rate-limit fix, so a `user_id` case or
   whitespace variant still gets a fresh quota (a quota-abuse vector, not a
   data leak - the buckets still separate by user). It needs the Day 3 + Day 4
   fixes deployed and the API key switched on.
2. **If it is not ours**, it should be taken down or firewalled.

The probe was read-only (no data written, synthetic ids only).

## Endpoints

| Method | Path | Purpose | Rate limited | Cache | Auth |
|--------|------|---------|--------------|-------|------|
| POST | `/v1/guide/chat` | the guide answer | yes (per user + per IP) | yes (`X-Cache: HIT`/`MISS`) | yes, when `AUTH_METHOD` is not `none` |
| GET | `/health` | liveness probe | **no** | no | **no** (always open) |

`POST /v1/guide/chat` is a **synchronous** endpoint: one request, one answer.
There is no streaming and no webhook.

## Request schema

```json
{
  "user_id": "u123",
  "match_id": "m456",
  "stage": "connect",
  "intent": "next_steps",
  "message": "optional free text",
  "topic": "optional short topic",
  "context": {}
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_id` | string | **yes** | Your user id. Rate-limit bucket and cache key are derived from it (normalised: trimmed, case-folded). |
| `match_id` | string | **yes** | The pair id. |
| `stage` | enum | **yes** | `connect`, `understand`, `reflect`, `discuss`, `agree`, `family`, `reflect_again`, `decision` - **all 8 values** (`docs/api.md` §7) |
| `intent` | enum | no | `conversation_ideas`, `help_me_understand`, `next_steps`, `privacy_safety` |
| `message` | string | no | Free text, **max 500 characters**. Either `intent` or `message` must be present. |
| `topic` | string | no | **max 100 characters**. |
| `context` | object | no | Extra context. Only consented fields reach retrieval; the rest are dropped. |

The schema is **frozen** (assumption 3 above): it has not changed since Day 1.

## Response schema (200)

```json
{
  "intent": "next_steps",
  "reply": "....",
  "questions": [],
  "chips": ["Conversation ideas", "Help me understand", "Privacy & safety"],
  "sources": ["KB-CONNECT-005", "KB-CONNECT-006"],
  "safety": { "status": "pass", "flags": [] },
  "fallback_used": false
}
```

| Field | Type | Notes |
|-------|------|-------|
| `intent` | enum string | the intent that was answered |
| `reply` | string | the answer, safe to show to the user |
| `questions` | list of string | up to 5 follow-up questions |
| `chips` | list of string | up to 4 quick actions |
| `sources` | list of string | knowledge-base ids, safe to display |
| `safety` | object | `status` is `pass`, `modified` or `blocked`; `flags` is a list |
| `fallback_used` | bool | **true means this is the safe fallback answer, not a real one** |

**`fallback_used` is the flag to branch on.** It is `true` when the service
could not reach a real answer (provider error or the LLM budget running out).
The HTTP status is still **200** - a fallback is not an error, and a client
must not retry it as one. Per the lead's instruction: show the reply normally
and **log it as a metric**.

## Error format (every non-2xx)

Identical shape for 401, 404, 405, 422, 429 and 500 - one parser is enough:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Request did not match the schema.",
    "details": ["stage: enum"]
  }
}
```

`code` is a stable machine-readable string; `message` is a fixed English
string (never built from caller input); `details` is a list of
`<schema field>: <pydantic error type>` strings. **The rejected value is never
echoed back**, so error logs cannot leak user text.

| Status | `code` | When | Notes |
|--------|--------|------|-------|
| 401 | `unauthorized` | credential missing or wrong (only when auth is on) | same answer for a missing and a wrong key |
| 422 | `invalid_request` | body does not match the schema | `details` names the field, not the value |
| 429 | `rate_limited` | per-user or per-IP quota reached | **`Retry-After` header is set** (whole seconds) |
| 500 | `internal_error` | unexpected server-side failure | body never contains internal detail |
| 404 | `not_found` | unknown route | |
| 405 | `method_not_allowed` | wrong verb on the route | |

## What the caller must do with each case

| Case | What the API guarantees | What the caller should do |
|------|------------------------|--------------------------|
| **429** | `Retry-After: <seconds>` header, integer, plus the standard error envelope | honour `Retry-After` and retry after that many seconds; a fixed backoff also works but ignores the server's own hint |
| **422** | `details` lists the offending **field names** | fix the field and re-send; the value itself is not returned, so keep the original payload on your side |
| **500** | standard envelope, no internal detail, `X-Request-Id` present | log the `X-Request-Id` and retry with backoff; do not parse the message |
| **401** | standard envelope, `code=unauthorized`, `X-Request-Id` present | the credential is missing or wrong - check the header name against `AUTH_METHOD`; **do not retry** in a tight loop |
| **`fallback_used: true`** | HTTP **200**, a valid, safe reply | show the reply to the user (optionally marked as a generic answer) and **log it as a metric**; **do not** retry - the same request will fall back again |
| **timeout (no response)** | the request is bounded by `LLM_TIMEOUT_SECONDS + 1s`; on expiry the API answers **200 with `fallback_used: true`** rather than dropping the connection | set the client timeout **above** that budget (default 11s, so use 15s+) so the client sees the fallback instead of a client-side timeout |

## Headers

| Header | Direction | Meaning |
|--------|-----------|---------|
| `X-Request-Id` | response | correlation id; **echoed back** if the caller sent one, otherwise generated |
| `X-Cache` | response | `HIT` or `MISS` - useful for measuring cache hit rate |
| `Retry-After` | response (429 only) | seconds to wait before retrying |
| `X-Request-Id` | request | optional; if sent, it is used in the access log and returned |
| `X-API-Key` | request | required only when `AUTH_METHOD=api_key` |
| `Authorization` | request | required only when `AUTH_METHOD=bearer` (`Bearer <token>`) |
| `WWW-Authenticate` | response (401, bearer mode) | `Bearer` |

## Response times (measured)

### Local container (mock mode) - 20 sequential calls

| Metric | Value |
|--------|-------|
| p50 | **3.3 ms** |
| p95 | **24.5 ms** |
| min / max | 2.9 ms / 28.6 ms |

### Staging

[PLACEHOLDER] - no staging endpoint confirmed, so no staging latency figures.

The container figure is the non-LLM floor. The **real** figure depends on the
LLM provider and **cannot be measured yet** - the real-mode entry
(`app.core.orchestrator.handle_chat`) is a lead follow-up (issue #15). The
contractual ceiling is `LLM_TIMEOUT_SECONDS + 1s` (default 11s), and the
project target is p95 < 12s once the real path exists.

**Recommendation for the client timeout: 15s** (above the 11s budget, so the
API's own fallback wins over a client-side timeout).

## Timeout behaviour (measured)

See `docs/recovery_test_notes.md` for the full scenario table. Summary:

| Situation | Result |
|-----------|--------|
| Orchestrator slower than `LLM_TIMEOUT_SECONDS` | 200, `fallback_used: true`, at `budget + 1s` (2s budget -> answered at 3.0s) |
| Orchestrator inside the budget | 200, real reply, `fallback_used: false` |
| Service stopped while a request is in flight | the request **completes** (200) and the container exits cleanly - fixed on Day 4, it used to be SIGKILLed and the connection dropped |

## Changes made on the API side (for the backend engineer and DevOps 2)

| # | Change | Type | Impact on the caller |
|---|--------|------|----------------------|
| 1 | `X-Request-Id` is now also returned on **500** responses | bug fix (contract conformance) | 500s can now be traced by the same id as every other status. Before, the id was only in the server log, so a client could not correlate a 500 with its own logs. `docs/api.md` already promised the header on "all chat/error responses" - the 500 path was the one place it was missing, so this is a **restoration of the documented contract, not a new one**. No request or response field changed. |
| 2 | `--timeout-graceful-shutdown 30` and `--timeout-keep-alive 5` in the image CMD, `stop_grace_period: 35s` in compose | hardening | no contract change; requests in flight during a stop now complete instead of the connection being dropped. **Staging still runs the old build** - it needs a redeploy to get this. |
| 3 | **Inbound API-key auth** (`X-API-Key` / Bearer, `AUTH_METHOD` configurable, key from the environment) | new feature, requested by the lead | `POST /v1/guide/chat` starts answering **401** once `AUTH_METHOD` leaves `none`. The default is still `none`, so **no caller is affected today**. `/health` stays open. |
| 4 | The request/response schema, the error envelope and the status codes are **unchanged** | - | none - Day 4 is verification, not a redesign. |

## What DevOps 2 needs to update

- **Postman collection:** add `X-Request-Id` as an optional request header
  (echoed in the response) and document the `Retry-After` header on the 429
  example. The five error examples (401 / 422 / 429 / 500 / 404) all share the
  same envelope.
- **Auth in the collection:** when `AUTH_METHOD` is confirmed, add the
  `X-API-Key` header to the chat request (and a 401 example). Until then the
  collection works unchanged against `AUTH_METHOD=none`.
- **API docs:** the request/response tables above are the contract; the
  `fallback_used` row and the "429 -> honour Retry-After" row are the parts a
  reader is most likely to miss.
- **Deployment notes:** the container now needs 35s of stop grace. A rolling
  deploy must not use a shorter termination grace period, or in-flight
  requests will be cut again.
- **Auth rollout:** the env vars are `AUTH_METHOD` and `API_KEY`. `API_KEY` is
  a secret - inject it from the CI secret store, never commit it, and never
  print it in a build log. Starting the service with `AUTH_METHOD` set but no
  `API_KEY` fails fast on purpose.
- **Staging:** the Day 3 and Day 4 fixes, and later the auth key, all still
  need a deploy to staging. See the staging placeholders above.
- **The collection's `base_url`:** it still points at
  `https://setu-guide.onrender.com`, an endpoint nobody has confirmed as
  staging. The collection is DevOps 2's, so it was left untouched on purpose -
  please confirm the base URL with the lead and change it there, or say so and
  it will be changed here.

## Open items

| # | Question | Who | Why it matters |
|---|----------|-----|----------------|
| 1 | Staging base URL, access method (VPN or allowlist) and image tag | lead / DevOps 2 | staging is [PLACEHOLDER] - nothing in this document is verified against a shared environment yet |
| 2 | Who deploys to staging, and who may restart the service during a test window? | lead / DevOps 2 (CI) | the Day 3 and Day 4 fixes are both still un-deployed; the shutdown scenarios need a restart on a real deployment |
| 3 | When is the shared test window? | lead / DevOps 2 | the load and restart runs were done locally; they should be repeated on staging |
| 4 | Final auth method (`X-API-Key` vs Bearer) and who issues and rotates the credential | lead | the code supports both; the default stays `none` until this is confirmed |
| 5 | Which environments require auth (local / staging / production)? | lead | the unconfirmed public endpoint is unauthenticated today |
| 6 | Is the unconfirmed public endpoint (`https://setu-guide.onrender.com`) ours? | lead / DevOps 2 | if it is ours it is public and unauthenticated and needs the fixes + the key; if it is not, it should be taken down |
| 7 | The backend engineer has no running backend to test against yet | lead | the end-to-end run stays pending; the API side is verified and ready |
| 8 | When `app.core.orchestrator.handle_chat` lands | lead | the real-mode latency (target p95 < 12s) and the real timeout path cannot be measured until then |
| 9 | Should the staging per-user limit be treated as hard until the Day 3 fix is deployed? | lead | if the unconfirmed endpoint is ours, the quota can currently be bypassed with `user_id` case/whitespace variants |

## Bug tracker

| Ref | Severity | Finding | Owner | Status |
|-----|----------|---------|-------|--------|
| Day-4 / integration finding 1 | Medium | 500 responses had no `X-Request-Id`, so a caller could not correlate a server error with its own logs (the documented contract in `docs/api.md` already promised it) | DevOps 1 | **Fixed** in `app/api/main.py`; test `test_500_uses_the_shared_error_envelope` |
| Day-4 / integration finding 2 | Low | No explicit keep-alive bound | DevOps 1 | **Fixed** (`--timeout-keep-alive 5`); test `test_idle_keepalive_connection_is_released` |
| Day-4 / integration finding 3 | Medium | The API had **no authentication** - any caller could call it | DevOps 1 / lead | **Fixed** - `X-API-Key` and Bearer implemented, method configurable, 25 unit tests + 1 container test. **Rollout open**: the default is still `none` until the lead confirms the method |
| Day-4 / integration finding 4 | Medium | Staging (unconfirmed endpoint) runs a build without the Day 3 rate-limit normalisation (fix A): `user_id` case/whitespace variants still get a fresh quota | DevOps 1 / lead | **Open** - needs PR #18 merged and deployed, then this check re-run |
| Day-4 / integration finding 5 | Medium | The unconfirmed public endpoint is reachable from the internet with no authentication | lead / DevOps 2 | **Open** - needs a decision: is it ours, and who deploys the fixes + the key? |
| Day-4 / integration finding 6 | Low | The Day-4 draft of this document listed only **5** stage values; the API accepts **8** (`connect`, `understand`, `reflect`, `discuss`, `agree`, `family`, `reflect_again`, `decision`), and the Day-4 contract test only exercised 5 of them. `docs/api.md` §7 was correct all along - the error was in the new document and the new test. | DevOps 1 | **Fixed** - this document now lists all 8, `test_every_stage_is_accepted` now covers all 8, and `test_request_schema_is_unchanged` freezes the whole schema so a 9th value cannot slip in unnoticed |
