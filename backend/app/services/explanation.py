"""Gemini-generated explanations for already-calculated scientific results."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_GEMINI_TIMEOUT_SECONDS = 120.0
DEFAULT_GEMINI_THINKING_BUDGET = 0
logger = logging.getLogger(__name__)


class MissingGeminiApiKeyError(RuntimeError):
    """Raised when the Gemini API key is not configured."""


class ExplanationGenerationError(RuntimeError):
    """Raised when Gemini cannot produce a safe explanation."""


class IncompleteExplanationError(ExplanationGenerationError):
    """Raised when Gemini returns too little usable text."""


_SYSTEM_PROMPT = """You are a scientific explanation editor, not a data analyst.

The user message contains an analysis result calculated by Python. Treat every
value in that JSON as authoritative. Write one or two concise, neutral
scientific sentences (maximum 80 words) explaining only what the supplied
result observes.

Strict rules:
- Never calculate, recalculate, derive, or reinterpret a trend, Sen's slope,
  p-value, or statistical significance.
- Use the supplied direction and significance fields as facts; do not infer
  them from numbers.
- Mention statistical significance when the supplied significant field is true
  or false, as appropriate.
- If you include a number, copy it exactly from the JSON. Do not convert units,
  round values, calculate percentages, compare against thresholds, or calculate
  the number of years.
- Prefer omitting all numerical values from the explanation. Never introduce a
  new number.
- Do not invent NASA data, observations, units, or causes. No causal evidence is
  supplied, so do not discuss causes or mechanisms.
- Return a complete sentence that names the supplied variable and uses the
  exact supplied direction word.
- Also state whether the supplied trend is statistically significant.
- Never return a fragment such as "Over the period" by itself.
- Return only the explanation text, with no heading, bullets, JSON, or markdown.
"""

_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
)
_UNSUPPORTED_CAUSAL_LANGUAGE = re.compile(
    r"\b(?:because|caus(?:e|al|ed|es)|due to|driven by|attributed to|"
    r"result(?:s|ed|ing)? from|mechanism|impact of|effect of)\b",
    re.IGNORECASE,
)
_UNSAFE_STATISTICAL_LANGUAGE = re.compile(
    r"(?:\bp\s*(?:-\s*)?value\s*[<>]=?|\b(?:less|greater|below|above)\s+"
    r"(?:than|the)|\b(?:re)?calculat(?:e|ed|ing)|\bthreshold\b|"
    r"\bconfidence interval\b)",
    re.IGNORECASE,
)


def _timeout_milliseconds() -> int:
    try:
        seconds = float(
            os.getenv("GEMINI_TIMEOUT_SECONDS", str(DEFAULT_GEMINI_TIMEOUT_SECONDS))
        )
    except ValueError:
        seconds = DEFAULT_GEMINI_TIMEOUT_SECONDS
    return int(min(max(seconds, 5.0), 300.0) * 1000)


def _thinking_budget() -> int:
    """Keep short editor responses from spending the output budget on reasoning."""

    try:
        budget = int(
            os.getenv(
                "GEMINI_THINKING_BUDGET",
                str(DEFAULT_GEMINI_THINKING_BUDGET),
            )
        )
    except ValueError:
        budget = DEFAULT_GEMINI_THINKING_BUDGET
    return min(max(budget, 0), 24576)


def _build_client(api_key: str) -> Any:
    """Build the official Google GenAI client lazily."""

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - deployment configuration
        raise ExplanationGenerationError(
            "The google-genai package is required for Gemini explanations."
        ) from exc

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=_timeout_milliseconds()),
    )


def _validate_explanation(text: str, result: dict[str, Any]) -> str:
    """Reject output that introduces calculations, causes, or new numbers."""

    explanation = text.strip()
    if not explanation:
        raise IncompleteExplanationError("The AI provider returned an empty explanation.")
    if len(explanation.split()) < 5:
        raise IncompleteExplanationError("The AI provider returned an incomplete explanation.")
    if len(explanation.split()) > 80:
        raise ExplanationGenerationError("The AI provider returned an overly long explanation.")

    trend = result.get("trend", {})
    direction = trend.get("direction") if isinstance(trend, dict) else None
    if isinstance(direction, str) and direction.lower() not in explanation.lower():
        raise IncompleteExplanationError(
            "The AI provider omitted the supplied trend direction."
        )
    if "significant" not in explanation.lower():
        raise IncompleteExplanationError(
            "The AI provider omitted statistical significance."
        )

    if _UNSUPPORTED_CAUSAL_LANGUAGE.search(explanation):
        raise ExplanationGenerationError(
            "The AI provider returned an unsupported causal explanation."
        )
    if _UNSAFE_STATISTICAL_LANGUAGE.search(explanation):
        raise ExplanationGenerationError(
            "The AI provider returned a statistical calculation or comparison."
        )

    allowed_numbers = set(
        _NUMBER_PATTERN.findall(json.dumps(result, ensure_ascii=False))
    )
    returned_numbers = _NUMBER_PATTERN.findall(explanation)
    if any(number not in allowed_numbers for number in returned_numbers):
        raise ExplanationGenerationError(
            "The AI provider introduced a numerical value not present in the result."
        )

    return explanation


def _extract_text(response: Any) -> str:
    """Read only normal text parts and ignore Gemini metadata parts."""

    candidates = getattr(response, "candidates", None) or []
    text_parts: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "thought", False):
                continue
            text = getattr(part, "text", None)
            if isinstance(text, str):
                text_parts.append(text)

    if text_parts:
        return "\n".join(text_parts).strip()

    # Keeps mocked clients and older SDK response shapes compatible.
    text = getattr(response, "text", None)
    return text.strip() if isinstance(text, str) else ""


def generate_explanation(result: dict[str, Any]) -> str:
    """Generate a safe explanation from a Python-validated analysis result."""

    api_key = os.getenv(GEMINI_API_KEY_ENV)
    if not api_key:
        raise MissingGeminiApiKeyError(f"{GEMINI_API_KEY_ENV} is not configured.")

    result_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
    prompt = "Explain this authoritative, already-calculated result:\n" + result_json
    client = None

    try:
        from google.genai import types

        client = _build_client(api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                # Gemini 2.5 counts thought tokens inside max_output_tokens.
                # Disable thinking here because this endpoint only edits an
                # already-calculated result and needs a short visible answer.
                thinking_config=types.ThinkingConfig(
                    thinking_budget=_thinking_budget()
                ),
                max_output_tokens=256,
                temperature=0.2,
            ),
        )
        explanation = _extract_text(response)
    except ExplanationGenerationError as exc:
        logger.warning("AI explanation rejected: %s", exc)
        raise
    except Exception as exc:
        logger.exception(
            "Gemini explanation request failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        raise ExplanationGenerationError(
            "The Gemini explanation service is unavailable."
        ) from exc
    finally:
        if client is not None:
            client.close()

    if not isinstance(explanation, str):
        raise ExplanationGenerationError(
            "The Gemini explanation service returned an invalid response."
        )

    try:
        return _validate_explanation(explanation, result)
    except ExplanationGenerationError as exc:
        logger.warning("AI explanation failed safety validation: %s", exc)
        raise
