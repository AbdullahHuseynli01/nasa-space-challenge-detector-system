"""Annual trend-analysis API routes."""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    Period,
    Region,
    TrendResponse,
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


router = APIRouter(prefix="/trend", tags=["trend"])


@router.get("", response_model=TrendResponse)
def get_trend(
    region: str = Query(..., description="Supported region: arctic or antarctic"),
) -> TrendResponse:
    """Return the deterministic annual sea-ice trend for a region."""

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
            detail="Unable to calculate the requested trend.",
        ) from exc

    period = Period(
        start=int(annual_data["year"].iloc[0]),
        end=int(annual_data["year"].iloc[-1]),
    )

    return TrendResponse(
        region=selected_region,
        variable=Variable.SEA_ICE_FRACTION,
        unit=Unit.FRACTION,
        period=period,
        trend=TrendResult(**trend),
    )
