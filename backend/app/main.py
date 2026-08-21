from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.authentication import API_SECRET_HEADER
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", API_SECRET_HEADER],
        max_age=600,
    )
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
