"""Monthly time-series API routes."""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import Region, TimeSeriesPoint, TimeSeriesResponse, Unit, Variable
from app.services.csv_loader import load_csv


router = APIRouter(prefix="/series", tags=["series"])


@router.get("", response_model=TimeSeriesResponse)
def get_series(
    region: str = Query(..., description="Supported region: arctic or antarctic"),
) -> TimeSeriesResponse:
    """Return the cleaned monthly sea-ice series for a supported region."""

    try:
        selected_region = Region(region)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Unsupported region. Choose arctic or antarctic.",
        ) from exc

    try:
        frame = load_csv(selected_region.value)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to load the requested time series.",
        ) from exc

    data = [
        TimeSeriesPoint(
            date=row.date.to_pydatetime(),
            value=float(row.value),
        )
        for row in frame.itertuples(index=False)
    ]

    return TimeSeriesResponse(
        region=selected_region,
        variable=Variable.SEA_ICE_FRACTION,
        unit=Unit.FRACTION,
        start_date=data[0].date,
        end_date=data[-1].date,
        data=data,
    )
