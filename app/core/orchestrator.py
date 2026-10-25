"""Pipeline: route -> input safety -> context -> retrieve -> generate -> output safety.

Owner: lead. Connects intern 3's router/prompts/responder and intern 2's retriever.
The API layer calls handle(); its schema (GuideRequest / GuideResponse) is frozen.
"""
import logging
import os
import re
from typing import List, Optional, Tuple

from app.core import pipeline
from app.core.llm_provider import MockLLMProvider
from app.core.responder import SUPPORTED_INTENTS, create_response, validate_response
from app.core.router import route_intent
from app.rag.retriever import retrieve as rag_retrieve
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


# Knowledge-base topics that make a user-facing answer for each quick action, plus the
# roadmap-sourced global chunks that are written for users (not rules for the assistant).
ANSWER_TOPICS = {
    Intent.conversation_ideas: ("conversation_starters",),
    Intent.help_me_understand: ("stage_description", "checklist"),
    Intent.next_steps: ("tips", "next_steps"),
    Intent.privacy_safety: ("privacy_consent", "safety"),
}
USER_FACING_GLOBAL = {"KB-GLOBAL-031", "KB-GLOBAL-032", "KB-GLOBAL-033", "KB-GLOBAL-035", "KB-GLOBAL-036",
                      "KB-GLOBAL-037", "KB-GLOBAL-038", "KB-GLOBAL-039", "KB-GLOBAL-040"}


def _chips(intent: Intent) -> List[str]:
    return [label for i, label in QUICK_ACTION_LABELS.items() if i != intent]


def _tidy(text: str) -> str:
    text = re.sub(r"^(Tip|Next step|Try):\s*", "", text.strip())
    return text[:1].upper() + text[1:]


def _extractive(intent: Intent, ctx: dict):
    """Answer straight from the verified knowledge-base chunks for this stage (no LLM).
    Returns (reply, questions, source_ids) or None when nothing usable was found."""
    stage = ctx["stage"]
    query = ctx.get("message") or ctx.get("topic") or ""
    hits = rag_retrieve(query, stage, intent.value, k=10)
    usable = [h for h in hits if h["topic"] in ANSWER_TOPICS[intent]
              and (h["stage"] == stage or h["chunk_id"] in USER_FACING_GLOBAL)]
    if not usable:
        return None
    if intent == Intent.conversation_ideas:
        questions: List[str] = []
        for h in usable:
            for q in re.findall(r"'([^']+\?)'", h["text"]):
                if q not in questions:
                    questions.append(q)
        if not questions:
            return None
        return CONVERSATION_INTRO, questions[:5], [h["chunk_id"] for h in usable]
    picked = usable[:3]
    return "\n".join(_tidy(h["text"]) for h in picked), [], [h["chunk_id"] for h in picked]


def _template(intent: Intent, message: str):
    items = create_response(intent.value, message)["response"]
    if intent == Intent.conversation_ideas:
        return CONVERSATION_INTRO, items[:5]
    return "\n".join(items), []


def generate(intent: Intent, ctx: dict, chunks: List[dict]) -> Tuple[str, List[str], List[str], bool, List[str]]:
    """Returns (reply, questions, chips, fallback_used, source_ids).

    No API key (mock provider): answer from the knowledge base. With a real LLM: build the
    prompt from the retrieved chunks and use the model's JSON answer. If the model fails or
    returns something invalid, fall back to the knowledge-base answer, then to a template.
    """
    message = _clean(ctx.get("message") or ctx.get("topic") or "", 500)
    default_sources = [c["id"] for c in chunks]
    provider = _provider()

    if isinstance(provider, MockLLMProvider):
        built = _extractive(intent, ctx)
        if built:
            reply, questions, used = built
            return reply, questions, _chips(intent), False, used
        reply, questions = _template(intent, message)
        return reply, questions, _chips(intent), True, default_sources

    prompt = pipeline.load_prompt(
        intent.value, message or f"(quick action: {QUICK_ACTION_LABELS[intent]})",
        ctx["stage"].replace("_", " ").title(), _context_text(ctx, chunks))
    try:
        result = provider.generate(prompt) if prompt else None
    except Exception as exc:                     # model down, quota, timeout...
        logger.warning("llm_failed type=%s", type(exc).__name__)    # never the message text
        result = None
    if result is not None and validate_response(result) and result.get("intent") == intent.value:
        items = [t.strip() for t in result["response"] if t.strip()]
        if items:
            if intent == Intent.conversation_ideas:
                return CONVERSATION_INTRO, items[:5], _chips(intent), False, default_sources
            return "\n".join(items), [], _chips(intent), False, default_sources

    built = _extractive(intent, ctx)
    if built:
        reply, questions, used = built
        return reply, questions, _chips(intent), True, used
    reply, questions = _template(intent, message)
    return reply, questions, _chips(intent), True, default_sources


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
        reply, questions, chips, fallback, sources = generate(intent, ctx, chunks)
        out_flags = guard.check_output(" ".join([reply] + questions))
        if out_flags:
            raise ValueError("output failed safety")
        return GuideResponse(intent=intent, reply=reply, questions=questions[:5], chips=chips[:4],
                             sources=sources, fallback_used=fallback)
    except Exception as exc:
        logger.warning("generation_failed type=%s", type(exc).__name__)   # never the message text
        text, qs = TEMPLATES[intent]
        status = SafetyStatus.modified if out_flags else SafetyStatus.passed
        return GuideResponse(intent=intent, reply=text, questions=qs,
                             safety=Safety(status=status, flags=out_flags), fallback_used=True)
