import ast
import inspect
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from app.contexts.production.event_mode_kernel.contracts import StartSessionRequest
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.contracts import (
    Reference,
    SessionSuggestion,
    SkipCounts,
    SuggestionConflictError,
    SuggestionRun,
    SuggestionStatus,
)
from app.contexts.production.session_suggestions.memory import InMemorySuggestionRepository
from app.contexts.production.session_suggestions.service import (
    SessionSuggestionService,
    kernel_operation_id,
)
from app.infrastructure.postgres import event_mode_kernel_repository, session_suggestion_repository
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_durable_event_mode_kernel import ACTOR_ID, kernel_with_bootstrap
from tests.test_session_suggestion_policy import NOW, asset, at


class Harness:
    def __init__(self) -> None:
        self.kernel, self.kernel_repo, self.event, self.stage, _ = kernel_with_bootstrap()
        self.expectation = self.kernel.record_program_expectation(
            event_id=self.event, stage_id=self.stage, key="synthetic", title="Synthetic talk",
            planned_start=at(0), planned_end=at(1800),
        )
        self.repository = InMemorySuggestionRepository(self.kernel_repo)
        self.repository.assets[self.stage] = (asset(0, 1800),)
        self.service = SessionSuggestionService(self.repository, FixedClock(NOW))

    def run(self) -> SuggestionRun:
        return self.service.run(event_id=self.event, stage_id=self.stage, actor_id=ACTOR_ID)

    def suggestion(self) -> SessionSuggestion:
        self.run()
        return self.service.page(self.event, self.stage)[0][0]


def test_run_input_digest_skip_counts_and_no_authority() -> None:
    h = Harness()
    first = h.run()
    assert h.run() == first
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)
    old = h.suggestion()
    h.repository.assets[h.stage] = (replace(asset(0, 1800), segmentation_ids=()),)
    second = h.run()
    assert second.id != first.id and second.skips.no_segmentation == 1
    assert h.service.read(h.event, old.id)[1] == SuggestionStatus.SUPERSEDED
    assert len(h.service.page(h.event, h.stage, status=SuggestionStatus.SUPERSEDED)[0]) == 1
    with pytest.raises(SuggestionConflictError, match="not_open"):
        h.service.confirm(event_id=h.event, suggestion_id=old.id,
                          command_id=EntityId.new(), actor_id=ACTOR_ID)


def test_confirm_adjusted_times_kernel_arguments_replay_and_no_automatic_completion() -> None:
    h = Harness()
    suggestion, command = h.suggestion(), EntityId.new()
    result = h.service.confirm(event_id=h.event, suggestion_id=suggestion.id, command_id=command,
                               actor_id=ACTOR_ID, start=at(10), end=at(1750))
    assert result.session_id is not None
    session = h.kernel_repo.get_session(result.session_id)
    assert session is not None
    assert session.authoritative_start == at(10) and session.authoritative_end == at(1750)
    assert session.title == h.expectation.title
    assert session.program_expectation_id == h.expectation.id
    assert session.package_state.value == "assembling"
    assert h.service.confirm(event_id=h.event, suggestion_id=suggestion.id, command_id=command,
                             actor_id=ACTOR_ID, start=at(10), end=at(1750)) == result
    assert len(h.kernel_repo.list_sessions_for_stage(h.stage)) == 1
    assert h.service.read(h.event, suggestion.id)[1] == SuggestionStatus.CONFIRMED
    assert kernel_operation_id(command, "start") != kernel_operation_id(command, "end")
    with pytest.raises(SuggestionConflictError, match="command_id_conflict"):
        h.service.confirm(event_id=h.event, suggestion_id=suggestion.id, command_id=command,
                           actor_id=ACTOR_ID, start=at(11), end=at(1750))


