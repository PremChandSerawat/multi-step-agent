"""Health check routes."""
from fastapi import APIRouter

from ..models import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API service is running and healthy.",
)
async def health() -> HealthResponse:
    """Return the health status of the API."""
    return HealthResponse(status="ok", version="0.1.0")

