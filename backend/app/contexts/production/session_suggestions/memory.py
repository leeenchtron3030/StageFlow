"""Transactional process-local test double; never a production fallback."""
from collections.abc import Generator
from contextlib import contextmanager
from copy import copy
from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock
from typing import cast

from app.contexts.editorial.derivation import match_phrases
from app.contexts.editorial.derivation_memory import InMemoryEditorialDerivationRepository
from app.contexts.production.event_mode_kernel.repository import InMemoryEventModeKernelRepository
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    AssetInput,
    InputSnapshot,
    Reference,
    ScheduleOffsetSetting,
    SessionSuggestion,
    SuggestionConflictError,
    SuggestionDecision,
    SuggestionNotFoundError,
    SuggestionRun,
    SuggestionStatus,
)
from .repository import SuggestionTransaction


class InMemorySuggestionRepository:
    def __init__(self, kernel: InMemoryEventModeKernelRepository,
                 editorial: InMemoryEditorialDerivationRepository | None = None) -> None:
        self.kernel_repository = kernel
        self.editorial = editorial or InMemoryEditorialDerivationRepository()
        self.assets: dict[EntityId, tuple[AssetInput, ...]] = {}
        self.runs: dict[EntityId, SuggestionRun] = {}
        self.suggestions: dict[EntityId, SessionSuggestion] = {}
        self.decisions: dict[EntityId, SuggestionDecision] = {}
        self.offsets: dict[EntityId, ScheduleOffsetSetting] = {}

    @contextmanager
    def transaction(self, clock: Clock) -> Generator[SuggestionTransaction]:
        # The existing memory Kernel is a test double with immutable values. Retain
        # its collections under its own lock to simulate the SQL unit of work.
        with cast(RLock, vars(self.kernel_repository)["_lock"]):
            kernel_state = {k: copy(v) for k, v in vars(self.kernel_repository).items()
                            if k != "_lock"}
            state = (self.runs.copy(), self.suggestions.copy(),
                     self.decisions.copy(), self.offsets.copy())
            self.kernel = DurableEventModeKernel(repository=self.kernel_repository, clock=clock)
            try:
                yield self
            except BaseException:
                vars(self.kernel_repository).update(kernel_state)
                self.runs, self.suggestions, self.decisions, self.offsets = state
                raise

    def scope(self, event_id: EntityId, stage_id: EntityId) -> None:
        if all(s.id != stage_id for s in self.kernel_repository.list_stages(event_id)):
            raise SuggestionNotFoundError("stage_not_found")

    def lock_event(self, event_id: EntityId) -> None:
        # The transaction already holds the memory Kernel's lock.
        pass

    def decision_scope(self, event_id: EntityId, stage_id: EntityId) -> None:
        self.scope(event_id, stage_id)

    def current_offset(self, event_id: EntityId, stage_id: EntityId
                       ) -> ScheduleOffsetSetting | None:
        return next((s for s in reversed(tuple(self.offsets.values()))
                     if s.event_id == event_id and s.stage_id == stage_id), None)

    def replay_offset(self, command_id: EntityId, digest: str) -> ScheduleOffsetSetting | None:
        prior = self.offsets.get(command_id)
        if prior is not None and prior.request_digest != digest:
            raise SuggestionConflictError("schedule_offset_command_id_conflict")
        return prior

    def save_offset(self, setting: ScheduleOffsetSetting) -> None:
        if setting.command_id in self.offsets or any(
                s.stage_id == setting.stage_id and s.version == setting.version
                for s in self.offsets.values()):
            raise SuggestionConflictError("schedule_offset_setting_exists")
        self.offsets[setting.command_id] = setting

    def offset_history(self, event_id: EntityId, stage_id: EntityId, after: int,
                       limit: int) -> tuple[ScheduleOffsetSetting, ...]:
        return tuple(sorted((s for s in self.offsets.values()
                             if s.event_id == event_id and s.stage_id == stage_id
                             and s.version > after), key=lambda s: s.version))[:limit]

    def snapshot(self, event_id: EntityId, stage_id: EntityId,
                 start_cues: Reference | None, end_cues: Reference | None) -> InputSnapshot:
        phrases = [None if ref is None else self.editorial.phrase_list(ref.id, ref.revision)
                   for ref in (start_cues, end_cues)]
        if any(p is not None and p.event_id != event_id for p in phrases):
            raise SuggestionConflictError("phrase_list_event_mismatch")
        assets: list[AssetInput] = []
        for item in self.assets.get(stage_id, ()):
            cues: list[list[datetime]] = [[], []]
            if item.transcript is not None and item.coverage is not None:
                for i, phrase_list in enumerate(phrases):
                    if phrase_list is not None:
                        for segment in self.editorial.transcript_segments(item.transcript.id):
                            cues[i].extend(item.coverage.start + timedelta(
                                microseconds=m.first_word.asset_start_microseconds)
                                for m in match_phrases(phrase_list, segment))
            assets.append(replace(item, start_cues=tuple(cues[0]), end_cues=tuple(cues[1])))
        expectations = self.kernel_repository.list_program_expectations(event_id)
        return InputSnapshot(
            tuple(x for x in expectations if x.stage_id == stage_id), tuple(assets))

    def find_run(self, digest: str) -> SuggestionRun | None:
        seen_stages: set[EntityId] = set()
        for run in reversed(tuple(self.runs.values())):
            if run.stage_id not in seen_stages and run.input_digest == digest:
                return run
            seen_stages.add(run.stage_id)
        return None

    def save_run(self, run: SuggestionRun, suggestions: tuple[SessionSuggestion, ...]) -> None:
        if run.id in self.runs or any(x.id in self.suggestions for x in suggestions):
            raise SuggestionConflictError("suggestion_run_exists")
        self.runs[run.id] = run
        self.suggestions.update((x.id, x) for x in suggestions)

    def get(self, event_id: EntityId, suggestion_id: EntityId) -> SessionSuggestion:
        value = self.suggestions.get(suggestion_id)
        if value is None or value.event_id != event_id:
            raise SuggestionNotFoundError("suggestion_not_found")
        return value

    def status(self, suggestion: SessionSuggestion) -> SuggestionStatus:
        latest = next(x for x in reversed(tuple(self.runs.values()))
                      if x.stage_id == suggestion.stage_id)
        if latest.id != suggestion.run_id:
            return SuggestionStatus.SUPERSEDED
        decision = next((d for d in self.decisions.values()
                         if d.suggestion_id == suggestion.id), None)
        return SuggestionStatus.OPEN if decision is None else decision.kind

    def replay(self, command_id: EntityId, digest: str) -> SuggestionDecision | None:
        prior = self.decisions.get(command_id)
        if prior is not None and prior.request_digest != digest:
            raise SuggestionConflictError("suggestion_command_id_conflict")
        return prior

    def save_decision(self, decision: SuggestionDecision) -> None:
        if (decision.command_id in self.decisions
                or any(x.suggestion_id == decision.suggestion_id for x in self.decisions.values())):
            raise SuggestionConflictError("suggestion_decision_exists")
        self.decisions[decision.command_id] = decision

    def page(self, event_id: EntityId, stage_id: EntityId, status: SuggestionStatus,
             after: EntityId | None, limit: int) -> tuple[SessionSuggestion, ...]:
        return tuple(sorted((x for x in self.suggestions.values()
                             if x.event_id == event_id and x.stage_id == stage_id
                             and self.status(x) == status
                             and (after is None or x.id.value > after.value)),
                            key=lambda x: x.id.value))[:limit]
