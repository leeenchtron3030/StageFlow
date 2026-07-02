from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config.settings import get_settings
from app.core.lifecycle.lifespan import lifespan
from app.core.logging.configure import configure_logging


def create_app() -> FastAPI:
    """Create the StageFlow FastAPI application."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.service_name,
        version=settings.api_version,
        lifespan=lifespan,
    )
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
