from __future__ import annotations

import hashlib
import json
from datetime import UTC

from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialMomentReviewAction,
    EditorialMomentReviewResult,
    EditorialReviewQueuePage,
    EditorialReviewQueuePosition,
    EditorialReviewRange,
    EditorialSessionCandidateProjection,
    ReviewEditorialMoment,
)
from .repository import EditorialMomentRepository


def _human_command_digest(document: dict[str, object]) -> str:
    serialized = json.dumps(
        document,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


class EditorialMomentService:
    def __init__(self, repository: EditorialMomentRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    def mark_moment(
        self,
        *,
        operation_id: EntityId,
        session_id: EntityId,
        expected_session_revision: int,
        timeline_start_microseconds: int,
        actor_id: EntityId,
        timeline_end_microseconds: int | None = None,
        note: str | None = None,
    ) -> EditorialCandidateMoment:
        normalized_note = None if note is None else note.strip()
        document: dict[str, object] = {
            'actor_id': actor_id.value,
            'expected_session_revision': expected_session_revision,
            'kind': 'editorial_moment_declaration',
            'note': normalized_note,
            'session_id': session_id.value,
            'timeline_end_microseconds': timeline_end_microseconds,
            'timeline_start_microseconds': timeline_start_microseconds,
        }
        return self.repository.declare(
            DeclareEditorialMoment(
                candidate_moment_id=EntityId.new(),
                operation_id=operation_id,
                session_id=session_id,
                expected_session_revision=expected_session_revision,
                timeline_start_microseconds=timeline_start_microseconds,
                timeline_end_microseconds=timeline_end_microseconds,
                actor_id=actor_id,
                note=normalized_note,
                declared_at=self.clock.now().astimezone(UTC),
                request_digest=_human_command_digest(document),
            )
        )

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]:
        return self.repository.list_for_session(session_id, limit=limit)

    def review_moment(
        self,
        *,
        operation_id: EntityId,
        candidate_moment_id: EntityId,
        expected_candidate_revision: int,
        actor_id: EntityId,
        action: EditorialMomentReviewAction,
        reason: str,
        notes: str | None = None,
        adjusted_timeline_start_microseconds: int | None = None,
        adjusted_timeline_end_microseconds: int | None = None,
    ) -> EditorialMomentReviewResult:
        parsed_action = EditorialMomentReviewAction(action)
        normalized_reason = reason.strip()
        normalized_notes = None if notes is None else notes.strip()
        if (adjusted_timeline_start_microseconds is None) != (
            adjusted_timeline_end_microseconds is None
        ):
            raise ValueError('adjusted range requires both start and end')
        if adjusted_timeline_start_microseconds is None:
            adjusted_range = None
        else:
            assert adjusted_timeline_end_microseconds is not None
            adjusted_range = EditorialReviewRange(
                timeline_start_microseconds=adjusted_timeline_start_microseconds,
                timeline_end_microseconds=adjusted_timeline_end_microseconds,
            )
        document: dict[str, object] = {
            'action': parsed_action.value,
            'actor_id': actor_id.value,
            'adjusted_timeline_end_microseconds': (
                None
                if adjusted_range is None
                else adjusted_range.timeline_end_microseconds
            ),
            'adjusted_timeline_start_microseconds': (
                None
                if adjusted_range is None
                else adjusted_range.timeline_start_microseconds
            ),
            'candidate_moment_id': candidate_moment_id.value,
            'expected_candidate_revision': expected_candidate_revision,
            'kind': 'editorial_moment_review',
            'notes': normalized_notes,
            'reason': normalized_reason,
        }
        return self.repository.review(
            ReviewEditorialMoment(
                review_decision_id=EntityId.new(),
                clip_id=(
                    EntityId.new()
                    if parsed_action
                    is EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP
                    else None
                ),
                operation_id=operation_id,
                candidate_moment_id=candidate_moment_id,
                expected_candidate_revision=expected_candidate_revision,
                actor_id=actor_id,
                action=parsed_action,
                reason=normalized_reason,
                notes=normalized_notes,
                adjusted_range=adjusted_range,
                decided_at=self.clock.now().astimezone(UTC),
                request_digest=_human_command_digest(document),
            )
        )

    def list_review_queue(
        self,
        event_id: EntityId,
        *,
        after: EditorialReviewQueuePosition | None = None,
        limit: int = 100,
    ) -> EditorialReviewQueuePage:
        return self.repository.list_review_queue(
            event_id,
            after=after,
            limit=limit,
        )

    def projection_for_session(
        self, session_id: EntityId
    ) -> EditorialSessionCandidateProjection:
        return self.repository.projection_for_session(session_id)

    def projections_for_sessions(
        self, session_ids: tuple[EntityId, ...]
    ) -> tuple[EditorialSessionCandidateProjection, ...]:
        return self.repository.projections_for_sessions(session_ids)

    def revalidate_session_boundary(
        self, session_id: EntityId
    ) -> tuple[EditorialCandidateMoment, ...]:
        return self.repository.revalidate_session_locations(
            session_id,
            evaluated_at=self.clock.now().astimezone(UTC),
        )


EditorialApplicationService = EditorialMomentService


__all__ = ["EditorialApplicationService", "EditorialMomentService"]
