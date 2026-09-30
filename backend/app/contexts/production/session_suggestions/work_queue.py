"""Read-only Stage projection of open suggestions in the latest run."""
from datetime import datetime
from typing import Protocol

from app.contexts.production.event_mode_kernel.contracts import (
    ProducerWorkDecisionType,
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
    ProducerWorkSubjectKind,
)
from app.shared.ids import EntityId

from .contracts import MAX_COUNT


class SessionSuggestionWorkQueueReader(Protocol):
    def list_pending_confirmations(
        self, event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
        limit: int = 50,
    ) -> tuple[ProducerWorkQueueSubject, ...]: ...


def validate_work_queue_limit(limit: int) -> None:
    if isinstance(limit, bool) or not 1 <= limit <= 101:
        raise ValueError("Work Queue limit must be between 1 and 101.")


def suggestion_work_queue_subject(
    *, event_id: EntityId, stage_id: EntityId, run_id: EntityId, created_at: datetime,
    open_count: int, weak_count: int,
) -> ProducerWorkQueueSubject:
    if not 0 <= weak_count <= open_count <= MAX_COUNT or open_count == 0:
        raise ValueError("Invalid pending suggestion counts.")
    return ProducerWorkQueueSubject(
        projection_id=f"suggestions:{stage_id}",
        decision_type=ProducerWorkDecisionType.PRESENTATION_CONFIRMATION_PENDING,
        subject_kind=ProducerWorkSubjectKind.STAGE_SUGGESTIONS,
        subject_id=run_id, subject_revision=1,
        event_id=event_id, stage_id=stage_id, session_id=None, priority=6,
        reason_codes=("presentation_confirmation_pending",
                      f"open_count:{open_count}", f"weak_count:{weak_count}"),
        action_reference=f"stage:{stage_id}:suggestions",
        created_at=created_at, updated_at=created_at,
    )
