from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.shared.ids import EntityId
from app.shared.time import Clock, require_aware_datetime


class EditorialMomentConflictError(RuntimeError):
    pass


class EditorialMomentNotFoundError(LookupError):
    pass


class EditorialMomentStorageUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DeclareEditorialMoment:
    candidate_moment_id: EntityId
    operation_id: EntityId
    session_id: EntityId
    expected_session_revision: int
    timeline_start_microseconds: int
    timeline_end_microseconds: int | None
    actor_id: EntityId
    note: str | None
    declared_at: datetime
    request_digest: str

    def __post_init__(self) -> None:
        if self.expected_session_revision < 1:
            raise ValueError("expected_session_revision must be positive")
        if self.timeline_start_microseconds < 0:
            raise ValueError("timeline_start_microseconds must be nonnegative")
        if (
            self.timeline_end_microseconds is not None
            and self.timeline_end_microseconds < self.timeline_start_microseconds
        ):
            raise ValueError("timeline_end_microseconds cannot precede the start")
        if self.note is not None:
            normalized = self.note.strip()
            if not normalized:
                raise ValueError("note must be nonempty when supplied")
            object.__setattr__(self, "note", normalized)
        require_aware_datetime(self.declared_at, "declared_at")
        if len(self.request_digest) != 64:
            raise ValueError("request_digest must be a sha256 hex digest")


@dataclass(frozen=True, slots=True)
class EditorialCandidateMoment:
    id: EntityId
    session_id: EntityId
    expected_session_revision: int
    timeline_start_microseconds: int
    timeline_end_microseconds: int | None
    session_authoritative_start: datetime
    session_authoritative_end: datetime | None
    actor_id: EntityId
    operation_id: EntityId
    note: str | None
    declared_at: datetime
    revision: int = 1
    origin: str = "declared"
    epistemic_kind: str = "declared"
    reason_code: str = "human_mark_moment"

    def __post_init__(self) -> None:
        if self.revision != 1:
            raise ValueError("declared Editorial Candidate Moment revision must be one")
        if self.origin != "declared" or self.epistemic_kind != "declared":
            raise ValueError("Editorial Candidate Moment must remain declared evidence")
        if self.reason_code != "human_mark_moment":
            raise ValueError("Editorial Candidate Moment reason is fixed")
        require_aware_datetime(
            self.session_authoritative_start, "session_authoritative_start"
        )
        if self.session_authoritative_end is not None:
            require_aware_datetime(
                self.session_authoritative_end, "session_authoritative_end"
            )
        require_aware_datetime(self.declared_at, "declared_at")


class EditorialMomentRepository(Protocol):
    def declare(self, command: DeclareEditorialMoment) -> EditorialCandidateMoment: ...

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]: ...


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


__all__ = [
    "DeclareEditorialMoment",
    "EditorialCandidateMoment",
    "EditorialMomentConflictError",
    "EditorialMomentNotFoundError",
    "EditorialMomentRepository",
    "EditorialMomentService",
    "EditorialMomentStorageUnavailableError",
]
