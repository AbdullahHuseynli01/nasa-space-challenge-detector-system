"""Validation, retries and error responses of the AI explanation service."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import groq
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import explanation as explanation_service


def _result(
    region: str,
    direction: str,
    sen_slope: float,
    p_value: float,
    significant: bool = True,
) -> dict[str, Any]:
    return {
        "region": region,
        "variable": "sea_ice_fraction",
        "period": {"start": 1980, "end": 2025},
        "trend": {
            "direction": direction,
            "sen_slope": sen_slope,
            "p_value": p_value,
            "significant": significant,
        },
    }


# What the dashboard sends: values rounded to 6 decimals, so Arctic's p-value is 0.
ARCTIC = _result("arctic", "decreasing", -0.000995, 0.0)
ARCTIC_UNROUNDED = _result("arctic", "decreasing", -0.0009949618541666705, 1.5489875233448501e-10)
ANTARCTIC = _result("antarctic", "increasing", 0.00049, 0.000009)
NO_TREND = _result("arctic", "no_significant_trend", 0.0003, 0.4, significant=False)
P_OF_0_002 = _result("arctic", "decreasing", -0.0018, 0.002)

VALID_ARCTIC_REPLY = (
    "From 1980 to 2025 the Arctic sea ice fraction shows a decreasing trend that is statistically significant."
)


@pytest.mark.parametrize(
    ("result", "reply"),
    [
        (ARCTIC, VALID_ARCTIC_REPLY),
        (ARCTIC, "The Arctic sea ice fraction declined between 1980 and 2025, and the decline is statistically significant."),
        # The sign is carried by "decreasing".
        (ARCTIC, "The Arctic sea ice fraction is decreasing by about 0.000995 per year, a statistically significant trend."),
        # gpt-oss often writes U+2011 (non-breaking hyphen) for minus signs and hyphens.
        (ARCTIC, "The Arctic sea\u2011ice fraction shows a decreasing trend of \u20110.000995 per year that is statistically significant."),
        (ARCTIC, "The calculated trend shows the Arctic sea ice fraction decreasing, and it is statistically significant."),
        (ARCTIC, "The Arctic sea ice fraction shows a decreasing trend that is statistically significant (p < 0.001)."),
        (ARCTIC, "The decreasing trend in Arctic sea ice fraction is statistically significant, with a p-value below the 0.05 threshold."),
        (ARCTIC, "The Arctic sea ice fraction shows a decreasing trend that is statistically significant at the 95% confidence level."),
        (ARCTIC, "The decreasing trend in Arctic sea ice fraction is statistically significant, so it is unlikely to be due to chance."),
        (ARCTIC, "**Explanation:** The Arctic sea ice fraction shows a decreasing trend that is statistically significant (p = 0.0)."),
        (ARCTIC_UNROUNDED, "The Arctic sea ice fraction shows a decreasing trend that is statistically significant (p \u2248 1.5 \u00d7 10\u207b\u00b9\u2070)."),
        (ARCTIC_UNROUNDED, "The Arctic sea ice fraction shows a decreasing trend of about 0.001 per year that is statistically significant (p = 1.55e-10)."),
        (ANTARCTIC, "The Antarctic sea ice fraction shows an increasing trend that is statistically significant (p = 9e\u201106)."),
        (ANTARCTIC, "The Antarctic sea ice fraction shows an increasing trend that is statistically significant (p \u2248 9 \u00d7 10^-6)."),
        (ANTARCTIC, "Between 1980 and 2025 the Antarctic sea ice fraction rose by 0.00049 per year, a statistically significant increase."),
        (NO_TREND, "The Arctic sea ice fraction shows no statistically significant trend between 1980 and 2025."),
        (NO_TREND, "The change in Arctic sea ice fraction from 1980 to 2025 is not statistically significant (p = 0.4)."),
        # Insights in the style the prompt asks for, with typical model typography.
        (
            ARCTIC,
            "From 1980 to 2025, Arctic sea ice fraction showed a statistically significant decreasing trend, "
            "with a Sen's slope of \u22120.000995 per year and a Mann\u2013Kendall p-value below 0.001.",
        ),
        (
            ARCTIC,
            "Between 1980 and 2025, the Arctic sea\u2011ice fraction declined at a Sen's slope of \u20110.000995 "
            "yr\u207b\u00b9; this decreasing trend is statistically significant (Mann-Kendall p < .001).",
        ),
        (
            ANTARCTIC,
            "From 1980 to 2025, Antarctic sea ice fraction rose at a Sen's slope of 0.00049 yr^-1, "
            "a statistically significant increasing trend (Mann-Kendall p < 0.001).",
        ),
        (
            ANTARCTIC,
            "Antarctic sea ice fraction increased from 1980 to 2025 (Sen's slope 0.00049 yr^{-1}), "
            "a statistically significant increasing trend with Mann-Kendall p < 0.001.",
        ),
        (
            P_OF_0_002,
            "From 1980 to 2025, Arctic sea ice fraction showed a statistically significant decreasing trend "
            "(Sen's slope -0.0018 per year, Mann-Kendall p = 0.002).",
        ),
        (
            NO_TREND,
            "From 1980 to 2025, Arctic sea ice fraction shows no statistically significant trend: "
            "the Sen's slope is 0.0003 per year and the Mann-Kendall p-value is 0.4.",
        ),
    ],
)
def test_sound_replies_are_accepted(result: dict[str, Any], reply: str) -> None:
    assert explanation_service._validate(reply, result)


@pytest.mark.parametrize(
    ("result", "reply", "reason"),
    [
        # A calculated duration is a new number.
        (ARCTIC, "The Arctic sea ice fraction shows a decreasing trend over 46 years that is statistically significant.", "number 46"),
        (ARCTIC, "The Arctic sea ice fraction is decreasing by 0.1 per year, which is statistically significant.", "number 0.1"),
        # Rates per decade and durations are calculations the prompt forbids.
        (ARCTIC, "Arctic sea ice fraction shows a statistically significant decreasing trend of -0.00995 per decade.", "number -0.00995"),
        (ARCTIC, "Over the 45-year record, Arctic sea ice fraction shows a statistically significant decreasing trend.", "number 45"),
        # A bound is allowed only when it is true.
        (P_OF_0_002, "The Arctic sea ice fraction shows a statistically significant decreasing trend (p < 0.001).", "number 0.001"),
        (ANTARCTIC, "The Antarctic sea ice fraction shows an increasing trend that is statistically significant (p \u2248 9.9 \u00d7 10\u207b\u2076).", "number 9.9e-6"),
        (ARCTIC, "The Arctic sea ice fraction shows a decreasing trend that is not statistically significant.", "not statistically significant"),
        (NO_TREND, "The Arctic sea ice fraction shows a statistically significant decreasing trend.", "not statistically significant"),
        (ARCTIC, "The Arctic sea ice fraction changed between 1980 and 2025, and the change is statistically significant.", "is decreasing"),
        (ANTARCTIC, "The Antarctic sea ice fraction shows a decreasing trend that is statistically significant.", "is increasing"),
        (ARCTIC, "The Arctic sea ice fraction shows a decreasing trend over the period.", "whether the trend is statistically significant"),
        (ARCTIC, "The Arctic sea ice fraction is decreasing significantly due to climate change.", "due to"),
        (ARCTIC, "The statistically significant decreasing trend is driven by warming.", "driven by"),
        (ARCTIC, "The decreasing trend is statistically significant within a 95% confidence interval.", "confidence interval"),
        (ARCTIC, "Decreasing and significant.", "incomplete"),
        (ARCTIC, "The Arctic sea ice fraction is decreasing and statistically significant. " * 12, "too long"),
    ],
)
def test_unsound_replies_are_rejected(result: dict[str, Any], reply: str, reason: str) -> None:
    with pytest.raises(explanation_service.RejectedReply, match=re.escape(reason)):
        explanation_service._validate(reply, result)


@pytest.mark.parametrize(
    ("result", "slope", "p_value"),
    [
        (ARCTIC, "-0.000995", "p < 0.001"),
        (ARCTIC_UNROUNDED, "-0.000995", "p < 0.001"),
        (ANTARCTIC, "0.00049", "p < 0.001"),
        (P_OF_0_002, "-0.0018", "p = 0.002"),
        (NO_TREND, "0.0003", "p = 0.4"),
        # Rounding must not make a significant p-value look like 0.05.
        (_result("arctic", "decreasing", -0.0012, 0.04996), "-0.0012", "p < 0.05"),
    ],
)
def test_the_model_gets_ready_to_quote_facts(result: dict[str, Any], slope: str, p_value: str) -> None:
    message = explanation_service._user_message(result)

    assert f"- Sen's slope: {slope} per year" in message
    assert f"- Mann-Kendall p-value: {p_value}" in message
    # No exponent notation (like Python's 9e-06) for the model to copy.
    assert not re.search(r"\d[eE][-+]?\d", message)


@pytest.mark.parametrize("result", [ARCTIC, ARCTIC_UNROUNDED, ANTARCTIC, P_OF_0_002, NO_TREND])
def test_an_insight_quoting_the_facts_passes_first_time(result: dict[str, Any]) -> None:
    facts = dict(
        line[2:].split(": ", 1)
        for line in explanation_service._user_message(result).splitlines()
        if line.startswith("- ")
    )
    trend = facts["Trend"]
    slope = facts["Sen's slope"]
    p_value = facts["Mann-Kendall p-value"]
    reply = (
        f"From {facts['Period']}, {facts['Region']} {facts['Variable']} shows "
        f"{trend if trend.startswith('no ') else 'a ' + trend}, with a Sen's slope of {slope} "
        f"and a Mann-Kendall {p_value}."
    )

    assert explanation_service._validate(reply, result) == reply


def test_cleaned_reply_uses_plain_hyphens() -> None:
    reply = (
        "Arctic sea\u2011ice fraction shows a statistically significant decreasing trend "
        "of \u20110.000995 per year."
    )

    assert explanation_service._validate(reply, ARCTIC) == (
        "Arctic sea-ice fraction shows a statistically significant decreasing trend of -0.000995 per year."
    )


def test_cleaned_reply_has_no_markdown_or_label() -> None:
    reply = '  **Explanation:**  "The Arctic sea ice fraction shows a decreasing trend that is statistically significant."  '

    assert explanation_service._validate(reply, ARCTIC) == (
        "The Arctic sea ice fraction shows a decreasing trend that is statistically significant."
    )


# --- Groq calls through the API -------------------------------------------------

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _stream(text: str, finish_reason: str = "stop") -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=text), finish_reason=finish_reason)]
        )
    ]


def _status_error(error: type[groq.APIStatusError], status: int, headers: dict[str, str] | None = None) -> groq.APIStatusError:
    body = {"error": {"message": f"Groq said no ({status}).", "type": "test"}}
    response = httpx.Response(status, headers=headers, json=body, request=httpx.Request("POST", _GROQ_URL))
    return error(f"Error code: {status} - {body}", response=response, body=body)


class ScriptedGroq:
    """Fake Groq client: each call returns or raises the next step; the last step repeats."""

    def __init__(self, *steps: object) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        step = self.steps.pop(0) if len(self.steps) > 1 else self.steps[0]
        if isinstance(step, Exception):
            raise step
        return step

    def close(self) -> None:
        pass


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record backoff waits instead of sleeping."""

    recorded: list[float] = []
    monkeypatch.setattr(explanation_service, "_sleep", recorded.append)
    return recorded


