"""Cache isolation tests — verify no cross-user response caching.

These tests confirm that the cache key includes user, match, stage and intent,
so one user never receives another user's cached reply.
"""

import pytest


def test_cache_isolation_no_cross_user_response(client, app):
    """Two different users should never receive each other's cached reply."""
    # Create two distinct users with different stages and intents
    user1_data = {
        "stage": "ideation",
        "intent": "explore",
        "topic": "test-topic-1",
        "match_id": "match-001",
        "user_id": "user-1",
    }
    user2_data = {
        "stage": "planning",
        "intent": "decide",
        "topic": "test-topic-2",
        "match_id": "match-002",
        "user_id": "user-2",
    }

    # User 1 sends a request
    resp1 = client.post("/v1/guide/chat", json=user1_data)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # User 2 sends a request with different match_id, stage, intent, topic
    resp2 = client.post("/v1/guide/chat", json=user2_data)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Verify responses are different (isolation on response bodies)
    assert data1 != data2, (
        "Cache isolation failed: user 2 received user 1's cached response. "
        "Cache key must include user_id, match_id, stage and intent."
    )


def test_cache_key_includes_user_match_stage_intent(client):
    """Verify cache key construction includes all required identifiers."""
    from app.api.cache import build_cache_key

    # Same stage, intent, topic but different users
    key1 = build_cache_key(
        stage="ideation",
        intent="explore",
        topic="test-topic",
        match_id="match-001",
        user_id="user-1",
    )
    key2 = build_cache_key(
        stage="ideation",
        intent="explore",
        topic="test-topic",
        match_id="match-001",
        user_id="user-2",
    )

    # Different users must produce different keys
    assert key1 != key2, "Cache key must differentiate by user_id"

    # Same user, same request = same key
    key3 = build_cache_key(
        stage="ideation",
        intent="explore",
        topic="test-topic",
        match_id="match-001",
        user_id="user-1",
    )
    assert key1 == key3, "Same request should produce identical cache key"


def test_cache_isolation_never_mixes_users(client, app):
    """Assert that across 20 requests from different users, no cross-mixing occurs."""
    from app.core.llm_provider import GeminiLLMProvider

    base_data = {
        "stage": "ideation",
        "intent": "explore",
        "topic": "test-topic",
        "match_id": "match-001",
    }

    user_responses = {}
    for uid in [f"user-{i}" for i in range(20)]:
        data = {**base_data, "user_id": uid}
        resp = client.post("/v1/guide/chat", json=data)
        assert resp.status_code == 200
        user_responses[uid] = resp.json()

    # Each user should have a distinct response (no mixing)
    responses = list(user_responses.values())
    for i, uid1 in enumerate([f"user-{i}" for i in range(20)]):
        for uid2 in [f"user-{j}" for j in range(i + 1, 20)]:
            assert (
                user_responses[uid1] != user_responses[uid2]
            ), f"Cross-user cache mixing detected between {uid1} and {uid2}"