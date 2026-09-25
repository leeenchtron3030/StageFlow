import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap.event_mode_kernel import (
    KernelStartupProgress,
    load_kernel_components_from_environment,
)
from app.contexts.production.event_mode_kernel.repository import (
    KernelStorageUnavailableError,
)
from app.core.config.settings import get_settings
from app.demo.autonomous import AutonomousEventNodeCoordinator

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.ready = True
    app.state.kernel = None
    app.state.kernel_ready = False
    app.state.kernel_startup_error = None
    app.state.autonomous_event_node = None
    startup_progress = KernelStartupProgress()
    app.state.kernel_startup_progress = startup_progress
    if get_settings().api_shared_secret is None:
        raise RuntimeError("stageflow_api_shared_secret_required")
    try:
        components = load_kernel_components_from_environment(progress=startup_progress)
        app.state.kernel = components
        if components is not None:
            status = components.status()
            app.state.kernel_ready = status is not None and status.ready
            coordinator = AutonomousEventNodeCoordinator(components)
            app.state.autonomous_event_node = coordinator
            coordinator.start()
    except KernelStorageUnavailableError as exc:
        _logger.error(
            "stageflow_kernel_startup_failed reason=storage_unavailable exception_type=%s",
            type(exc).__name__,
        )
        startup_progress.database_available = False
        app.state.kernel_startup_error = str(exc)
    except (OSError, RuntimeError, ValueError) as exc:
        _logger.error(
            "stageflow_kernel_startup_failed reason=configuration_or_runtime exception_type=%s",
            type(exc).__name__,
        )
        app.state.kernel_startup_error = str(exc)
    try:
        yield
    finally:
        coordinator = app.state.autonomous_event_node
        if isinstance(coordinator, AutonomousEventNodeCoordinator):
            coordinator.stop()
        app.state.kernel_ready = False
