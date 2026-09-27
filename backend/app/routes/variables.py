"""Variable API routes."""

from fastapi import APIRouter

from app.models.schemas import Unit, Variable, VariableMetadata


router = APIRouter(prefix="/variables", tags=["variables"])


@router.get("", response_model=list[VariableMetadata])
def list_variables() -> list[VariableMetadata]:
    """Return metadata for the variables supported by the current datasets."""

    return [
        VariableMetadata(
            id=Variable.SEA_ICE_FRACTION,
            name="Sea Ice Covered Fraction",
            unit=Unit.FRACTION,
            description="Fraction of the selected region covered by sea ice.",
        )
    ]
