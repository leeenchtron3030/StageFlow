from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.evidence import EvidenceContext
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateBasis,
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
    OperationalStateValue,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from ..operational_state_acceptance.operational_state_acceptance_lineage import (
    OperationalStateAcceptanceLineage,
)

OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS = (
    OperationalStateKind.RECORDING_STATE,
    OperationalStateKind.SESSION_STATE,
)

_SUPPORTED_FAMILY_BY_KIND = {
    OperationalStateKind.RECORDING_STATE: OperationalStateFamily.DIRECTLY_OBSERVABLE,
    OperationalStateKind.SESSION_STATE: OperationalStateFamily.EVIDENCE_DERIVED,
}


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryRecord:
    """Persisted view of one accepted immutable Operational State."""

    state: OperationalState
    persisted_status: OperationalStateStatus
    acceptance_id: EntityId
    accepted_evaluation_id: EntityId
    acceptance_rule_id: EntityId
    lineage: OperationalStateAcceptanceLineage
    accepted_at: datetime
    persisted_at: datetime
    predecessor_state_id: EntityId | None = None
    successor_state_id: EntityId | None = None
    revision: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _require_aware(self.accepted_at, "OperationalStateRepositoryRecord.accepted_at")
        _require_aware(self.persisted_at, "OperationalStateRepositoryRecord.persisted_at")
        if self.state.kind not in OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS:
            raise ValueError("Repository record state kind is outside ED-0046 scope.")
        if self.state.family is not _SUPPORTED_FAMILY_BY_KIND[self.state.kind]:
            raise ValueError("Repository record state family must match its supported kind.")
        if self.state.status is not OperationalStateStatus.CURRENT:
            raise ValueError("Accepted source state must retain status current.")
        if self.persisted_status not in (
            OperationalStateStatus.CURRENT,
            OperationalStateStatus.SUPERSEDED,
        ):
            raise ValueError("Persisted status must be current or superseded.")
        if self.revision is not None and self.revision < 1:
            raise ValueError("Repository record revision must be positive.")
        if self.accepted_evaluation_id != self.lineage.evaluation_id:
            raise ValueError("Repository record Evaluation ID must match lineage.")
        if self.state.kind is not self.lineage.evaluated_state_kind:
            raise ValueError("Repository record state kind must match lineage.")
        if self.state.value is not self.lineage.proposed_state_value:
            raise ValueError("Repository record state value must match accepted lineage.")
        if self.accepted_evaluation_id not in self.state.basis.transition_evaluation_ids:
            raise ValueError("Repository record basis must contain its Evaluation ID.")
        if (
            self.lineage.policy_id is None
            or self.lineage.policy_id not in self.state.basis.policy_ids
        ):
            raise ValueError("Repository record basis must contain its policy ID.")
        if (
            self.lineage.applied_rule_id is None
            or self.lineage.applied_rule_id not in self.state.basis.transition_rule_ids
        ):
            raise ValueError("Repository record basis must contain its transition rule ID.")
        if self.state.basis.evidence_context != self.lineage.evaluation_context:
            raise ValueError("Repository record must retain accepted Evidence context.")
        if self.predecessor_state_id == self.state.id:
            raise ValueError("Repository record predecessor must differ from its state ID.")
        if self.successor_state_id == self.state.id:
            raise ValueError("Repository record successor must differ from its state ID.")
        if (
            self.persisted_status is OperationalStateStatus.CURRENT
            and self.successor_state_id is not None
        ):
            raise ValueError("A current repository record cannot reference a successor.")
        if (
            self.persisted_status is OperationalStateStatus.SUPERSEDED
            and self.successor_state_id is None
        ):
            raise ValueError("A superseded repository record requires a successor reference.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def state_id(self) -> EntityId:
        return self.state.id

    @property
    def family(self) -> OperationalStateFamily:
        return self.state.family

    @property
    def kind(self) -> OperationalStateKind:
        return self.state.kind

    @property
    def subject(self) -> OperationalStateSubject:
        return self.state.subject

    @property
    def value(self) -> OperationalStateValue:
        return self.state.value

    @property
    def status(self) -> OperationalStateStatus:
        """Return authoritative persisted status, not the unchanged proposal status."""

        return self.persisted_status

    @property
    def basis(self) -> OperationalStateBasis:
        return self.state.basis

    @property
    def evidence_context(self) -> EvidenceContext:
        context = self.state.basis.evidence_context
        if context is None:  # Defensive; accepted ED-0046 records reject this in validation.
            raise RuntimeError("Repository record is missing accepted Evidence context.")
        return context

    @property
    def evaluation_at(self) -> datetime:
        """Return the successor state time retained from its accepted Evaluation."""

        return self.state.observed_or_derived_at