@pytest.mark.parametrize("failure_point", ["end", "decision"])
def test_crash_between_kernel_calls_and_decision_rolls_back_then_replays(
    failure_point: str,
) -> None:
    h = Harness()
    suggestion, command = h.suggestion(), EntityId.new()
    target = (patch.object(DurableEventModeKernel, "correct_session_boundary",
                           side_effect=RuntimeError("crash")) if failure_point == "end"
              else patch.object(h.repository, "save_decision", side_effect=RuntimeError("crash")))
    with target, pytest.raises(RuntimeError, match="crash"):
        h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                          command_id=command, actor_id=ACTOR_ID)
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)
    assert h.service.read(h.event, suggestion.id)[1] == SuggestionStatus.OPEN
    result = h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                               command_id=command, actor_id=ACTOR_ID)
    assert result.session_id is not None
    assert len(h.kernel_repo.list_sessions_for_stage(h.stage)) == 1


def test_stale_and_already_realized_typed_refusals() -> None:
    h = Harness()
    old = h.suggestion()
    h.kernel.record_program_expectation(event_id=h.event, stage_id=h.stage, key="synthetic",
                                         title="Revised", planned_start=at(0), planned_end=at(1800))
    with pytest.raises(SuggestionConflictError, match="stale_expectation_revision"):
        h.service.confirm(event_id=h.event, suggestion_id=old.id,
                          command_id=EntityId.new(), actor_id=ACTOR_ID)
    new = h.suggestion()
    # A direct Kernel start can realize the talk after evaluation, before confirm.
    h.kernel.start_session(StartSessionRequest(
        operation_id=EntityId.new(), event_id=h.event, stage_id=h.stage,
        actor_id=ACTOR_ID, authoritative_start=at(0), requested_at=NOW,
        program_expectation_id=h.expectation.id,
    ))
    with pytest.raises(SuggestionConflictError, match="expectation_already_realized"):
        h.service.confirm(event_id=h.event, suggestion_id=new.id,
                          command_id=EntityId.new(), actor_id=ACTOR_ID)


def test_reject_bounds_replay_and_human_authority() -> None:
    h = Harness()
    suggestion, command = h.suggestion(), EntityId.new()
    rejected = h.service.reject(event_id=h.event, suggestion_id=suggestion.id, command_id=command,
                                actor_id=ACTOR_ID, reason="Different presentation")
    assert h.service.reject(event_id=h.event, suggestion_id=suggestion.id, command_id=command,
                            actor_id=ACTOR_ID, reason="Different presentation") == rejected
    assert h.service.read(h.event, suggestion.id)[1] == SuggestionStatus.REJECTED
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)
    with pytest.raises(ValueError):
        h.service.reject(event_id=h.event, suggestion_id=suggestion.id, command_id=EntityId.new(),
                          actor_id=ACTOR_ID, reason=" " * 501)
    with pytest.raises(ValueError, match="requires_human"):
        h.service.run(event_id=h.event, stage_id=h.stage,
                      actor_id=ACTOR_ID, authority_kind="automatic")


def test_optional_cues_reuse_phrase_matching_without_editorial_candidates() -> None:
    from app.contexts.editorial.derivation_contracts import EditorialPhraseList
    from tests.test_derived_editorial_candidates import segment

    h = Harness()
    phrases = EditorialPhraseList(EntityId.new(), h.event, "start", 1, "Start cues",
                                   ("silver lantern",), ACTOR_ID, NOW)
    h.repository.editorial.phrases[phrases.id, 1] = phrases
    transcript_id = EntityId.new()
    h.repository.editorial.segments[transcript_id] = (segment("silver lantern"),)
    h.repository.assets[h.stage] = (
        replace(asset(0, 1800), transcript=Reference(transcript_id, 1)),)
    run = h.service.run(event_id=h.event, stage_id=h.stage, actor_id=ACTOR_ID,
                        start_cue_list=Reference(phrases.id, 1))
    assert run.assets[0].start_cues == (NOW,)
    assert not h.repository.editorial.candidates
    assert h.service.page(h.event, h.stage)[0][0].candidate.start_cue_support


def test_kernel_import_boundary() -> None:
    root = Path(__file__).parents[1] / "app" / "contexts" / "production" / "event_mode_kernel"
    assert tuple(root.glob("*.py")), "Kernel import-boundary scan must inspect real files"
    assert all("session_suggestions" not in path.read_text(encoding="utf-8")
               for path in root.glob("*.py"))


