from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import Header, HTTPException, Request

from app.core.config.settings import get_settings

API_SECRET_HEADER = "X-StageFlow-API-Secret"

_logger = logging.getLogger(__name__)


def require_api_secret(
    request: Request,
    presented_secret: Annotated[str | None, Header(alias=API_SECRET_HEADER)] = None,
) -> None:
    """Fail closed unless the request presents the configured API shared secret."""

    configured = get_settings().api_shared_secret
    if configured is None:
        _logger.error("stageflow_api_authentication_unavailable")
        raise HTTPException(status_code=503, detail="api_authentication_unavailable")
    if not hmac.compare_digest(presented_secret or "", configured.get_secret_value()):
        _logger.warning(
            "stageflow_api_request_rejected reason=unauthorized method=%s path=%s",
            request.method,
            request.url.path,
        )
        raise HTTPException(status_code=401, detail="unauthorized")


__all__ = ["API_SECRET_HEADER", "require_api_secret"]