@pytest.fixture
def groq_steps(monkeypatch: pytest.MonkeyPatch):
    def install(*steps: object) -> ScriptedGroq:
        fake = ScriptedGroq(*steps)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setattr(explanation_service, "_build_client", lambda api_key: fake)
        return fake

    return install


def test_rejected_reply_is_retried_with_the_reason(client: TestClient, groq_steps, waits: list[float]) -> None:
    rejected = "The Arctic sea ice fraction shows a decreasing trend over 46 years that is statistically significant."
    fake = groq_steps(_stream(rejected), _stream(VALID_ARCTIC_REPLY))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 200
    assert response.json() == {"explanation": VALID_ARCTIC_REPLY}
    assert len(fake.calls) == 2
    assert waits == []
    retry_messages = fake.calls[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": rejected}
    assert "number 46" in retry_messages[-1]["content"]


def test_every_reply_rejected_returns_502_and_logs_each_reply(
    client: TestClient,
    groq_steps,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = groq_steps(_stream("The Arctic sea ice fraction is decreasing due to climate change and is significant."))

    with caplog.at_level(logging.INFO, logger="app"):
        response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 502
    assert response.json() == {"detail": "Unable to generate a safe scientific explanation."}
    assert len(fake.calls) == explanation_service.MAX_ATTEMPTS
    rejections = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Explanation rejected:")]
    assert len(rejections) == explanation_service.MAX_ATTEMPTS
    assert '"due to"' in rejections[0] and "climate change" in rejections[0]
    assert any(r.getMessage().startswith("Explanation failed: HTTP 502") for r in caplog.records)


def test_reply_cut_off_at_the_token_limit_is_retried(client: TestClient, groq_steps) -> None:
    fake = groq_steps(_stream("The Arctic sea ice fraction shows a", finish_reason="length"), _stream(VALID_ARCTIC_REPLY))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 200
    assert len(fake.calls) == 2


def test_empty_reply_is_retried_without_an_empty_assistant_message(client: TestClient, groq_steps) -> None:
    fake = groq_steps(_stream("", finish_reason="length"), _stream(VALID_ARCTIC_REPLY))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 200
    assert fake.calls[1]["messages"] == fake.calls[0]["messages"]


def test_groq_rate_limit_is_retried_after_its_retry_after(
    client: TestClient,
    groq_steps,
    waits: list[float],
) -> None:
    fake = groq_steps(_status_error(groq.RateLimitError, 429, {"retry-after": "3"}), _stream(VALID_ARCTIC_REPLY))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 200
    assert len(fake.calls) == 2
    assert waits == [3.0]


def test_persistent_groq_rate_limit_returns_429_with_retry_after(
    client: TestClient,
    groq_steps,
    waits: list[float],
) -> None:
    fake = groq_steps(_status_error(groq.RateLimitError, 429, {"retry-after": "2"}))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "2"
    assert response.json() == {"detail": "The AI service is busy. Please try again shortly."}
    assert len(fake.calls) == explanation_service.MAX_ATTEMPTS
    assert waits == [2.0] * (explanation_service.MAX_ATTEMPTS - 1)


def test_groq_wait_longer_than_the_budget_is_passed_to_the_client(
    client: TestClient,
    groq_steps,
    waits: list[float],
) -> None:
    fake = groq_steps(_status_error(groq.RateLimitError, 429, {"retry-after": "600"}))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 429
    # Capped: any 429 pauses the whole dashboard until Retry-After.
    assert response.headers["retry-after"] == str(explanation_service.MAX_RETRY_AFTER_SECONDS)
    assert len(fake.calls) == 1
    assert waits == []


def test_connection_error_is_retried_with_backoff(client: TestClient, groq_steps, waits: list[float]) -> None:
    fake = groq_steps(groq.APIConnectionError(request=httpx.Request("POST", _GROQ_URL)), _stream(VALID_ARCTIC_REPLY))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 200
    assert len(fake.calls) == 2
    assert len(waits) == 1 and 0.5 <= waits[0] <= 1.0


def test_groq_server_errors_return_502_after_retries(client: TestClient, groq_steps) -> None:
    fake = groq_steps(_status_error(groq.InternalServerError, 503))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 502
    assert response.json() == {"detail": "The AI service could not be reached. Please try again."}
    assert len(fake.calls) == explanation_service.MAX_ATTEMPTS


def test_groq_timeout_returns_504(client: TestClient, groq_steps) -> None:
    groq_steps(groq.APITimeoutError(request=httpx.Request("POST", _GROQ_URL)))

    response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 504
    assert response.json() == {"detail": "The AI service took too long to respond. Please try again."}


def test_invalid_groq_key_returns_503_without_retrying(
    client: TestClient,
    groq_steps,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = groq_steps(_status_error(groq.AuthenticationError, 401))

    with caplog.at_level(logging.INFO, logger="app"):
        response = client.post("/api/explain", json=ARCTIC)

    assert response.status_code == 503
    assert len(fake.calls) == 1
    # Groq's own message reaches the logs.
    assert any("Groq said no (401)" in r.getMessage() for r in caplog.records)


def test_app_logs_go_to_stdout() -> None:
    app_logger = logging.getLogger("app")

    assert app_logger.level == logging.INFO
    assert any(isinstance(handler, logging.StreamHandler) for handler in app_logger.handlers)
