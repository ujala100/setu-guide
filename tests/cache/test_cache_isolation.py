"""Phase 2 Day 3: cache isolation (tests/cache/).

Critical rule under test: two different users must never receive each
other's cached reply. The fake orchestrator encodes the request (user,
match, stage, topic) into the reply text, so any cross-entry mix-up shows
up in the response body - not just in call counts.

Also covers the never-cached set (free text, errors, fallback replies,
safety modified/blocked, flags), CACHE_ENABLED=false, and the 5-part key.

Owner: DevOps 1 (app/api). Synthetic data only.
"""
from app.api.cache import cache_key, response_cache
from app.schemas.guide import (GuideRequest, GuideResponse, Intent, Safety,
                               SafetyFlag, SafetyStatus, Stage)

CHAT = "/v1/guide/chat"
QUICK = {"user_id": "alice", "match_id": "m1", "stage": "connect",
         "intent": "next_steps"}


def _fake_handle(monkeypatch, *, reply=None, safety=None, fallback=False,
                 fail=False):
    """Fake orchestrator whose reply encodes the request it saw."""
    calls = {"n": 0}

    def fake(req):
        calls["n"] += 1
        if fail:
            raise RuntimeError("synthetic orchestrator failure")
        text = reply(req) if reply else f"reply#{calls['n']}"
        return GuideResponse(
            intent=req.intent or Intent.next_steps,
            reply=text,
            safety=safety or Safety(),
            fallback_used=fallback,
        )

    monkeypatch.setattr("app.api.main.handle", fake)
    return calls


def _encoded(req):
    return f"user={req.user_id}|match={req.match_id}|stage={req.stage.value}|topic={req.topic or '-'}"


# --- cross-user isolation (CRITICAL) ------------------------------------------

def test_two_users_never_receive_each_others_cached_reply(client, set_env,
                                                          monkeypatch):
    """Same stage/intent/topic/match_id, two users, distinct replies."""
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, reply=lambda r: f"reply-for-{r.user_id}")
    a1 = client.post(CHAT, json={**QUICK, "user_id": "alice"})
    b1 = client.post(CHAT, json={**QUICK, "user_id": "bob"})
    a2 = client.post(CHAT, json={**QUICK, "user_id": "alice"})
    b2 = client.post(CHAT, json={**QUICK, "user_id": "bob"})
    assert [r.status_code for r in (a1, b1, a2, b2)] == [200, 200, 200, 200]
    # one orchestrator call per user: a2 and b2 were served from the cache
    assert a2.headers["X-Cache"] == b2.headers["X-Cache"] == "HIT"
    assert calls["n"] == 2
    # every response carries its own user's reply - no cross-user leakage
    assert a1.json()["reply"] == a2.json()["reply"] == "reply-for-alice"
    assert b1.json()["reply"] == b2.json()["reply"] == "reply-for-bob"
    assert "bob" not in a2.json()["reply"]
    assert "alice" not in b2.json()["reply"]


def test_interleaved_requests_keep_every_users_own_reply(client, set_env,
                                                         monkeypatch):
    """Alternating rounds: each HIT must replay that user's own reply."""
    set_env(CACHE_ENABLED="true")
    _fake_handle(monkeypatch, reply=_encoded)
    for _ in range(3):
        for uid in ("alice", "bob"):
            r = client.post(CHAT, json={**QUICK, "user_id": uid})
            assert r.status_code == 200
            assert r.json()["reply"] == (
                f"user={uid}|match=m1|stage=connect|topic=-")


def test_different_match_id_never_returns_the_other_matches_reply(client, set_env,
                                                                  monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, reply=_encoded)
    first_m1 = client.post(CHAT, json={**QUICK, "match_id": "m1"})
    first_m2 = client.post(CHAT, json={**QUICK, "match_id": "m2"})
    again_m1 = client.post(CHAT, json={**QUICK, "match_id": "m1"})
    again_m2 = client.post(CHAT, json={**QUICK, "match_id": "m2"})
    assert first_m1.headers["X-Cache"] == first_m2.headers["X-Cache"] == "MISS"
    assert again_m1.headers["X-Cache"] == again_m2.headers["X-Cache"] == "HIT"
    assert calls["n"] == 2
    assert again_m1.json()["reply"] == "user=alice|match=m1|stage=connect|topic=-"
    assert again_m2.json()["reply"] == "user=alice|match=m2|stage=connect|topic=-"


def test_different_stage_never_returns_the_other_stages_reply(client, set_env,
                                                              monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, reply=_encoded)
    connect = client.post(CHAT, json={**QUICK, "stage": "connect"})
    reflect = client.post(CHAT, json={**QUICK, "stage": "reflect"})
    connect_hit = client.post(CHAT, json={**QUICK, "stage": "connect"})
    reflect_hit = client.post(CHAT, json={**QUICK, "stage": "reflect"})
    assert connect.headers["X-Cache"] == reflect.headers["X-Cache"] == "MISS"
    assert connect_hit.headers["X-Cache"] == reflect_hit.headers["X-Cache"] == "HIT"
    assert calls["n"] == 2
    assert "stage=connect" in connect_hit.json()["reply"]
    assert "stage=reflect" in reflect_hit.json()["reply"]


