from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Protocol, cast
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api.authentication import API_SECRET_HEADER
from app.api.v1.router import router as api_router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialClip,
    EditorialGenerationState,
    EditorialMomentConflictError,
    EditorialMomentReviewAction,
    EditorialMomentReviewDecision,
    EditorialMomentReviewResult,
    EditorialMomentService,
    EditorialReviewQueueItem,
    EditorialReviewQueuePage,
    EditorialReviewQueuePosition,
    EditorialReviewRange,
    EditorialReviewState,
    EditorialSessionCandidateProjection,
    ReviewEditorialMoment,
)
from app.contexts.events import (
    EventStageBootstrapRequest,
    StageBootstrapDefinition,
)
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    StartSessionRequest,
)
from app.core.config.deployment import EffectiveKernelConfiguration
from app.infrastructure.postgres import (
    PostgresEditorialMomentRepository,
    PostgresEventModeKernelRepository,
    PostgresMigrationRunner,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 28, 17, 0, tzinfo=UTC)
AUTH_HEADERS = {
    API_SECRET_HEADER: 'stageflow-test-only-shared-secret-0123456789'
}


class SyncHttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Response: ...

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
    ) -> Response: ...


def _id(number: int) -> EntityId:
    return EntityId(f'93000000-0000-0000-0000-{number:012d}')


SESSION_ID = _id(1)
EVENT_ID = _id(3)
STAGE_ID = _id(4)


def _candidate(
    number: int,
    *,
    session_id: EntityId = SESSION_ID,
    revision: int = 1,
    declared_at: datetime = NOW,
    point: bool = False,
) -> EditorialCandidateMoment:
    return EditorialCandidateMoment(
        id=_id(number),
        session_id=session_id,
        expected_session_revision=1,
        timeline_start_microseconds=number * 1_000_000,
        timeline_end_microseconds=(
            None if point else (number + 30) * 1_000_000
        ),
        session_authoritative_start=NOW,
        session_authoritative_end=NOW + timedelta(hours=1),
        actor_id=_id(2),
        operation_id=_id(number + 100),
        note='producer mark',
        declared_at=declared_at,
        revision=revision,
    )


