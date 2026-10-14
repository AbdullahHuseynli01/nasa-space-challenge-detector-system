"""AI explanation endpoint for calculated analysis results."""

from fastapi import APIRouter, HTTPException

from app.models.schemas import ExplanationRequest, ExplanationResponse
from app.services.explanation import ExplanationError, generate_explanation


router = APIRouter(prefix="/explain", tags=["explanation"])


@router.post(
    "",
    response_model=ExplanationResponse,
    responses={
        429: {"description": "Groq is rate-limiting the server. Retry after the Retry-After header."},
        502: {"description": "No reply passed validation, or Groq could not be reached."},
        503: {"description": "AI explanations are not configured on this server."},
        504: {"description": "Groq did not answer in time."},
    },
)
def explain_analysis(request: ExplanationRequest) -> ExplanationResponse:
    """Explain a result that has already been calculated by Python."""

    try:
        explanation = generate_explanation(request.model_dump(mode="json"))
    except ExplanationError as exc:
        # The service has already logged the details.
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.public_message,
            headers=headers,
        ) from exc

    return ExplanationResponse(explanation=explanation)
