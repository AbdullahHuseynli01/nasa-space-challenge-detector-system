"""Region API routes."""

from fastapi import APIRouter

from app.models.schemas import Region


router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", response_model=list[Region])
def list_regions() -> list[Region]:
    """Return the regions supported by the API."""

    return list(Region)
