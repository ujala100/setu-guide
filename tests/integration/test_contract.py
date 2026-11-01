"""Day 4: the contract an external backend (Shakshi) codes against.

Owner: DevOps 1 (app/api). This suite is the integrator-facing view of the
API: the full response schema, the error envelope for every status the caller
can meet, and the latency budget.

It is deliberately separate from tests/failure/test_bad_input.py (which covers
input validation exhaustively) and tests/ratelimit (which covers the limiter
internals). Here the focus is: "if I build a client against these rules, will
it work?" - field names, types, header semantics and timing.

Synthetic ids only.
"""
import statistics
import time

import pytest

CHAT = "/v1/guide/chat"
HEALTH = "/health"

# The complete response contract, as an integrator sees it.
EXPECTED_RESPONSE_FIELDS = {
    "intent", "reply", "questions", "chips", "sources", "safety", "fallback_used",
}
EXPECTED_ERROR_FIELDS = {"code", "message", "details"}

VALID_BODY = {"user_id": "d4_contract_u1", "match_id": "d4_contract_m1",
              "stage": "connect", "intent": "next_steps"}

# The frozen request schema (lead instruction, 2026-10-22: "the frozen schema
# is the source of truth; schema changes go only through me"). This is the
# fingerprint an integrator codes against - if a field is added, renamed or
# retyped without the lead's sign-off, this test fails.
EXPECTED_REQUEST_FIELDS = {
    "user_id", "match_id", "stage", "intent", "message", "topic", "context",
}
EXPECTED_REQUIRED_FIELDS = {"user_id", "match_id", "stage"}
# The full stage enum from app/schemas/guide.py (docs/api.md section 7).
EXPECTED_STAGES = {"connect", "understand", "reflect", "discuss", "agree",
                   "family", "reflect_again", "decision"}
EXPECTED_INTENTS = {"conversation_ideas", "help_me_understand",
                    "next_steps", "privacy_safety"}


def _assert_error_envelope(r, status, code):
    """Every error the caller can meet uses the same shape."""
    assert r.status_code == status, f"expected {status}, got {r.status_code}: {r.text[:200]}"
    assert r.headers["content-type"].startswith("application/json")
    assert r.headers.get("X-Request-Id"), "X-Request-Id missing"
    body = r.json()
    assert set(body) == {"error"}, f"unexpected top-level keys: {set(body)}"
    err = body["error"]
    assert set(err) == EXPECTED_ERROR_FIELDS, f"bad error keys: {set(err)}"
    assert err["code"] == code
    assert isinstance(err["message"], str) and err["message"]
    assert isinstance(err["details"], list)
    return err


# ------------------------------------------------------------- happy path

def test_request_schema_is_unchanged():
    """The request schema is frozen (lead instruction, 2026-10-22).

    Whoever deviates from the frozen schema fixes their own side, so an
    accidental change here - a renamed field, a new one, a different type, a
    different length limit or a new enum value - must fail loudly instead of
    quietly breaking every client. Schema changes go through the lead.

    The JSON schema is used because that is exactly what an integrator's
    generated client is built from.
    """
    from app.schemas.guide import GuideRequest

    schema = GuideRequest.model_json_schema()
    props = schema["properties"]
    defs = schema["$defs"]

    assert set(props) == EXPECTED_REQUEST_FIELDS, (
        f"the request schema changed: added {set(props) - EXPECTED_REQUEST_FIELDS}, "
        f"removed {EXPECTED_REQUEST_FIELDS - set(props)}")
    assert set(schema["required"]) == EXPECTED_REQUIRED_FIELDS, (
        f"the required fields changed: {set(schema['required'])}")

    assert props["user_id"]["type"] == "string"
    assert props["match_id"]["type"] == "string"

    stage_values = defs["Stage"]["enum"]
    assert stage_values == ["connect", "understand", "reflect", "discuss",
                            "agree", "family", "reflect_again", "decision"], (
        f"the stage enum changed: {stage_values}")
    intent_values = defs["Intent"]["enum"]
    assert set(intent_values) == EXPECTED_INTENTS, (
        f"the intent enum changed: {intent_values}")

    assert props["message"]["anyOf"][0]["maxLength"] == 500
    assert props["topic"]["anyOf"][0]["maxLength"] == 100


