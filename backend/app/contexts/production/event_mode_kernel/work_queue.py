from __future__ import annotations

from datetime import datetime

from app.shared.ids import EntityId

from .contracts import (
    AssociationStatus,
    MediaAssociation,
    ProducerWorkDecisionType,
    ProducerWorkQueueSubject,
    ProducerWorkSubjectKind,
    RegisteredMediaAsset,
    Session,
    SessionPackageState,
)

_PACKAGE_DECISIONS = {
    SessionPackageState.CORRECTION_REQUIRED: (
        ProducerWorkDecisionType.PACKAGE_CORRECTION_REQUIRED,
        3,
    ),
    SessionPackageState.READY_FOR_REVIEW: (
        ProducerWorkDecisionType.PACKAGE_READY_FOR_REVIEW,
        4,
    ),
}

_ASSOCIATION_DECISIONS = {
    AssociationStatus.CONFLICT: (
        ProducerWorkDecisionType.ASSOCIATION_CONFLICT,
        1,
    ),
    AssociationStatus.UNRESOLVED: (
        ProducerWorkDecisionType.ASSOCIATION_UNRESOLVED,
        2,
    ),
}


def session_work_queue_subject(session: Session) -> ProducerWorkQueueSubject | None:
    decision = _PACKAGE_DECISIONS.get(session.package_state)
    if decision is None:
        return None
    decision_type, priority = decision
    return ProducerWorkQueueSubject(
        projection_id=f"package:{session.id.value}",
        decision_type=decision_type,
        subject_kind=ProducerWorkSubjectKind.SESSION_PACKAGE,
        subject_id=session.id,
        subject_revision=session.revision,
        event_id=session.event_id,
        stage_id=session.stage_id,
        session_id=session.id,
        priority=priority,
        reason_codes=(decision_type.value,),
        action_reference=f"session:{session.id.value}:package",
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def association_work_queue_subject(
    association: MediaAssociation,
    asset: RegisteredMediaAsset,
    *,
    event_id: EntityId,
) -> ProducerWorkQueueSubject | None:
    decision = _ASSOCIATION_DECISIONS.get(association.status)
    if decision is None:
        return None
    decision_type, priority = decision
    return ProducerWorkQueueSubject(
        projection_id=f"association:{association.asset_id.value}",
        decision_type=decision_type,
        subject_kind=ProducerWorkSubjectKind.MEDIA_ASSOCIATION,
        subject_id=association.asset_id,
        subject_revision=association.revision,
        event_id=event_id,
        stage_id=asset.stage_id,
        session_id=None,
        priority=priority,
        reason_codes=association.reason_codes or (decision_type.value,),
        action_reference=f"media-association:{association.asset_id.value}",
        created_at=association.decided_at,
        updated_at=association.decided_at,
    )


def work_queue_sort_key(
    subject: ProducerWorkQueueSubject,
) -> tuple[int, datetime, str]:
    return (subject.priority, subject.updated_at, subject.projection_id)


__all__ = [
    "association_work_queue_subject",
    "session_work_queue_subject",
    "work_queue_sort_key",
]
