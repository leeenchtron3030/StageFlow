from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceSet
from app.shared.ids import EntityId

from .session_boundary_evidence_context import SessionBoundaryEvidenceContext


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionBoundaryEvidenceResult:
    """Descriptive output from cross-domain possible-boundary composition."""

    start_boundary_evidence_sets: Sequence[EvidenceSet]
    end_boundary_evidence_sets: Sequence[EvidenceSet]
    consumed_source_evidence_set_ids: Sequence[EntityId]
    ignored_source_evidence_set_ids: Sequence[EntityId]
    unsupported_source_evidence_set_ids: Sequence[EntityId]
    duplicate_source_evidence_set_ids: Sequence[EntityId]
    applied_rule_ids: Sequence[EntityId]
    generated_boundary_contexts: Sequence[SessionBoundaryEvidenceContext]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "start_boundary_evidence_sets",
            tuple(self.start_boundary_evidence_sets),
        )
        object.__setattr__(
            self,
            "end_boundary_evidence_sets",
            tuple(self.end_boundary_evidence_sets),
        )
        object.__setattr__(
            self,
            "consumed_source_evidence_set_ids",
            tuple(self.consumed_source_evidence_set_ids),
        )
        object.__setattr__(
            self,
            "ignored_source_evidence_set_ids",
            tuple(self.ignored_source_evidence_set_ids),
        )
        object.__setattr__(
            self,
            "unsupported_source_evidence_set_ids",
            tuple(self.unsupported_source_evidence_set_ids),
        )
        object.__setattr__(
            self,
            "duplicate_source_evidence_set_ids",
            tuple(self.duplicate_source_evidence_set_ids),
        )
        object.__setattr__(self, "applied_rule_ids", tuple(self.applied_rule_ids))
        object.__setattr__(
            self,
            "generated_boundary_contexts",
            tuple(self.generated_boundary_contexts),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def evidence_sets(self) -> tuple[EvidenceSet, ...]:
        return tuple(self.start_boundary_evidence_sets) + tuple(
            self.end_boundary_evidence_sets
        )

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_sets)
