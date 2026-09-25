from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.shared.ids import EntityId

from .contracts import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialMomentReviewResult,
    EditorialReviewQueuePage,
    EditorialReviewQueuePosition,
    EditorialSessionCandidateProjection,
    ReviewEditorialMoment,
)


class EditorialMomentConflictError(RuntimeError):
    pass


class EditorialMomentNotFoundError(LookupError):
    pass


class EditorialMomentStorageUnavailableError(RuntimeError):
    pass


class EditorialMomentRepository(Protocol):
    def declare(self, command: DeclareEditorialMoment) -> EditorialCandidateMoment: ...

    def review(
        self, command: ReviewEditorialMoment
    ) -> EditorialMomentReviewResult: ...

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]: ...

    def projection_for_session(
        self, session_id: EntityId
    ) -> EditorialSessionCandidateProjection: ...

    def projections_for_sessions(
        self, session_ids: tuple[EntityId, ...]
    ) -> tuple[EditorialSessionCandidateProjection, ...]: ...

    def revalidate_session_locations(
        self, session_id: EntityId, *, evaluated_at: datetime
    ) -> tuple[EditorialCandidateMoment, ...]: ...

    def list_review_queue(
        self,
        event_id: EntityId,
        *,
        after: EditorialReviewQueuePosition | None = None,
        limit: int = 100,
    ) -> EditorialReviewQueuePage: ...


__all__ = [
    "EditorialMomentConflictError",
    "EditorialMomentNotFoundError",
    "EditorialMomentRepository",
    "EditorialMomentStorageUnavailableError",
]
