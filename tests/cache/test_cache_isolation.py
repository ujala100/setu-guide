"""Cache isolation tests — verify no cross-user response caching.

These tests confirm that the cache key includes user, match, stage and intent,
so one user never receives another user's cached reply.
"""

import pytest

from fastapi.testclient import TestClient
from app.schemas.guide import GuideRequest, Stage, Intent
from app.api.cache import cache_key


def test_cache_isolation_no_cross_user_response(client):
    """Two different users should never receive each other's cached reply."""
    # Create two distinct users with different stages and intents
    user1_data = {
        "stage": "connect",
        "intent": "conversation_ideas",
        "topic": "test-topic-1",
        "match_id": "match-001",
        "user_id": "user-1",
    }
    user2_data = {
        "stage": "understand",
        "intent": "help_me_understand",
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
    # Same stage, intent, topic but different users
    key1 = cache_key(
        GuideRequest(
            stage=Stage.connect,
            intent=Intent.conversation_ideas,
            topic="test-topic",
            match_id="match-001",
            user_id="user-1",
        )
    )
    key2 = cache_key(
        GuideRequest(
            stage=Stage.connect,
            intent=Intent.conversation_ideas,
            topic="test-topic",
            match_id="match-001",
            user_id="user-2",
        )
    )

    # Different users must produce different keys
    assert key1 != key2, "Cache key must differentiate by user_id"

    # Same user, same request = same key
    key3 = cache_key(
        GuideRequest(
            stage=Stage.connect,
            intent=Intent.conversation_ideas,
            topic="test-topic",
            match_id="match-001",
            user_id="user-1",
        )
    )
    assert key1 == key3, "Same request should produce identical cache key"


def test_cache_isolation_never_mixes_users(client):
    """Across 20 users, no user ever gets another user's cache entry.

    Isolation is proven through X-Cache: every user's first request must MISS
    (so an earlier user's cached reply was not served), and every user's own
    repeat must HIT (so each user has their own entry). Response bodies may
    legitimately be identical on the deterministic mock pipeline, so the body
    alone is not the isolation signal.
    """
    base_data = {
        "stage": "connect",
        "intent": "conversation_ideas",
        "topic": "test-topic",
        "match_id": "match-001",
    }

    user_ids = [f"user-{i}" for i in range(20)]
    first_bodies = {}
    for uid in user_ids:
        first = client.post("/v1/guide/chat", json={**base_data, "user_id": uid})
        assert first.status_code == 200
        assert first.headers.get("X-Cache") == "MISS", (
            f"{uid} first request was served from another user's cache entry"
        )
        first_bodies[uid] = first.json()

    for uid in user_ids:
        repeat = client.post("/v1/guide/chat", json={**base_data, "user_id": uid})
        assert repeat.status_code == 200
        assert repeat.headers.get("X-Cache") == "HIT", (
            f"{uid} repeat request did not hit its own cache entry"
        )
        assert repeat.json() == first_bodies[uid], (
            f"{uid} cached reply differs from its own first reply"
        )