class MemoryEditorialReviewRepository:
    '''Test double only; PostgreSQL remains the runtime authority.'''

    def __init__(
        self,
        candidates: tuple[EditorialCandidateMoment, ...],
        *,
        event_id: EntityId = EVENT_ID,
        stage_id: EntityId = STAGE_ID,
    ) -> None:
        self.event_id = event_id
        self.stage_id = stage_id
        self.candidates = {item.id: item for item in candidates}
        self.decisions = {
            item.id: list[EditorialMomentReviewDecision]() for item in candidates
        }
        self.clips = {item.id: list[EditorialClip]() for item in candidates}
        self.by_operation: dict[
            EntityId, tuple[str, EditorialMomentReviewResult]
        ] = {}
        self.next_sequence = 1

    def declare(self, command: DeclareEditorialMoment) -> EditorialCandidateMoment:
        del command
        raise NotImplementedError

    def review(
        self, command: ReviewEditorialMoment
    ) -> EditorialMomentReviewResult:
        replay = self.by_operation.get(command.operation_id)
        if replay is not None:
            digest, result = replay
            if digest != command.request_digest:
                raise EditorialMomentConflictError(
                    'human_command_operation_id_conflict'
                )
            return result
        candidate = self.candidates.get(command.candidate_moment_id)
        if candidate is None:
            raise LookupError('candidate_moment_not_found')
        if candidate.revision != command.expected_candidate_revision:
            raise EditorialMomentConflictError('candidate_revision_conflict')
        decision = EditorialMomentReviewDecision(
            id=command.review_decision_id,
            sequence=self.next_sequence,
            operation_id=command.operation_id,
            candidate_moment_id=candidate.id,
            candidate_revision=candidate.revision,
            actor_id=command.actor_id,
            action=command.action,
            reason=command.reason,
            notes=command.notes,
            adjusted_range=command.adjusted_range,
            decided_at=command.decided_at,
        )
        self.next_sequence += 1
        clip: EditorialClip | None = None
        if (
            command.action
            is EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP
        ):
            approved_range = command.adjusted_range
            if approved_range is None:
                if candidate.timeline_end_microseconds is None:
                    raise EditorialMomentConflictError(
                        'approval_requires_timeline_range'
                    )
                approved_range = EditorialReviewRange(
                    candidate.timeline_start_microseconds,
                    candidate.timeline_end_microseconds,
                )
            assert command.clip_id is not None
            clip = EditorialClip(
                id=command.clip_id,
                session_id=candidate.session_id,
                candidate_moment_id=candidate.id,
                candidate_revision=candidate.revision,
                review_decision_id=decision.id,
                approved_range=approved_range,
                created_at=command.decided_at,
            )
        result = EditorialMomentReviewResult(decision=decision, clip=clip)
        self.decisions[candidate.id].append(decision)
        if clip is not None:
            self.clips[candidate.id].append(clip)
        self.by_operation[command.operation_id] = (
            command.request_digest,
            result,
        )
        return result

    def _project(self, candidate: EditorialCandidateMoment) -> EditorialCandidateMoment:
        history = self.decisions[candidate.id]
        return replace(
            candidate,
            review_state=(
                EditorialReviewState.UNREVIEWED
                if not history
                else history[-1].review_state
            ),
            updated_at=(
                candidate.updated_at
                if not history
                else history[-1].decided_at
            ),
        )

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]:
        return tuple(
            self._project(candidate)
            for candidate in sorted(
                (
                    item
                    for item in self.candidates.values()
                    if item.session_id == session_id
                ),
                key=lambda item: (
                    item.timeline_start_microseconds,
                    item.id.value,
                ),
            )[:limit]
        )

    def projection_for_session(
        self, session_id: EntityId
    ) -> EditorialSessionCandidateProjection:
        candidates = self.list_for_session(session_id)
        return EditorialSessionCandidateProjection(
            session_id=session_id,
            candidate_count=len(candidates),
            latest_candidate_activity_at=(
                None
                if not candidates
                else max(
                    item.updated_at or item.declared_at for item in candidates
                )
            ),
            generation_state=EditorialGenerationState.HEALTHY,
        )

    def projections_for_sessions(
        self, session_ids: tuple[EntityId, ...]
    ) -> tuple[EditorialSessionCandidateProjection, ...]:
        return tuple(self.projection_for_session(item) for item in session_ids)

    def revalidate_session_locations(
        self, session_id: EntityId, *, evaluated_at: datetime
    ) -> tuple[EditorialCandidateMoment, ...]:
        del evaluated_at
        return self.list_for_session(session_id)

    def list_review_queue(
        self,
        event_id: EntityId,
        *,
        after: EditorialReviewQueuePosition | None = None,
        limit: int = 100,
    ) -> EditorialReviewQueuePage:
        if event_id != self.event_id:
            return EditorialReviewQueuePage(event_id, (), 0, 0, None)
        items: list[EditorialReviewQueueItem] = []
        pending_times: list[datetime] = []
        for candidate in self.candidates.values():
            projected = self._project(candidate)
            priority = {
                EditorialReviewState.UNREVIEWED: 0,
                EditorialReviewState.REVISION_REQUESTED: 1,
                EditorialReviewState.DEFERRED: 2,
                EditorialReviewState.REJECTED: 3,
                EditorialReviewState.APPROVED: 4,
            }[projected.review_state]
            item = EditorialReviewQueueItem(
                event_id=self.event_id,
                stage_id=self.stage_id,
                candidate=projected,
                decisions=tuple(self.decisions[candidate.id]),
                clips=tuple(self.clips[candidate.id]),
                review_priority=priority,
            )
            items.append(item)
            if projected.review_state in {
                EditorialReviewState.UNREVIEWED,
                EditorialReviewState.REVISION_REQUESTED,
                EditorialReviewState.DEFERRED,
            }:
                pending_times.append(candidate.declared_at)
        items.sort(
            key=lambda item: (
                item.review_priority,
                item.candidate.declared_at,
                item.candidate.id.value,
            )
        )
        if after is not None:
            after_key = (
                after.review_priority,
                after.created_at,
                after.candidate_moment_id.value,
            )
            items = [
                item
                for item in items
                if (
                    item.review_priority,
                    item.candidate.declared_at,
                    item.candidate.id.value,
                )
                > after_key
            ]
        return EditorialReviewQueuePage(
            event_id=event_id,
            items=tuple(items[:limit]),
            total_candidate_count=len(self.candidates),
            pending_candidate_count=len(pending_times),
            oldest_pending_candidate_at=(
                None if not pending_times else min(pending_times)
            ),
        )


