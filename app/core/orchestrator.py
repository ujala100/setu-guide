"""Pipeline: route -> input safety -> context -> retrieve -> generate -> output safety.

Owner: lead. Connects intern 3's router/prompts/responder and intern 2's retriever.
The API layer calls handle(); its schema (GuideRequest / GuideResponse) is frozen.
"""
import logging
import os
import re
from typing import List, Optional, Tuple

from app.core import pipeline
from app.core.responder import SUPPORTED_INTENTS, create_response, validate_response
from app.core.router import route_intent
from app.rag.retriever import retrieve_for_orchestrator
from app.safety import guard
from app.schemas.guide import GuideRequest, GuideResponse, Intent, Safety, SafetyStatus

logger = logging.getLogger("setu.guide.core")

QUICK_ACTION_LABELS = {
    Intent.conversation_ideas: "Conversation ideas",
    Intent.help_me_understand: "Help me understand",
    Intent.next_steps: "Tips for next steps",
    Intent.privacy_safety: "Privacy & safety",
}
CONVERSATION_INTRO = "Here are some questions you can explore. Choose the ones that feel right."
UNKNOWN_REPLY = ("I could not confidently understand your request. Please try asking in a little "
                 "more detail, or choose one of the quick actions.")

# Explicit privacy/safety words always get privacy/safety guidance (unless a quick action is set).
PRIVACY_WORDS = re.compile(r"\b(privacy|private|safe|safety|consent|confidential)\b", re.I)

TEMPLATES = {  # last-resort answers if anything above raises
    Intent.conversation_ideas: (CONVERSATION_INTRO,
                                ["What does a typical day look like for you?",
                                 "How do you like to spend your weekends?"]),
    Intent.help_me_understand: ("I can compare what you've both chosen to share. Ask about the things you haven't discussed yet.", []),
    Intent.next_steps: ("Take it at your own pace. Pick one topic for this stage and talk it through.", []),
    Intent.privacy_safety: ("I only use details people choose to share, and I can't reveal private answers. You can pause or leave a journey at any time.", []),
}

# Only these consented fields ever reach retrieval or the LLM. Anything else
# (private reflections, readiness answers, contact details) is dropped here.
ALLOWED_FIELDS = {"interests", "lifestyle", "relationship_priorities", "partner_type",
                  "relocation", "career_importance", "languages", "location"}


def _allowed(d):
    return {k: v for k, v in (d or {}).items() if k in ALLOWED_FIELDS}


def _strip_markers(text: str) -> str:
    """Remove characters that could break out of the prompt delimiters or placeholders."""
    return re.sub(r"[<>\[\]\r\n\t]+", " ", str(text)).strip()


def _clean(value, limit: int = 200) -> str:
    text = ", ".join(map(str, value)) if isinstance(value, (list, tuple, set)) else str(value)
    return _strip_markers(text)[:limit]


# ----------------------------------------------------------------- routing
def _detect(req: GuideRequest) -> Optional[Intent]:
    if req.intent:                       # a quick action always wins
        return req.intent
    text = req.message or ""
    if PRIVACY_WORDS.search(text):
        return Intent.privacy_safety
    try:
        found = route_intent(text, None)
    except Exception:
        found = None
    return Intent(found) if found in SUPPORTED_INTENTS else None


def route(req: GuideRequest) -> Intent:
    return _detect(req) or Intent.conversation_ideas


# ----------------------------------------------------------------- context / retrieval
def build_context(req: GuideRequest) -> dict:
    return {"stage": req.stage.value, "topic": req.topic, "message": req.message or "",
            "profiles": {"viewer": _allowed((req.context or {}).get("viewer")),
                         "match": _allowed((req.context or {}).get("match"))}}


def retrieve(intent: Intent, ctx: dict, query: str) -> List[dict]:
    return retrieve_for_orchestrator(intent, ctx, query, k=3)   # [{"id","text","topic","source"}]


