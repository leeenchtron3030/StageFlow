from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event import ProductionEventType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ObservationProvenance:
    """ID-only lineage from one Production Event to one Observation."""

    source_event_id: EntityId
    source_event_type: ProductionEventType
    source_event_occurred_at: datetime | None
    interpreter_kind: str
    interpreter_id: EntityId | None = None
    interpretation_rule_id: EntityId | str | None = None
    producer_identifier: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.source_event_occurred_at is not None:
            require_aware_datetime(
                self.source_event_occurred_at,
                "ObservationProvenance.source_event_occurred_at",
            )
        if not self.interpreter_kind.strip():
            raise ValueError("ObservationProvenance interpreter_kind must not be empty.")
        if self.producer_identifier is not None and not self.producer_identifier.strip():
            raise ValueError(
                "ObservationProvenance producer_identifier must not be empty."
            )
        if isinstance(self.interpretation_rule_id, str):
            if not self.interpretation_rule_id.strip():
                raise ValueError(
                    "ObservationProvenance interpretation_rule_id must not be empty."
                )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def source_event_timestamp(self) -> datetime | None:
        """Compatibility-readable name for the source event occurrence time."""

        return self.source_event_occurred_at

    def traceability_metadata(self) -> Mapping[str, Any]:
        """Return structured scalar lineage suitable for generic downstream metadata."""

        return MappingProxyType(
            {
                "source_production_event_id": self.source_event_id.to_json(),
                "source_production_event_type": self.source_event_type.value,
                "source_event_occurred_at": (
                    self.source_event_occurred_at.isoformat()
                    if self.source_event_occurred_at is not None
                    else None
                ),
                "observation_interpreter_kind": self.interpreter_kind,
                "observation_interpreter_id": (
                    self.interpreter_id.to_json()
                    if self.interpreter_id is not None
                    else None
                ),
                "interpretation_rule_id": (
                    self.interpretation_rule_id.to_json()
                    if isinstance(self.interpretation_rule_id, EntityId)
                    else self.interpretation_rule_id
                ),
                "source_producer_identifier": self.producer_identifier,
            }
        )
