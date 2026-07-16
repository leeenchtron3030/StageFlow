from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceRole,
    EvidenceSignal,
    EvidenceStrength,
)
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionBoundaryEvidenceRule:
    """Declarative treatment of one structured source Evidence Signal."""

    id: EntityId
    accepted_source_concerns: Sequence[EvidenceConcern]
    accepted_signal: EvidenceSignal
    target_boundary_concern: EvidenceConcern
    target_role: EvidenceRole
    rationale_template: str
    strength_treatment: EvidenceStrength | None = None
    context_requirements: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        concerns = tuple(self.accepted_source_concerns)
        if not concerns or EvidenceConcern.UNKNOWN in concerns:
            raise ValueError("Session boundary rules require known source concerns.")
        if self.accepted_signal is EvidenceSignal.UNKNOWN:
            raise ValueError("Session boundary rules require a known source signal.")
        if self.target_boundary_concern not in {
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceConcern.POSSIBLE_SESSION_END,
        }:
            raise ValueError("Session boundary rules must target a possible boundary concern.")
        if self.target_role is EvidenceRole.UNKNOWN:
            raise ValueError("Session boundary rules require an explicit target role.")
        if not self.rationale_template.strip():
            raise ValueError("Session boundary rule rationale must not be empty.")
        object.__setattr__(self, "accepted_source_concerns", concerns)
        object.__setattr__(self, "context_requirements", tuple(self.context_requirements))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def accepts(self, concern: EvidenceConcern, signal: EvidenceSignal) -> bool:
        return concern in self.accepted_source_concerns and signal is self.accepted_signal

    def rationale(self) -> str:
        return self.rationale_template.format(
            source_signal=self.accepted_signal.value,
            target_concern=self.target_boundary_concern.value,
            target_role=self.target_role.value,
        )
