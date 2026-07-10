from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceConcern
from app.contexts.production.operational_state import OperationalStateValue
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingTransitionRule:
    """Declarative rule for one supported recording transition target."""

    id: EntityId
    evidence_marker: str
    proposed_state: OperationalStateValue
    required_concern: EvidenceConcern = EvidenceConcern.RECORDING_COVERAGE
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.evidence_marker.strip():
            raise ValueError("RecordingTransitionRule evidence_marker must not be empty.")
        if self.proposed_state not in {
            OperationalStateValue.ACTIVE,
            OperationalStateValue.PAUSED,
            OperationalStateValue.STOPPED,
        }:
            raise ValueError("RecordingTransitionRule only supports active, paused, or stopped.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
