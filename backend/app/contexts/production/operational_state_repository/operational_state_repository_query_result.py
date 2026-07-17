from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .operational_state_repository_error import OperationalStateRepositoryError


class OperationalStateRepositoryQueryOutcome(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    INVALID_QUERY = "invalid_query"
    CURRENT_STATE_CONFLICT = "current_state_conflict"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryQueryResult[T]:
    """Typed query result that never makes not-found ambiguous with failure."""

    outcome: OperationalStateRepositoryQueryOutcome
    value: T | None = None
    error: OperationalStateRepositoryError | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.outcome is OperationalStateRepositoryQueryOutcome.FOUND:
            if self.value is None:
                raise ValueError("A found repository query requires a value.")
            if self.error is not None:
                raise ValueError("A found repository query cannot contain an error.")
        elif self.value is not None:
            raise ValueError("A non-found repository query cannot contain a value.")
        if (
            self.error is not None
            and self.outcome is not OperationalStateRepositoryQueryOutcome.UNKNOWN
        ):
            raise ValueError("Repository errors are represented only by the unknown outcome.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def is_found(self) -> bool:
        return self.outcome is OperationalStateRepositoryQueryOutcome.FOUND
