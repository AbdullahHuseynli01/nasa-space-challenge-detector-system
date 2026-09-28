"""Integration tests for the public sea-ice API endpoints."""

from datetime import datetime
import math
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_cors_origins
from app.services import explanation as explanation_service


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Use the real FastAPI application and bundled datasets."""

    with TestClient(app) as test_client:
        yield test_client


def assert_number(value: object) -> None:
    """Assert that a JSON value is a finite number, not a boolean."""

    assert isinstance(value, (int, float))
    assert not isinstance(value, bool)
    assert math.isfinite(value)


def assert_trend_result(trend: dict[str, object]) -> None:
    assert set(trend) == {
        "direction",
        "sen_slope",
        "p_value",
        "significant",
    }
    assert trend["direction"] in {
        "increasing",
        "decreasing",
        "no_significant_trend",
    }
    assert_number(trend["sen_slope"])
    assert -1 <= trend["sen_slope"] <= 1
    assert_number(trend["p_value"])
    assert 0 <= trend["p_value"] <= 1
    assert isinstance(trend["significant"], bool)


def assert_period(period: dict[str, object]) -> None:
    assert set(period) == {"start", "end"}
    assert isinstance(period["start"], int)
    assert isinstance(period["end"], int)
    assert not isinstance(period["start"], bool)
    assert not isinstance(period["end"], bool)
    assert period["start"] <= period["end"]


def test_regions_returns_supported_regions(client: TestClient) -> None:
    response = client.get("/api/regions")

    assert response.status_code == 200
    assert response.json() == ["arctic", "antarctic"]


def test_variables_returns_current_dataset_variable(client: TestClient) -> None:
    response = client.get("/api/variables")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "sea_ice_fraction",
            "name": "Sea Ice Covered Fraction",
            "unit": "fraction",
            "description": "Fraction of the selected region covered by sea ice.",
        }
    ]


@pytest.mark.parametrize("region", ["arctic", "antarctic"])
def test_series_returns_clean_monthly_data(
    client: TestClient,
    region: str,
) -> None:
    response = client.get("/api/series", params={"region": region})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "region",
        "variable",
        "unit",
        "start_date",
        "end_date",
        "data",
    }
    assert payload["region"] == region
    assert payload["variable"] == "sea_ice_fraction"
    assert payload["unit"] == "fraction"
    assert payload["data"]

    dates = []
    for point in payload["data"]:
        assert set(point) == {"date", "value"}
        dates.append(datetime.fromisoformat(point["date"].replace("Z", "+00:00")))
        assert_number(point["value"])
        assert 0 <= point["value"] <= 1

    assert dates == sorted(dates)
    assert dates[0] == datetime.fromisoformat(
        payload["start_date"].replace("Z", "+00:00")
    )
    assert dates[-1] == datetime.fromisoformat(
        payload["end_date"].replace("Z", "+00:00")
    )


@pytest.mark.parametrize("region", ["arctic", "antarctic"])
def test_trend_returns_statistical_result(
    client: TestClient,
    region: str,
) -> None:
    response = client.get("/api/trend", params={"region": region})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"region", "variable", "unit", "period", "trend"}
    assert payload["region"] == region
    assert payload["variable"] == "sea_ice_fraction"
    assert payload["unit"] == "fraction"
    assert_period(payload["period"])
    assert_trend_result(payload["trend"])


@pytest.mark.parametrize("region", ["arctic", "antarctic"])
def test_analysis_returns_sorted_annual_series_and_trend(
    client: TestClient,
    region: str,
) -> None:
    response = client.get("/api/analysis", params={"region": region})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "region",
        "variable",
        "unit",
        "period",
        "annual_series",
        "trend",
    }
    assert payload["region"] == region
    assert payload["variable"] == "sea_ice_fraction"
    assert payload["unit"] == "fraction"
    assert_period(payload["period"])
    assert payload["annual_series"]

    years = []
    for point in payload["annual_series"]:
        assert set(point) == {"year", "value"}
        assert isinstance(point["year"], int)
        assert not isinstance(point["year"], bool)
        years.append(point["year"])
        assert_number(point["value"])
        assert 0 <= point["value"] <= 1

    assert years == sorted(years)
    assert len(years) == len(set(years))
    assert years[0] == payload["period"]["start"]
    assert years[-1] == payload["period"]["end"]
    assert_trend_result(payload["trend"])


def _explanation_request() -> dict[str, object]:
    return {
        "region": "arctic",
        "variable": "sea_ice_fraction",
        "period": {"start": 1948, "end": 2025},
        "trend": {
            "direction": "decreasing",
            "sen_slope": -0.0018,
            "p_value": 0.002,
            "significant": True,
        },
    }


def test_explain_uses_groq_without_recalculating(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> list[SimpleNamespace]:
            calls.update(kwargs)
            return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=("The supplied result shows a decreasing sea-ice fraction trend that is statistically significant.")))])]

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()), close=lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        explanation_service,
        "_build_client",
        lambda api_key: fake_client,
    )

    response = client.post("/api/explain", json=_explanation_request())

    assert response.status_code == 200
    assert response.json() == {
        "explanation": (
            "The supplied result shows a decreasing sea-ice fraction trend "
            "that is statistically significant."
        )
    }
    assert calls["model"] == "openai/gpt-oss-120b"
    assert "-0.0018" in calls["contents"]
    assert "0.002" in calls["contents"]
    assert "test-key" not in response.text


def test_explain_rejects_incomplete_groq_output(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCompletions:
        def create(self, **kwargs: object) -> list[SimpleNamespace]:
            return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Over the period"))])]

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()), close=lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        explanation_service,
        "_build_client",
        lambda api_key: fake_client,
    )

    response = client.post("/api/explain", json=_explanation_request())

    assert response.status_code == 502


def test_explain_rejects_api_key_in_request(
    client: TestClient,
) -> None:
    payload = _explanation_request()
    payload["api_key"] = "client-secret-that-must-not-be-accepted"

    response = client.post("/api/explain", json=payload)

    assert response.status_code == 422
    assert "client-secret-that-must-not-be-accepted" not in response.text


def test_explain_rejects_new_numeric_values(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCompletions:
        def create(self, **kwargs: object) -> list[SimpleNamespace]:
            return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="The change spans 77 years."))])]

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()), close=lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        explanation_service,
        "_build_client",
        lambda api_key: fake_client,
    )

    response = client.post("/api/explain", json=_explanation_request())

    assert response.status_code == 502


def test_explain_requires_groq_api_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    response = client.post("/api/explain", json=_explanation_request())

    assert response.status_code == 503


def test_production_requires_explicit_cors_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        get_cors_origins()


@pytest.mark.parametrize("path", ["/api/series", "/api/trend", "/api/analysis"])
def test_invalid_region_returns_bad_request(
    client: TestClient,
    path: str,
) -> None:
    response = client.get(path, params={"region": "pacific"})

    assert response.status_code == 400
    assert "detail" in response.json()
    assert "pacific" not in response.text