def _review(
    service: EditorialMomentService,
    candidate: EditorialCandidateMoment,
    *,
    operation_number: int,
    action: EditorialMomentReviewAction,
    reason: str = 'reviewed by editor',
    adjusted: tuple[int, int] | None = None,
) -> EditorialMomentReviewResult:
    return service.review_moment(
        operation_id=_id(operation_number),
        candidate_moment_id=candidate.id,
        expected_candidate_revision=candidate.revision,
        actor_id=_id(5),
        action=action,
        reason=reason,
        notes='visible decision history',
        adjusted_timeline_start_microseconds=(
            None if adjusted is None else adjusted[0]
        ),
        adjusted_timeline_end_microseconds=(
            None if adjusted is None else adjusted[1]
        ),
    )


def test_all_review_actions_append_history_and_approval_creates_only_a_clip() -> None:
    candidate = _candidate(10)
    repository = MemoryEditorialReviewRepository((candidate,))
    service = EditorialMomentService(repository, FixedClock(NOW))

    deferred = _review(
        service,
        candidate,
        operation_number=200,
        action=EditorialMomentReviewAction.DEFER,
    )
    revised = _review(
        service,
        candidate,
        operation_number=201,
        action=EditorialMomentReviewAction.REVISE_RANGE,
        adjusted=(12_000_000, 32_000_000),
    )
    rejected = _review(
        service,
        candidate,
        operation_number=202,
        action=EditorialMomentReviewAction.REJECT,
    )
    approved = _review(
        service,
        candidate,
        operation_number=203,
        action=EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP,
        adjusted=(13_000_000, 31_000_000),
    )

    assert [item.decision.sequence for item in (deferred, revised, rejected, approved)] == [
        1,
        2,
        3,
        4,
    ]
    assert approved.clip is not None
    assert approved.clip.candidate_moment_id == candidate.id
    assert approved.clip.candidate_revision == candidate.revision
    assert approved.clip.review_decision_id == approved.decision.id
    assert approved.clip.approved_range == EditorialReviewRange(
        13_000_000,
        31_000_000,
    )
    assert approved.clip.revision == 1
    assert candidate.timeline_start_microseconds == 10_000_000
    assert candidate.timeline_end_microseconds == 40_000_000
    page = service.list_review_queue(repository.event_id)
    assert page.items[0].candidate.review_state is EditorialReviewState.APPROVED
    assert [item.action for item in page.items[0].decisions] == [
        EditorialMomentReviewAction.DEFER,
        EditorialMomentReviewAction.REVISE_RANGE,
        EditorialMomentReviewAction.REJECT,
        EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP,
    ]
    with pytest.raises(FrozenInstanceError):
        approved.decision.reason = 'mutated'  # type: ignore[misc]


def test_review_replay_conflict_stale_revision_and_point_approval_are_explicit() -> None:
    candidate = _candidate(20)
    repository = MemoryEditorialReviewRepository((candidate,))
    service = EditorialMomentService(repository, FixedClock(NOW))
    original = _review(
        service,
        candidate,
        operation_number=210,
        action=EditorialMomentReviewAction.REJECT,
    )

    assert _review(
        service,
        candidate,
        operation_number=210,
        action=EditorialMomentReviewAction.REJECT,
    ) == original
    with pytest.raises(
        EditorialMomentConflictError,
        match='human_command_operation_id_conflict',
    ):
        _review(
            service,
            candidate,
            operation_number=210,
            action=EditorialMomentReviewAction.REJECT,
            reason='different replay',
        )

    stale = _candidate(21, revision=2)
    stale_repository = MemoryEditorialReviewRepository((stale,))
    stale_service = EditorialMomentService(stale_repository, FixedClock(NOW))
    with pytest.raises(
        EditorialMomentConflictError,
        match='candidate_revision_conflict',
    ):
        stale_service.review_moment(
            operation_id=_id(211),
            candidate_moment_id=stale.id,
            expected_candidate_revision=1,
            actor_id=_id(5),
            action=EditorialMomentReviewAction.DEFER,
            reason='stale editor state',
        )

    point = _candidate(22, point=True)
    point_service = EditorialMomentService(
        MemoryEditorialReviewRepository((point,)),
        FixedClock(NOW),
    )
    with pytest.raises(
        EditorialMomentConflictError,
        match='approval_requires_timeline_range',
    ):
        _review(
            point_service,
            point,
            operation_number=212,
            action=EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP,
        )


