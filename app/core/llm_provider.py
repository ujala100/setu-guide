
import os
import json
from google import genai
import logging
import time
from openai import OpenAI

logger = logging.getLogger("setu.guide.llm")

class LLMProvider:
    def generate(self, prompt):
        raise NotImplementedError(
            "LLM provider has not been configured yet."
        )


class MockLLMProvider(LLMProvider):

    def generate(self, prompt):

        prompt_lower = prompt.lower()

        # Identify the intent from the prompt's specific instruction.
        if (
            "conversation ideas" in prompt_lower
            or "suggest conversation" in prompt_lower
        ):
            return {
                "intent": "conversation_ideas",
                "response": [
                    "What is something you both enjoy discussing?",
                    "What is something you would like to understand better about each other?",
                    "What topic would you both feel comfortable talking about?"
                ]
            }

        if (
            "help me understand" in prompt_lower
            or "explain the topic" in prompt_lower
            or "explain the situation" in prompt_lower
        ):
            return {
                "intent": "help_me_understand",
                "response": [
                    "Let's break the topic down into simpler points.",
                    "You can look at the different perspectives involved.",
                    "If something is still unclear, you can ask a more specific question."
                ]
            }

        if (
            "next steps" in prompt_lower
            or "what to do next" in prompt_lower
        ):
            return {
                "intent": "next_steps",
                "response": [
                    "You could discuss the topic openly with each other.",
                    "You could identify what is still unclear.",
                    "You could decide together what you would like to discuss next."
                ]
            }

        if (
            "privacy and safety" in prompt_lower
            or "privacy or safety" in prompt_lower
            or "privacy_safety" in prompt_lower
        ):
            return {
                "intent": "privacy_safety",
                "response": [
                    "Please review the available privacy and safety information before sharing sensitive information.",
                    "Avoid sharing unnecessary personal or sensitive details.",
                    "If you have a specific privacy concern, ask about that concern directly."
                ]
            }

        return {
            "intent": None,
            "response": [
                "I could not confidently identify the request."
            ]
        }



class GeminiLLMProvider(LLMProvider):
    MODEL = "gemini-3.8-flash"

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set."
            )

        self.client = genai.Client(
            api_key=api_key,
            http_options={"timeout": 10000},
        )

    def generate(self, prompt):
        start = time.perf_counter()

        try:
            interaction = self.client.interactions.create(
                model=self.MODEL,
                input=prompt,
            )
            output_text = interaction.output_text.strip()

            usage = getattr(interaction, "usage", None)
            if usage is None:
                logger.info(
                    "provider=gemini usage_available=false"
                )
            else:
                input_tokens = getattr(
                    usage, "total_input_tokens", 0
                ) or 0
                output_tokens = getattr(
                    usage, "total_output_tokens", 0
                ) or 0
                total_tokens = getattr(
                    usage, "total_tokens",
                    input_tokens + output_tokens,
                ) or 0

                # Estimates for the model's configured pricing.
                estimated_cost = (
                    input_tokens * 0.30
                    + output_tokens * 2.50
                ) / 1_000_000

                logger.info(
                    "provider=gemini input_tokens=%s "
                    "output_tokens=%s total_tokens=%s "
                    "estimated_cost_usd=%.10f latency_ms=%.2f",
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost,
                    (time.perf_counter() - start) * 1000,
                )

            output_text = output_text.removeprefix(
                "```json"
            ).removeprefix("```").strip()

            if output_text.endswith("```"):
                output_text = output_text[:-3].strip()

            return json.loads(output_text)

        except Exception as error:
            logger.warning(
                "Gemini request or response processing failed: %s",
                type(error).__name__,
            )
            return None


class OpenAILLMProvider(LLMProvider):
    MODEL = "gpt-4.1-mini"

    def __init__(self, api_key=None, timeout_seconds=10.0):
        api_key = api_key or os.environ.get("LLM_API_KEY")
        if not api_key:
            raise ValueError(
                "LLM_API_KEY is required for the OpenAI provider."
            )

        self.client = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    def generate(self, prompt):
        start = time.perf_counter()

        try:
            result = self.client.responses.create(
                model=self.MODEL,
                input=prompt,
                text={"format": {"type": "json_object"}},
            )

            usage = getattr(result, "usage", None)
            if usage is None:
                logger.info(
                    "provider=openai usage_available=false"
                )
            else:
                input_tokens = getattr(
                    usage, "input_tokens", 0
                ) or 0
                output_tokens = getattr(
                    usage, "output_tokens", 0
                ) or 0
                total_tokens = getattr(
                    usage, "total_tokens",
                    input_tokens + output_tokens,
                ) or 0

                logger.info(
                    "provider=openai input_tokens=%s "
                    "output_tokens=%s total_tokens=%s latency_ms=%.2f",
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    (time.perf_counter() - start) * 1000,
                )

            output_text = result.output_text.strip()
            output_text = output_text.removeprefix(
                "```json"
            ).removeprefix("```").strip()

            if output_text.endswith("```"):
                output_text = output_text[:-3].strip()

            return json.loads(output_text)

        except Exception as error:
            logger.warning(
                "OpenAI request or response processing failed: %s",
                type(error).__name__,
            )
            return None
