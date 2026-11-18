"""Day 4: inbound API-key authentication.

Owner: DevOps 1 (app/api). The lead asked for an API key in a header, read
from the environment and never committed, with the method configurable so it
can be switched to Bearer later.

Covered here:
- the default (AUTH_METHOD=none) changes nothing
- api_key mode: missing / wrong / right key, and /health stays open
- bearer mode: the right header, the wrong scheme, and X-API-Key is ignored
- startup fails fast when a method is on but no key is set
- the key never appears in a response body, a header or a log line

Synthetic keys only ("day4-test-key-...").
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import SettingsError, get_settings

CHAT = "/v1/guide/chat"
HEALTH = "/health"
KEY = "day4-test-key-abc123"
BODY = {"user_id": "d4_auth_u1", "match_id": "d4_auth_m1",
        "stage": "connect", "intent": "next_steps"}


@pytest.fixture
def auth_env(set_env):
    """Turn auth on with a known key."""
    def _on(method="api_key", key=KEY):
        set_env(AUTH_METHOD=method, API_KEY=key)
        return key
    return _on


def _assert_401(r):
    """The standard error envelope, and no hint about what was wrong."""
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"
    assert r.headers["content-type"].startswith("application/json")
    assert r.headers.get("X-Request-Id"), "X-Request-Id missing on the 401"
    body = r.json()
    assert set(body) == {"error"}, body
    err = body["error"]
    assert set(err) == {"code", "message", "details"}, err
    assert err["code"] == "unauthorized"
    assert err["details"] == []
    assert KEY not in r.text, "the key leaked into the response body"


# ------------------------------------------------------- default behaviour

def test_auth_is_off_by_default(client):
    """Nothing changes until the team confirms the method: the endpoint stays
    open and every other test in the repo keeps working."""
    assert get_settings().auth_method == "none"
    assert client.post(CHAT, json=BODY).status_code == 200


def test_health_never_needs_a_credential(client, auth_env):
    """The container HEALTHCHECK and the load-balancer probe call /health
    without a key, so auth must not cover it."""
    auth_env()
    assert client.get(HEALTH).status_code == 200
    assert client.get(HEALTH).json() == {"status": "ok"}


# ------------------------------------------------------------- api_key mode

def test_api_key_mode_accepts_the_right_key(client, auth_env):
    auth_env("api_key")
    r = client.post(CHAT, json=BODY, headers={"X-API-Key": KEY})
    assert r.status_code == 200
    assert r.json()["fallback_used"] is False


def test_api_key_mode_rejects_a_missing_key(client, auth_env):
    auth_env("api_key")
    _assert_401(client.post(CHAT, json=BODY))


def test_api_key_mode_rejects_a_wrong_key(client, auth_env):
    auth_env("api_key")
    _assert_401(client.post(CHAT, json=BODY, headers={"X-API-Key": "wrong-key"}))


def test_api_key_mode_rejects_a_prefix_of_the_key(client, auth_env):
    """A truncated key is not a key - no prefix matching."""
    auth_env("api_key")
    _assert_401(client.post(CHAT, json=BODY, headers={"X-API-Key": KEY[:-1]}))


def test_api_key_mode_rejects_a_key_with_extra_characters(client, auth_env):
    auth_env("api_key")
    _assert_401(client.post(CHAT, json=BODY, headers={"X-API-Key": KEY + "x"}))


def test_api_key_mode_rejects_an_empty_key(client, auth_env):
    auth_env("api_key")
    _assert_401(client.post(CHAT, json=BODY, headers={"X-API-Key": ""}))


def test_api_key_mode_ignores_the_bearer_header(client, auth_env):
    """In api_key mode a Bearer token is not a credential."""
    auth_env("api_key")
    _assert_401(client.post(CHAT, json=BODY, headers={"Authorization": f"Bearer {KEY}"}))


def test_unauthenticated_request_is_not_rate_limited_or_answered(client, auth_env):
    """A 401 must not consume the caller's rate-limit quota and must not
    produce an answer - the request never reaches the orchestrator."""
    auth_env("api_key")
    for _ in range(5):
        _assert_401(client.post(CHAT, json=BODY))
    # the quota is untouched: the same user still gets a normal answer once
    # the key is presented
    assert client.post(CHAT, json=BODY, headers={"X-API-Key": KEY}).status_code == 200


# -------------------------------------------------------------- bearer mode

def test_bearer_mode_accepts_the_right_token(client, auth_env):
    auth_env("bearer")
    r = client.post(CHAT, json=BODY, headers={"Authorization": f"Bearer {KEY}"})
    assert r.status_code == 200


def test_bearer_mode_rejects_a_missing_token(client, auth_env):
    auth_env("bearer")
    _assert_401(client.post(CHAT, json=BODY))


def test_bearer_mode_rejects_a_wrong_token(client, auth_env):
    auth_env("bearer")
    _assert_401(client.post(CHAT, json=BODY, headers={"Authorization": "Bearer wrong"}))


def test_bearer_mode_rejects_a_missing_scheme(client, auth_env):
    """`Authorization: <key>` without the scheme is not a bearer token."""
    auth_env("bearer")
    _assert_401(client.post(CHAT, json=BODY, headers={"Authorization": KEY}))


def test_bearer_mode_rejects_a_wrong_scheme(client, auth_env):
    auth_env("bearer")
    _assert_401(client.post(CHAT, json=BODY, headers={"Authorization": f"Basic {KEY}"}))


def test_bearer_mode_ignores_the_api_key_header(client, auth_env):
    """Switching method is a configuration change, so the old header must stop
    working - otherwise both would be accepted at once."""
    auth_env("bearer")
    _assert_401(client.post(CHAT, json=BODY, headers={"X-API-Key": KEY}))


def test_bearer_mode_advertises_the_scheme(client, auth_env):
    auth_env("bearer")
    r = client.post(CHAT, json=BODY)
    assert r.headers.get("WWW-Authenticate") == "Bearer"


# ------------------------------------------------------------ configuration

def test_startup_fails_fast_when_auth_is_on_without_a_key(set_env):
    """A missing key must stop the process with one clear line, not start and
    then reject every request."""
    set_env(AUTH_METHOD="api_key", API_KEY="")
    with pytest.raises(SettingsError) as exc:
        get_settings()
    assert "API_KEY is required" in str(exc.value)


def test_startup_fails_fast_for_an_unknown_method(set_env):
    set_env(AUTH_METHOD="basic", API_KEY=KEY)
    with pytest.raises(SettingsError) as exc:
        get_settings()
    assert "AUTH_METHOD" in str(exc.value)


def test_the_placeholder_key_is_refused_as_a_live_credential(set_env):
    """Copying .env.example to .env and flipping AUTH_METHOD must not leave
    the endpoint open with a guessable key."""
    set_env(AUTH_METHOD="api_key", API_KEY="placeholder-not-a-real-key")
    with pytest.raises(SettingsError) as exc:
        get_settings()
    assert "placeholder" in str(exc.value).lower()


def test_the_placeholder_key_is_fine_while_auth_is_off(set_env):
    """The template must still start the service as it ships."""
    set_env(AUTH_METHOD="none", API_KEY="placeholder-not-a-real-key")
    assert get_settings().auth_method == "none"


def test_the_startup_error_never_contains_the_key(set_env):
    set_env(AUTH_METHOD="bearer", API_KEY="")
    with pytest.raises(SettingsError) as exc:
        get_settings()
    assert "placeholder" not in str(exc.value).lower()


# ------------------------------------------------------------- log hygiene

def test_the_key_never_reaches_the_access_log(client, auth_env, caplog):
    """The structured access log must not carry the credential."""
    import logging

    auth_env("api_key")
    with caplog.at_level(logging.INFO, logger="setu.guide"):
        client.post(CHAT, json=BODY, headers={"X-API-Key": KEY})
        client.post(CHAT, json=BODY, headers={"X-API-Key": "wrong-key"})
    text = caplog.text
    assert "http_request" in text, "no access log line captured"
    assert KEY not in text, "the API key leaked into the access log"
    assert "wrong-key" not in text, "the presented key leaked into the access log"


def test_the_key_is_not_committed_to_the_repo():
    """.env holds the real value and is git-ignored; .env.example only has a
    placeholder. Nothing in the tracked files may contain a real key."""
    import os
    import subprocess

    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True,
                              text=True, timeout=60).stdout.split()
    assert ".env" not in tracked, ".env must never be tracked"
    for name in tracked:
        if name.endswith(".env.example") or name == ".env.example":
            with open(os.path.join(repo, name), encoding="utf-8") as fh:
                content = fh.read()
            assert "placeholder-not-a-real-key" in content or "API_KEY=" in content
    # the example must not contain anything that looks like a live key
    with open(os.path.join(repo, ".env.example"), encoding="utf-8") as fh:
        example = fh.read()
    for line in example.splitlines():
        if line.startswith("API_KEY="):
            value = line.split("=", 1)[1].strip()
            assert value in ("", "placeholder-not-a-real-key"), (
                f".env.example must only hold a placeholder, found {value!r}")


def test_the_settings_repr_hides_the_key(set_env):
    """A stray print(settings) must not show the secret."""
    set_env(AUTH_METHOD="api_key", API_KEY=KEY)
    text = repr(get_settings())
    assert KEY not in text, "the API key is visible in the settings repr"
