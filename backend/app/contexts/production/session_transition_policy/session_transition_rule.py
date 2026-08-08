from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.contexts.production.evidence import EvidenceConcern, EvidenceRole
from app.contexts.production.operational_state import OperationalStateValue
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .session_transition_requirement import SessionTransitionRequirement


class SessionTransitionContradictionBehavior(StrEnum):
    BLOCK = "transition_not_supported"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_SESSION_VALUES = {
    OperationalStateValue.INACTIVE,
    OperationalStateValue.ACTIVE,
    OperationalStateValue.ENDING,
    OperationalStateValue.ENDED,
}

_SUPPORTED_TRANSITIONS = {
    (OperationalStateValue.INACTIVE, OperationalStateValue.ACTIVE),
    (OperationalStateValue.ACTIVE, OperationalStateValue.ENDING),
    (OperationalStateValue.ACTIVE, OperationalStateValue.ENDED),
    (OperationalStateValue.ENDING, OperationalStateValue.ENDED),
    (OperationalStateValue.ENDED, OperationalStateValue.ACTIVE),
    (OperationalStateValue.INACTIVE, OperationalStateValue.INACTIVE),
    (OperationalStateValue.ACTIVE, OperationalStateValue.ACTIVE),
    (OperationalStateValue.ENDING, OperationalStateValue.ENDING),
    (OperationalStateValue.ENDED, OperationalStateValue.ENDED),
}


@dataclass(frozen=True, slots=True)
class SessionTransitionRule:
    """Statically defined rule for one supported Session state transition."""

    id: EntityId
    current_state_value: OperationalStateValue
    proposed_state_value: OperationalStateValue
    required_boundary_concern: EvidenceConcern
    requirements: Sequence[SessionTransitionRequirement]
    allowed_evidence_roles: Sequence[EvidenceRole]
    contradiction_behavior: SessionTransitionContradictionBehavior
    rationale_template: str
    requirements_require_distinct_sources: bool = False
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.current_state_value not in _SESSION_VALUES:
            raise ValueError("Session transition rule current value is unsupported.")
        if self.proposed_state_value not in _SESSION_VALUES:
            raise ValueError("Session transition rule proposed value is unsupported.")
        if (self.current_state_value, self.proposed_state_value) not in _SUPPORTED_TRANSITIONS:
            raise ValueError("Session transition rule transition is outside supported scope.")
        if self.required_boundary_concern not in {
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceConcern.POSSIBLE_SESSION_END,
        }:
            raise ValueError("Session transition rule requires a boundary Evidence concern.")
        if not self.requirements:
            raise ValueError("Session transition rule requires declarative requirements.")
        if any(
            requirement.current_state_value is not self.current_state_value
            or requirement.proposed_state_value is not self.proposed_state_value
            for requirement in self.requirements
        ):
            raise ValueError("Session transition rule requirements must target its transition.")
        if not self.allowed_evidence_roles:
            raise ValueError("Session transition rule requires allowed Evidence roles.")
        if not self.rationale_template.strip():
            raise ValueError("Session transition rule rationale must not be empty.")
        object.__setattr__(self, "requirements", tuple(self.requirements))
        object.__setattr__(
            self,
            "allowed_evidence_roles",
            tuple(self.allowed_evidence_roles),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def rationale(self) -> str:
        return self.rationale_template.format(
            current_state=self.current_state_value.value,
            proposed_state=self.proposed_state_value.value,
            boundary_concern=self.required_boundary_concern.value,
        )
