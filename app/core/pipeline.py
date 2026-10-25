import json
import sys
import os

from app.config import get_settings
from app.core.llm_provider import OpenAILLMProvider


# Add project root to Python path
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from app.core.router import route_intent

from app.core.llm_provider import (
    MockLLMProvider,
    GeminiLLMProvider
)

from app.core.responder import (
    create_response,
    validate_response
)


from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

PROMPT_FILES = {
    "conversation_ideas": PROMPT_DIR / "conversation_ideas.txt",
    "help_me_understand": PROMPT_DIR / "help_me_understand.txt",
    "next_steps": PROMPT_DIR / "next_steps.txt",
    "privacy_safety": PROMPT_DIR / "privacy_safety.txt",
}

def load_prompt(
    intent,
    user_message,
    journey_stage="Not provided",
    retrieved_context="Not provided"
):
    """
    Load the prompt template for the selected intent
    and insert the available context.
    """

    prompt_file = PROMPT_FILES.get(intent)

    if not prompt_file:
        return None

    with open(
    prompt_file,
    "r",
    encoding="utf-8"
) as file:

        prompt = file.read()

    prompt = prompt.replace(
        "[USER_MESSAGE]",
        user_message
    )

    prompt = prompt.replace(
        "[JOURNEY_STAGE]",
        journey_stage
    )

    prompt = prompt.replace(
        "[RETRIEVED_CONTEXT]",
        retrieved_context
    )

    return prompt



def get_provider(use_gemini=False):
    """Select a provider using shared application settings."""

    settings = get_settings()

    # Mock mode always takes priority.
    if settings.use_mock:
        return MockLLMProvider()

    if settings.llm_provider == "openai":
        return OpenAILLMProvider(
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if settings.llm_provider == "gemini" or use_gemini:
        return GeminiLLMProvider()

    raise ValueError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )


def run_pipeline(
    user_message,
    quick_action=None,
    journey_stage="Not provided",
    retrieved_context="Not provided",
    use_gemini=False
):
    """
    Run the complete Sambandh Setu response pipeline.

    Flow:

    User message
        ↓
    Intent Router
        ↓
    Prompt selection
        ↓
    LLM Provider
        ↓
    JSON validation
        ↓
    Template fallback
    """

    # Step 1: Determine intent
    intent = route_intent(
        user_message,
        quick_action
    )

    # Step 2: Handle unknown intent
    if intent is None:

        return {
            "intent": None,
            "response": [
                "I could not confidently understand your request. "
                "Please try asking your question in a little more detail."
            ]
        }

    # Step 3: Build prompt
    prompt = load_prompt(
        intent,
        user_message,
        journey_stage,
        retrieved_context
    )


    # Step 4: Select provider and retry up to two attempts.
    llm_result = None

    try:
        provider = get_provider()

        for attempt in range(2):
            try:
                candidate = provider.generate(prompt)

                if validate_response(candidate):
                    llm_result = candidate
                    break

                print(
                    f"Invalid LLM response on attempt {attempt + 1}."
                )

            except Exception as error:
                print(
                    f"LLM provider failed on attempt "
                    f"{attempt + 1}: {type(error).__name__}"
                )

    except Exception as error:
        print(
            f"LLM provider initialization failed: "
            f"{type(error).__name__}"
        )

    # Step 5: Return a valid response if one was obtained.
    if llm_result is not None:
        return llm_result

    # Step 6: Template fallback.
    return create_response(intent, user_message)


def handle_request(request, use_gemini=False):
    """
    Integration interface for the backend.

    Expected request format:

    {
        "message": "What can we talk about?",
        "quick_action": null,
        "journey_stage": "Connect",
        "retrieved_context": "Optional retrieved context"
    }
    """

    user_message = request.get(
        "message",
        ""
    )

    quick_action = request.get(
        "quick_action"
    )

    journey_stage = request.get(
        "journey_stage",
        "Not provided"
    )

    retrieved_context = request.get(
        "retrieved_context",
        "Not provided"
    )

    return run_pipeline(
        user_message=user_message,
        quick_action=quick_action,
        journey_stage=journey_stage,
        retrieved_context=retrieved_context,
        use_gemini=use_gemini
    )


if __name__ == "__main__":

    test_cases = [

        {
            "message": "What can we talk about?",
            "quick_action": None,
            "journey_stage": "Connect",
            "retrieved_context": (
                "Both users want to get to know "
                "each other better."
            )
        },

        {
            "message": "Can you explain this to me?",
            "quick_action": None,
            "journey_stage": "Understand",
            "retrieved_context": (
                "The users are discussing expectations."
            )
        },

        {
            "message": "What should we discuss next?",
            "quick_action": None,
            "journey_stage": "Reflect",
            "retrieved_context": (
                "The previous discussion covered "
                "shared interests."
            )
        },

        {
            "message": "Is my information private?",
            "quick_action": "privacy_safety",
            "journey_stage": "Connect",
            "retrieved_context": (
                "No additional context provided."
            )
        }
    ]

    for test in test_cases:

        print("\nUser Message:")
        print(test["message"])

        print("Quick Action:")
        print(test["quick_action"])

        print("Journey Stage:")
        print(test["journey_stage"])

        result = run_pipeline(
            user_message=test["message"],
            quick_action=test["quick_action"],
            journey_stage=test["journey_stage"],
            retrieved_context=test["retrieved_context"],
            use_gemini=False
        )

        print("\nPipeline Response:")
        print(
            json.dumps(
                result,
                indent=2
            )
        )

        print("-" * 60)