def test_success_response_has_the_documented_fields(client):
    """The full success shape: field names, types and containers. An
    integrator's model must match this exactly."""
    r = client.post(CHAT, json=VALID_BODY)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == EXPECTED_RESPONSE_FIELDS, (
        f"response fields changed: {set(body) ^ EXPECTED_RESPONSE_FIELDS}")
    assert isinstance(body["reply"], str) and body["reply"]
    assert isinstance(body["intent"], str)
    assert isinstance(body["questions"], list) and len(body["questions"]) <= 5
    assert isinstance(body["chips"], list) and len(body["chips"]) <= 4
    assert isinstance(body["sources"], list)
    assert isinstance(body["fallback_used"], bool)
    assert isinstance(body["safety"], dict)
    assert set(body["safety"]) >= {"status"}
    assert body["safety"]["status"] in ("pass", "modified", "blocked")


def test_success_response_is_stable_across_repeats(client):
    """The same request shape always yields the same field set - a client can
    rely on the model even when the content changes."""
    shapes = set()
    for i in range(3):
        r = client.post(CHAT, json={**VALID_BODY, "user_id": f"d4_contract_u{i}"})
        assert r.status_code == 200
        shapes.add(tuple(sorted(r.json())))
    assert len(shapes) == 1, f"response shape is not stable: {shapes}"


