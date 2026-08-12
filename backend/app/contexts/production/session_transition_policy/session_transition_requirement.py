from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence import EvidenceRole, EvidenceSignal
from app.contexts.production.operational_state import OperationalStateValue
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_SESSION_VALUES = {
    OperationalStateValue.INACTIVE,
    OperationalStateValue.ACTIVE,
    OperationalStateValue.ENDING,
    OperationalStateValue.ENDED,
}


@dataclass(frozen=True, slots=True)
class SessionTransitionRequirement:
    """One categorical Evidence requirement for a Session transition."""

    id: EntityId
    current_state_value: OperationalStateValue
    proposed_state_value: OperationalStateValue
    evidence_categories: Sequence[str]
    minimum_categorical_count: int
    require_independent_sources: bool
    allowed_signals: Sequence[EvidenceSignal]
    rationale: str
    disallowed_signals: Sequence[EvidenceSignal] = field(default_factory=tuple)
    allowed_roles: Sequence[EvidenceRole] = (EvidenceRole.SUPPORTS,)
    requires_fresh_context: bool = False
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.current_state_value not in _SESSION_VALUES:
            raise ValueError("Session transition requirement current value is unsupported.")
        if self.proposed_state_value not in _SESSION_VALUES:
            raise ValueError("Session transition requirement proposed value is unsupported.")
        if self.minimum_categorical_count < 1:
            raise ValueError("Session transition requirement count must be at least one.")
        if not self.evidence_categories:
            raise ValueError("Session transition requirement needs Evidence categories.")
        if not self.allowed_signals:
            raise ValueError("Session transition requirement needs allowed Signals.")
        if not self.allowed_roles:
            raise ValueError("Session transition requirement needs allowed Evidence roles.")
        if not self.rationale.strip():
            raise ValueError("Session transition requirement rationale must not be empty.")
        object.__setattr__(self, "evidence_categories", tuple(self.evidence_categories))
        object.__setattr__(self, "allowed_signals", tuple(self.allowed_signals))
        object.__setattr__(self, "disallowed_signals", tuple(self.disallowed_signals))
        object.__setattr__(self, "allowed_roles", tuple(self.allowed_roles))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
