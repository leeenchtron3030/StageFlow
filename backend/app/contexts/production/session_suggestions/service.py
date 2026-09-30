from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from app.contexts.events import ProgramExpectationLifecycle
from app.contexts.production.event_mode_kernel.contracts import (
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
    StartSessionRequest,
)
from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock, require_aware_datetime

from . import policy_v3, policy_v4
from .boundary_proposals import produce_boundary_proposals
from .contracts import (
    POLICY_V3,
    Reference,
    ScheduleOffsetEntry,
    ScheduleOffsetSetting,
    SessionSuggestion,
    Span,
    SuggestionConflictError,
    SuggestionDecision,
    SuggestionNotFoundError,
    SuggestionRun,
    SuggestionStatus,
    validate_offset_entries,
)
from .repository import SuggestionRepository, SuggestionTransaction
from .work_queue import validate_work_queue_limit

# Internal evaluation selector; changing the production default needs owner approval.
POLICY_VERSION = 3


def kernel_operation_id(command_id: EntityId, command: str) -> EntityId:
    name = f"stageflow:session-suggestion:{command_id.value}:{command}"
    return EntityId(str(uuid5(NAMESPACE_URL, name)))


def reference_document(reference: Reference | None) -> dict[str, object] | None:
    return None if reference is None else {"id": reference.id.value, "revision": reference.revision}


def realized_expectation_ids(tx: SuggestionTransaction, event_id: EntityId) -> set[EntityId]:
    return {s.program_expectation_id
            for stage in tx.kernel.repository.list_stages(event_id)
            for s in tx.kernel.repository.list_sessions_for_stage(stage.id)
            if s.program_expectation_id is not None}