@pytest.mark.parametrize("decision", ["confirm", "reject"])
def test_new_run_supersedes_decided_suggestion_but_command_replay_is_retained(
    decision: str,
) -> None:
    h = Harness()
    suggestion, command = h.suggestion(), EntityId.new()
    if decision == "confirm":
        result = h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                                    command_id=command, actor_id=ACTOR_ID)
    else:
        result = h.service.reject(event_id=h.event, suggestion_id=suggestion.id,
                                   command_id=command, actor_id=ACTOR_ID, reason="Synthetic reason")
    h.repository.assets[h.stage] = (replace(asset(0, 1800), segmentation_ids=()),)
    h.run()
    assert h.service.read(h.event, suggestion.id)[1] == SuggestionStatus.SUPERSEDED
    if decision == "confirm":
        assert h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                                  command_id=command, actor_id=ACTOR_ID) == result
    else:
        assert h.service.reject(event_id=h.event, suggestion_id=suggestion.id,
                                 command_id=command, actor_id=ACTOR_ID,
                                 reason="Synthetic reason") == result


def test_concurrent_identical_confirmation_creates_exactly_one_session() -> None:
    h = Harness()
    suggestion, command = h.suggestion(), EntityId.new()

    def confirm(_: int):
        return h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                                  command_id=command, actor_id=ACTOR_ID)

    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = tuple(pool.map(confirm, range(8)))
    assert all(x == decisions[0] for x in decisions)
    assert len(h.kernel_repo.list_sessions_for_stage(h.stage)) == 1


def test_confirm_invokes_existing_kernel_with_deterministic_operation_ids() -> None:
    h = Harness()
    suggestion, command = h.suggestion(), EntityId.new()
    start = DurableEventModeKernel.start_session
    correct = DurableEventModeKernel.correct_session_boundary
    with (patch.object(DurableEventModeKernel, "start_session", autospec=True,
                       side_effect=start) as start_call,
          patch.object(DurableEventModeKernel, "correct_session_boundary", autospec=True,
                       side_effect=correct) as end_call):
        result = h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                                    command_id=command, actor_id=ACTOR_ID)
    request = start_call.call_args.args[1]
    assert request.operation_id == kernel_operation_id(command, "start")
    assert request.program_expectation_id == h.expectation.id
    assert request.authoritative_start == suggestion.candidate.span.start
    assert request.actor_id == ACTOR_ID and request.title == h.expectation.title
    assert end_call.call_args.kwargs["operation_id"] == kernel_operation_id(command, "end")
    assert end_call.call_args.kwargs["session_id"] == result.session_id
    assert end_call.call_args.kwargs["boundary_at"] == suggestion.candidate.span.end


def test_run_digest_changes_with_each_revision_and_cue_list_version() -> None:
    from app.contexts.editorial.derivation_contracts import EditorialPhraseList

    h = Harness()
    baseline = h.run()
    initial = h.repository.assets[h.stage][0]
    assert initial.timing is not None
    for changed in (
        replace(initial, timing=Reference(initial.timing.id, 2)),
        replace(initial, segmentation_ids=(EntityId.new(),)),
        replace(initial, transcript=Reference(EntityId.new(), 2)),
    ):
        h.repository.assets[h.stage] = (changed,)
        assert h.run().input_digest != baseline.input_digest
    h.repository.assets[h.stage] = (initial,)
    returned = h.run()
    assert returned.id != baseline.id and returned.input_digest == baseline.input_digest
    phrase_id = EntityId.new()
    for version in (1, 2):
        h.repository.editorial.phrases[phrase_id, version] = EditorialPhraseList(
            phrase_id, h.event, "cues", version, "Cues", ("welcome",), ACTOR_ID, NOW)
    first = h.service.run(event_id=h.event, stage_id=h.stage, actor_id=ACTOR_ID,
                          start_cue_list=Reference(phrase_id, 1))
    second = h.service.run(event_id=h.event, stage_id=h.stage, actor_id=ACTOR_ID,
                           start_cue_list=Reference(phrase_id, 2))
    assert first.id != second.id


