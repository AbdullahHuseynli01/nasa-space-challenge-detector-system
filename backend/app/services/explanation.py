"""Groq-generated explanations for calculated scientific results."""
from __future__ import annotations
import json, logging, math, os, re, threading
from collections import OrderedDict
from typing import Any

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_API_KEY_ENV = "GROQ_API_KEY"
logger = logging.getLogger(__name__)

class MissingGroqApiKeyError(RuntimeError): pass
class ExplanationGenerationError(RuntimeError): pass
class IncompleteExplanationError(ExplanationGenerationError): pass

_SYSTEM_PROMPT = """You are a scientific explanation editor, not a data analyst. The user message contains an analysis result calculated by Python. Treat every value in that JSON as authoritative. Write one or two concise, neutral scientific sentences (maximum 80 words). Never calculate or reinterpret values, trends, slopes, p-values, or significance. Use supplied direction and significant fields as facts. Do not invent data, units, causes, or mechanisms. Return only explanation text, with no heading, bullets, JSON, or markdown. Name the supplied variable, use the exact supplied direction word, and state whether the trend is statistically significant."""
_NUMBER = re.compile(r"(?<![\w.])-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?")
_CACHE_SIZE = 64
# Validated explanations keyed by the exact result: the data is static, so a
# repeat request is answered without another Groq call (or another chance of rejection).
_cache: OrderedDict[str, str] = OrderedDict()
_cache_lock = threading.Lock()
_BAD = re.compile(r"\b(?:because|caus(?:e|al|ed|es)|due to|driven by|mechanism|impact of|effect of)\b|\b(?:re)?calculat(?:e|ed|ing)\b|\bthreshold\b|\bconfidence interval\b", re.I)

def clear_cache() -> None:
    with _cache_lock: _cache.clear()

def _build_client(api_key: str) -> Any:
    try:
        from groq import Groq
    except ImportError as exc:
        raise ExplanationGenerationError("The groq package is required for explanations.") from exc
    try: timeout = min(max(float(os.getenv("GROQ_TIMEOUT_SECONDS", "120")), 5), 300)
    except ValueError: timeout = 120.0
    return Groq(api_key=api_key, timeout=timeout)

def _supported(token: str, supplied: list[float]) -> bool:
    """Whole numbers (years, counts) must match exactly; decimals may be rounded (5%)."""
    value = float(token)
    if not any(c in token for c in ".eE"): return value in supplied
    return any(math.isclose(value, s, rel_tol=0.05, abs_tol=1e-6) for s in supplied)

def _validate(text: str, result: dict[str, Any]) -> str:
    text = text.strip(); words = text.split()
    if len(words) < 5: raise IncompleteExplanationError("The AI provider returned an incomplete explanation.")
    if len(words) > 80: raise ExplanationGenerationError("The AI provider returned an overly long explanation.")
    trend = result.get("trend", {}); direction = trend.get("direction") if isinstance(trend, dict) else None
    if isinstance(direction, str) and not any(form in text.lower() for form in (direction.lower(), direction.replace("_", " ").lower())): raise IncompleteExplanationError("The supplied trend direction is missing.")
    if "significant" not in text.lower() or _BAD.search(text): raise ExplanationGenerationError("The AI provider returned unsafe scientific language.")
    supplied = [float(n) for n in _NUMBER.findall(json.dumps(result, ensure_ascii=False))] + [0.05]
    if not all(_supported(n, supplied) for n in _NUMBER.findall(text.replace("\u2212", "-"))): raise ExplanationGenerationError("The AI provider introduced an unsupported number.")
    return text

def _stream_text(completion: Any) -> str:
    out = []
    for chunk in completion:
        choices = getattr(chunk, "choices", []) or []
        if choices:
            content = getattr(getattr(choices[0], "delta", None), "content", None)
            if isinstance(content, str): out.append(content)
    return "".join(out)

def generate_explanation(result: dict[str, Any]) -> str:
    key = os.getenv(GROQ_API_KEY_ENV)
    if not key: raise MissingGroqApiKeyError(f"{GROQ_API_KEY_ENV} is not configured.")
    cache_key = json.dumps(result, ensure_ascii=False, sort_keys=True)
    with _cache_lock:
        if cache_key in _cache:
            _cache.move_to_end(cache_key)
            return _cache[cache_key]
    client = None
    try:
        client = _build_client(key)
        completion = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role":"system","content":_SYSTEM_PROMPT},{"role":"user","content":"Explain this authoritative, already-calculated result:\n" + cache_key}], temperature=0.2, max_completion_tokens=1024, top_p=1, reasoning_effort="low", stream=True, stop=None)
        text = _validate(_stream_text(completion), result)
    except (MissingGroqApiKeyError, ExplanationGenerationError): raise
    except Exception as exc:
        logger.exception("Groq explanation request failed: %s", exc)
        raise ExplanationGenerationError("The Groq explanation service is unavailable.") from exc
    finally:
        if client is not None and hasattr(client, "close"): client.close()
    with _cache_lock:
        _cache[cache_key] = text
        _cache.move_to_end(cache_key)
        while len(_cache) > _CACHE_SIZE: _cache.popitem(last=False)
    return text
