
import json


SUPPORTED_INTENTS = {
    "conversation_ideas",
    "help_me_understand",
    "next_steps",
    "privacy_safety",
}


def create_response(intent, user_message):
    """Create a template response when the LLM is unavailable."""

    responses = {
        "conversation_ideas": [
            "What is something you both enjoy discussing?",
            "What is something you would like to understand better about each other?",
            "What topic would you both feel comfortable talking about?",
        ],
        "help_me_understand": [
            "Let's break the topic down into simpler points.",
            "You can look at the different perspectives involved.",
            "If something is still unclear, you can ask a more specific question.",
        ],
        "next_steps": [
            "You could discuss the topic openly with each other.",
            "You could identify what is still unclear.",
            "You could decide together what you would like to discuss next.",
        ],
        "privacy_safety": [
            "Please review the available privacy and safety information before sharing sensitive information.",
            "Avoid sharing unnecessary personal or sensitive details.",
            "If you have a specific privacy concern, ask about that concern directly.",
        ],
    }

    if intent not in SUPPORTED_INTENTS:
        return {
            "intent": None,
            "response": [
                "I could not confidently identify the request."
            ],
        }

    return {
        "intent": intent,
        "response": responses[intent],
    }


def validate_response(response):
    """Validate the internal responder response structure."""

    try:
        parsed = json.loads(json.dumps(response))

        if not isinstance(parsed, dict):
            return False

        if parsed.get("intent") not in SUPPORTED_INTENTS:
            return False

        items = parsed.get("response")

        if not isinstance(items, list) or not items:
            return False

        return all(isinstance(item, str) for item in items)

    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    result = create_response(
        "conversation_ideas",
        "What can we talk about?",
    )

    print(json.dumps(result, indent=2))
    print("Validation Result:", validate_response(result))
