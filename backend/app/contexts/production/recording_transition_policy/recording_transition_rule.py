from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence import EvidenceConcern, EvidenceSignal
from app.contexts.production.operational_state import OperationalStateValue
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingTransitionRule:
    """Declarative rule for one supported recording transition target."""

    id: EntityId
    evidence_signal: EvidenceSignal
    proposed_state: OperationalStateValue
    required_concern: EvidenceConcern = EvidenceConcern.RECORDING_COVERAGE
    legacy_evidence_marker: str | None = None
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.proposed_state not in {
            OperationalStateValue.ACTIVE,
            OperationalStateValue.PAUSED,
            OperationalStateValue.STOPPED,
        }:
            raise ValueError("RecordingTransitionRule only supports active, paused, or stopped.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
