"""Trend-analysis API routes."""

from fastapi import APIRouter

from app.models.schemas import TrendAnalysisStatus
from app.services.trend_analysis import get_trend_analysis_status


router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("", response_model=TrendAnalysisStatus)
def trend_status() -> TrendAnalysisStatus:
    """Report the current implementation status of trend analysis."""

    return get_trend_analysis_status()
