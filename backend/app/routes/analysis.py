"""Combined annual-series and trend-analysis API routes."""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    AnalysisResponse,
    AnnualSeriesPoint,
    Period,
    Region,
    TrendResult,
    Unit,
    Variable,
)
from app.services.csv_loader import load_csv
from app.services.trend_analysis import (
    InsufficientObservationsError,
    annualize_time_series,
    calculate_annual_trend,
)


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("", response_model=AnalysisResponse)
def get_analysis(
    region: str = Query(..., description="Supported region: arctic or antarctic"),
) -> AnalysisResponse:
    """Return annual sea-ice means and deterministic trend statistics."""

    try:
        selected_region = Region(region)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Unsupported region. Choose arctic or antarctic.",
        ) from exc

    try:
        monthly_data = load_csv(selected_region.value)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to load the requested time series.",
        ) from exc

    try:
        annual_data = annualize_time_series(monthly_data)
        trend = calculate_annual_trend(annual_data)
    except InsufficientObservationsError as exc:
        raise HTTPException(
            status_code=422,
            detail="Not enough complete annual observations to calculate a trend.",
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate the requested analysis.",
        ) from exc

    annual_series = [
        AnnualSeriesPoint(year=int(row.year), value=float(row.value))
        for row in annual_data.itertuples(index=False)
    ]
    period = Period(
        start=annual_series[0].year,
        end=annual_series[-1].year,
    )

    return AnalysisResponse(
        region=selected_region,
        variable=Variable.SEA_ICE_FRACTION,
        unit=Unit.FRACTION,
        period=period,
        annual_series=annual_series,
        trend=TrendResult(**trend),
    )
