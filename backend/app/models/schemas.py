"""Validated Pydantic schemas for the sea-ice API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchemaBase(BaseModel):
    """Shared strict configuration for API schemas."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Region(str, Enum):
    """Supported polar regions."""

    ARCTIC = "arctic"
    ANTARCTIC = "antarctic"


class Variable(str, Enum):
    """Supported scientific variables."""

    SEA_ICE_FRACTION = "sea_ice_fraction"


class Unit(str, Enum):
    """Units supported by the current variable."""

    FRACTION = "fraction"


class VariableMetadata(SchemaBase):
    """Metadata describing a variable exposed by the API."""

    id: Variable
    name: str
    unit: Unit
    description: str


class Period(SchemaBase):
    """Inclusive calendar-year period."""

    start: int = Field(ge=1, le=9999)
    end: int = Field(ge=1, le=9999)

    @model_validator(mode="after")
    def validate_order(self) -> "Period":
        if self.start > self.end:
            raise ValueError("period.start must be less than or equal to period.end")
        return self


class TimeSeriesPoint(SchemaBase):
    """One timestamped sea-ice fraction observation."""

    date: datetime
    value: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


# Descriptive alias for callers that prefer the longer name.
TimeSeriesDataPoint = TimeSeriesPoint


class TimeSeriesResponse(SchemaBase):
    """Clean time-series data returned to the frontend."""

    region: Region
    variable: Variable
    unit: Unit
    start_date: datetime
    end_date: datetime
    data: list[TimeSeriesPoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time_series_order(self) -> "TimeSeriesResponse":
        dates = [point.date for point in self.data]

        if self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")

        try:
            is_sorted = dates == sorted(dates)
        except TypeError as exc:
            raise ValueError(
                "time-series dates must use a consistent timezone format"
            ) from exc

        if not is_sorted:
            raise ValueError("time-series data must be sorted by date ascending")

        if len(dates) != len(set(dates)):
            raise ValueError("time-series data must not contain duplicate dates")

        if dates and (self.start_date != dates[0] or self.end_date != dates[-1]):
            raise ValueError("start_date and end_date must match the time-series bounds")

        return self


class TrendDirection(str, Enum):
    """Allowed classifications for a tested trend."""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    NO_SIGNIFICANT_TREND = "no_significant_trend"


class TrendResult(SchemaBase):
    """Statistical result for an annual sea-ice trend."""

    direction: TrendDirection
    sen_slope: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    p_value: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    significant: bool

    @model_validator(mode="after")
    def validate_consistency(self) -> "TrendResult":
        expected_significance = self.p_value < 0.05
        if self.significant != expected_significance:
            raise ValueError(
                "significant must equal (p_value < 0.05)"
            )

        if not self.significant:
            if self.direction is not TrendDirection.NO_SIGNIFICANT_TREND:
                raise ValueError(
                    "non-significant results must use direction "
                    "'no_significant_trend'"
                )
            return self

        if self.direction is TrendDirection.INCREASING and self.sen_slope <= 0:
            raise ValueError("increasing trends must have a positive sen_slope")
        if self.direction is TrendDirection.DECREASING and self.sen_slope >= 0:
            raise ValueError("decreasing trends must have a negative sen_slope")
        if self.direction is TrendDirection.NO_SIGNIFICANT_TREND:
            raise ValueError(
                "significant results must be classified as increasing or decreasing"
            )

        return self


class TrendResponse(SchemaBase):
    """Complete trend response matching the frontend contract."""

    region: Region
    variable: Variable
    unit: Unit
    period: Period
    trend: TrendResult


class AnnualSeriesPoint(SchemaBase):
    """One annual mean sea-ice fraction observation."""

    year: int = Field(ge=1, le=9999)
    value: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class AnalysisResponse(SchemaBase):
    """Complete annual series and trend result for a region."""

    region: Region
    variable: Variable
    unit: Unit
    period: Period
    annual_series: list[AnnualSeriesPoint] = Field(min_length=1)
    trend: TrendResult

    @model_validator(mode="after")
    def validate_annual_series(self) -> "AnalysisResponse":
        years = [point.year for point in self.annual_series]

        if years != sorted(years):
            raise ValueError("annual_series must be sorted by year ascending")

        if len(years) != len(set(years)):
            raise ValueError("annual_series must not contain duplicate years")

        if years[0] != self.period.start or years[-1] != self.period.end:
            raise ValueError("period must match the annual_series bounds")

        return self


class ExplanationRequest(SchemaBase):
    """Already-calculated analysis passed to the AI explanation layer."""

    region: Region
    variable: Variable
    period: Period
    trend: TrendResult


class ExplanationResponse(SchemaBase):
    """Concise natural-language explanation of a calculated analysis."""

    explanation: str = Field(min_length=1, max_length=1000)


class ErrorResponse(SchemaBase):
    """Consistent JSON error payload."""

    error: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] | None = None


class HealthResponse(SchemaBase):
    """Response returned by the service health endpoints."""

    status: str
    service: str


class TrendAnalysisStatus(SchemaBase):
    """Status response retained for the existing scaffold route."""

    status: str
    message: str
