from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.operational_state.operational_state import OperationalState
from app.contexts.production.operational_state.operational_state_family import (
    OperationalStateFamily,
)
from app.contexts.production.operational_state.operational_state_kind import (
    OperationalStateKind,
)
from app.contexts.production.operational_state.operational_state_status import (
    OperationalStateStatus,
)
from app.contexts.production.operational_state.operational_state_subject import (
    OperationalStateSubjectType,
)
from app.contexts.production.operational_state.operational_state_value import (
    OperationalStateValue,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class OperationalStateSummary:
    """Lightweight diagnostics for an OperationalState."""

    state_id: EntityId
    family: OperationalStateFamily
    kind: OperationalStateKind
    subject_type: OperationalStateSubjectType
    value: OperationalStateValue
    status: OperationalStateStatus
    observation_reference_count: int
    evidence_set_reference_count: int
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None

    @classmethod
    def from_state(cls, state: OperationalState) -> OperationalStateSummary:
        return cls(
            state_id=state.id,
            family=state.family,
            kind=state.kind,
            subject_type=state.subject.subject_type,
            value=state.value,
            status=state.status,
            observation_reference_count=len(state.basis.observation_ids),
            evidence_set_reference_count=len(state.basis.evidence_set_ids),
            recording_block_id=state.recording_block_id,
            stage_id=state.stage_id,
        )
