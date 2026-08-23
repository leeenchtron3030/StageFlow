from __future__ import annotations

import hashlib
import json
from datetime import UTC

from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialSessionCandidateProjection,
)
from .repository import EditorialMomentRepository


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
        document = json.dumps(
            {
                "actor_id": actor_id.value,
                "expected_session_revision": expected_session_revision,
                "kind": "editorial_moment_declaration",
                "note": normalized_note,
                "session_id": session_id.value,
                "timeline_end_microseconds": timeline_end_microseconds,
                "timeline_start_microseconds": timeline_start_microseconds,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
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
                request_digest=hashlib.sha256(document.encode("utf-8")).hexdigest(),
            )
        )

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]:
        return self.repository.list_for_session(session_id, limit=limit)

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
