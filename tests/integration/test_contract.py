"""Integration contract tests — verify the full response field set and error envelope.

These tests pin what an external backend needs: response schema, error codes,
Retry-After on 429, fallback_used on 200, X-Request-Id on every status,
and the frozen request schema (all 8 stage values, 4 intent values, field names
and length limits).

Aligned with dev's frozen contract (docs/api.md sections 7-9, 14-15):
- 8 stages / 4 intents exactly as frozen in app/schemas/guide.py.
- Response fields: intent, reply, questions, chips, sources, safety,
  fallback_used.
- Errors raised today: 404 not_found, 405 method_not_allowed, 422
  invalid_request, 429 rate_limited, 500 internal_error. 400/401/403/503 are
  static mappings the implementation never raises (docs/api.md section 14),
  so they are not asserted here; 401 coverage lives with the auth tests on
  the feature/auth-tests branch.
"""

import pytest


STAGE_VALUES = [
    "connect", "understand", "reflect", "discuss",
    "agree", "family", "reflect_again", "decision",
]
INTENT_VALUES = [
    "conversation_ideas", "help_me_understand",
    "next_steps", "privacy_safety",
]

RESPONSE_FIELDS = {
    "intent", "reply", "questions", "chips",
    "sources", "safety", "fallback_used",
}

# Status codes the app actually returns today (docs/api.md section 14).
ERROR_STATUS_CODES = [404, 405, 422, 429, 500]
EXPECTED_ERROR_CODES = {
    404: "not_found",
    405: "method_not_allowed",
    422: "invalid_request",
    429: "rate_limited",
    500: "internal_error",
}

# Synthetic sentinel proving exception text never reaches the response.
INTERNAL_ERROR_SENTINEL = "contract-500-sentinel-must-not-leak"


def post_chat(client, headers=None, **overrides):
    """POST /v1/guide/chat with a valid quick-action payload plus overrides."""
    payload = {
        "stage": "connect",
        "intent": "next_steps",
        "topic": "test-topic",
        "match_id": "match-001",
        "user_id": "user-1",
    }
    payload.update(overrides)
    return client.post("/v1/guide/chat", json=payload, headers=headers)


def trigger_error(client, code, monkeypatch):
    """Deterministically trigger each error status the contract documents."""
    if code == 404:
        return client.get("/v1/guide/nonexistent")
    if code == 405:
        # Documented example of a wrong-method call (docs/api.md section 14).
        return client.get("/v1/guide/chat")
    if code == 422:
        return post_chat(client, stage="not-a-real-stage")
    if code == 429:
        resp = None
        for _ in range(35):
            resp = post_chat(client, user_id="contract-envelope-429-user")
            if resp.status_code == 429:
                break
        return resp
    if code == 500:
        def _boom(_req):
            raise RuntimeError(INTERNAL_ERROR_SENTINEL)
        # app.api.main._orchestrator_entry reads `handle` from module globals
        # at call time, so patching it here is the supported test seam.
        monkeypatch.setattr("app.api.main.handle", _boom)
        return post_chat(client, stage="connect", intent="next_steps",
                         user_id="contract-envelope-500-user")
    raise AssertionError(f"unhandled error code {code}")


# --- Response field set ---


@pytest.mark.parametrize("stage", STAGE_VALUES)
def test_all_stage_values_accepted(client, stage):
    """All 8 frozen stage values must be accepted."""
    resp = post_chat(client, stage=stage, intent="conversation_ideas")
    assert resp.status_code == 200, (
        f"stage={stage!r} rejected with {resp.status_code}: {resp.text}"
    )


@pytest.mark.parametrize("intent", INTENT_VALUES)
def test_all_intent_values_accepted(client, intent):
    """All 4 frozen intent values must be accepted."""
    resp = post_chat(client, stage="connect", intent=intent)
    assert resp.status_code == 200, (
        f"intent={intent!r} rejected with {resp.status_code}: {resp.text}"
    )


def test_response_has_full_field_set(client):
    """Response must contain exactly the 7 documented fields."""
    resp = post_chat(client, stage="connect", intent="next_steps")
    assert resp.status_code == 200
    data = resp.json()

    assert set(data.keys()) == RESPONSE_FIELDS, (
        f"Response field set mismatch: {sorted(data.keys())}"
    )
    assert isinstance(data["intent"], str)
    assert isinstance(data["reply"], str) and data["reply"]
    assert isinstance(data["questions"], list)
    assert isinstance(data["chips"], list)
    assert isinstance(data["sources"], list)
    assert isinstance(data["fallback_used"], bool)
    assert set(data["safety"].keys()) == {"status", "flags"}


