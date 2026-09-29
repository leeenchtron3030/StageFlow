from dataclasses import asdict
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from app.contexts.events import ProgramExpectationLifecycle
from app.contexts.production.event_mode_kernel.contracts import StartSessionRequest
from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock, require_aware_datetime

from .contracts import (
    POLICY_V1,
    Reference,
    SessionSuggestion,
    Span,
    SuggestionConflictError,
    SuggestionDecision,
    SuggestionRun,
    SuggestionStatus,
)
from .policy import evaluate
from .repository import SuggestionRepository


def kernel_operation_id(command_id: EntityId, command: str) -> EntityId:
    name = f"stageflow:session-suggestion:{command_id.value}:{command}"
    return EntityId(str(uuid5(NAMESPACE_URL, name)))


def reference_document(reference: Reference | None) -> dict[str, object] | None:
    return None if reference is None else {"id": reference.id.value, "revision": reference.revision}


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
        with self.repository.transaction(self.clock) as tx:
            tx.lock_event(event_id)
            tx.scope(event_id, stage_id)
            inputs = tx.snapshot(event_id, stage_id, start_cue_list, end_cue_list)
            digest = human_command_digest({
                "event_id": event_id.value, "stage_id": stage_id.value,
                "policy": asdict(POLICY_V1),
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
            result = evaluate(inputs)
            run = SuggestionRun(
                EntityId.new(), event_id, stage_id, digest, actor_id, self.clock.now(),
                tuple(Reference(x.id, x.revision) for x in inputs.expectations), inputs.assets,
                start_cue_list, end_cue_list, result.skips,
            )
            tx.save_run(run, tuple(SessionSuggestion(EntityId.new(), run.id, event_id, stage_id, x)
                                   for x in result.candidates))
            return run

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
                    if any(s.program_expectation_id == expected.id
                           for stage in tx.kernel.repository.list_stages(event_id)
                           for s in tx.kernel.repository.list_sessions_for_stage(stage.id)):
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
