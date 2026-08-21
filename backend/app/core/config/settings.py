from functools import lru_cache
from os import getenv
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr

_DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://127.0.0.1:3000",
    "http://localhost:3000",
)


def _cors_allowed_origins(value: str | None) -> tuple[str, ...]:
    candidates = _DEFAULT_CORS_ALLOWED_ORIGINS if value is None else tuple(
        item.strip() for item in value.split(",") if item.strip()
    )
    if not candidates:
        raise ValueError("STAGEFLOW_CORS_ALLOWED_ORIGINS must contain at least one origin.")
    for origin in candidates:
        parsed = urlsplit(origin)
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("STAGEFLOW_CORS_ALLOWED_ORIGINS contains an invalid origin.")
    return tuple(dict.fromkeys(candidates))


class Settings(BaseModel):
    """Runtime settings needed for minimal backend startup."""

    model_config = ConfigDict(frozen=True)

    service_id: str = "stageflow-backend"
    service_name: str = "StageFlow Backend"
    api_version: str = "0.1.0"
    log_level: str = "INFO"
    api_shared_secret: SecretStr | None = None
    cors_allowed_origins: tuple[str, ...] = _DEFAULT_CORS_ALLOWED_ORIGINS


@lru_cache
def get_settings() -> Settings:
    secret = getenv("STAGEFLOW_API_SHARED_SECRET")
    if secret is not None and len(secret) < 32:
        raise ValueError("STAGEFLOW_API_SHARED_SECRET must contain at least 32 characters.")
    return Settings(
        service_id=getenv("STAGEFLOW_SERVICE_ID", "stageflow-backend"),
        service_name=getenv("STAGEFLOW_SERVICE_NAME", "StageFlow Backend"),
        api_version=getenv("STAGEFLOW_API_VERSION", "0.1.0"),
        log_level=getenv("STAGEFLOW_LOG_LEVEL", "INFO"),
        api_shared_secret=SecretStr(secret) if secret else None,
        cors_allowed_origins=_cors_allowed_origins(
            getenv("STAGEFLOW_CORS_ALLOWED_ORIGINS")
        ),
    )
