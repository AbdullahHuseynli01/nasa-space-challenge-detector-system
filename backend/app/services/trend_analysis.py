"""Deterministic non-parametric trend analysis for annual sea-ice data.

The public ``analyze_trend`` function accepts the monthly ``date``/``value``
DataFrame returned by :mod:`app.services.csv_loader`. It first computes means
for complete calendar years, then applies:

* Theil-Sen estimation for Sen's slope.
* The Hamed-Rao modified Mann-Kendall test for serially correlated data.

Because the input is reduced to one observation per calendar year, a seasonal
Mann-Kendall test is not needed. The p-value uses the tie-corrected Mann-
Kendall score and a Hamed-Rao variance correction based on significant
autocorrelations of the detrended ranks. The test is interpreted at
``ALPHA = 0.05``.

Reference: Hamed and Rao, "A modified Mann-Kendall trend test for
autocorrelated data", Journal of Hydrology 204 (1998), 182-196,
doi:10.1016/S0022-1694(97)00125-X.
"""

from __future__ import annotations

from typing import Final, Literal, TypedDict

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata, theilslopes


ALPHA: Final[float] = 0.05
AUTOCORRELATION_ALPHA: Final[float] = 0.05
MIN_ANNUAL_OBSERVATIONS: Final[int] = 10
NEAR_CONSTANT_TOLERANCE: Final[float] = 1e-12

TrendDirection = Literal["increasing", "decreasing", "no_significant_trend"]


class TrendResult(TypedDict):
    """JSON-compatible result returned by the trend calculation."""

    direction: TrendDirection
    sen_slope: float
    p_value: float
    significant: bool


class InsufficientObservationsError(ValueError):
    """Raised when a trend cannot be tested with enough annual observations."""


def _require_columns(data: pd.DataFrame, columns: set[str]) -> None:
    missing = columns.difference(data.columns)
    if missing:
        missing_columns = ", ".join(sorted(missing))
        raise ValueError(f"Trend data is missing required column(s): {missing_columns}")


