from __future__ import annotations

from app.contexts.events import (
    ProgramExpectation,
    ProgramExpectationLifecycle,
    ProgramExpectationReconciliation,
    ProgramExpectationSnapshot,
)
from app.contexts.production.event_mode_kernel.repository import (
    EventModeKernelRepository,
    KernelConflictError,
    KernelNotFoundError,
)
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import ExternalProgramSource

ProgramSyncResult = ProgramExpectationReconciliation


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

    def synchronize(self, *, event_id: EntityId, stage_id: EntityId) -> ProgramSyncResult:
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

        fetched = self._source.fetch_program()
        synchronized_at = self._clock.now()
        scope = f"{self._source.provider}:{self._source.event_id}:{self._source.room_id}"
        expectations: list[ProgramExpectation] = []
        for item in fetched:
            if item.event_id != self._source.event_id or item.room_id != self._source.room_id:
                raise KernelConflictError("devcon_program_snapshot_scope_mismatch")
            expectations.append(
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
                    recorded_at=synchronized_at,
                    lifecycle_state=ProgramExpectationLifecycle.CURRENT,
                    synchronization_scope=scope,
                    last_observed_at=synchronized_at,
                    lifecycle_changed_at=synchronized_at,
                )
            )
        return self._repository.reconcile_program_expectations(
            ProgramExpectationSnapshot(
                event_id=event_id,
                stage_id=stage_id,
                provider=self._source.provider,
                synchronization_scope=scope,
                observed_at=synchronized_at,
                expectations=tuple(expectations),
            )
        )

    def probe(self) -> int:
        return len(self._source.fetch_program())

    def cached_program(self, *, event_id: EntityId) -> tuple[ProgramExpectation, ...]:
        return self._repository.list_program_expectations(event_id)


__all__ = ["DevconProgramSync", "ProgramSyncResult"]
