from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.shared.ids import EntityId

from ..operational_state_acceptance.operational_state_acceptance_result import (
    OperationalStateAcceptanceResult,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryCommitRequest:
    """One immutable request to atomically store one acceptance result."""

    acceptance_result: OperationalStateAcceptanceResult
    commit_at: datetime
    expected_current_state_id: EntityId | None = None
    expected_revision: int | None = None
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _require_aware(self.commit_at, "OperationalStateRepositoryCommitRequest.commit_at")
        if self.expected_revision is not None and self.expected_revision < 0:
            raise ValueError("Expected repository revision must not be negative.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def acceptance_id(self) -> EntityId:
        return self.acceptance_result.id

    @property
    def evaluation_id(self) -> EntityId:
        return self.acceptance_result.accepted_evaluation_id

    @property
    def successor_state_id(self) -> EntityId | None:
        successor = self.acceptance_result.successor_state
        return successor.id if successor is not None else None