def annualize_time_series(data: pd.DataFrame) -> pd.DataFrame:
    """Return complete calendar-year means from a monthly time series.

    A year is included only when all twelve calendar months are present once.
    This prevents a partial terminal year, such as January 2026 in the NASA
    exports, from being treated as a complete annual observation.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("Trend data must be provided as a pandas DataFrame")

    _require_columns(data, {"date", "value"})

    dates = pd.to_datetime(data["date"], errors="coerce")
    values = pd.to_numeric(data["value"], errors="coerce")
    finite_values = pd.Series(
        np.isfinite(values.to_numpy(dtype=float, na_value=np.nan)),
        index=data.index,
    )
    valid = (
        dates.notna()
        & values.notna()
        & finite_values
        & values.ge(0)
        & values.le(1)
    )

    monthly = pd.DataFrame(
        {
            "date": dates[valid],
            "value": values[valid],
        }
    )

    if monthly.empty:
        raise InsufficientObservationsError(
            "Trend analysis requires at least "
            f"{MIN_ANNUAL_OBSERVATIONS} complete annual observations; "
            "the input contains no valid monthly observations."
        )

    monthly["year"] = monthly["date"].dt.year
    monthly["month"] = monthly["date"].dt.month

    annual = (
        monthly.groupby("year", sort=True)
        .agg(
            value=("value", "mean"),
            observations=("value", "count"),
            unique_months=("month", "nunique"),
        )
        .reset_index()
    )
    annual = annual.loc[
        (annual["observations"] == 12) & (annual["unique_months"] == 12),
        ["year", "value"],
    ]

    if len(annual) < MIN_ANNUAL_OBSERVATIONS:
        raise InsufficientObservationsError(
            "Trend analysis requires at least "
            f"{MIN_ANNUAL_OBSERVATIONS} complete annual observations; "
            f"found {len(annual)}."
        )

    return annual.reset_index(drop=True)


def _constant_series_result() -> TrendResult:
    """Return the safe result for constant or numerically near-constant data."""

    return {
        "direction": "no_significant_trend",
        "sen_slope": 0.0,
        "p_value": 1.0,
        "significant": False,
    }


def _mann_kendall_score(values: np.ndarray) -> tuple[float, float]:
    """Return the MK score and its tie-corrected independent variance."""

    n = len(values)
    score = 0.0
    for index in range(n - 1):
        score += float(np.sign(values[index + 1 :] - values[index]).sum())

    _, tie_counts = np.unique(values, return_counts=True)
    tie_counts = tie_counts[tie_counts > 1]
    tie_correction = np.sum(
        tie_counts * (tie_counts - 1) * (2 * tie_counts + 5)
    )
    variance = (
        n * (n - 1) * (2 * n + 5) - tie_correction
    ) / 18.0
    return score, float(variance)


def _modified_mann_kendall_p_value(
    years: np.ndarray,
    values: np.ndarray,
    sen_slope: float,
) -> float:
    """Return a two-sided Hamed-Rao autocorrelation-adjusted p-value.

    The annual series is detrended with the Sen slope before its values are
    ranked. Significant lag autocorrelations of those ranks inflate the
    independent Mann-Kendall variance according to the Hamed-Rao effective
    sample-size correction.
    """

    n = len(values)
    score, independent_variance = _mann_kendall_score(values)
    if score == 0 or independent_variance <= 0:
        return 1.0

    detrended = values - sen_slope * years
    ranks = rankdata(detrended, method="average")
    autocorrelation_sum = 0.0

    if np.ptp(ranks) > 0:
        autocorrelation_threshold = norm.ppf(
            1 - AUTOCORRELATION_ALPHA / 2
        ) / np.sqrt(n)
        denominator = n * (n - 1) * (n - 2)

        for lag in range(1, n - 2):
            weight = (n - lag) * (n - lag - 1) * (n - lag - 2)
            lag_correlation = np.corrcoef(
                ranks[:-lag], ranks[lag:]
            )[0, 1]
            if (
                np.isfinite(lag_correlation)
                and abs(lag_correlation) > autocorrelation_threshold
            ):
                autocorrelation_sum += weight * lag_correlation

    # Hamed-Rao uses the signed autocorrelation sum. Negative serial
    # correlation reduces the effective variance; taking abs() here would
    # change the statistical test and can produce incorrect p-values.
    correction = 1 + 2 * autocorrelation_sum / denominator
    # Guard against a numerically negative factor from noisy high-lag
    # estimates. The correction must remain strictly positive for sqrt().
    correction = max(correction, np.finfo(float).eps)
    corrected_variance = independent_variance * correction
    if score > 0:
        z_score = (score - 1) / np.sqrt(corrected_variance)
    else:
        z_score = (score + 1) / np.sqrt(corrected_variance)

    p_value = float(2 * norm.sf(abs(z_score)))
    return float(np.clip(p_value, 0.0, 1.0))


def calculate_annual_trend(annual_data: pd.DataFrame) -> TrendResult:
    """Calculate Sen's slope and a Mann-Kendall p-value for annual data.

    ``annual_data`` must contain one row per year with ``year`` and ``value``
    columns. The slope is measured in sea-ice fraction per year. A two-sided
    p-value below ``ALPHA`` marks the trend as statistically significant.
    """

    if not isinstance(annual_data, pd.DataFrame):
        raise TypeError("Annual trend data must be provided as a pandas DataFrame")

    _require_columns(annual_data, {"year", "value"})

    years = pd.to_numeric(annual_data["year"], errors="coerce")
    values = pd.to_numeric(annual_data["value"], errors="coerce")
    finite = np.isfinite(
        years.to_numpy(dtype=float, na_value=np.nan)
    ) & np.isfinite(values.to_numpy(dtype=float, na_value=np.nan))
    valid = (
        years.notna()
        & values.notna()
        & pd.Series(finite, index=annual_data.index)
        & values.ge(0)
        & values.le(1)
    )

    candidate_years = years[valid].to_numpy(dtype=float)
    if not np.equal(candidate_years, np.floor(candidate_years)).all():
        raise ValueError("Annual trend years must be whole calendar years")

    cleaned = pd.DataFrame(
        {
            "year": years[valid].astype(int),
            "value": values[valid].astype(float),
        }
    ).sort_values("year")

    if cleaned["year"].duplicated().any():
        raise ValueError("Annual trend data must contain at most one observation per year")

    if len(cleaned) < MIN_ANNUAL_OBSERVATIONS:
        raise InsufficientObservationsError(
            "Trend analysis requires at least "
            f"{MIN_ANNUAL_OBSERVATIONS} annual observations; found {len(cleaned)}."
        )

    x = cleaned["year"].to_numpy(dtype=float)
    y = cleaned["value"].to_numpy(dtype=float)

    if np.ptp(y) <= NEAR_CONSTANT_TOLERANCE:
        return _constant_series_result()

    sen_slope = float(
        theilslopes(y, x, alpha=1 - ALPHA, method="separate").slope
    )
    p_value = _modified_mann_kendall_p_value(x, y, sen_slope)

    if not np.isfinite(sen_slope) or not np.isfinite(p_value):
        return _constant_series_result()

    significant = p_value < ALPHA
    if significant and sen_slope > NEAR_CONSTANT_TOLERANCE:
        direction: TrendDirection = "increasing"
    elif significant and sen_slope < -NEAR_CONSTANT_TOLERANCE:
        direction = "decreasing"
    else:
        direction = "no_significant_trend"

    return {
        "direction": direction,
        "sen_slope": sen_slope,
        "p_value": p_value,
        "significant": significant,
    }


def analyze_trend(data: pd.DataFrame) -> TrendResult:
    """Aggregate monthly observations and calculate the annual trend."""

    annual_data = annualize_time_series(data)
    return calculate_annual_trend(annual_data)


def calculate_trend(data: pd.DataFrame) -> TrendResult:
    """Backward-friendly alias for :func:`analyze_trend`."""

    return analyze_trend(data)


def get_trend_analysis_status() -> dict[str, str]:
    """Return the current implementation status for the existing scaffold route."""

    return {
        "status": "implemented",
        "message": "Annual Sen's slope and Mann-Kendall trend analysis is available.",
    }
