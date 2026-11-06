
import os
import sys
from pathlib import Path

from app.config import get_settings
from app.core.llm_provider import (
    MockLLMProvider,
    GeminiLLMProvider,
    OpenAILLMProvider,
)
from app.core.responder import validate_response, create_response


# Add project root to Python path.
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)


PROMPT_FILES = {
    "conversation": "conversation_ideas.txt",
    "conversation_ideas": "conversation_ideas.txt",
    "understand": "help_me_understand.txt",
    "help_me_understand": "help_me_understand.txt",
    "next_steps": "next_steps.txt",
    "privacy_safety": "privacy_safety.txt",
}


def load_prompt(
    intent,
    user_message="",
    journey_stage="",
    retrieved_context="",
    stage=None,
):
    """Load a prompt and replace its context placeholders."""
    intent = getattr(intent, "value", intent)
    filename = PROMPT_FILES.get(intent)

    if not filename:
        return ""

    prompt_path = Path(__file__).resolve().parent / "prompts" / filename

    try:
        template = prompt_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    # Support both the older stage= argument and journey_stage=.
    if stage is not None:
        journey_stage = stage

    return (
        template
        .replace("[JOURNEY_STAGE]", str(journey_stage or "Not specified"))
        .replace("[USER_MESSAGE]", str(user_message or "Not specified"))
        .replace(
            "[RETRIEVED_CONTEXT]",
            str(retrieved_context or "No additional context available."),
        )
    )


def get_provider(use_gemini=False):
    """Select the configured LLM provider."""
    settings = get_settings()

    # Keep automated tests independent of external APIs.
    if settings.use_mock:
        return MockLLMProvider()

    if use_gemini or settings.llm_provider == "gemini":
        return GeminiLLMProvider()

    if settings.llm_provider == "openai":
        return OpenAILLMProvider(
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def run_pipeline(
    user_message,
    quick_action=None,
    journey_stage="",
    retrieved_context="",
    use_gemini=False,
):
    """Route, prompt, validate, retry, and fall back safely."""
    from app.core.router import route_intent

    # A quick action takes priority over free-text classification.
    intent = route_intent(
        user_message,
        quick_action=quick_action,
    )
    intent = getattr(intent, "value", intent)

    prompt = load_prompt(
        intent,
        user_message=user_message,
        journey_stage=journey_stage,
        retrieved_context=retrieved_context,
    )

    # Include a clear fallback prompt if a template is unavailable.
    if not prompt:
        prompt = (
            "Return a valid JSON response with an intent and a list "
            "of response strings.\n"
            f"Intent: {intent}\n"
            f"User message: {user_message}\n"
            f"Journey stage: {journey_stage or 'Not specified'}\n"
            f"Retrieved context: "
            f"{retrieved_context or 'No additional context available.'}"
        )

    # Obtain the provider. Calling without arguments preserves
    # compatibility with existing tests that replace get_provider.
    try:
        provider = get_provider()
    except Exception as error:
        print(
            "LLM provider initialization failed: "
            f"{type(error).__name__}"
        )
        return create_response(intent, user_message)

    # Retry once after an exception or invalid response.
    for attempt in range(2):
        try:
            candidate = provider.generate(prompt)

            if validate_response(candidate):
                return candidate

            print(f"Invalid LLM response on attempt {attempt + 1}.")

        except Exception as error:
            print(
                f"LLM provider failed on attempt {attempt + 1}: "
                f"{type(error).__name__}"
            )

    return create_response(intent, user_message)


def handle_request(request, use_gemini=False):
    """Handle a string request or a dictionary containing a message."""
    if isinstance(request, dict):
        user_message = (
            request.get("message")
            or request.get("user_message")
            or ""
        )
        quick_action = request.get("quick_action")
        journey_stage = request.get("journey_stage", "")
        retrieved_context = request.get("retrieved_context", "")
    else:
        user_message = str(request or "")
        quick_action = None
        journey_stage = ""
        retrieved_context = ""

    return run_pipeline(
        user_message,
        quick_action=quick_action,
        journey_stage=journey_stage,
        retrieved_context=retrieved_context,
        use_gemini=use_gemini,
    )
