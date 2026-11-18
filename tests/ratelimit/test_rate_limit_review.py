"""Phase 2 Day 3: rate-limit review (tests/ratelimit/).

Standalone audit evidence for the Day-3 checklist:
- per-user and per-IP N+1 -> 429 rate_limited + Retry-After
- one user at the limit does not affect other users
- /health is never limited
- bypass attempts: user_id format/case, X-Forwarded-For spoofing with
  TRUSTED_PROXY=false, many user_ids from one IP (IP limit backstop)
- the service stays up under a burst, and the limiter's memory stays bounded

Some checks overlap tests/test_day2_rate_limit.py on purpose: this suite is
the Day-3 audit artifact and pins every behaviour under review in one place.

Owner: DevOps 1 (app/api). Synthetic data only.
"""
from app.api.ratelimit import _MAX_KEYS, limiter

CHAT = "/v1/guide/chat"
BASE = {"user_id": "u1", "match_id": "m1", "stage": "connect", "intent": "next_steps"}


def _post(client, headers=None, **overrides):
    return client.post(CHAT, json={**BASE, **overrides}, headers=headers)


def _assert_rate_limited(response):
    """Every rejection is 429 rate_limited with a usable Retry-After."""
    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "rate_limited"
    assert error["details"] == []
    assert int(response.headers["Retry-After"]) >= 1


# --- 1. N+1 limits ------------------------------------------------------------

def test_user_n_plus_one_is_429_rate_limited_with_retry_after(client, set_env):
    set_env(RATE_LIMIT_PER_USER="3/minute", RATE_LIMIT_PER_IP="1000/minute")
    for _ in range(3):
        assert _post(client).status_code == 200
    _assert_rate_limited(_post(client))


def test_ip_n_plus_one_is_429_rate_limited_with_retry_after(client, set_env):
    set_env(RATE_LIMIT_PER_USER="1000/minute", RATE_LIMIT_PER_IP="3/minute")
    for i in range(3):
        assert _post(client, user_id=f"u{i}").status_code == 200
    _assert_rate_limited(_post(client, user_id="u_next"))


# --- 2. isolation between users ----------------------------------------------

def test_user_at_the_limit_does_not_affect_other_users(client, set_env):
    set_env(RATE_LIMIT_PER_USER="2/minute", RATE_LIMIT_PER_IP="1000/minute")
    assert _post(client, user_id="a").status_code == 200
    assert _post(client, user_id="a").status_code == 200
    _assert_rate_limited(_post(client, user_id="a"))
    # b starts with a full quota even though a is exhausted ...
    assert _post(client, user_id="b").status_code == 200
    assert _post(client, user_id="b").status_code == 200
    # ... and a's blocked request never consumed b's quota.
    _assert_rate_limited(_post(client, user_id="a"))
    assert _post(client, user_id="b").status_code == 429, "b used exactly its own 2"


def test_health_is_never_rate_limited(client, set_env):
    set_env(RATE_LIMIT_PER_USER="2/minute", RATE_LIMIT_PER_IP="2/minute")
    assert _post(client).status_code == 200
    assert _post(client).status_code == 200
    _assert_rate_limited(_post(client))  # chat budget is exhausted
    for _ in range(20):
        assert client.get("/health").status_code == 200


# --- 3. bypass attempts -------------------------------------------------------

def test_forwarded_for_spoof_is_ignored_when_trusted_proxy_is_false(client, set_env):
    """A client forging X-Forwarded-For must stay in its one real-IP bucket."""
    set_env(RATE_LIMIT_PER_USER="1000/minute", RATE_LIMIT_PER_IP="3/minute",
            TRUSTED_PROXY="false")
    for i in range(3):
        spoof = {"X-Forwarded-For": f"10.9.8.{i}"}
        assert _post(client, user_id=f"u{i}", headers=spoof).status_code == 200
    # 4th request: a different forged header, same real client -> still blocked.
    _assert_rate_limited(
        _post(client, user_id="u3", headers={"X-Forwarded-For": "10.9.8.99"}))


def test_many_user_ids_from_one_ip_still_hit_the_ip_limit(client, set_env):
    """Rotating user_ids must not dodge the per-IP limit."""
    set_env(RATE_LIMIT_PER_USER="1000/minute", RATE_LIMIT_PER_IP="5/minute")
    statuses = [_post(client, user_id=f"rotating_{i}").status_code for i in range(10)]
    assert statuses[:5] == [200] * 5
    assert statuses[5:] == [429] * 5
    _assert_rate_limited(_post(client, user_id="rotating_again"))


def test_user_id_format_and_case_variants_share_the_same_quota(client, set_env):
    """Fix gap A: case/whitespace variants of one id used to mint a fresh
    bucket each (limit 3/min -> 12+ requests got through). The bucket key is
    now normalised (strip + casefold), so variants share the quota."""
    set_env(RATE_LIMIT_PER_USER="3/minute", RATE_LIMIT_PER_IP="1000/minute")
    for _ in range(3):
        assert _post(client, user_id="u1").status_code == 200
    for variant in ("U1", " u1", "u1 ", "u1\xa0", "U1 "):
        _assert_rate_limited(_post(client, user_id=variant))
    # Normalisation is scoped: a genuinely different id keeps its own quota.
    assert _post(client, user_id="u0001").status_code == 200


# --- 4. the service stays up under a burst -------------------------------------

def test_service_stays_up_under_a_burst(client, set_env):
    set_env(RATE_LIMIT_PER_USER="5/minute", RATE_LIMIT_PER_IP="10/minute")
    statuses = [_post(client).status_code for _ in range(200)]
    assert set(statuses) <= {200, 429}, f"unexpected status in burst: {set(statuses)}"
    assert statuses.count(200) == 5, "burst must respect the configured limit"
    for _ in range(5):
        assert client.get("/health").status_code == 200
    limiter.reset()  # window elapsed
    assert _post(client).status_code == 200, "service must recover after the window"


def test_limiter_memory_stays_bounded_under_distinct_user_ids():
    """Fix gap B: _sweep only dropped day-old buckets, so a flood of fresh
    distinct ids grew _hits past _MAX_KEYS (probe: 11 001 keys at cap 10 000)
    - unbounded memory under a high-cardinality attack. Buckets over the cap
    are now evicted least-recently-used first."""
    quota = 1_000_000
    window = 60
    ip = ("ip:203.0.113.9", quota, window)
    for i in range(_MAX_KEYS + 1_000):
        allowed, _, _ = limiter.hit([(f"user:flood_{i}", quota, window), ip])
        assert allowed, "flood ids are under the configured quota"
    assert len(limiter._hits) <= _MAX_KEYS, "limiter dict must stay bounded"
    # Eviction is least-recently-used: the active IP bucket survives the flood.
    allowed, blocked, _ = limiter.hit([("ip:203.0.113.9", 1, window)])
    assert not allowed and blocked == "ip:203.0.113.9"
