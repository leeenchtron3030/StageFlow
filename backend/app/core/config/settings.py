from functools import lru_cache
from os import getenv

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    """Runtime settings needed for minimal backend startup."""

    model_config = ConfigDict(frozen=True)

    service_id: str = "stageflow-backend"
    service_name: str = "StageFlow Backend"
    api_version: str = "0.1.0"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        service_id=getenv("STAGEFLOW_SERVICE_ID", "stageflow-backend"),
        service_name=getenv("STAGEFLOW_SERVICE_NAME", "StageFlow Backend"),
        api_version=getenv("STAGEFLOW_API_VERSION", "0.1.0"),
        log_level=getenv("STAGEFLOW_LOG_LEVEL", "INFO"),
    )