def test_x_request_id_on_every_status(client):
    """X-Request-Id must be present on every response including errors."""
    # 200 OK — the caller-supplied value is echoed back
    rid = "contract-req-echo-123"
    resp = post_chat(client, stage="connect", intent="next_steps",
                     headers={"X-Request-Id": rid})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") == rid, "caller X-Request-Id not echoed on 200"

    # 422 validation error
    resp = post_chat(client, stage="not-a-real-stage")
    assert resp.status_code == 422
    assert resp.headers.get("X-Request-Id"), "X-Request-Id missing on 422"

    # 404 not found
    resp = client.get("/v1/guide/nonexistent")
    assert resp.status_code == 404
    assert resp.headers.get("X-Request-Id"), "X-Request-Id missing on 404"


# --- Error envelope ---


@pytest.mark.parametrize("code", ERROR_STATUS_CODES)
def test_error_returns_standard_envelope(client_no_raise, monkeypatch, code):
    """Every documented error must return the standard error envelope."""
    resp = trigger_error(client_no_raise, code, monkeypatch)
    assert resp.status_code == code, (
        f"expected {code}, got {resp.status_code}: {resp.text}"
    )

    body = resp.json()
    assert set(body.keys()) == {"error"}, f"unexpected envelope keys: {sorted(body.keys())}"
    err = body["error"]
    assert set(err.keys()) == {"code", "message", "details"}, (
        f"unexpected error keys: {sorted(err.keys())}"
    )
    assert err["code"] == EXPECTED_ERROR_CODES[code]
    assert isinstance(err["message"], str) and err["message"]
    assert isinstance(err["details"], list)

    if code == 422:
        # 422 lists per-field details ("<field>: <pydantic-type>"), never values.
        assert err["details"], "422 envelope must carry per-field details"

    if code == 500:
        # Exception text (str(exc)) must never be echoed into the response.
        assert INTERNAL_ERROR_SENTINEL not in resp.text


def test_429_has_retry_after_integer(client):
    """429 must have Retry-After as integer number of seconds."""
    resp = None
    for _ in range(35):
        resp = post_chat(client, user_id="contract-retry-after-user")
        if resp.status_code == 429:
            break

    assert resp is not None and resp.status_code == 429, (
        f"per-user limit (30/min) never triggered: got {resp.status_code}"
    )
    ra = resp.headers.get("Retry-After")
    assert ra is not None, "429 response missing Retry-After header"
    assert ra.isdigit(), f"Retry-After must be integer, got: {ra!r}"
    assert int(ra) >= 1, "Retry-After must be positive"


def test_fallback_used_is_200_not_error(client):
    """fallback_used must be a boolean on a 200, never an error status."""
    resp = post_chat(client, stage="connect", intent="next_steps")
    assert resp.status_code == 200
    data = resp.json()
    assert "fallback_used" in data, "fallback_used missing on 200"
    assert isinstance(data["fallback_used"], bool), "fallback_used must be boolean"
    # A normal quick action on the mock path needs no fallback.
    assert data["fallback_used"] is False


# --- Frozen request schema ---


def test_request_schema_field_length_limits(client):
    """Field length limits must be enforced as 422 (topic 100, message 500)."""
    # topic: exactly 100 is accepted, 101+ is rejected with 422
    resp = post_chat(client, stage="connect", intent="next_steps", topic="t" * 100)
    assert resp.status_code == 200
    resp = post_chat(client, stage="connect", intent="next_steps", topic="t" * 101)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_request"

    # message: exactly 500 is accepted, 501+ is rejected with 422
    resp = post_chat(client, stage="connect", message="m" * 500)
    assert resp.status_code == 200
    resp = post_chat(client, stage="connect", message="m" * 501)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_request"


def test_no_extra_unexpected_fields(client):
    """Response should not contain unexpected fields."""
    resp = post_chat(client, stage="connect", intent="next_steps")
    assert resp.status_code == 200
    data = resp.json()

    # These should NOT be in the response
    unexpected = {"api_key", "auth_token", "password", "secret"}
    overlap = unexpected & set(data.keys())
    assert not overlap, f"Unexpected fields in response: {overlap}"