class SessionSuggestionService:
    def __init__(self, repository: SuggestionRepository, clock: Clock) -> None:
        self.repository, self.clock = repository, clock

    @staticmethod
    def _human(authority_kind: str) -> None:
        if authority_kind != "human":
            raise ValueError("session_suggestion_requires_human")

    def run(self, *, event_id: EntityId, stage_id: EntityId, actor_id: EntityId,
            start_cue_list: Reference | None = None, end_cue_list: Reference | None = None,
            authority_kind: str = "human") -> SuggestionRun:
        self._human(authority_kind)
        policy, evaluate = {
            3: (POLICY_V3, policy_v3.evaluate),
            4: (policy_v4.POLICY_V4, policy_v4.evaluate),
        }[POLICY_VERSION]
        with self.repository.transaction(self.clock) as tx:
            tx.lock_event(event_id)
            tx.scope(event_id, stage_id)
            if start_cue_list is None and end_cue_list is None:
                composition = tx.current_composition(event_id)
                if composition is not None:
                    start_cue_list = composition.start_cue_list
                    end_cue_list = composition.end_cue_list
            inputs = tx.snapshot(event_id, stage_id, start_cue_list, end_cue_list)
            override = tx.current_offset(event_id, stage_id)
            realized = realized_expectation_ids(tx, event_id)
            expected_ids = {x.id for x in inputs.expectations}
            linked = sorted((s for stage in tx.kernel.repository.list_stages(event_id)
                             for s in tx.kernel.repository.list_sessions_for_stage(stage.id)
                             if s.program_expectation_id in expected_ids), key=lambda s: s.id.value)
            # Serialize current-boundary reads against Kernel corrections without
            # locking unrelated Stage rows or changing the policy input snapshot.
            linked = [tx.boundary_session(event_id, s.id, lock=True) for s in linked]
            digest = human_command_digest({
                "event_id": event_id.value, "stage_id": stage_id.value,
                "policy": asdict(policy),
                # Only this Stage's expectations: a confirm on another Stage must not
                # force a new run here.
                "realized_expectation_ids": sorted(
                    x.id.value for x in inputs.expectations if x.id in realized),
                "linked_session_boundaries": [
                    {"id": s.id.value, "revision": s.revision,
                     "start": s.authoritative_start.isoformat(),
                     "end": (None if s.authoritative_end is None
                             else s.authoritative_end.isoformat())}
                    for s in linked],
                "override_setting_version": None if override is None else override.version,
                "expectations": [reference_document(Reference(x.id, x.revision))
                                 for x in sorted(inputs.expectations, key=lambda x: x.id.value)],
                "assets": [{"id": x.asset_id.value, "timing": reference_document(x.timing),
                            "segmentation": sorted(i.value for i in x.segmentation_ids),
                            "transcript": reference_document(x.transcript)}
                           for x in sorted(inputs.assets, key=lambda x: x.asset_id.value)],
                "start_cue_list": reference_document(start_cue_list),
                "end_cue_list": reference_document(end_cue_list),
            })
            prior = tx.find_run(digest)
            if prior is not None:
                return prior
            result = evaluate(inputs, override)
            # Keep realized talks in evaluation to preserve alignment and coverage.
            candidates = tuple(x for x in result.candidates
                               if x.expectation is None or x.expectation.id not in realized)
            skips = replace(result.skips,
                            already_realized=len(result.candidates) - len(candidates))
            by_expectation = {c.expectation.id: c for c in result.candidates
                              if c.expectation is not None and c.expectation.id in realized}
            proposals_created = sum(
                produce_boundary_proposals(tx, s, by_expectation[expected], policy=policy)
                for s in linked if (expected := s.program_expectation_id) in by_expectation)
            run = SuggestionRun(
                EntityId.new(), event_id, stage_id, digest, actor_id, self.clock.now(),
                tuple(Reference(x.id, x.revision) for x in inputs.expectations), inputs.assets,
                start_cue_list, end_cue_list, skips, policy, result.blocks,
                None if override is None else override.version,
                proposals_created,
            )
            tx.save_run(run, tuple(SessionSuggestion(EntityId.new(), run.id, event_id, stage_id, x,
                                                     policy.id, policy.version)
                                   for x in candidates))
            return run

    def latest_run(self, event_id: EntityId, stage_id: EntityId) -> SuggestionRun:
        with self.repository.transaction(self.clock) as tx:
            tx.scope(event_id, stage_id)
            run = tx.latest_run(event_id, stage_id)
            if run is None:
                raise SuggestionNotFoundError("suggestion_run_not_found")
            return run

    def list_pending_confirmations(
        self, event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
        limit: int = 50,
    ) -> tuple[ProducerWorkQueueSubject, ...]:
        validate_work_queue_limit(limit)
        with self.repository.transaction(self.clock) as tx:
            return tx.list_pending_confirmations(event_id, after=after, limit=limit)

    def set_offset(self, *, event_id: EntityId, stage_id: EntityId, command_id: EntityId,
                   actor_id: EntityId, entries: tuple[ScheduleOffsetEntry, ...],
                   authority_kind: str = "human") -> ScheduleOffsetSetting:
        self._human(authority_kind)
        entries = tuple(entries)
        validate_offset_entries(entries)
        digest = human_command_digest({
            "event_id": event_id.value, "stage_id": stage_id.value, "set_by": actor_id.value,
            "entries": [{"effective_from": e.effective_from.isoformat(),
                         "offset_seconds": e.offset_seconds} for e in entries],
        })
        with self.repository.transaction(self.clock) as tx:
            tx.lock_event(event_id)
            tx.scope(event_id, stage_id)
            prior = tx.replay_offset(command_id, digest)
            if prior is not None:
                return prior
            current = tx.current_offset(event_id, stage_id)
            setting = ScheduleOffsetSetting(
                event_id, stage_id, 1 if current is None else current.version + 1,
                command_id, digest, actor_id, self.clock.now(), entries,
            )
            tx.save_offset(setting)
            return setting

    def current_offset(self, event_id: EntityId, stage_id: EntityId
                       ) -> ScheduleOffsetSetting | None:
        with self.repository.transaction(self.clock) as tx:
            tx.scope(event_id, stage_id)
            return tx.current_offset(event_id, stage_id)

    def offset_history(self, event_id: EntityId, stage_id: EntityId, *, after: int = 0,
                       limit: int = 50) -> tuple[tuple[ScheduleOffsetSetting, ...], int | None]:
        if type(after) is not int or not 0 <= after <= 2_147_483_647 or not 1 <= limit <= 100:
            raise ValueError("invalid schedule offset history page")
        with self.repository.transaction(self.clock) as tx:
            tx.scope(event_id, stage_id)
            values = tx.offset_history(event_id, stage_id, after, limit + 1)
            return values[:limit], values[limit - 1].version if len(values) > limit else None

    def read(self, event_id: EntityId, suggestion_id: EntityId
             ) -> tuple[SessionSuggestion, SuggestionStatus]:
        with self.repository.transaction(self.clock) as tx:
            value = tx.get(event_id, suggestion_id)
            return value, tx.status(value)

    def page(self, event_id: EntityId, stage_id: EntityId, *,
             status: SuggestionStatus = SuggestionStatus.OPEN, after: EntityId | None = None,
             limit: int = 50) -> tuple[tuple[SessionSuggestion, ...], EntityId | None]:
        if not 1 <= limit <= 100:
            raise ValueError("invalid suggestion page limit")
        with self.repository.transaction(self.clock) as tx:
            tx.scope(event_id, stage_id)
            values = tx.page(event_id, stage_id, status, after, limit + 1)
            return values[:limit], values[limit - 1].id if len(values) > limit else None

    def confirm(self, *, event_id: EntityId, suggestion_id: EntityId,
                command_id: EntityId, actor_id: EntityId, start: datetime | None = None,
                end: datetime | None = None, authority_kind: str = "human") -> SuggestionDecision:
        return self._decide(event_id, suggestion_id, command_id, actor_id,
                            SuggestionStatus.CONFIRMED, start, end, None, authority_kind)

    def reject(self, *, event_id: EntityId, suggestion_id: EntityId,
               command_id: EntityId, actor_id: EntityId, reason: str,
               authority_kind: str = "human") -> SuggestionDecision:
        if not 1 <= len(reason.strip()) <= 500 or "\x00" in reason:
            raise ValueError("rejection reason out of bounds")
        return self._decide(event_id, suggestion_id, command_id, actor_id,
                            SuggestionStatus.REJECTED, None, None, reason.strip(), authority_kind)

    def _decide(self, event_id: EntityId, suggestion_id: EntityId, command_id: EntityId,
                actor_id: EntityId, kind: SuggestionStatus, start: datetime | None,
                end: datetime | None, reason: str | None,
                authority_kind: str) -> SuggestionDecision:
        self._human(authority_kind)

        for value in (start, end):
            if value is not None:
                require_aware_datetime(value, "adjusted boundary")
        digest = human_command_digest({
            "event_id": event_id.value, "suggestion_id": suggestion_id.value,
            "actor_id": actor_id.value, "kind": kind.value, "reason": reason,
            "start": None if start is None else start.astimezone(UTC).isoformat(),
            "end": None if end is None else end.astimezone(UTC).isoformat(),
        })
        with self.repository.transaction(self.clock) as tx:
            replay = tx.replay(command_id, digest)
            if replay is not None:
                return replay
            suggestion = tx.get(event_id, suggestion_id)
            tx.decision_scope(event_id, suggestion.stage_id)
            if tx.status(suggestion) != SuggestionStatus.OPEN:
                raise SuggestionConflictError("suggestion_not_open")
            now = self.clock.now()
            session_id, used = None, None
            if kind == SuggestionStatus.CONFIRMED:
                used = Span(start or suggestion.candidate.span.start,
                            end or suggestion.candidate.span.end)
                expected = suggestion.candidate.expectation
                expectation = (None if expected is None
                               else tx.kernel.repository.get_program_expectation(expected.id))
                if expected is not None:
                    if (expectation is None or expectation.revision != expected.revision
                            or expectation.lifecycle_state != ProgramExpectationLifecycle.CURRENT
                            or expectation.stage_id != suggestion.stage_id):
                        raise SuggestionConflictError("stale_expectation_revision")
                    if expected.id in realized_expectation_ids(tx, event_id):
                        raise SuggestionConflictError("expectation_already_realized")
                session = tx.kernel.start_session(StartSessionRequest(
                    operation_id=kernel_operation_id(command_id, "start"), event_id=event_id,
                    stage_id=suggestion.stage_id, actor_id=actor_id,
                    authoritative_start=used.start,
                    requested_at=now,
                    program_expectation_id=None if expected is None else expected.id,
                    title=None if expectation is None else expectation.title,
                ))
                tx.kernel.correct_session_boundary(
                    operation_id=kernel_operation_id(command_id, "end"), session_id=session.id,
                    boundary_kind="end", boundary_at=used.end, actor_id=actor_id,
                    reason="session_suggestion_confirmed",
                )
                session_id = session.id
            decision = SuggestionDecision(command_id, digest, suggestion_id, actor_id, now,
                                           kind, reason, session_id, used)
            tx.save_decision(decision)
            return decision
