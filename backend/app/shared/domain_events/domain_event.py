from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base contract for future domain events."""

    event_type: str
    correlation_id: CorrelationId
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: EntityId = field(default_factory=EntityId.new)
    actor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
