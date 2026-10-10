"""AI explanation endpoint for calculated analysis results."""

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import ExplanationRequest, ExplanationResponse
from app.services.explanation import (
    ExplanationGenerationError,
    MissingGroqApiKeyError,
    generate_explanation,
)


router = APIRouter(prefix="/explain", tags=["explanation"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ExplanationResponse)
def explain_analysis(request: ExplanationRequest) -> ExplanationResponse:
    """Explain a result that has already been calculated by Python."""

    try:
        explanation = generate_explanation(request.model_dump(mode="json"))
    except MissingGroqApiKeyError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI explanations are not configured on this server.",
        ) from exc
    except ExplanationGenerationError as exc:
        logger.warning("Explanation rejected: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Unable to generate a safe scientific explanation.",
        ) from exc

    return ExplanationResponse(explanation=explanation)
