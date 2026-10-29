"""Shared config for the load scenarios (tests/load/). Owner: DevOps 1.

ALL VALUES ARE PLACEHOLDERS - confirm with the lead. TARGET_URL becomes the
staging URL when it exists.

Day 2 (Phase 2) run profiles and pass limits are kept as variables at the top
of this file (RUN_PROFILES, REAL_RUN_PROFILE, PASS_MAX_*): 20 users, 50 users,
then a 10-minute sustained run; 5xx < 1 %, p95 < 2 s (mock/cached) and < 12 s
(real LLM).

Safety rules that apply to every scenario:
- Never point a load run at a real LLM provider (free-tier quota): the main
  runs use USE_MOCK=true, and the only real-mode run is the small 5-user /
  60 s one described in tests/README.md.
- Synthetic inputs only: data/ has no evaluation scenarios yet (data/README.md),
  so stages/intents come from the frozen schema (app/schemas/guide.py) and the
  free-text prompts below are made up. Never real user data.
"""
import os
import uuid

from locust import HttpUser

TARGET_URL = os.environ.get("TARGET_URL", "http://localhost:8000")
LOAD_USERS = int(os.environ.get("LOAD_USERS", "20"))           # 20 concurrent
RAMP_UP_SECONDS = int(os.environ.get("RAMP_UP_SECONDS", "30"))  # 30 s ramp-up
DURATION = os.environ.get("DURATION", "5m")                    # 5 minutes

# --- Day 2 profiles (Phase 2): 20 users, 50 users, then a 10-min sustained run.
# PLACEHOLDER until the lead confirms the final profile. Keep as variables.
RUN_PROFILES = [
    {"name": "day2_20u", "users": 20, "spawn": 1.0, "duration": "2m"},
    {"name": "day2_50u", "users": 50, "spawn": 2.0, "duration": "2m"},
    {"name": "day2_10min", "users": 20, "spawn": 0.5, "duration": "10m"},
]
# Real-LLM probe (only when a provider is wired in; contacts no provider today).
REAL_RUN_PROFILE = {"name": "real_small", "users": 5, "spawn": 1.0, "duration": "60s"}

# --- Pass criteria: PLACEHOLDER until lead confirms. Variables, not magic numbers.
PASS_MAX_5XX_PERCENT = 1.0      # 5xx error rate must stay under 1 %
PASS_MAX_P95_MOCK_MS = 2000     # p95 with mock / cached replies (ms)
PASS_MAX_P95_REAL_MS = 12000    # p95 with the real LLM (ms)
PASS_MAX_429S = 0               # no 429 during a run (limits raised for the run)

# 8 stages x 4 intents - must match the frozen schema in app/schemas/guide.py.
STAGES = ["connect", "understand", "reflect", "discuss",
          "agree", "family", "reflect_again", "decision"]
INTENTS = ["conversation_ideas", "help_me_understand",
           "next_steps", "privacy_safety"]

# Synthetic free-text prompts covering different stages. Stand-ins only until
# the evaluation owner publishes scenarios in data/.
FREE_TEXTS = [
    "How do I start a conversation about relocating for work?",
    "What should I ask before we discuss marriage?",
    "I feel nervous about bringing up family expectations.",
    "Can you help me understand what they meant by this message?",
    "What is a good next step after our first disagreement?",
    "How do I talk about career priorities without sounding selfish?",
    "Give me a question about weekend routines and hobbies.",
    "How do I say I need more time before deciding?",
    "What topics are safe to discuss in the reflect stage?",
    "How do I raise privacy concerns politely?",
]


class SetuUser(HttpUser):
    """Base class: target host and one synthetic session per virtual user.

    The session id stays stable for the whole run so the response cache
    behaves the way it would for one real user.
    """
    host = TARGET_URL
    abstract = True

    def on_start(self):
        token = uuid.uuid4().hex[:8]
        self.user_id = f"load_user_{token}"
        self.match_id = f"load_match_{token}"

    def payload_quick_action(self, stage=None, intent=None):
        """Quick action payload: intent set, no message (cacheable shape)."""
        import random
        return {
            "user_id": self.user_id,
            "match_id": self.match_id,
            "stage": stage or random.choice(STAGES),
            "intent": intent or random.choice(INTENTS),
        }

    def payload_free_text(self):
        """Free-text payload: message set, no intent (never cacheable)."""
        import random
        return {
            "user_id": self.user_id,
            "match_id": self.match_id,
            "stage": random.choice(STAGES),
            "message": random.choice(FREE_TEXTS),
        }
