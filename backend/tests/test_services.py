"""Focused unit tests for data preparation and statistical analysis."""

import numpy as np
import pandas as pd
import pytest

from app.services import csv_loader
from app.services.csv_loader import load_csv
from app.services.trend_analysis import (
    annualize_time_series,
    calculate_annual_trend,
)


def test_bundled_csvs_load_and_partial_terminal_year_is_excluded() -> None:
    frame = load_csv("arctic")

    assert not frame.empty
    assert frame["date"].is_monotonic_increasing
    assert frame["value"].between(0, 1).all()

    annual = annualize_time_series(frame)

    assert len(annual) == 46
    assert annual["year"].iloc[0] == 1980
    assert annual["year"].iloc[-1] == 2025


def test_annualization_requires_all_twelve_unique_months() -> None:
    dates = pd.date_range("2020-01-01", "2021-01-01", freq="MS")
    data = pd.DataFrame({"date": dates, "value": 0.5})

    annual = annualize_time_series(data)

    assert annual.to_dict("records") == [{"year": 2020, "value": 0.5}]


def test_csv_loader_rejects_duplicate_timestamps(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "duplicate.csv"
    path.write_text(
        "Time,Sea Ice Fraction\n"
        "2020-01-01,0.4\n"
        "2020-01-01,0.5\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(csv_loader.DATASET_PATHS, "duplicate", path)

    with pytest.raises(ValueError, match="duplicate timestamps"):
        csv_loader.load_csv("duplicate")


def test_monotonic_annual_series_has_expected_sen_slope() -> None:
    years = np.arange(2000, 2020)
    annual = pd.DataFrame(
        {
            "year": years,
            "value": 0.1 + 0.01 * np.arange(len(years)),
        }
    )

    result = calculate_annual_trend(annual)

    assert result["direction"] == "increasing"
    assert result["significant"] is True
    assert result["sen_slope"] == pytest.approx(0.01)
    assert 0 <= result["p_value"] < 0.05


def test_constant_annual_series_is_not_significant() -> None:
    annual = pd.DataFrame(
        {
            "year": np.arange(2000, 2010),
            "value": np.full(10, 0.5),
        }
    )

    result = calculate_annual_trend(annual)

    assert result == {
        "direction": "no_significant_trend",
        "sen_slope": 0.0,
        "p_value": 1.0,
        "significant": False,
    }


def test_exactly_linear_series_does_not_crash() -> None:
    years = np.arange(2000, 2020)
    # Exact binary fractions make every detrended rank identical.
    annual = pd.DataFrame({"year": years, "value": 0.25 + (years - 2000) / 1024})

    result = calculate_annual_trend(annual)

    assert result["direction"] == "increasing"
    assert result["significant"] is True
    assert result["sen_slope"] == pytest.approx(1 / 1024)


@pytest.mark.parametrize(
    ("region", "direction", "low", "high"),
    [("arctic", "decreasing", 1e-11, 1e-9), ("antarctic", "increasing", 1e-6, 1e-4)],
)
def test_bundled_p_values_use_standard_autocorrelation(
    region: str, direction: str, low: float, high: float
) -> None:
    # The overlapping-segment estimator used to report 3.6e-12 and exactly 0.
    result = calculate_annual_trend(annualize_time_series(load_csv(region)))

    assert result["direction"] == direction
    assert low < result["p_value"] < high
