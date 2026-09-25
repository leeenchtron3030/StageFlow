"""Synchronous program-source boundary; planned context never realizes Sessions."""

from typing import Protocol, runtime_checkable

from app.contexts.events import ProgramExpectation, ProgramExpectationReconciliation
from app.shared.ids import EntityId

ProgramSyncResult = ProgramExpectationReconciliation


class ProgramSourceUnavailableError(RuntimeError):
    """A source could not supply a complete, valid snapshot; keep the durable cache."""


@runtime_checkable
class ProgramScheduleSource(Protocol):
    def synchronize(self, *, event_id: EntityId, stage_id: EntityId) -> ProgramSyncResult: ...

    def probe(self) -> int: ...

    def cached_program(self, *, event_id: EntityId) -> tuple[ProgramExpectation, ...]: ...
