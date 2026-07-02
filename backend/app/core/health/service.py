from pydantic import BaseModel, ConfigDict

from app.core.config.settings import Settings


class HealthResponse(BaseModel):
    """Minimal health response for backend startup verification."""

    model_config = ConfigDict(frozen=True)

    status: str
    service: str


def get_health(settings: Settings) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_id)
