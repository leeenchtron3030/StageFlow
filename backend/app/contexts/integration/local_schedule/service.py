from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.contexts.events import ProgramExpectation, ProgramExpectationSnapshot
from app.contexts.integration.program_source import ProgramSourceUnavailableError, ProgramSyncResult
from app.contexts.production.event_mode_kernel.repository import EventModeKernelRepository
from app.shared.ids import EntityId
from app.shared.time import Clock

_MAXIMUM_BYTES = 4 * 1024 * 1024
_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LocalScheduleReadError(ProgramSourceUnavailableError):
    """The local schedule could not be read within its byte bound."""


class LocalScheduleContractError(ProgramSourceUnavailableError):
    """The complete local schedule does not satisfy the versioned contract."""


class _Session(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    session_key: _Text
    title: _Text
    speakers: tuple[_Text, ...]
    stage_key: _Text
    planned_start: AwareDatetime
    planned_end: AwareDatetime

    @field_validator("planned_start", "planned_end", mode="before")
    @classmethod
    def timestamp_string(cls, value: object) -> datetime:
        if not isinstance(value, str):
            raise ValueError("timestamp must be an ISO 8601 string")
        return datetime.fromisoformat(value)

    @model_validator(mode="after")
    def ordered_interval(self) -> _Session:
        if self.planned_end < self.planned_start:
            raise ValueError("planned end precedes start")
        return self


class _Schedule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    event_key: _Text
    sessions: tuple[_Session, ...] = Field(max_length=10_000)

    @model_validator(mode="after")
    def unique_session_keys(self) -> _Schedule:
        keys = [session.session_key for session in self.sessions]
        if len(set(keys)) != len(keys):
            raise LocalScheduleContractError("local_schedule_duplicate_session_key")
        return self


def _unique_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LocalScheduleContractError("local_schedule_duplicate_json_key")
        result[key] = value
    return result


class LocalScheduleFileSource:
    """One complete file read per invocation; persistence belongs to the repository."""

    def __init__(
        self,
        *,
        path: Path,
        event_key: str,
        stage_keys: tuple[str, ...],
        repository: EventModeKernelRepository,
        clock: Clock,
    ) -> None:
        self._path = path
        self._event_key = event_key
        self._stage_keys = frozenset(stage_keys)
        self._repository = repository
        self._clock = clock

    def _read(self) -> _Schedule:
        try:
            with self._path.open("rb") as handle:
                content = handle.read(_MAXIMUM_BYTES + 1)
        except OSError as exc:
            raise LocalScheduleReadError("local_schedule_unavailable") from exc
        if len(content) > _MAXIMUM_BYTES:
            raise LocalScheduleReadError("local_schedule_too_large")
        try:
            # Validate duplicate object members before the strict JSON model parser.
            json.loads(content, object_pairs_hook=_unique_members)
            schedule = _Schedule.model_validate_json(content)
        except (ValueError, RecursionError) as exc:
            raise LocalScheduleContractError("local_schedule_invalid_format") from exc
        if schedule.event_key != self._event_key:
            raise LocalScheduleContractError("local_schedule_event_key_mismatch")
        if any(session.stage_key not in self._stage_keys for session in schedule.sessions):
            raise LocalScheduleContractError("local_schedule_unknown_stage_key")
        return schedule

    def synchronize(self, *, event_id: EntityId, stage_id: EntityId) -> ProgramSyncResult:
        event = self._repository.get_event_by_key(self._event_key)
        if event is None or event.id != event_id:
            raise LocalScheduleContractError("local_schedule_event_scope_mismatch")
        stage = next(
            (item for item in self._repository.list_stages(event_id) if item.id == stage_id),
            None,
        )
        if stage is None or stage.key not in self._stage_keys:
            raise LocalScheduleContractError("local_schedule_stage_scope_mismatch")
        schedule = self._read()
        observed_at = self._clock.now()
        # Escape identity delimiters; neither file location nor title defines identity.
        event_key = quote(self._event_key, safe="")
        scope = f"local_file:{event_key}:{quote(stage.key, safe='')}"
        expectations = tuple(
            ProgramExpectation(
                id=EntityId.new(),
                event_id=event_id,
                key=f"local_file:{event_key}:{quote(session.session_key, safe='')}",
                stage_id=stage_id,
                title=session.title,
                speakers=session.speakers,
                planned_start=session.planned_start,
                planned_end=session.planned_end,
                external_references={
                    "provider": "local_file",
                    "external_event_id": schedule.event_key,
                    "external_session_id": session.session_key,
                    "external_room_id": session.stage_key,
                },
                revision=1,
                recorded_at=observed_at,
                synchronization_scope=scope,
                last_observed_at=observed_at,
                lifecycle_changed_at=observed_at,
            )
            for session in schedule.sessions
            if session.stage_key == stage.key
        )
        return self._repository.reconcile_program_expectations(
            ProgramExpectationSnapshot(
                event_id=event_id,
                stage_id=stage_id,
                provider="local_file",
                synchronization_scope=scope,
                observed_at=observed_at,
                expectations=expectations,
            )
        )

    def probe(self) -> int:
        return len(self._read().sessions)

    def cached_program(self, *, event_id: EntityId) -> tuple[ProgramExpectation, ...]:
        return self._repository.list_program_expectations(event_id)
