from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.shared.ids import EntityId


class OperationalStateRepositoryErrorCode(StrEnum):
    """Unexpected repository failures, kept separate from domain outcomes."""

    UNAVAILABLE_STORAGE = "unavailable_storage"
    CORRUPTED_STORAGE = "corrupted_storage"
    SERIALIZATION_FAILURE = "serialization_failure"
    TRANSACTION_FAILURE = "transaction_failure"
    IMPLEMENTATION_ERROR = "implementation_error"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryError:
    """Immutable description of an unexpected repository-system failure."""

    code: OperationalStateRepositoryErrorCode
    message: str
    related_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("OperationalStateRepositoryError message must not be empty.")
        object.__setattr__(self, "related_ids", tuple(dict.fromkeys(self.related_ids)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
