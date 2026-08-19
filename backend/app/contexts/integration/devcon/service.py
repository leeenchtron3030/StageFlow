from __future__ import annotations

from dataclasses import dataclass

from app.contexts.events import ProgramExpectation
from app.contexts.production.event_mode_kernel.repository import (
    EventModeKernelRepository,
    KernelConflictError,
    KernelNotFoundError,
)
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import ExternalProgramSource


@dataclass(frozen=True, slots=True)
class ProgramSyncResult:
    event_id: EntityId
    stage_id: EntityId
    expectations: tuple[ProgramExpectation, ...]


class DevconProgramSync:
    def __init__(
        self,
        *,
        repository: EventModeKernelRepository,
        source: ExternalProgramSource,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._source = source
        self._clock = clock

    def synchronize(
        self, *, event_id: EntityId, stage_id: EntityId
    ) -> ProgramSyncResult:
        stage = next(
            (
                candidate
                for candidate in self._repository.list_stages(event_id)
                if candidate.id == stage_id
            ),
            None,
        )
        if stage is None:
            raise KernelNotFoundError("demo_stage_not_found")
        if stage.event_id != event_id:
            raise KernelConflictError("demo_stage_event_mismatch")

        recorded_at = self._clock.now()
        synchronized: list[ProgramExpectation] = []
        for item in self._source.fetch_program():
            synchronized.append(
                self._repository.put_program_expectation(
                    ProgramExpectation(
                        id=EntityId.new(),
                        event_id=event_id,
                        key=f"devcon:{item.event_id}:{item.session_id}",
                        stage_id=stage_id,
                        title=item.title,
                        speakers=item.speakers,
                        planned_start=item.planned_start,
                        planned_end=item.planned_end,
                        external_references={
                            "provider": "devcon",
                            "devcon_event_id": item.event_id,
                            "devcon_session_id": item.session_id,
                            "devcon_room_id": item.room_id,
                            "devcon_room_name": item.room_name,
                        },
                        revision=1,
                        recorded_at=recorded_at,
                    )
                )
            )
        return ProgramSyncResult(
            event_id=event_id,
            stage_id=stage_id,
            expectations=tuple(synchronized),
        )

    def probe(self) -> int:
        return len(self._source.fetch_program())

    def cached_program(self, *, event_id: EntityId) -> tuple[ProgramExpectation, ...]:
        return self._repository.list_program_expectations(event_id)


__all__ = ["DevconProgramSync", "ProgramSyncResult"]
