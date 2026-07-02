from fastapi import APIRouter

from app.core.config.settings import get_settings
from app.core.health.service import HealthResponse, get_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return get_health(get_settings())
