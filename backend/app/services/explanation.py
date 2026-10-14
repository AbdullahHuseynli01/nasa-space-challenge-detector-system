"""Groq-generated explanations for calculated scientific results.

The model only rewords a result that Python has already calculated. Every reply
is checked before it is returned: it must state the supplied direction and
significance, must not claim causes, and may only quote numbers from the
result (rounded, or written in another common notation). A rejected reply is
retried with the reason, and temporary Groq failures are retried with backoff,
all within one time budget.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from typing import Any

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_API_KEY_ENV = "GROQ_API_KEY"

# Groq calls per explanation, including retries after a rejected reply or a
# temporary Groq failure.
MAX_ATTEMPTS = 3
# The longest one explanation may take, across all attempts and waits.
TIME_BUDGET_SECONDS = 45.0
DEFAULT_ATTEMPT_TIMEOUT_SECONDS = 20.0
# Any 429 pauses the whole dashboard until Retry-After, so a longer Groq wait
# is passed on in steps of at most this many seconds.
MAX_RETRY_AFTER_SECONDS = 60
MIN_WORDS = 5
MAX_WORDS = 100
# ExplanationResponse.explanation allows at most 1000 characters.
MAX_CHARACTERS = 1000

logger = logging.getLogger(__name__)
# Tests replace this so retries do not really wait.
_sleep = time.sleep


class ExplanationError(RuntimeError):
    """No explanation could be produced. Subclasses choose the HTTP response."""

    status_code = 502
    public_message = "Unable to generate a safe scientific explanation."

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class MissingGroqApiKeyError(ExplanationError):
    status_code = 503
    public_message = "AI explanations are not configured on this server."


class GroqConfigurationError(ExplanationError):
    """Groq refused the request itself: a bad key, unknown model or invalid parameter."""

    status_code = 503
    public_message = "AI explanations are not configured correctly on this server."


class ExplanationGenerationError(ExplanationError):
    """Groq answered, but no reply passed validation."""


class GroqBusyError(ExplanationError):
    """Groq rate-limited the server; the client may retry after ``retry_after`` seconds."""

    status_code = 429
    public_message = "The AI service is busy. Please try again shortly."


class GroqTimeoutError(ExplanationError):
    status_code = 504
    public_message = "The AI service took too long to respond. Please try again."


class GroqUnavailableError(ExplanationError):
    status_code = 502
    public_message = "The AI service could not be reached. Please try again."


class RejectedReply(Exception):
    """A reply that failed validation, with a hint for the next attempt."""

    def __init__(self, reason: str, hint: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.hint = hint


_SYSTEM_PROMPT = """You write a data insight for a NASA open-data dashboard, using only facts that Python has already calculated.
Rules:
- Mention the region, the variable, the start and end years, the trend direction, the Sen's slope with its unit, and the Mann-Kendall p-value with whether the trend is statistically significant.
- Copy every number exactly as it is written in the facts. Do not round, convert or recalculate anything, and add no other numbers: no durations, percentages or rates per decade.
- Use the exact wording given for the direction and the significance.
- Do not explain causes or mention climate change, predictions, comparisons or anything else that is not in the facts.
- Write one or two sentences, 30 to 45 words, as plain text: no heading, label, list, quotes or markdown."""

_CACHE_SIZE = 64
# Validated explanations keyed by the exact result: the data is static, so a
# repeat request is answered without another Groq call (or another chance of rejection).
_cache: OrderedDict[str, str] = OrderedDict()
_cache_lock = threading.Lock()

# Models write minus signs and ranges with several dash characters (hyphen,
# non-breaking hyphen, figure dash, en and em dash, minus sign, small and
# full-width hyphen-minus).
_DASHES = str.maketrans(dict.fromkeys([0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212, 0xFE63, 0xFF0D], "-"))
# The dashboard highlights "sea-ice fraction" and "-0.000995" only with a
# plain hyphen, so replies get one instead of gpt-oss's (non-breaking) hyphens.
_HYPHENS = str.maketrans(dict.fromkeys([0x2010, 0x2011], "-"))
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
# "1.5 × 10⁻¹⁰", "1.5 x 10^-10" and "10^(-6)", rewritten as "1.5e-10" and "1e-6".
_POWER_OF_TEN = re.compile(
    r"(?<![\w.])(?:(?P<mantissa>\d+(?:\.\d+)?)\s*[×x*·⋅]\s*)?10\s*"
    r"(?:\^\s*\(?\s*(?P<caret>[-+]?\d+)\s*\)?|(?P<superscript>[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))"
)
# "yr-1", "year^-1" and "yr^{-1}" are units, not the number -1.
_PER_YEAR_UNIT = re.compile(r"\b(?:yr|year)s?\s*\^?\s*\{?\s*-\s*1\s*\}?(?!\d)", re.I)
_NUMBER = re.compile(
    r"(?<![\w.])(?P<number>-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?)(?P<percent>\s*(?:%|per\s?cent))?",
    re.I,
)
_DIRECTION_WORDS = {
    "increasing": re.compile(
        r"\b(?:increas(?:e|es|ed|ing)|ris(?:e|es|ing)|rose|upward|grow(?:s|n|ing|th)?|grew)\b",
        re.I,
    ),
    "decreasing": re.compile(
        r"\b(?:decreas(?:e|es|ed|ing)|declin(?:e|es|ed|ing)|downward|fall(?:s|ing)?|fell|"
        r"drop(?:s|ped|ping)?|reduc(?:e|es|ed|ing|tion)|shrink(?:s|ing)?|shrank|loss|los(?:e|es|ing))\b",
        re.I,
    ),
}
_SIGNIFICANT = re.compile(r"\bsignifican(?:t|tly|ce)\b", re.I)
_NOT_SIGNIFICANT = re.compile(
    r"(?:\b(?:not|no|non)|n't)[\s-]+(?:statistically[\s-]+)?significan(?:t|ce)\b"
    r"|\b(?:in|non-?)significant\b"
    r"|\black(?:s|ing)?\s+(?:of\s+)?(?:statistical\s+)?significance\b"
    r"|\b(?:not|no)\s+(?:\w+\s+){1,3}?(?:statistical(?:ly)?\s+)?significan(?:t|ce)\b",
    re.I,
)
# "Unlikely to be due to chance" describes significance, not a cause.
_CHANCE = re.compile(
    r"\b(?:due\s+to|caused\s+by)\s+(?:random\s+)?(?:chance|variation|variability|fluctuations?|noise)\b",
    re.I,
)
_UNSUPPORTED_CLAIMS = re.compile(
    r"\b(?:because|caus(?:e|es|ed|al|ation)|due\s+to|driven\s+by|mechanisms?|impacts?\s+of|effects?\s+of|"
    r"climate\s+change|global\s+warming|warming|greenhouse|emissions?|confidence\s+intervals?)\b",
    re.I,
)
_LABEL = re.compile(r"^(?:explanation|summary|answer)\s*:\s*", re.I)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def generate_explanation(result: dict[str, Any]) -> str:
    """Return a validated explanation of ``result``, or raise an ExplanationError."""

    api_key = os.getenv(GROQ_API_KEY_ENV)
    if not api_key:
        logger.error("Explanation failed: %s is not set on the server.", GROQ_API_KEY_ENV)
        raise MissingGroqApiKeyError(f"{GROQ_API_KEY_ENV} is not configured.")

    result_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
    with _cache_lock:
        if result_json in _cache:
            _cache.move_to_end(result_json)
            return _cache[result_json]

    label = f"{result.get('region')}/{result.get('variable')}"
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _user_message(result)},
    ]
    started = time.monotonic()
    deadline = started + TIME_BUDGET_SECONDS
    failure: ExplanationError = GroqTimeoutError("The time budget ran out before Groq answered.")
    attempt = 0

    try:
        client = _build_client(api_key)
    except ExplanationError as exc:
        logger.error("Explanation failed: %s", exc)
        raise

    try:
        while attempt < MAX_ATTEMPTS and deadline - time.monotonic() >= 1:
            attempt += 1
            try:
                reply, finish_reason = _request_reply(
                    client, messages, timeout=min(_attempt_timeout(), deadline - time.monotonic())
                )
            except Exception as exc:
                failure, wait = _upstream_failure(exc, attempt)
                logger.warning(
                    "Explanation upstream error: %s (%s, attempt %d of %d)",
                    failure,
                    label,
                    attempt,
                    MAX_ATTEMPTS,
                    # Unexpected errors get a traceback; Groq's own errors are self-explanatory.
                    exc_info=type(failure) is ExplanationGenerationError,
                )
                if wait is None or attempt == MAX_ATTEMPTS or wait > deadline - time.monotonic() - 1:
                    break
                _sleep(wait)
                continue

            try:
                if finish_reason == "length":
                    raise RejectedReply(
                        "Groq stopped at the token limit before finishing",
                        "Answer in one or two short sentences.",
                    )
                explanation = _validate(reply, result)
            except RejectedReply as rejection:
                logger.warning(
                    "Explanation rejected: %s (%s, attempt %d of %d). Reply: %r",
                    rejection.reason,
                    label,
                    attempt,
                    MAX_ATTEMPTS,
                    reply[:500],
                )
                failure = ExplanationGenerationError(f"Last reply rejected: {rejection.reason}")
                # An empty reply (all tokens spent on reasoning) is simply retried:
                # Groq may refuse an assistant message with no content.
                if reply.strip():
                    messages = [
                        *messages,
                        {"role": "assistant", "content": reply},
                        {
                            "role": "user",
                            "content": f"That reply was rejected because {rejection.reason}. {rejection.hint} "
                            "Reply with the corrected explanation only.",
                        },
                    ]
                continue

            logger.info(
                "Explanation generated for %s in %.1fs (attempt %d of %d)",
                label,
                time.monotonic() - started,
                attempt,
                MAX_ATTEMPTS,
            )
            with _cache_lock:
                _cache[result_json] = explanation
                _cache.move_to_end(result_json)
                while len(_cache) > _CACHE_SIZE:
                    _cache.popitem(last=False)
            return explanation
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    logger.error(
        "Explanation failed: HTTP %d for %s after %d attempt(s) in %.1fs. %s",
        failure.status_code,
        label,
        attempt,
        time.monotonic() - started,
        failure,
    )
    raise failure


def _user_message(result: dict[str, Any]) -> str:
    """The result as ready-to-quote facts: every number is in a form the validator accepts."""

    trend = result.get("trend") or {}
    period = result.get("period") or {}
    significant = bool(trend.get("significant"))
    if significant:
        direction = str(trend.get("direction"))
        trend_text = f"statistically significant {direction} trend"
        wording = f'"{direction}" and "statistically significant"'
    else:
        trend_text = "no statistically significant trend"
        wording = f'"{trend_text}"'
    return "\n".join(
        [
            "Facts:",
            f"- Region: {str(result.get('region', '')).capitalize()}",
            f"- Variable: {str(result.get('variable', '')).replace('_', ' ')}",
            f"- Period: {period.get('start')} to {period.get('end')}",
            f"- Trend: {trend_text}",
            f"- Sen's slope: {_plain_decimal(float(trend.get('sen_slope', 0.0)))} per year",
            f"- Mann-Kendall p-value: {_p_value_text(float(trend.get('p_value', 1.0)), significant)}",
            "",
            f"Required wording: {wording}.",
        ]
    )


def _plain_decimal(value: float, digits: int = 3) -> str:
    """``value`` to ``digits`` significant digits with no exponent: -0.00099496 → "-0.000995"."""

    if value == 0:
        return "0"
    decimals = max(0, digits - 1 - math.floor(math.log10(abs(value))))
    text = f"{value:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _p_value_text(p_value: float, significant: bool) -> str:
    """A p-value as usually reported: below 0.001 as "p < 0.001", otherwise 3 significant digits."""

    if p_value < 0.001:
        return "p < 0.001"
    text = f"{p_value:.3g}"
    if significant and float(text) >= 0.05:
        # Rounding must not turn a significant p-value (below 0.05) into 0.05.
        return "p < 0.05"
    return f"p = {text}"


def _build_client(api_key: str) -> Any:
    try:
        from groq import Groq
    except ImportError as exc:
        raise GroqConfigurationError("The groq package is not installed.") from exc
    # generate_explanation retries, within its time budget, so the SDK must not.
    return Groq(api_key=api_key, timeout=_attempt_timeout(), max_retries=0)


def _attempt_timeout() -> float:
    try:
        seconds = float(os.getenv("GROQ_TIMEOUT_SECONDS", str(DEFAULT_ATTEMPT_TIMEOUT_SECONDS)))
    except ValueError:
        return DEFAULT_ATTEMPT_TIMEOUT_SECONDS
    if not math.isfinite(seconds):
        return DEFAULT_ATTEMPT_TIMEOUT_SECONDS
    return min(max(seconds, 5.0), TIME_BUDGET_SECONDS)


def _request_reply(client: Any, messages: list[dict[str, str]], timeout: float) -> tuple[str, str | None]:
    """Send one chat request; return the streamed reply text and Groq's finish reason."""

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.2,
        max_completion_tokens=1024,
        top_p=1,
        reasoning_effort="low",
        stream=True,
        stop=None,
        timeout=timeout,
    )
    parts: list[str] = []
    finish_reason = None
    for chunk in completion:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        content = getattr(getattr(choices[0], "delta", None), "content", None)
        if isinstance(content, str):
            parts.append(content)
        finish_reason = getattr(choices[0], "finish_reason", None) or finish_reason
    return "".join(parts), finish_reason


