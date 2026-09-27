"""AI explanation endpoint for calculated analysis results."""

from fastapi import APIRouter, HTTPException

from app.models.schemas import ExplanationRequest, ExplanationResponse
from app.services.explanation import (
    ExplanationGenerationError,
    MissingGeminiApiKeyError,
    generate_explanation,
)


router = APIRouter(prefix="/explain", tags=["explanation"])


@router.post("", response_model=ExplanationResponse)
def explain_analysis(request: ExplanationRequest) -> ExplanationResponse:
    """Explain a result that has already been calculated by Python."""

    try:
        explanation = generate_explanation(request.model_dump(mode="json"))
    except MissingGeminiApiKeyError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI explanations are not configured on this server.",
        ) from exc
    except ExplanationGenerationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to generate a safe scientific explanation.",
        ) from exc

    return ExplanationResponse(explanation=explanation)
