"""Transactional process-local test double; never a production fallback."""
from collections.abc import Generator
from contextlib import contextmanager
from copy import copy
from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock
from typing import cast

from app.contexts.editorial.derivation import match_phrases
from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.contexts.editorial.derivation_memory import InMemoryEditorialDerivationRepository
from app.contexts.production.event_mode_kernel.contracts import (
    BoundaryDecision,
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
    Session,
    SessionBoundaryProposal,
)
from app.contexts.production.event_mode_kernel.repository import InMemoryEventModeKernelRepository
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.work_queue import work_queue_sort_key
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    AssetInput,
    BoundaryProposalDecision,
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
from .cue_composition import BoundaryCueComposition
from .repository import SuggestionTransaction
from .work_queue import suggestion_work_queue_subject, validate_work_queue_limit


class InMemorySuggestionRepository:
    def __init__(self, kernel: InMemoryEventModeKernelRepository,
                 editorial: InMemoryEditorialDerivationRepository | None = None) -> None:
        self.kernel_repository = kernel
        self.editorial = editorial or InMemoryEditorialDerivationRepository()
        self.assets: dict[EntityId, tuple[AssetInput, ...]] = {}
        self.runs: dict[EntityId, SuggestionRun] = {}
        self.suggestions: dict[EntityId, SessionSuggestion] = {}
        self.decisions: dict[EntityId, SuggestionDecision] = {}
        self.boundary_decisions: dict[EntityId, BoundaryProposalDecision] = {}
        self.offsets: dict[EntityId, ScheduleOffsetSetting] = {}
        self.compositions: dict[EntityId, BoundaryCueComposition] = {}

    @contextmanager
    def transaction(self, clock: Clock) -> Generator[SuggestionTransaction]:
        # The existing memory Kernel is a test double with immutable values. Retain
        # its collections under its own lock to simulate the SQL unit of work.
        with (cast(RLock, vars(self.kernel_repository)["_lock"]),
              self.editorial.transaction()):
            kernel_state = {k: copy(v) for k, v in vars(self.kernel_repository).items()
                            if k != "_lock"}
            state = (self.runs.copy(), self.suggestions.copy(),
                     self.decisions.copy(), self.offsets.copy(), self.compositions.copy(),
                     self.boundary_decisions.copy())
            self.kernel = DurableEventModeKernel(repository=self.kernel_repository, clock=clock)
            try:
                yield self
            except BaseException:
                vars(self.kernel_repository).update(kernel_state)
                (self.runs, self.suggestions, self.decisions, self.offsets,
                 self.compositions, self.boundary_decisions) = state
                raise

    def boundary_session(self, event_id: EntityId, session_id: EntityId,
                         *, lock: bool = False) -> Session:
        session = self.kernel_repository.get_session(session_id)
        if session is None or session.event_id != event_id:
            raise SuggestionNotFoundError("session_not_found")
        return session

    def _boundary_proposals(self) -> dict[EntityId, SessionBoundaryProposal]:
        return cast(dict[EntityId, SessionBoundaryProposal],
                    vars(self.kernel_repository)["_boundary_proposals"])

    def boundary_proposal(self, session_id: EntityId,
                          proposal_id: EntityId) -> SessionBoundaryProposal:
        proposal = self._boundary_proposals().get(proposal_id)
        if proposal is None or proposal.session_id != session_id:
            raise SuggestionNotFoundError("boundary_proposal_not_found")
        return proposal

    def boundary_decided(self, proposal_id: EntityId) -> bool:
        return any(d.proposal_id == proposal_id for d in self.boundary_decisions.values())

    def boundary_stale(self, proposal: SessionBoundaryProposal) -> bool:
        boundaries = cast(list[BoundaryDecision], vars(self.kernel_repository)["_boundaries"])
        return any(b.session_id == proposal.session_id and b.boundary_kind == proposal.boundary_kind
                   and b.decided_at > proposal.proposed_at for b in boundaries) or any(
            p.session_id == proposal.session_id and p.boundary_kind == proposal.boundary_kind
            and (p.proposed_at, p.id.value) > (proposal.proposed_at, proposal.id.value)
            for p in self._boundary_proposals().values())

    def latest_nonstale_boundary_proposals(self, session_id: EntityId
                                           ) -> tuple[SessionBoundaryProposal, ...]:
        """Latest per edge, regardless of decision, unless corrected since proposal."""
        return tuple(sorted((p for p in self._boundary_proposals().values()
                             if p.session_id == session_id and not self.boundary_stale(p)),
                            key=lambda p: p.boundary_kind))

    def open_boundary_proposals(self, session_id: EntityId
                                ) -> tuple[SessionBoundaryProposal, ...]:
        return tuple(sorted((p for p in self._boundary_proposals().values()
                             if p.session_id == session_id and not self.boundary_decided(p.id)
                             and not self.boundary_stale(p)), key=lambda p: p.boundary_kind))

    def replay_boundary_decision(self, command_id: EntityId, digest: str
                                 ) -> BoundaryProposalDecision | None:
        prior = self.boundary_decisions.get(command_id)
        if prior is not None and prior.request_digest != digest:
            raise SuggestionConflictError("boundary_proposal_command_id_conflict")
        return prior

    def save_boundary_decision(self, value: BoundaryProposalDecision) -> None:
        if value.command_id in self.boundary_decisions or self.boundary_decided(value.proposal_id):
            raise SuggestionConflictError("boundary_proposal_decided")
        self.boundary_decisions[value.command_id] = value

    def boundary_decision_history(self, session_id: EntityId, after: EntityId | None,
                                  limit: int) -> tuple[BoundaryProposalDecision, ...]:
        return tuple(sorted((d for d in self.boundary_decisions.values()
                             if d.session_id == session_id
                             and (after is None or d.command_id.value > after.value)),
                            key=lambda d: d.command_id.value))[:limit]

    def cue_event_scope(self, event_id: EntityId) -> None:
        if event_id not in cast(dict[EntityId, object], vars(self.kernel_repository)["_events"]):
            raise SuggestionNotFoundError("event_not_found")

    def current_composition(self, event_id: EntityId) -> BoundaryCueComposition | None:
        values = [v for v in self.compositions.values() if v.event_id == event_id]
        return max(values, key=lambda v: v.version, default=None)

    def replay_composition(self, command_id: EntityId, digest: str
                           ) -> BoundaryCueComposition | None:
        value = self.compositions.get(command_id)
        if value is not None and value.request_digest != digest:
            raise SuggestionConflictError("cue_composition_command_id_conflict")
        return value

    def publish_cue_list(self, value: EditorialPhraseList) -> EditorialPhraseList:
        self.cue_event_scope(value.event_id)
        prior = next((p for p in self.editorial.phrases.values()
                      if p.event_id == value.event_id and p.key == value.key), None)
        if prior is not None:
            value = replace(value, id=prior.id)
        if (value.id, value.version) in self.editorial.phrases:
            raise SuggestionConflictError("phrase_list_version_exists")
        self.editorial.phrases[value.id, value.version] = value
        return value

    def save_composition(self, value: BoundaryCueComposition) -> None:
        if value.command_id in self.compositions or any(
                v.event_id == value.event_id and v.version == value.version
                for v in self.compositions.values()):
            raise SuggestionConflictError("cue_composition_exists")
        self.compositions[value.command_id] = value

    def composition_history(self, event_id: EntityId, after: int, limit: int
                            ) -> tuple[BoundaryCueComposition, ...]:
        return tuple(sorted((v for v in self.compositions.values()
                             if v.event_id == event_id and v.version > after),
                            key=lambda v: v.version))[:limit]

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

    def latest_run(self, event_id: EntityId, stage_id: EntityId) -> SuggestionRun | None:
        return next((r for r in reversed(tuple(self.runs.values()))
                     if r.event_id == event_id and r.stage_id == stage_id), None)

    def list_pending_confirmations(
        self, event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
        limit: int = 50,
    ) -> tuple[ProducerWorkQueueSubject, ...]:
        validate_work_queue_limit(limit)
        latest = {r.stage_id: r for r in self.runs.values() if r.event_id == event_id}
        items: list[ProducerWorkQueueSubject] = []
        for run in latest.values():
            opened = [s for s in self.suggestions.values()
                      if s.run_id == run.id and self.status(s) == SuggestionStatus.OPEN]
            if opened:
                item = suggestion_work_queue_subject(
                    event_id=event_id, stage_id=run.stage_id, run_id=run.id,
                    created_at=run.created_at, open_count=len(opened),
                    weak_count=sum(s.candidate.strength == "weak" for s in opened),
                )
                if after is None or work_queue_sort_key(item) > (
                        after.priority, after.updated_at, after.projection_id):
                    items.append(item)
        return tuple(sorted(items, key=work_queue_sort_key)[:limit])

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