def _upstream_failure(exc: Exception, attempt: int) -> tuple[ExplanationError, float | None]:
    """Map a failed Groq call to the error to report and the wait before retrying (None: give up)."""

    import groq

    if isinstance(exc, groq.APIStatusError):
        status = exc.status_code
        if status in (429, 498):  # 498: Groq's flex tier is over capacity
            wait = _retry_after_seconds(exc.response) or _backoff(attempt)
            retry_after = max(1, min(MAX_RETRY_AFTER_SECONDS, math.ceil(wait)))
            return GroqBusyError(f"Groq rate limit (HTTP {status}): {exc}", retry_after=retry_after), wait
        if status in (408, 409) or status >= 500:
            wait = _retry_after_seconds(exc.response) or _backoff(attempt)
            return GroqUnavailableError(f"Groq error (HTTP {status}): {exc}"), wait
        return GroqConfigurationError(f"Groq refused the request (HTTP {status}): {exc}"), None
    if isinstance(exc, groq.APITimeoutError):
        return GroqTimeoutError(f"Groq did not answer in time: {exc}"), _backoff(attempt)
    if isinstance(exc, groq.APIError):
        # Connection failures, and errors Groq reports in the middle of a stream.
        return GroqUnavailableError(f"Groq request failed: {exc}"), _backoff(attempt)
    return ExplanationGenerationError(f"Unexpected error while calling Groq: {exc!r}"), None


