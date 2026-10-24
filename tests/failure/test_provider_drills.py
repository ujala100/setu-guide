"""Phase 2 Day 2: provider-level failure drills (real mode, USE_MOCK=false).

These are the drills from the Day 2 brief that the Day 3 suite did NOT cover:
the provider being DOWN (connection refused), the provider RATE-LIMITING us
(429 from the provider), and the provider returning an EMPTY reply.

Day 3's test_llm_failures.py already covers the other drills (slow / timeout,
invalid JSON, invalid schema, wrong type, fallback-not-cached, recovery), so
those are deliberately NOT re-implemented here - one home per case.

app/core belongs to the AI/ML team and is never edited: each drill plants a
fake orchestrator entry point with monkeypatch for the duration of one test,
exactly like the Day 3 drills. The contract that must hold for EVERY drill:
    HTTP 200, template reply, fallback_used=true, safety.status="pass",
    flags=[], never a 500, and the fallback reply is NEVER cached.
"""
import time

from app.api.chat import FALLBACK_REPLY
from app.core import orchestrator

CHAT = "/v1/guide/chat"
QUICK_ACTION = {"user_id": "day2_drill_u1", "match_id": "day2_drill_m1",
                "stage": "reflect", "intent": "next_steps"}


def _real_mode(client, set_env, monkeypatch, entry, **extra):
    """USE_MOCK=false + a fake orchestrator entry point for one drill."""
    set_env(USE_MOCK="false", LLM_API_KEY="dummy-key-for-drills", **extra)
    monkeypatch.setattr(orchestrator, "handle_chat", entry, raising=False)
    return client.post(CHAT, json=QUICK_ACTION)


def assert_safe_fallback(r):
    assert r.status_code == 200, f"drill leaked as HTTP {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert set(body) >= {"intent", "reply", "safety", "fallback_used"}
    assert body["fallback_used"] is True
    assert body["reply"] == FALLBACK_REPLY
    assert body["safety"]["status"] == "pass"
    assert body["safety"]["flags"] == []
    assert r.headers["X-Cache"] == "MISS"
    return body


def _assert_not_cached(client):
    """A second identical quick action must MISS again: fallbacks are never cached."""
    again = client.post(CHAT, json=QUICK_ACTION)
    assert again.headers["X-Cache"] == "MISS"
    assert again.json()["fallback_used"] is True
    return again


# ------------------------------------------------------------------- drills

def test_drill_llm_down_connection_refused(client, set_env, monkeypatch):
    """Drill: provider refuses the connection (LLM down)."""
    def refused(_req):
        raise ConnectionRefusedError("connection refused by llm host")

    r = _real_mode(client, set_env, monkeypatch, refused)
    assert_safe_fallback(r)
    _assert_not_cached(client)


def test_drill_llm_rate_limited_by_provider(client, set_env, monkeypatch):
    """Drill: provider answers 429 (quota exhausted).

    The provider's 429 must become a safe 200 template fallback for OUR caller.
    It must NOT be forwarded as a 429: our own 429 is reserved for OUR rate
    limiter, and the caller cannot fix the provider's quota by retrying fast.
    """
    class ProviderRateLimited(Exception):
        """Stands in for the provider SDK's 429 / quota error."""

    def limited(_req):
        raise ProviderRateLimited("provider returned 429 quota exceeded")

    r = _real_mode(client, set_env, monkeypatch, limited)
    body = assert_safe_fallback(r)
    assert r.status_code != 429
    assert "Retry-After" not in r.headers
    assert "quota" not in body["reply"].lower()
    _assert_not_cached(client)


def test_drill_llm_returns_empty_reply(client, set_env, monkeypatch):
    """Drill: provider returns an empty reply (empty string)."""
    def empty(_req):
        return ""

    r = _real_mode(client, set_env, monkeypatch, empty)
    assert_safe_fallback(r)
    _assert_not_cached(client)


def test_drill_llm_returns_whitespace_only_reply(client, set_env, monkeypatch):
    """Drill: provider returns only whitespace (looks like content, is not)."""
    def whitespace(_req):
        return "   \n\t  "

    r = _real_mode(client, set_env, monkeypatch, whitespace)
    assert_safe_fallback(r)
    _assert_not_cached(client)


def test_drill_llm_slow_beyond_timeout(client, set_env, monkeypatch):
    """Drill: provider slower than LLM_TIMEOUT_SECONDS (already Day 3 territory,
    kept here so the Day 2 drill set is self-contained and all-green)."""
    def slow(_req):
        time.sleep(1.0)

    monkeypatch.setattr("app.api.chat.TIMEOUT_MARGIN_SECONDS", 0.0)
    started = time.monotonic()
    r = _real_mode(client, set_env, monkeypatch, slow, LLM_TIMEOUT_SECONDS="0.05")
    elapsed = time.monotonic() - started
    assert_safe_fallback(r)
    assert elapsed < 0.9, f"timeout not enforced, took {elapsed:.2f}s"
    _assert_not_cached(client)


def test_drill_recovers_when_provider_returns(client, set_env, monkeypatch):
    """Every drill ends the same way: once the provider is healthy again the
    service serves a normal reply - the fallback must not stick."""
    def refused(_req):
        raise ConnectionRefusedError("connection refused")

    _real_mode(client, set_env, monkeypatch, refused)

    def healthy(_req):
        from app.schemas.guide import GuideResponse, Intent
        return GuideResponse(intent=Intent.next_steps, reply="provider recovered")

    monkeypatch.setattr(orchestrator, "handle_chat", healthy, raising=False)
    r = client.post(CHAT, json=QUICK_ACTION)
    assert r.status_code == 200
    body = r.json()
    assert body["fallback_used"] is False
    assert body["reply"] == "provider recovered"


def test_drill_logs_carry_no_message_or_ids(client, set_env, monkeypatch, caplog):
    """Privacy rule for ALL runs: the drill path must not log the message text,
    the topic, user_id, match_id or the API key."""
    import logging

    marker_msg = "DRILL-MARKER-MSG private thoughts about relocating"
    marker_topic = "DRILL-MARKER-TOPIC"
    marker_user = "drill-marker-user-42"
    marker_match = "drill-marker-match-42"
    marker_key = "sk-DRILL-MARKER-KEY-42"
    payload = {"user_id": marker_user, "match_id": marker_match,
               "stage": "family", "message": marker_msg, "topic": marker_topic}

    def refused(_req):
        raise ConnectionRefusedError("connection refused")

    set_env(USE_MOCK="false", LLM_API_KEY=marker_key, LOG_LEVEL="INFO")
    monkeypatch.setattr(orchestrator, "handle_chat", refused, raising=False)
    with caplog.at_level(logging.INFO, logger="setu.guide"):
        r = client.post(CHAT, json=payload)
    assert r.status_code == 200
    logged = caplog.text
    for marker in (marker_msg, marker_topic, marker_user, marker_match, marker_key):
        assert marker not in logged, f"marker leaked into logs: {marker}"
    # the failure was logged by type only
    assert "orchestrator_failed" in logged