def test_return_to_earlier_inputs_creates_fresh_latest_run() -> None:
    h = Harness()
    initial = h.repository.assets[h.stage]
    first = h.run()
    first_suggestion = h.service.page(h.event, h.stage)[0][0]
    h.repository.assets[h.stage] = (replace(initial[0], segmentation_ids=()),)
    second = h.run()
    second_suggestion = h.service.page(h.event, h.stage)[0][0]
    h.repository.assets[h.stage] = initial
    third = h.run()
    assert third.id not in (first.id, second.id)
    assert third.input_digest == first.input_digest
    assert h.run() == third
    assert len(h.repository.runs) == 3
    assert h.service.read(h.event, first_suggestion.id)[1] == SuggestionStatus.SUPERSEDED
    assert h.service.read(h.event, second_suggestion.id)[1] == SuggestionStatus.SUPERSEDED
    opened, _ = h.service.page(h.event, h.stage)
    assert opened and all(s.run_id == third.id for s in opened)


@pytest.mark.parametrize("end_seconds", [9, 10])
def test_confirm_refuses_adjusted_end_at_or_before_start(end_seconds: int) -> None:
    h = Harness()
    suggestion = h.suggestion()
    with pytest.raises(ValueError, match="end must follow start"):
        h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                          command_id=EntityId.new(), actor_id=ACTOR_ID,
                          start=at(10), end=at(end_seconds))
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)
    assert not h.repository.decisions
    assert h.service.read(h.event, suggestion.id)[1] == SuggestionStatus.OPEN


def test_bound_kernel_repository_borrowed_connection_assumptions() -> None:
    # _BorrowedConnection suppresses the connection context's commit/close. This
    # adapter must be reviewed if the Kernel ever bypasses that context boundary.
    adapter = event_mode_kernel_repository.PostgresEventModeKernelRepository
    assert vars(session_suggestion_repository)["_BoundKernelRepository"].__bases__ == (adapter,)
    tree = ast.parse(inspect.getsource(event_mode_kernel_repository))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert calls
    assert not any(isinstance(call.func, ast.Attribute) and call.func.attr == "commit"
                   or isinstance(call.func, ast.Name) and call.func.id == "commit"
                   for call in calls)
    connect_calls = [call for call in calls
                     if isinstance(call.func, ast.Attribute) and call.func.attr == "connect"
                     or isinstance(call.func, ast.Name) and call.func.id == "connect"]
    connect_method = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.FunctionDef) and node.name == "_connect")
    assert len(connect_calls) == 1 and connect_calls[0] in ast.walk(connect_method)
    borrowed_calls = [call for call in calls
                      if isinstance(call.func, ast.Attribute) and call.func.attr == "_connect"]
    assert borrowed_calls
    contexts = [item.context_expr for node in ast.walk(tree) if isinstance(node, ast.With)
                for item in node.items]
    assert all(call in contexts and isinstance(call.func, ast.Attribute)
               and isinstance(call.func.value, ast.Name) and call.func.value.id == "self"
               for call in borrowed_calls)