# ----------------------------------------------------------------- generation
def _context_text(ctx: dict, chunks: List[dict]) -> str:
    lines = ["Guidance:"] + [f"- {_strip_markers(c['text'])}" for c in chunks]
    shared = []
    for who, label in (("viewer", "You"), ("match", "Your match")):
        for key, value in (ctx.get("profiles", {}).get(who) or {}).items():
            shared.append(f"- {label} - {key.replace('_', ' ')}: {_clean(value)}")
    if shared:
        lines += ["Shared details (each person chose to share these):"] + shared
    return "\n".join(lines)[:3000]


def _gemini_settings() -> Tuple[bool, Optional[str]]:
    """Use Gemini only when USE_MOCK=false and a key is set."""
    try:
        from app.config import get_settings
        s = get_settings()
        return (not s.use_mock) and bool(s.llm_api_key), s.llm_api_key
    except Exception:
        return False, None


_gemini = None


def _provider():
    global _gemini
    use_gemini, key = _gemini_settings()
    if not use_gemini:
        return pipeline.get_provider(use_gemini=False)
    if _gemini is None:
        os.environ.setdefault("GEMINI_API_KEY", key)    # intern 3's provider reads this name
        _gemini = pipeline.get_provider(use_gemini=True)
    return _gemini


def generate(intent: Intent, ctx: dict, chunks: List[dict]) -> Tuple[str, List[str], List[str], bool]:
    """Returns (reply, questions, chips, fallback_used)."""
    message = _clean(ctx.get("message") or ctx.get("topic") or "", 500)
    if not message:
        message = f"(quick action: {QUICK_ACTION_LABELS[intent]})"
    stage_label = ctx["stage"].replace("_", " ").title()
    prompt = pipeline.load_prompt(intent.value, message, stage_label, _context_text(ctx, chunks))
    if prompt is None:
        raise ValueError("no prompt for intent")

    result = _provider().generate(prompt)
    if result is not None and validate_response(result) and result.get("intent") == intent.value:
        items, fallback = [s.strip() for s in result["response"] if s.strip()], False
    else:
        items, fallback = create_response(intent.value, message)["response"], True
    if not items:
        items, fallback = create_response(intent.value, message)["response"], True

    if intent == Intent.conversation_ideas:
        reply, questions = CONVERSATION_INTRO, items[:5]
    else:
        reply, questions = "\n".join(items), []
    chips = [label for i, label in QUICK_ACTION_LABELS.items() if i != intent]
    return reply, questions, chips, fallback


# ----------------------------------------------------------------- entry point
def handle(req: GuideRequest) -> GuideResponse:
    detected = _detect(req)
    intent = detected or Intent.conversation_ideas

    in_flags = guard.check_input(req.message or "")
    if in_flags:
        return GuideResponse(intent=intent, reply=guard.safe_reply(in_flags),
                             safety=Safety(status=SafetyStatus.blocked, flags=in_flags),
                             fallback_used=True)
    if detected is None:
        return GuideResponse(intent=intent, reply=UNKNOWN_REPLY,
                             chips=list(QUICK_ACTION_LABELS.values()))
    out_flags = []
    try:
        ctx = build_context(req)
        chunks = retrieve(intent, ctx, req.message or req.topic or "")
        reply, questions, chips, fallback = generate(intent, ctx, chunks)
        out_flags = guard.check_output(" ".join([reply] + questions))
        if out_flags:
            raise ValueError("output failed safety")
        return GuideResponse(intent=intent, reply=reply, questions=questions[:5], chips=chips[:4],
                             sources=[c["id"] for c in chunks], fallback_used=fallback)
    except Exception as exc:
        logger.warning("generation_failed type=%s", type(exc).__name__)   # never the message text
        text, qs = TEMPLATES[intent]
        status = SafetyStatus.modified if out_flags else SafetyStatus.passed
        return GuideResponse(intent=intent, reply=text, questions=qs,
                             safety=Safety(status=status, flags=out_flags), fallback_used=True)
