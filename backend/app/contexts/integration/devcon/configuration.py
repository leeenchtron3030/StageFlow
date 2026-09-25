from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DevconReadConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str = "https://api.devcon.org"
    event_id: str
    room_id: str
    page_size: int = Field(default=500, ge=1, le=1000)
    maximum_catalog_sessions: int = Field(default=5000, ge=1, le=10_000)
    timeout_seconds: int = Field(default=10, ge=1, le=30)

    @field_validator("event_id", "room_id")
    @classmethod
    def non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("base_url")
    @classmethod
    def official_https_endpoint(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.devcon.org"
            or parsed.port is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Devcon read base_url must be https://api.devcon.org")
        return "https://api.devcon.org"