def test_different_topic_gets_its_own_reply_not_the_cached_one(client, set_env,
                                                               monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, reply=_encoded)
    budget = client.post(CHAT, json={**QUICK, "topic": "budget"})
    family = client.post(CHAT, json={**QUICK, "topic": "family"})
    budget_hit = client.post(CHAT, json={**QUICK, "topic": "budget"})
    assert budget.headers["X-Cache"] == family.headers["X-Cache"] == "MISS"
    assert budget_hit.headers["X-Cache"] == "HIT"
    assert calls["n"] == 2
    assert "topic=budget" in budget_hit.json()["reply"]
    assert "topic=family" in family.json()["reply"]


# --- never cached --------------------------------------------------------------

def test_free_text_is_never_cached(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, reply=lambda r: f"saw={r.message}")
    body = {"user_id": "alice", "match_id": "m1", "stage": "connect",
            "message": "what should i say next?"}
    first = client.post(CHAT, json=body)
    second = client.post(CHAT, json=body)
    assert first.status_code == second.status_code == 200
    assert first.headers["X-Cache"] == second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2, "free text must reach the orchestrator every time"


def test_500_errors_are_never_cached(client_no_raise, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, fail=True)
    first = client_no_raise.post(CHAT, json=QUICK)
    second = client_no_raise.post(CHAT, json=QUICK)
    assert first.status_code == second.status_code == 500
    assert "X-Cache" not in first.headers and "X-Cache" not in second.headers
    assert calls["n"] == 2, "an error must not seed the cache"


def test_fallback_replies_are_never_cached(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, reply=lambda r: "fallback text",
                         fallback=True)
    first = client.post(CHAT, json=QUICK)
    second = client.post(CHAT, json=QUICK)
    assert first.json()["fallback_used"] is True
    assert first.headers["X-Cache"] == second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2


def test_safety_modified_reply_is_never_cached(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, safety=Safety(status=SafetyStatus.modified))
    first = client.post(CHAT, json=QUICK)
    second = client.post(CHAT, json=QUICK)
    assert first.json()["safety"]["status"] == "modified"
    assert first.headers["X-Cache"] == second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2


def test_safety_blocked_reply_is_never_cached(client, set_env, monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(monkeypatch, safety=Safety(status=SafetyStatus.blocked))
    first = client.post(CHAT, json=QUICK)
    second = client.post(CHAT, json=QUICK)
    assert first.json()["safety"]["status"] == "blocked"
    assert first.headers["X-Cache"] == second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2


def test_flags_even_with_pass_status_are_never_cached(client, set_env,
                                                      monkeypatch):
    set_env(CACHE_ENABLED="true")
    calls = _fake_handle(
        monkeypatch,
        safety=Safety(status=SafetyStatus.passed,
                      flags=[SafetyFlag.outcome_prediction]))
    first = client.post(CHAT, json=QUICK)
    second = client.post(CHAT, json=QUICK)
    assert first.json()["safety"]["status"] == "pass"
    assert first.headers["X-Cache"] == second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2


# --- config --------------------------------------------------------------------

def test_cache_enabled_false_really_disables_the_cache(client, set_env,
                                                       monkeypatch):
    set_env(CACHE_ENABLED="false")
    calls = _fake_handle(monkeypatch, reply=lambda r: f"reply-for-{r.user_id}")
    first = client.post(CHAT, json=QUICK)
    second = client.post(CHAT, json=QUICK)
    assert first.headers["X-Cache"] == second.headers["X-Cache"] == "MISS"
    assert calls["n"] == 2, "a disabled cache must call the orchestrator twice"
    assert response_cache._cache is None, \
        "a disabled cache must not even build a store"


def test_cache_key_includes_user_match_stage_intent_and_topic():
    base = GuideRequest(user_id="alice", match_id="m1", stage=Stage.connect,
                        intent=Intent.next_steps, topic="budget")
    key = cache_key(base)
    assert key == ("connect", "next_steps", "budget", "m1", "alice")
    assert cache_key(base) == key  # deterministic for an identical request
    variants = [
        GuideRequest(user_id="bob", match_id="m1", stage=Stage.connect,
                     intent=Intent.next_steps, topic="budget"),
        GuideRequest(user_id="alice", match_id="m2", stage=Stage.connect,
                     intent=Intent.next_steps, topic="budget"),
        GuideRequest(user_id="alice", match_id="m1", stage=Stage.reflect,
                     intent=Intent.next_steps, topic="budget"),
        GuideRequest(user_id="alice", match_id="m1", stage=Stage.connect,
                     intent=Intent.privacy_safety, topic="budget"),
        GuideRequest(user_id="alice", match_id="m1", stage=Stage.connect,
                     intent=Intent.next_steps, topic="family"),
    ]
    for variant in variants:
        assert cache_key(variant) != key, f"key must change: {variant}"
