from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class StageFlowError:
    """Structured, safe-to-log error contract."""

    code: str
    message: str
    details: MappingProxyType[str, Any] | None = None

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(
            self,
            "details",
            MappingProxyType(dict(details)) if details is not None else None,
        )

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = dict(self.details)
        return payload


class ValidationError(StageFlowError):
    """Input or contract validation failed."""


class DomainError(StageFlowError):
    """A generic domain rule failed."""


class InfrastructureError(StageFlowError):
    """An infrastructure dependency failed."""


class IntegrationError(StageFlowError):
    """An external integration boundary failed."""


class ConfigurationError(StageFlowError):
    """Application configuration is invalid."""
