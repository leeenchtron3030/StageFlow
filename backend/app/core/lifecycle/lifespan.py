from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap.event_mode_kernel import load_kernel_components_from_environment


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.ready = True
    app.state.kernel = None
    app.state.kernel_ready = False
    app.state.kernel_startup_error = None
    try:
        components = load_kernel_components_from_environment()
        app.state.kernel = components
        if components is not None:
            status = components.status()
            app.state.kernel_ready = status is not None and status.ready
    except (RuntimeError, ValueError) as exc:
        app.state.kernel_startup_error = str(exc)
    try:
        yield
    finally:
        app.state.kernel_ready = False