def _retry_after_seconds(response: Any) -> float | None:
    headers = getattr(response, "headers", None) or {}
    for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        try:
            seconds = float(headers.get(name)) * scale
        except (TypeError, ValueError):
            continue
        if math.isfinite(seconds) and seconds > 0:
            return seconds
    return None


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter: up to 1 s, 2 s, 4 s … capped at 8 s."""

    return min(8.0, 2.0 ** (attempt - 1)) * random.uniform(0.5, 1.0)


def _validate(text: str, result: dict[str, Any]) -> str:
    """Return the cleaned reply, or raise RejectedReply saying what is wrong with it."""

    cleaned = _clean(text)
    words = len(cleaned.split())
    if words < MIN_WORDS:
        raise RejectedReply(f"it is incomplete ({words} words)", "Write one or two complete sentences.")
    if words > MAX_WORDS or len(cleaned) > MAX_CHARACTERS:
        raise RejectedReply(f"it is too long ({words} words)", "Write 30 to 45 words.")

    normalized = _expand_powers_of_ten(_PER_YEAR_UNIT.sub("per year", cleaned.translate(_DASHES)))
    trend = result.get("trend")
    trend = trend if isinstance(trend, dict) else {}
    _check_direction_and_significance(normalized, trend)
    _check_claims(normalized)
    _check_numbers(normalized, result, trend)
    return cleaned


def _clean(text: str) -> str:
    """Collapse whitespace, use plain hyphens, drop markdown emphasis, a leading label and wrapping quotes."""

    cleaned = _LABEL.sub("", " ".join(text.translate(_HYPHENS).replace("**", "").replace("__", "").split()))
    if len(cleaned) > 1 and cleaned[0] in "\"“" and cleaned[-1] in "\"”":
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _expand_powers_of_ten(text: str) -> str:
    def to_e_notation(match: re.Match[str]) -> str:
        exponent = (match["caret"] or match["superscript"]).translate(_SUPERSCRIPTS)
        return f"{match['mantissa'] or '1'}e{exponent}"

    return _POWER_OF_TEN.sub(to_e_notation, text)


def _check_direction_and_significance(text: str, trend: dict[str, Any]) -> None:
    direction = trend.get("direction")
    negated = _NOT_SIGNIFICANT.search(text)

    if not trend.get("significant"):
        if not negated:
            raise RejectedReply(
                "it does not say the trend is not statistically significant",
                'Say there is "no statistically significant trend".',
            )
        return

    words = _DIRECTION_WORDS.get(direction)
    if words is not None and not words.search(text):
        raise RejectedReply(f"it does not say the trend is {direction}", f'Say the trend is "{direction}".')
    if negated:
        raise RejectedReply(
            f'it says "{negated.group(0)}" about a statistically significant trend',
            'Say the trend is "statistically significant".',
        )
    if not _SIGNIFICANT.search(text):
        raise RejectedReply(
            "it does not say whether the trend is statistically significant",
            'Say the trend is "statistically significant".',
        )


def _check_claims(text: str) -> None:
    claim = _UNSUPPORTED_CLAIMS.search(_CHANCE.sub("", text))
    if claim:
        raise RejectedReply(
            f'it mentions "{claim.group(0)}", which the result does not support',
            "Do not mention causes, climate change or confidence intervals; describe only the result.",
        )


def _check_numbers(text: str, result: dict[str, Any], trend: dict[str, Any]) -> None:
    values = [abs(value) for value in _numbers_in(result)]
    levels = _significance_levels(trend.get("p_value"))
    for match in _NUMBER.finditer(text):
        token = match["number"]
        if not _number_is_supported(token, bool(match["percent"]), values, levels):
            raise RejectedReply(
                f"it contains the number {token}{'%' if match['percent'] else ''}, which is not in the result",
                "Use only the numbers in the facts, copied exactly as written.",
            )


def _numbers_in(value: Any) -> Iterator[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _numbers_in(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _numbers_in(item)


def _significance_levels(p_value: Any) -> list[float]:
    """Levels a reply may quote: 0.05 (95%) always, stricter ones only when p is below them."""

    levels = [0.05, 0.95]
    if isinstance(p_value, (int, float)) and not isinstance(p_value, bool):
        for exponent in range(2, 11):
            level = 10.0**-exponent
            if p_value < level:
                levels += [level, 1 - level]
    return levels


def _number_is_supported(token: str, percent: bool, values: list[float], levels: list[float]) -> bool:
    written = abs(float(token))
    if not math.isfinite(written):
        return False
    if percent:
        # "95% confidence", "the 1% level": conventional levels, not data values.
        return any(math.isclose(written / 100, level) for level in levels)
    if not any(char in token for char in ".eE"):
        # Whole numbers (years, counts) must appear exactly as supplied.
        return written in values
    if any(math.isclose(written, level) for level in levels):
        return True
    # Signs are not compared: "decreasing by 0.001" describes a slope of -0.000995.
    unit = _last_digit_unit(token)
    return any(_rounds_to(written, unit, value) for value in values)


def _last_digit_unit(token: str) -> float:
    """Place value of the last written digit: 0.0018 → 0.0001, 1.5e-10 → 1e-11."""

    mantissa, _, exponent = token.lower().lstrip("-").partition("e")
    return 10.0 ** (int(exponent or 0) - len(mantissa.partition(".")[2]))


def _rounds_to(written: float, unit: float, actual: float) -> bool:
    """True if ``written`` is ``actual`` rounded to the digits shown, or within 5% of it."""

    return math.isclose(written, actual, rel_tol=0.05) or abs(written - actual) <= unit / 2 * (1 + 1e-6)
