"""Real SQL reads; render_postgres_dsn rolls back all rows and schema changes."""
from dataclasses import replace
from datetime import timedelta

import pytest

from app.contexts.production.event_mode_kernel.contracts import ProducerWorkQueuePosition
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.contracts import (
    POLICY_V2,
    Reference,
    ScheduleOffsetEntry,
    Strength,
    SuggestionNotFoundError,
)
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.infrastructure.postgres.event_mode_kernel_repository import (
    PostgresEventModeKernelRepository,
)
from app.infrastructure.postgres.session_suggestion_repository import PostgresSuggestionRepository
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_session_suggestion_policy import NOW, at
from tests.test_session_suggestions_postgres import seeded


def test_postgres_latest_run_versions_blocks_scope_and_sequence(render_postgres_dsn: str) -> None:
    service, seed = seeded(render_postgres_dsn)
    event, stage = seed.event_id, seed.stage_id
    legacy = service.latest_run(event, stage)
    assert legacy.policy.version == "1" and legacy.id == seed.run_id
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(NOW))
    other = next(s.id for s in kernel.repository.list_stages(event) if s.id != stage)
    with pytest.raises(SuggestionNotFoundError, match="suggestion_run_not_found"):
        service.latest_run(event, other)
    with pytest.raises(SuggestionNotFoundError, match="stage_not_found"):
        service.latest_run(EntityId.new(), stage)
    with service.repository.transaction(FixedClock(NOW)) as tx:
        assert tx.latest_run(EntityId.new(), stage) is None
        v2 = replace(legacy, id=EntityId.new(), input_digest="b" * 64, policy=POLICY_V2)
        tx.save_run(v2, ())
    assert service.latest_run(event, stage) == v2
    kernel.record_program_expectation(event_id=event, stage_id=stage, key="talk", title="Talk 1",
                                      planned_start=at(0), planned_end=at(1800))
    service.set_offset(event_id=event, stage_id=stage, command_id=EntityId.new(),
                        actor_id=ACTOR_ID, entries=(ScheduleOffsetEntry(at(0), 120),))
    # Latest is insertion sequence, including when the injected clock moved backwards.
    service.clock = FixedClock(NOW - timedelta(days=1))
    v3 = service.run(event_id=event, stage_id=stage, actor_id=ACTOR_ID)
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                          FixedClock(NOW))
    assert restarted.latest_run(event, stage) == v3
    assert v3.blocks[0].schedule_offset_seconds == 120
    assert v3.blocks[0].override_setting_version == v3.override_setting_version == 1
    # No media on this Stage: the latest run is still returned, and old open work is hidden.
    assert restarted.list_pending_confirmations(event) == ()


def test_postgres_pending_counts_decisions_supersession_and_keyset(
    render_postgres_dsn: str,
) -> None:
    service, seed = seeded(render_postgres_dsn)
    event, stage = seed.event_id, seed.stage_id
    kernel = PostgresEventModeKernelRepository(render_postgres_dsn)
    other = next(s.id for s in kernel.list_stages(event) if s.id != stage)
    first_run = service.latest_run(event, stage)
    original, = service.list_pending_confirmations(event)
    assert original.subject_id == first_run.id and original.priority == 6
    assert "open_count:1" in original.reason_codes
    assert "weak_count:1" in original.reason_codes
    assert service.list_pending_confirmations(EntityId.new()) == ()
    kernel_service = DurableEventModeKernel(repository=kernel, clock=FixedClock(NOW))
    expectation = kernel_service.record_program_expectation(
        event_id=event, stage_id=other, key="talk", title="Talk 1",
        planned_start=at(0), planned_end=at(180))
    with service.repository.transaction(FixedClock(NOW)) as tx:
        # Equal timestamps exercise the projection-ID tie breaker, not insertion order.
        run = replace(first_run, id=EntityId.new(), stage_id=other, input_digest="c" * 64)
        weak = replace(seed, id=EntityId.new(), run_id=run.id, stage_id=other)
        medium = replace(weak, id=EntityId.new(),
                         candidate=replace(weak.candidate, strength=Strength.MEDIUM,
                                           expectation=Reference(expectation.id, 1),
                                           start_plan_offset_seconds=0, end_plan_offset_seconds=0))
        tx.save_run(run, (weak, medium))
    items = service.list_pending_confirmations(event, limit=101)
    assert len(items) == 2
    assert [i.projection_id for i in items] == sorted(i.projection_id for i in items)
    item = next(i for i in items if i.stage_id == other)
    assert set(item.reason_codes) == {
        "presentation_confirmation_pending", "open_count:2", "weak_count:1"}
    assert item.subject_revision == 1 and item.session_id is None
    assert item.created_at == item.updated_at == run.created_at
    assert item.action_reference == f"stage:{other}:suggestions"
    assert service.list_pending_confirmations(event, limit=1) == items[:1]
    assert service.list_pending_confirmations(event, after=items[0].position, limit=1) == items[1:]
    assert service.list_pending_confirmations(event, after=items[-1].position) == ()
    assert service.list_pending_confirmations(
        event, after=ProducerWorkQueuePosition(5, NOW + timedelta(days=1), "assembly:last"),
    ) == items
    assert service.list_pending_confirmations(
        event, after=ProducerWorkQueuePosition(7, NOW, "later"),
    ) == ()
    for limit in (0, 102, True):
        with pytest.raises(ValueError):
            service.list_pending_confirmations(event, limit=limit)
    service.reject(event_id=event, suggestion_id=weak.id, command_id=EntityId.new(),
                   actor_id=ACTOR_ID, reason="Synthetic review")
    remaining = next(i for i in service.list_pending_confirmations(event) if i.stage_id == other)
    assert set(remaining.reason_codes) == {
        "presentation_confirmation_pending", "open_count:1", "weak_count:0"}
    service.confirm(event_id=event, suggestion_id=medium.id, command_id=EntityId.new(),
                    actor_id=ACTOR_ID)
    assert service.list_pending_confirmations(event) == (original,)
    # A newer run with no suggestions must not fall back to the last run with open work.
    with service.repository.transaction(FixedClock(NOW)) as tx:
        empty = replace(first_run, id=EntityId.new(), input_digest="d" * 64)
        tx.save_run(empty, ())
    assert service.latest_run(event, stage) == empty
    assert service.list_pending_confirmations(event) == ()
