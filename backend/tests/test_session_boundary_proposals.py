"""Synthetic refinement production, human decisions, and atomic replay."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.contexts.production.event_mode_kernel.contracts import (
    EpistemicKind,
    Session,
    SessionBoundaryProposal,
    StartSessionRequest,
)
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.boundary_proposals import (
    SYSTEM_PROPOSER_ID,
    BoundaryProposalService,
    produce_boundary_proposals,
)
from app.contexts.production.session_suggestions.contracts import (
    BoundaryProposalDecision,
    BoundaryProposalDecisionKind,
    Candidate,
    EdgeKind,
    Strength,
    SuggestionConflictError,
    SuggestionNotFoundError,
)
from app.contexts.production.session_suggestions.service import kernel_operation_id
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_suggestion_policy import NOW, at
from tests.test_session_suggestions import Harness


def realized(start: float = 60, end: float = 1740) -> tuple[Harness, Session, Candidate]:
    h = Harness()
    suggestion = h.suggestion()
    decision = h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                                 command_id=EntityId.new(), actor_id=ACTOR_ID,
                                 start=at(start), end=at(end))
    assert decision.session_id is not None
    session = h.kernel_repo.get_session(decision.session_id)
    assert session is not None
    h.service.clock = FixedClock(at(1))
    return h, session, suggestion.candidate


def boundaries(h: Harness) -> BoundaryProposalService:
    return BoundaryProposalService(h.repository, h.service.clock)


def proposal(h: Harness, session: Session, edge: str = "start", seconds: float = 0
             ) -> SessionBoundaryProposal:
    with h.repository.transaction(h.service.clock) as tx:
        return tx.kernel.propose_session_boundary(
            session_id=session.id, boundary_kind=edge, boundary_at=at(seconds),
            epistemic_kind=EpistemicKind.DERIVED, proposer_id=SYSTEM_PROPOSER_ID,
            evidence_ids=(EntityId.new(),), policy_id="boundary-suggestion", policy_version="3",
            reason="recording_boundary",
        )


def decide(h: Harness, p: SessionBoundaryProposal, *, apply: bool = True,
           command: EntityId | None = None) -> BoundaryProposalDecision:
    action = boundaries(h).apply if apply else boundaries(h).dismiss
    return action(event_id=h.event, session_id=p.session_id, proposal_id=p.id,
                  command_id=command or EntityId.new(), actor_id=ACTOR_ID)


@pytest.mark.parametrize("delta,expected", [(0, 0), (29.999, 0), (30, 2), (60, 2), (-30, 2)])
def test_run_threshold_current_boundaries_evidence_and_no_automatic_authority(
    delta: float, expected: int,
) -> None:
    h, session, candidate = realized(delta, 1800 - delta)
    result = h.run()
    assert result.boundary_proposals_created == expected
    assert result.skips.already_realized == 1
    opened = boundaries(h).open(h.event, session.id)
    assert len(opened) == expected
    for p in opened:
        assert p.boundary_at == getattr(candidate.span, p.boundary_kind)
        assert p.evidence_ids == tuple(sorted({*candidate.segmentation_ids,
                                               *(r.id for r in candidate.timing_references)},
                                              key=lambda i: i.value))
        assert p.epistemic_kind == EpistemicKind.DERIVED
        assert (p.policy_id, p.policy_version, p.reason) == (
            "boundary-suggestion", "3", "recording_boundary")
        assert p.proposer_id == SYSTEM_PROPOSER_ID == EntityId(str(uuid5(
            NAMESPACE_URL, "stageflow:session-suggestion:boundary-proposer")))
        assert p.proposed_at == at(1)
    assert h.kernel_repo.get_session(session.id) == session
    assert not h.service.page(h.event, h.stage)[0]
    assert h.run() == result  # Immutable run replay retains the original count.
    # New evidence with the same candidate edges must deduplicate, not just replay.
    h.repository.assets[h.stage] = (replace(h.repository.assets[h.stage][0],
                                           segmentation_ids=(EntityId.new(),)),)
    newer = h.run()
    assert newer.id != result.id and newer.boundary_proposals_created == 0
    assert boundaries(h).open(h.event, session.id) == opened


@pytest.mark.parametrize("kind,reason", [(EdgeKind.FREEZE, "changeover_edge"),
                                        (EdgeKind.GAP, "recording_gap"),
                                        (EdgeKind.COVERAGE, "recording_boundary"),
                                        (EdgeKind.SCHEDULE, None)])
@pytest.mark.parametrize("cue", [False, True])
def test_reason_mapping_and_schedule_exclusion_per_edge(
    kind: EdgeKind, reason: str | None, cue: bool,
) -> None:
    h, session, candidate = realized()
    candidate = replace(candidate, start_edge_kind=kind, end_edge_kind=EdgeKind.SCHEDULE,
                        start_cue_support=cue, strength=Strength.WEAK)
    with h.repository.transaction(h.service.clock) as tx:
        count = produce_boundary_proposals(tx, session, candidate)
    opened = boundaries(h).open(h.event, session.id)
    assert count == len(opened) == (0 if reason is None else 1)
    if opened:
        assert opened[0].boundary_kind == "start"
        assert opened[0].reason == ("cue_supported" if cue else reason)


def test_missing_evidence_and_absent_current_end_are_skipped() -> None:
    h, session, candidate = realized()
    # Defensive production guard: normal policy contracts already require timing.
    with patch.object(Candidate, "__post_init__"):
        no_evidence = replace(candidate, timing_references=(), segmentation_ids=())
    with h.repository.transaction(h.service.clock) as tx:
        assert produce_boundary_proposals(tx, session, no_evidence) == 0
        assert produce_boundary_proposals(tx, replace(session, authoritative_end=None),
                                         candidate) == 1
    assert [p.boundary_kind for p in boundaries(h).open(h.event, session.id)] == ["start"]


def test_unlinked_session_is_not_refined() -> None:
    h = Harness()
    h.kernel.start_session(StartSessionRequest(EntityId.new(), h.event, h.stage, ACTOR_ID,
                                               at(60), NOW))
    assert h.run().boundary_proposals_created == 0
    assert h.service.page(h.event, h.stage)[0]


@pytest.mark.parametrize("dismissed", [False, True])
def test_current_correction_invalidates_run_replay_and_stale_dedup(dismissed: bool) -> None:
    h, session, _ = realized()
    first = h.run()
    old = next(p for p in boundaries(h).open(h.event, session.id) if p.boundary_kind == "start")
    if dismissed:
        decide(h, old, apply=False)
    kernel = DurableEventModeKernel(repository=h.kernel_repo, clock=FixedClock(at(2)))
    # Same timestamp still creates history and must invalidate replay/dedup.
    kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session.id,
                                    boundary_kind="start", boundary_at=session.authoritative_start,
                                    actor_id=ACTOR_ID, reason="Human review")
    h.service.clock = FixedClock(at(3))
    second = h.run()
    assert second.id != first.id and second.boundary_proposals_created == 1
    assert old not in boundaries(h).open(h.event, session.id)
    assert len(boundaries(h).open(h.event, session.id)) == 2


@pytest.mark.parametrize("failure_point", ["proposal", "run"])
def test_proposal_production_and_run_are_atomic(failure_point: str) -> None:
    h, session, _ = realized()
    old_runs = h.repository.runs.copy()
    if failure_point == "run":
        target = patch.object(h.repository, "save_run", side_effect=RuntimeError("crash"))
    else:
        original = DurableEventModeKernel.propose_session_boundary
        calls = 0

        def fail_second(self: DurableEventModeKernel, **kwargs: object) -> SessionBoundaryProposal:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("crash")
            return original(self, **kwargs)  # type: ignore[arg-type]

        target = patch.object(DurableEventModeKernel, "propose_session_boundary", fail_second)
    with target, pytest.raises(RuntimeError, match="crash"):
        h.run()
    assert h.repository.runs == old_runs
    assert not h.kernel_repo.list_boundary_proposals(session.id)
    assert h.run().boundary_proposals_created == 2


def test_apply_corrects_one_edge_replays_and_decision_is_last() -> None:
    h, session, _ = realized()
    h.run()
    p = next(p for p in boundaries(h).open(h.event, session.id) if p.boundary_kind == "start")
    command = EntityId.new()
    with patch.object(h.repository, "save_boundary_decision", side_effect=RuntimeError("crash")):
        with pytest.raises(RuntimeError, match="crash"):
            decide(h, p, command=command)
    assert h.kernel_repo.get_session(session.id) == session
    assert len(boundaries(h).open(h.event, session.id)) == 2
    original = DurableEventModeKernel.correct_session_boundary
    with patch.object(DurableEventModeKernel, "correct_session_boundary", autospec=True,
                      side_effect=original) as correction:
        decision = decide(h, p, command=command)
        assert correction.call_args.kwargs["operation_id"] == kernel_operation_id(
            command, "apply-boundary")
    assert decide(h, p, command=command) == decision
    updated = h.kernel_repo.get_session(session.id)
    assert updated is not None
    assert updated.authoritative_start == p.boundary_at
    assert updated.authoritative_end == session.authoritative_end
    assert updated.revision == session.revision + 1
    with pytest.raises(SuggestionConflictError, match="boundary_proposal_decided"):
        decide(h, p)
    with pytest.raises(SuggestionConflictError, match="command_id_conflict"):
        decide(h, p, apply=False, command=command)
    assert p not in boundaries(h).open(h.event, session.id)


@pytest.mark.parametrize("cause", ["boundary", "newer", "other_edge"])
def test_stale_checks_and_open_reads_are_edge_specific(cause: str) -> None:
    h, session, _ = realized()
    p = proposal(h, session)
    h.service.clock = FixedClock(at(2))
    if cause == "newer":
        replacement = proposal(h, session, seconds=10)
        decide(h, replacement, apply=False)  # Deciding newer never revives older.
    else:
        kernel = DurableEventModeKernel(repository=h.kernel_repo, clock=h.service.clock)
        kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session.id,
                                        boundary_kind="end" if cause == "other_edge" else "start",
                                        boundary_at=at(1700 if cause == "other_edge" else 70),
                                        actor_id=ACTOR_ID, reason="Human correction")
    if cause == "other_edge":
        assert boundaries(h).open(h.event, session.id) == (p,)
        assert decide(h, p).kind == "applied"
    else:
        assert not boundaries(h).open(h.event, session.id)
        with pytest.raises(SuggestionConflictError, match="boundary_proposal_stale"):
            decide(h, p)


def test_dismiss_history_paging_bounds_human_authority_and_scope() -> None:
    h, session, _ = realized()
    h.run()
    opened = boundaries(h).open(h.event, session.id)
    for p in opened:
        decision = decide(h, p, apply=False)
        assert decide(h, p, apply=False, command=decision.command_id) == decision
    assert h.kernel_repo.get_session(session.id) == session
    assert not boundaries(h).open(h.event, session.id)
    first, cursor = boundaries(h).history(h.event, session.id, limit=1)
    second, end = boundaries(h).history(h.event, session.id, limit=1, after=cursor)
    assert len(first) == len(second) == 1 and cursor is not None and end is None
    assert {d.proposal_id for d in (*first, *second)} == {p.id for p in opened}
    with pytest.raises(FrozenInstanceError):
        attribute = "reason"
        setattr(first[0], attribute, "Changed")
    with pytest.raises(SuggestionNotFoundError):
        boundaries(h).open(EntityId.new(), session.id)
    for reason in ("", " ", "x" * 501, "x\x00y"):
        with pytest.raises(ValueError, match="reason out of bounds"):
            boundaries(h).dismiss(event_id=h.event, session_id=session.id, proposal_id=opened[0].id,
                                   command_id=EntityId.new(), actor_id=ACTOR_ID, reason=reason)
    with pytest.raises(ValueError, match="requires_human"):
        boundaries(h).apply(event_id=h.event, session_id=session.id, proposal_id=opened[0].id,
                             command_id=EntityId.new(), actor_id=ACTOR_ID,
                             authority_kind="automatic")


def test_concurrent_apply_dismiss_has_one_decision_and_no_duplicate_correction() -> None:
    h, session, _ = realized()
    p = proposal(h, session)

    def attempt(apply: bool) -> str:
        try:
            return decide(h, p, apply=apply).kind
        except SuggestionConflictError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(attempt, (True, False)))
    assert outcomes.count("boundary_proposal_decided") == 1
    assert len(boundaries(h).history(h.event, session.id)[0]) == 1


@pytest.mark.parametrize("count", [-1, True, 1.5, 2_147_483_648])
def test_run_proposal_count_bounds(count: int) -> None:
    h = Harness()
    with pytest.raises(ValueError, match="boundary proposal count"):
        replace(h.run(), boundary_proposals_created=count)


@pytest.mark.parametrize("seconds,version,dismissed,expected", [
    (0, "3", False, 1), (10, "3", False, 2), (0, "2", False, 2), (0, "3", True, 1),
])
def test_dedup_requires_matching_time_and_version_regardless_of_dismissal(
    seconds: int, version: str, dismissed: bool, expected: int,
) -> None:
    h, session, candidate = realized()
    with h.repository.transaction(h.service.clock) as tx:
        p = tx.kernel.propose_session_boundary(
            session_id=session.id, boundary_kind="start", boundary_at=at(seconds),
            epistemic_kind=EpistemicKind.DERIVED, proposer_id=SYSTEM_PROPOSER_ID,
            evidence_ids=candidate.segmentation_ids, policy_id="boundary-suggestion",
            policy_version=version, reason="recording_boundary",
        )
    if dismissed:
        decide(h, p, apply=False)
    h.service.clock = FixedClock(at(2))
    with h.repository.transaction(h.service.clock) as tx:
        assert produce_boundary_proposals(tx, session, candidate) == expected
    opened = boundaries(h).open(h.event, session.id)
    assert len(opened) == (1 if dismissed else 2)
    if dismissed:
        assert opened[0].boundary_kind == "end"
    else:
        start = next(p for p in opened if p.boundary_kind == "start")
        assert start.boundary_at == candidate.span.start and start.policy_version == "3"


def test_dismiss_then_apply_other_edge_and_rerun_creates_no_duplicate() -> None:
    h, session, _ = realized()
    first = h.run()
    opened = boundaries(h).open(h.event, session.id)
    start = next(p for p in opened if p.boundary_kind == "start")
    end = next(p for p in opened if p.boundary_kind == "end")
    h.service.clock = FixedClock(at(2))
    decide(h, start, apply=False)
    decide(h, end)
    updated = h.kernel_repo.get_session(session.id)
    assert updated is not None and updated.authoritative_end == end.boundary_at
    before = h.kernel_repo.list_boundary_proposals(session.id)
    h.service.clock = FixedClock(at(3))
    second = h.run()
    assert second.id != first.id and second.boundary_proposals_created == 0
    assert h.kernel_repo.list_boundary_proposals(session.id) == before
    assert not boundaries(h).open(h.event, session.id)


def test_dismiss_then_changed_candidate_time_creates_new_proposal() -> None:
    h, session, _ = realized()
    first = h.run()
    start = next(p for p in boundaries(h).open(h.event, session.id) if p.boundary_kind == "start")
    decide(h, start, apply=False)
    original = h.repository.assets[h.stage][0]
    assert original.coverage is not None and original.timing is not None
    h.repository.assets[h.stage] = (replace(
        original, coverage=replace(original.coverage, start=at(-60)),
        timing=replace(original.timing, revision=original.timing.revision + 1)),)
    h.service.clock = FixedClock(at(2))
    second = h.run()
    assert second.id != first.id and second.boundary_proposals_created == 1
    newer = next(p for p in boundaries(h).open(h.event, session.id) if p.boundary_kind == "start")
    assert newer.id != start.id and newer.boundary_at == at(-60)


def test_applied_matching_edge_is_below_threshold_even_when_history_is_newer() -> None:
    h, session, candidate = realized()
    p = proposal(h, session)
    h.service.clock = FixedClock(at(2))
    decide(h, p)
    updated = h.kernel_repo.get_session(session.id)
    assert updated is not None and updated.authoritative_start == candidate.span.start
    with h.repository.transaction(h.service.clock) as tx:
        assert tx.boundary_stale(p)  # Later apply history prevents dedup by this proposal.
        with patch.object(tx.kernel, "propose_session_boundary", wraps=(
                tx.kernel.propose_session_boundary)) as propose:
            assert produce_boundary_proposals(tx, updated, candidate) == 1
        assert propose.call_args.kwargs["boundary_kind"] == "end"


@pytest.mark.parametrize("latest_seconds,expected", [(0, 1), (10, 2)])
def test_dedup_uses_latest_proposal_even_when_dismissed(
    latest_seconds: int, expected: int,
) -> None:
    h, session, candidate = realized()
    proposal(h, session, seconds=10 if latest_seconds == 0 else 0)
    h.service.clock = FixedClock(at(2))
    latest = proposal(h, session, seconds=latest_seconds)
    decide(h, latest, apply=False)
    h.service.clock = FixedClock(at(3))
    with h.repository.transaction(h.service.clock) as tx:
        assert tx.latest_nonstale_boundary_proposals(session.id) == (latest,)
        assert produce_boundary_proposals(tx, session, candidate) == expected


def test_proposal_timestamp_ties_follow_kernel_id_order() -> None:
    h, session, _ = realized()
    base = proposal(h, session)
    first = replace(base, id=EntityId("00000000-0000-0000-0000-000000000001"))
    latest = replace(base, id=EntityId("ffffffff-ffff-ffff-ffff-ffffffffffff"), boundary_at=at(10))
    h.kernel_repo.put_boundary_proposal(latest)
    h.kernel_repo.put_boundary_proposal(first)  # Insertion order does not override Kernel ordering.
    assert boundaries(h).open(h.event, session.id) == (latest,)
    with pytest.raises(SuggestionConflictError, match="boundary_proposal_stale"):
        decide(h, first)


def test_decision_contract_rejects_naive_time_and_invalid_digest() -> None:
    args = (EntityId.new(), EntityId.new(), BoundaryProposalDecisionKind.DISMISSED,
            EntityId.new(), "a" * 64, ACTOR_ID)
    with pytest.raises(ValueError):
        BoundaryProposalDecision(*args, NOW.replace(tzinfo=None))
    decision = BoundaryProposalDecision(*args, NOW)
    with pytest.raises(ValueError, match="request digest"):
        replace(decision, request_digest="bad")