def _client(
    repository: MemoryEditorialReviewRepository,
) -> SyncHttpClient:
    kernel_repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(
        repository=kernel_repository,
        clock=FixedClock(NOW + timedelta(hours=1)),
    )
    configuration = cast(
        EffectiveKernelConfiguration,
        cast(
            Any,
            SimpleNamespace(
                deployment=SimpleNamespace(
                    event=SimpleNamespace(key='editorial-review-test')
                )
            ),
        ),
    )
    app = FastAPI()
    app.include_router(api_router, prefix='/api/v1')
    app.state.kernel = KernelComponents(
        configuration=configuration,
        repository=kernel_repository,
        kernel=kernel,
        editorial_moments=EditorialMomentService(
            repository,
            kernel.clock,
        ),
    )
    return cast(SyncHttpClient, TestClient(app))


def test_editorial_review_routes_are_authenticated_and_keyset_paginated() -> None:
    candidates = (
        _candidate(30, declared_at=NOW),
        _candidate(31, declared_at=NOW + timedelta(seconds=1)),
        _candidate(32, declared_at=NOW + timedelta(seconds=2)),
    )
    repository = MemoryEditorialReviewRepository(candidates)
    client = _client(repository)
    review_url = (
        f'/api/v1/editorial/moments/{candidates[0].id.value}/reviews'
    )
    command = {
        'operation_id': _id(220).value,
        'actor_id': _id(5).value,
        'confirmed': 'confirmed',
        'expected_candidate_revision': 1,
        'action': 'approve_and_create_clip',
        'reason': 'strong live moment',
    }

    assert client.post(review_url, json=command).status_code == 401
    unconfirmed = dict(command)
    del unconfirmed['confirmed']
    assert client.post(
        review_url,
        headers=AUTH_HEADERS,
        json=unconfirmed,
    ).status_code == 422
    reviewed = client.post(
        review_url,
        headers=AUTH_HEADERS,
        json=command,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()['clip']['candidate_moment_id'] == candidates[0].id.value

    queue_url = (
        f'/api/v1/editorial/events/{repository.event_id.value}/review-queue'
    )
    assert client.get(queue_url).status_code == 401
    first = client.get(
        f'{queue_url}?limit=1',
        headers=AUTH_HEADERS,
    )
    assert first.status_code == 200
    first_payload = cast(dict[str, Any], first.json())
    assert first_payload['total_candidate_count'] == 3
    assert first_payload['pending_candidate_count'] == 2
    assert first_payload['oldest_pending_age_seconds'] == 3599
    assert first_payload['items_truncated'] is True
    assert first_payload['next_cursor']
    second = client.get(
        f'{queue_url}?limit=1&cursor={first_payload["next_cursor"]}',
        headers=AUTH_HEADERS,
    )
    assert second.status_code == 200
    second_payload = cast(dict[str, Any], second.json())
    assert second_payload['items'][0]['candidate']['candidate_moment_id'] != (
        first_payload['items'][0]['candidate']['candidate_moment_id']
    )
    assert client.get(
        (
            f'/api/v1/editorial/events/{EntityId.new().value}/review-queue'
            f'?cursor={first_payload["next_cursor"]}'
        ),
        headers=AUTH_HEADERS,
    ).status_code == 422


@pytest.mark.skipif(
    not os.getenv('STAGEFLOW_TEST_POSTGRES_DSN'),
    reason='STAGEFLOW_TEST_POSTGRES_DSN is required for durability qualification.',
)
def test_postgres_review_history_clip_replay_queue_and_restart_reconstruct() -> None:
    dsn = os.environ['STAGEFLOW_TEST_POSTGRES_DSN']
    PostgresMigrationRunner(dsn).apply_event_mode_kernel_v1()
    kernel_repository = PostgresEventModeKernelRepository(dsn)
    kernel = DurableEventModeKernel(
        repository=kernel_repository,
        clock=FixedClock(NOW),
    )
    suffix = uuid4().hex
    bootstrap_operation_id = EntityId.new()
    start_operation_id = EntityId.new()
    mark_operation_id = EntityId.new()
    other_mark_operation_id = EntityId.new()
    review_operation_ids = tuple(EntityId.new() for _ in range(3))
    event_id: EntityId | None = None
    stage_id: EntityId | None = None
    session_id: EntityId | None = None
    candidate_id: EntityId | None = None
    other_candidate_id: EntityId | None = None
    try:
        bootstrapped = kernel.bootstrap(
            EventStageBootstrapRequest(
                operation_id=bootstrap_operation_id,
                event_key=f'editorial-review-{suffix}',
                event_name='Editorial Review Test',
                stages=(
                    StageBootstrapDefinition(
                        key='main',
                        name='Main',
                        source_bindings={
                            f'source-{suffix}': 'C:/synthetic/main'
                        },
                    ),
                ),
                actor_id=EntityId.new(),
                requested_at=NOW,
            )
        )
        assert bootstrapped.event is not None
        event_id = bootstrapped.event.id
        stage_id = bootstrapped.stages[0].id
        session = kernel_repository.start_session(
            StartSessionRequest(
                operation_id=start_operation_id,
                event_id=event_id,
                stage_id=stage_id,
                actor_id=EntityId.new(),
                authoritative_start=NOW,
                requested_at=NOW,
            )
        )
        session_id = session.id
        service = EditorialMomentService(
            PostgresEditorialMomentRepository(dsn),
            FixedClock(NOW + timedelta(minutes=1)),
        )
        candidate = service.mark_moment(
            operation_id=mark_operation_id,
            session_id=session.id,
            expected_session_revision=session.revision,
            timeline_start_microseconds=10_000_000,
            timeline_end_microseconds=40_000_000,
            actor_id=EntityId.new(),
            note='durable review candidate',
        )
        candidate_id = candidate.id
        other_candidate = service.mark_moment(
            operation_id=other_mark_operation_id,
            session_id=session.id,
            expected_session_revision=session.revision,
            timeline_start_microseconds=50_000_000,
            timeline_end_microseconds=70_000_000,
            actor_id=EntityId.new(),
            note='second durable review candidate',
        )
        other_candidate_id = other_candidate.id
        service.review_moment(
            operation_id=review_operation_ids[0],
            candidate_moment_id=candidate.id,
            expected_candidate_revision=1,
            actor_id=EntityId.new(),
            action=EditorialMomentReviewAction.DEFER,
            reason='return after live turn',
        )
        service.review_moment(
            operation_id=review_operation_ids[1],
            candidate_moment_id=candidate.id,
            expected_candidate_revision=1,
            actor_id=EntityId.new(),
            action=EditorialMomentReviewAction.REVISE_RANGE,
            reason='tighten the range',
            adjusted_timeline_start_microseconds=12_000_000,
            adjusted_timeline_end_microseconds=35_000_000,
        )
        approved = service.review_moment(
            operation_id=review_operation_ids[2],
            candidate_moment_id=candidate.id,
            expected_candidate_revision=1,
            actor_id=_id(5),
            action=EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP,
            reason='approved selection',
            adjusted_timeline_start_microseconds=13_000_000,
            adjusted_timeline_end_microseconds=34_000_000,
        )
        assert approved.clip is not None
        assert service.review_moment(
            operation_id=review_operation_ids[2],
            candidate_moment_id=candidate.id,
            expected_candidate_revision=1,
            actor_id=_id(5),
            action=EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP,
            reason='approved selection',
            adjusted_timeline_start_microseconds=13_000_000,
            adjusted_timeline_end_microseconds=34_000_000,
        ) == approved
        with pytest.raises(
            EditorialMomentConflictError,
            match='human_command_operation_id_conflict',
        ):
            service.review_moment(
                operation_id=review_operation_ids[2],
                candidate_moment_id=candidate.id,
                expected_candidate_revision=1,
                actor_id=_id(5),
                action=EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP,
                reason='conflicting replay',
                adjusted_timeline_start_microseconds=13_000_000,
                adjusted_timeline_end_microseconds=34_000_000,
            )
        with pytest.raises(
            EditorialMomentConflictError,
            match='candidate_revision_conflict',
        ):
            service.review_moment(
                operation_id=EntityId.new(),
                candidate_moment_id=candidate.id,
                expected_candidate_revision=2,
                actor_id=_id(5),
                action=EditorialMomentReviewAction.DEFER,
                reason='stale candidate projection',
            )

        restarted = EditorialMomentService(
            PostgresEditorialMomentRepository(dsn),
            FixedClock(NOW + timedelta(minutes=2)),
        )
        first_page = restarted.list_review_queue(event_id, limit=1)
        assert first_page.total_candidate_count == 2
        assert first_page.pending_candidate_count == 1
        assert first_page.items[0].candidate.id == other_candidate.id
        second_page = restarted.list_review_queue(
            event_id,
            after=first_page.items[0].position,
            limit=1,
        )
        assert second_page.items[0].candidate.id == candidate.id
        assert (
            second_page.items[0].candidate.review_state
            is EditorialReviewState.APPROVED
        )
        sequences = [
            item.sequence for item in second_page.items[0].decisions
        ]
        assert sequences[0] > 0
        assert sequences == list(range(sequences[0], sequences[0] + 3))
        assert second_page.items[0].clips == (approved.clip,)
        with psycopg.connect(dsn) as connection:
            assert connection.execute(
                """
                SELECT count(*)
                FROM stageflow.editorial_moment_review_decision
                WHERE candidate_moment_id = %s
                """,
                (candidate.id.value,),
            ).fetchone() == (3,)
    finally:
        if event_id is not None and stage_id is not None:
            with psycopg.connect(dsn) as connection:
                candidate_ids = [
                    item.value
                    for item in (candidate_id, other_candidate_id)
                    if item is not None
                ]
                if candidate_ids:
                    connection.execute(
                        'DELETE FROM stageflow.editorial_clip '
                        'WHERE candidate_moment_id = ANY(%s::uuid[])',
                        (candidate_ids,),
                    )
                    connection.execute(
                        'DELETE FROM stageflow.editorial_moment_review_decision '
                        'WHERE candidate_moment_id = ANY(%s::uuid[])',
                        (candidate_ids,),
                    )
                    connection.execute(
                        'DELETE FROM '
                        'stageflow.editorial_candidate_moment_location_history '
                        'WHERE candidate_moment_id = ANY(%s::uuid[])',
                        (candidate_ids,),
                    )
                    connection.execute(
                        'DELETE FROM stageflow.editorial_candidate_moment '
                        'WHERE candidate_moment_id = ANY(%s::uuid[])',
                        (candidate_ids,),
                    )
                if session_id is not None:
                    connection.execute(
                        'DELETE FROM stageflow.session_boundary_history '
                        'WHERE session_id = %s',
                        (session_id.value,),
                    )
                    connection.execute(
                        'DELETE FROM stageflow.session_start_operation '
                        'WHERE session_id = %s',
                        (session_id.value,),
                    )
                    connection.execute(
                        'DELETE FROM stageflow.session WHERE session_id = %s',
                        (session_id.value,),
                    )
                connection.execute(
                    'DELETE FROM stageflow.human_command_idempotency '
                    'WHERE operation_id = ANY(%s::uuid[])',
                    (
                        [
                            start_operation_id.value,
                            mark_operation_id.value,
                            other_mark_operation_id.value,
                        ],
                    ),
                )
                connection.execute(
                    'DELETE FROM stageflow.stage_source_binding '
                    'WHERE stage_id = %s',
                    (stage_id.value,),
                )
                connection.execute(
                    'DELETE FROM stageflow.stage WHERE stage_id = %s',
                    (stage_id.value,),
                )
                connection.execute(
                    'DELETE FROM stageflow.event_stage_bootstrap_operation '
                    'WHERE event_id = %s',
                    (event_id.value,),
                )
                connection.execute(
                    'DELETE FROM stageflow.business_event WHERE event_id = %s',
                    (event_id.value,),
                )


@pytest.mark.skipif(
    not os.getenv('STAGEFLOW_TEST_POSTGRES_DSN'),
    reason='STAGEFLOW_TEST_POSTGRES_DSN is required for migration qualification.',
)
def test_0011_reverses_before_0010_and_reapplies_without_disturbing_0008() -> None:
    dsn = os.environ['STAGEFLOW_TEST_POSTGRES_DSN']
    runner = PostgresMigrationRunner(dsn)
    runner.apply_event_mode_kernel_v1()
    try:
        runner.reverse_editorial_candidate_moment_v1()
        with psycopg.connect(dsn) as connection:
            assert connection.execute(
                "SELECT to_regclass('stageflow.editorial_candidate_moment')"
            ).fetchone() == ('stageflow.editorial_candidate_moment',)
            assert connection.execute(
                "SELECT to_regclass("
                "'stageflow.editorial_candidate_moment_location_history')"
            ).fetchone() == (None,)
            assert connection.execute(
                "SELECT to_regclass("
                "'stageflow.editorial_moment_review_decision')"
            ).fetchone() == (None,)
            assert connection.execute(
                "SELECT to_regclass('stageflow.editorial_clip')"
            ).fetchone() == (None,)
    finally:
        runner.apply_editorial_candidate_moment_v1()
    with psycopg.connect(dsn) as connection:
        assert connection.execute(
            """
            SELECT version
            FROM stageflow.schema_migration
            WHERE version IN (
                '0010_editorial_candidate_moment',
                '0011_editorial_review_foundation'
            )
            ORDER BY version
            """
        ).fetchall() == [
            ('0010_editorial_candidate_moment',),
            ('0011_editorial_review_foundation',),
        ]