def test_confirm_then_run_filters_realized_preserving_alignment_coverage_and_queue() -> None:
    h = Harness()
    talk2 = h.kernel.record_program_expectation(
        event_id=h.event, stage_id=h.stage, key="talk-2", title="Talk 2",
        planned_start=at(1920), planned_end=at(3600))
    h.repository.assets[h.stage] = (asset(300, 3900, freezes=((1800, 1920),),
                                         silences=((1800, 1920),)),)
    first = h.run()
    before = {s.candidate.expectation.id: s for s in h.service.page(h.event, h.stage)[0]
              if s.candidate.expectation is not None}
    assert set(before) == {h.expectation.id, talk2.id}
    talk1_span = before[h.expectation.id].candidate.span
    h.service.confirm(event_id=h.event, suggestion_id=before[h.expectation.id].id,
                      command_id=EntityId.new(), actor_id=ACTOR_ID)
    second = h.run()
    assert second.id != first.id and second.input_digest != first.input_digest
    assert second.skips == replace(first.skips, already_realized=1)
    assert second.expectations == first.expectations and second.blocks == first.blocks
    after, _ = h.service.page(h.event, h.stage)
    assert len(after) == 1 and after[0].candidate == before[talk2.id].candidate
    assert all(s.candidate.expectation is not None or
               s.candidate.span.end <= talk1_span.start or
               s.candidate.span.start >= talk1_span.end for s in after)
    assert all(s.candidate.expectation is None or
               s.candidate.expectation.id != h.expectation.id
               for s in h.repository.suggestions.values() if s.run_id == second.id)
    assert h.run() == h.service.latest_run(h.event, h.stage) == second
    queue, = h.service.list_pending_confirmations(h.event)
    assert "open_count:1" in queue.reason_codes
    h.service.confirm(event_id=h.event, suggestion_id=after[0].id,
                      command_id=EntityId.new(), actor_id=ACTOR_ID)
    assert h.run().skips.already_realized == 2
    assert h.service.page(h.event, h.stage)[0] == ()
    assert h.service.list_pending_confirmations(h.event) == ()


def test_run_and_confirm_share_cross_stage_realization_rule() -> None:
    h = Harness()
    suggestion = h.suggestion()
    other_stage = next(s.id for s in h.kernel_repo.list_stages(h.event) if s.id != h.stage)
    h.kernel.start_session(StartSessionRequest(
        operation_id=EntityId.new(), event_id=h.event, stage_id=other_stage,
        actor_id=ACTOR_ID, authoritative_start=at(0), requested_at=NOW,
        program_expectation_id=h.expectation.id,
    ))
    with pytest.raises(SuggestionConflictError, match="expectation_already_realized"):
        h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                          command_id=EntityId.new(), actor_id=ACTOR_ID)
    assert h.run().skips.already_realized == 1
    assert h.service.page(h.event, h.stage)[0] == ()


def test_rejected_talk_is_eligible_on_new_run() -> None:
    h = Harness()
    suggestion = h.suggestion()
    h.service.reject(event_id=h.event, suggestion_id=suggestion.id,
                     command_id=EntityId.new(), actor_id=ACTOR_ID, reason="Synthetic reason")
    # Rejection alone retains digest replay; new evidence creates a new run.
    h.repository.assets[h.stage] = (replace(asset(0, 1800), segmentation_ids=()),)
    run = h.run()
    fresh, = h.service.page(h.event, h.stage)[0]
    assert fresh.id != suggestion.id
    assert fresh.candidate.expectation == suggestion.candidate.expectation
    assert run.skips.already_realized == 0


def test_realized_filter_preserves_unrelated_unscheduled_candidate() -> None:
    h = Harness()
    h.repository.assets[h.stage] = (asset(0, 3600, freezes=((1800, 1920),)),)
    h.run()
    before = h.service.page(h.event, h.stage)[0]
    scheduled, = (s for s in before if s.candidate.expectation is not None)
    unscheduled, = (s for s in before if s.candidate.expectation is None)
    h.service.confirm(event_id=h.event, suggestion_id=scheduled.id,
                      command_id=EntityId.new(), actor_id=ACTOR_ID)
    assert h.run().skips.already_realized == 1
    remaining, = h.service.page(h.event, h.stage)[0]
    assert remaining.candidate == unscheduled.candidate


@pytest.mark.parametrize("value", [-1, 2_147_483_648, True, 1.5])
def test_already_realized_skip_rejects_invalid_counts(value: int) -> None:
    with pytest.raises(ValueError, match="skip count out of bounds"):
        SkipCounts(already_realized=value)


def test_already_realized_skip_default_and_upper_bound() -> None:
    assert SkipCounts().already_realized == 0
    assert SkipCounts(already_realized=2_147_483_647).already_realized == 2_147_483_647