def test_request_id_is_echoed_back_for_tracing(client):
    """A caller-supplied X-Request-Id comes back on the response, so the
    backend can join its own logs with the API's access log."""
    r = client.post(CHAT, json=VALID_BODY,
                    headers={"X-Request-Id": "d4-trace-0001"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-Id") == "d4-trace-0001"


def test_health_endpoint_shape(client):
    """The liveness probe an orchestrator or load balancer will call."""
    r = client.get(HEALTH)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ------------------------------------------------------------ error paths

def test_422_uses_the_shared_error_envelope(client):
    """Schema mismatch: the caller gets 422 with the same envelope as every
    other error, and details that name the field but never the value."""
    r = client.post(CHAT, json={**VALID_BODY, "stage": "teleport"})
    err = _assert_error_envelope(r, 422, "invalid_request")
    assert any("stage" in d for d in err["details"]), err["details"]
    assert "teleport" not in r.text, "the rejected value must not be echoed back"


def test_429_carries_retry_after_as_an_integer(client, set_env):
    """429 must tell the caller when to come back: `Retry-After` is a whole
    number of seconds, and the body uses the shared error envelope."""
    set_env(RATE_LIMIT_PER_USER="2/minute", RATE_LIMIT_PER_IP="1000/minute")
    statuses = [client.post(CHAT, json=VALID_BODY).status_code for _ in range(3)]
    assert statuses[:2] == [200, 200], statuses
    assert statuses[2] == 429, statuses

    r = client.post(CHAT, json=VALID_BODY)
    err = _assert_error_envelope(r, 429, "rate_limited")
    assert err["details"] == []
    retry_after = r.headers.get("Retry-After")
    assert retry_after is not None, "429 without Retry-After"
    assert retry_after.isdigit(), f"Retry-After must be an integer number of seconds: {retry_after!r}"
    assert 0 < int(retry_after) <= 60, f"Retry-After out of range: {retry_after}"


def test_500_uses_the_shared_error_envelope(client_no_raise, monkeypatch):
    """An unexpected server-side failure is still a clean 500 in the same
    envelope - the caller can parse every error with one function - and it
    still carries X-Request-Id, so the caller can trace it (Day 4 fix)."""
    import app.api.main as api_main

    def boom(*_args, **_kwargs):
        raise RuntimeError("integration-canary-boom")

    monkeypatch.setattr(api_main, "handle", boom)
    r = client_no_raise.post(CHAT, json=VALID_BODY)
    _assert_error_envelope(r, 500, "internal_error")
    assert "integration-canary-boom" not in r.text, "internal detail leaked to the caller"


def test_every_error_status_uses_the_same_envelope(client, set_env):
    """A caller can rely on one error parser: 422, 429 and 500 all look the
    same on the wire."""
    set_env(RATE_LIMIT_PER_USER="1/minute", RATE_LIMIT_PER_IP="1000/minute")
    seen = {}

    r = client.post(CHAT, json={**VALID_BODY, "stage": "teleport"})
    seen[r.status_code] = set(r.json()["error"])
    client.post(CHAT, json=VALID_BODY)  # 200, consumes the quota
    r = client.post(CHAT, json=VALID_BODY)
    seen[r.status_code] = set(r.json()["error"])
    r = client.get("/no/such/route")
    seen[r.status_code] = set(r.json()["error"])

    assert set(seen) >= {404, 422, 429}, seen
    for status, fields in seen.items():
        assert fields == EXPECTED_ERROR_FIELDS, f"status {status}: {fields}"


# ------------------------------------------------------- fallback contract

def test_fallback_answer_is_a_normal_200(client, set_env):
    """When the orchestrator cannot answer, the caller still gets HTTP 200 and
    a usable reply - `fallback_used` is the flag that tells them it is not a
    real answer. A backend must not treat it as an error.

    Real mode is used on purpose: in mock mode an orchestrator error
    propagates as a 500 (Day 1 behaviour), while real mode converts it into
    the safe fallback answer.
    """
    set_env(USE_MOCK="false", LLM_API_KEY="integration-dummy-key")
    r = client.post(CHAT, json=VALID_BODY)
    assert r.status_code == 200, f"fallback must not be an error status: {r.status_code}"
    body = r.json()
    assert body["fallback_used"] is True
    assert isinstance(body["reply"], str) and body["reply"]
    assert set(body) == EXPECTED_RESPONSE_FIELDS


def test_real_answer_is_marked_fallback_used_false(client):
    """The normal path must be distinguishable from the fallback by this flag
    alone - that is what a backend branches on."""
    r = client.post(CHAT, json=VALID_BODY)
    assert r.status_code == 200
    assert r.json()["fallback_used"] is False


# --------------------------------------------------------------- latency

def test_response_time_budget_for_a_backend_client(client):
    """Mock mode is the latency floor a backend sees. It pins the order of
    magnitude so a regression in per-request overhead is visible; the real
    p95 target (<12s) needs the real provider and is tracked with #15."""
    samples = []
    for i in range(20):
        started = time.perf_counter()
        r = client.post(CHAT, json={**VALID_BODY, "user_id": f"d4_lat_u{i}"})
        samples.append(time.perf_counter() - started)
        assert r.status_code == 200
    p50 = statistics.median(samples)
    p95 = sorted(samples)[int(len(samples) * 0.95) - 1]
    assert p50 < 0.5, f"p50 {p50:.3f}s is too slow for a non-LLM call"
    assert p95 < 1.0, f"p95 {p95:.3f}s is too slow for a non-LLM call"


@pytest.mark.parametrize("stage", sorted(EXPECTED_STAGES))
def test_every_stage_is_accepted(client, stage):
    """The stage enum is the part of the contract a backend hard-codes; all
    eight values must be accepted and answered - not just the five that
    happened to appear in an earlier draft of this suite."""
    r = client.post(CHAT, json={**VALID_BODY, "stage": stage})
    assert r.status_code == 200, f"stage {stage}: {r.status_code}"
    assert set(r.json()) == EXPECTED_RESPONSE_FIELDS
