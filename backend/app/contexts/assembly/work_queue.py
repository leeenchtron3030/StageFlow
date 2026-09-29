"""Read-only projection of the existing Assembly approval eligibility."""
from app.contexts.production.event_mode_kernel.contracts import (
    ProducerWorkDecisionType,
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
    ProducerWorkSubjectKind,
)
from app.shared.ids import EntityId

from .contracts import ApprovalState
from .session_contracts import AssemblyRevision, SessionAssembly


def validate_work_queue_limit(limit: int) -> None:
    # The API's maximum page plus its truncation sentinel.
    if isinstance(limit, bool) or not 1 <= limit <= 101:
        raise ValueError("Work Queue limit must be between 1 and 101.")


def assembly_work_queue_position(revision: AssemblyRevision) -> ProducerWorkQueuePosition:
    return ProducerWorkQueuePosition(5, revision.created_at, f"assembly:{revision.session_id}")


def assembly_work_queue_subject(
    assembly: SessionAssembly, *, stage_id: EntityId,
) -> ProducerWorkQueueSubject | None:
    revision = assembly.revision
    if (revision.revision_number != assembly.current_revision_number
            or revision.validation.state != "valid" or assembly.stale
            or assembly.decision_count != 0
            or assembly.approval_state != ApprovalState.UNREVIEWED):
        return None
    return ProducerWorkQueueSubject(
        projection_id=f"assembly:{revision.session_id}",
        decision_type=ProducerWorkDecisionType.ASSEMBLY_APPROVAL_PENDING,
        subject_kind=ProducerWorkSubjectKind.SESSION_ASSEMBLY,
        subject_id=revision.id,
        subject_revision=revision.revision_number,
        event_id=revision.event_id,
        stage_id=stage_id,
        session_id=revision.session_id,
        priority=5,
        reason_codes=("assembly_approval_pending",),
        action_reference=f"session:{revision.session_id}:assembly",
        created_at=revision.created_at,
        updated_at=revision.created_at,
    )
