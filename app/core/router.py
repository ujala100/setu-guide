
# Sambandh Setu - Intent Router

SUPPORTED_INTENTS = {
    "conversation_ideas",
    "help_me_understand",
    "next_steps",
    "privacy_safety",
}


def route_intent(user_message, quick_action=None):
    """
    Determine the user's intent.

    A valid quick action takes priority over free-text classification.
    Return None when no confident keyword match is found.
    """

    # Rule 1: Quick action takes priority.
    if quick_action in SUPPORTED_INTENTS:
        return quick_action

    # Rule 2: Handle empty messages.
    if not isinstance(user_message, str) or not user_message.strip():
        return None

    message = user_message.lower().strip()

    # Rule 3: Conversation ideas.
    conversation_keywords = [
        "what can we talk",
        "what should we talk",
        "what do we talk",
        "conversation",
        "questions to ask",
        "questions can we ask",
        "questions to discuss",
        "topics to discuss",
        "things to talk",
        "things we can discuss",
        "what topics",
        "conversation ideas",
        "talk about",
        "discuss with each other",
        "hum kya baat karein",
        "em matladali",
    ]

    if any(keyword in message for keyword in conversation_keywords):
        return "conversation_ideas"

    # Rule 4: Help me understand.
    understand_keywords = [
        "explain",
        "don't understand",
        "do not understand",
        "what does this mean",
        "what does that mean",
        "meaning",
        "clarify",
        "confused about",
        "help me understand",
        "mujhe samjhao",
        "ardham kaaledu",
    ]

    if any(keyword in message for keyword in understand_keywords):
        return "help_me_understand"

    # Rule 5: Next steps.
    next_step_keywords = [
        "what should we do next",
        "what should we discuss next",
        "what can we do next",
        "what do we do next",
        "what are the next steps",
        "next step",
        "next steps",
        "what next",
        "where do we go from here",
        "what can we do from here",
        "ab kya karein",
        "next em cheyyali",
        "ippudu em cheyyali",
    ]

    if any(keyword in message for keyword in next_step_keywords):
        return "next_steps"

    # Rule 6: Privacy and safety.
    privacy_keywords = [
        "private",
        "privacy",
        "personal information",
        "my information",
        "who can see",
        "data",
        "safe",
        "safety",
        "consent",
        "data handled",
        "information handled",
        "what information should i avoid",
        "meri information kaun dekh sakta hai",
        "should i share my personal details",
        "personal details",
    ]

    if any(keyword in message for keyword in privacy_keywords):
        return "privacy_safety"

    # Rule 7: No confident match.
    return None


def detect_intent(user_message, quick_action=None):
    """Compatibility alias for callers using detect_intent()."""
    return route_intent(user_message, quick_action)


if __name__ == "__main__":
    test_messages = [
        "What can we talk about?",
        "Can you explain this to me?",
        "What should we discuss next?",
        "Is my information private?",
        "hum kya baat karein",
        "mujhe samjhao",
        "next em cheyyali",
        "Hello, I have a question.",
    ]

    for message in test_messages:
        print(f"Message: {message}")
        print(f"Intent: {route_intent(message)}")
        print("-" * 50)
