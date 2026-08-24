from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Protocol, cast
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api.v1.router import router as api_router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.events import (
    EventStageBootstrapRequest,
    StageBootstrapDefinition,
)
from app.contexts.production.event_mode_kernel import (
    AssociationAuthority,
    AssociationInputReference,
    AssociationStatus,
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    MediaAssociation,
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
    SessionPackageState,
    StartSessionRequest,
)
from app.core.config.deployment import EffectiveKernelConfiguration
from app.infrastructure.postgres import (
    PostgresEventModeKernelRepository,
    PostgresMigrationRunner,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 23, 18, 0, tzinfo=UTC)
AUTH_HEADERS = {
    "X-StageFlow-API-Secret": "stageflow-test-only-shared-secret-0123456789"
}


class SyncHttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> Response: ...


def _id(number: int) -> EntityId:
    return EntityId(f"92000000-0000-0000-0000-{number:012d}")


def _bootstrap(
    kernel: DurableEventModeKernel,
    *,
    number: int,
) -> tuple[EntityId, tuple[EntityId, EntityId]]:
    result = kernel.bootstrap(
        EventStageBootstrapRequest(
            operation_id=_id(number),
            event_key=f"work-queue-event-{number}",
            event_name=f"Work Queue Event {number}",
            stages=(
                StageBootstrapDefinition(
                    key=f"main-{number}",
                    name="Main",
                    source_bindings={f"main-source-{number}": "C:/synthetic/main"},
                ),
                StageBootstrapDefinition(
                    key=f"studio-{number}",
                    name="Studio",
                    source_bindings={f"studio-source-{number}": "C:/synthetic/studio"},
                ),
            ),
            actor_id=_id(number + 1),
            requested_at=NOW,
        )
    )
    assert result.event is not None
    return result.event.id, (result.stages[0].id, result.stages[1].id)


def _session(
    repository: InMemoryEventModeKernelRepository,
    *,
    event_id: EntityId,
    stage_id: EntityId,
    number: int,
    state: SessionPackageState,
    updated_at: datetime,
) -> EntityId:
    session = repository.start_session(
        StartSessionRequest(
            operation_id=_id(number),
            event_id=event_id,
            stage_id=stage_id,
            actor_id=_id(number + 1),
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    repository.set_package_state(session.id, state.value, updated_at)
    return session.id


def _association(
    repository: InMemoryEventModeKernelRepository,
    *,
    stage_id: EntityId,
    number: int,
    status: AssociationStatus,
    decided_at: datetime,
    source_binding_key: str,
) -> EntityId:
    candidate = MediaCandidate(
        id=_id(number),
        proposed_asset_id=_id(number + 1),
        stage_id=stage_id,
        source_binding_key=source_binding_key,
        source_reference=f"C:/synthetic/media-{number}.mkv",
        discovered_at=NOW,
        last_observed_at=NOW,
        state=MediaRegistrationState.READY,
        revision=1,
    )
    repository.register_candidate(candidate)
    asset = RegisteredMediaAsset(
        id=candidate.proposed_asset_id,
        candidate_id=candidate.id,
        manifest_id=_id(number + 2),
        stage_id=stage_id,
        source_binding_key=candidate.source_binding_key,
        registered_at=NOW,
    )
    repository.register_asset(asset)
    repository.put_association(
        MediaAssociation(
            asset_id=asset.id,
            status=status,
            session_id=None,
            authority=AssociationAuthority.DETERMINISTIC,
            reason_codes=(f"test_{status.value}",),
            evidence_ids=(),
            revision=1,
            decided_at=decided_at,
            policy_id="test-association-policy",
            policy_version="1",
            input_references=(
                AssociationInputReference(
                    "registered_media_asset",
                    asset.id.value,
                ),
            ),
        )
    )
    return asset.id


def _world() -> tuple[
    InMemoryEventModeKernelRepository,
    EntityId,
    EntityId,
    EntityId,
    EntityId,
    EntityId,
]:
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    event_id, stages = _bootstrap(kernel, number=1)
    other_event_id, other_stages = _bootstrap(kernel, number=100)
    ready_session_id = _session(
        repository,
        event_id=event_id,
        stage_id=stages[0],
        number=10,
        state=SessionPackageState.READY_FOR_REVIEW,
        updated_at=NOW + timedelta(minutes=4),
    )
    correction_session_id = _session(
        repository,
        event_id=event_id,
        stage_id=stages[1],
        number=20,
        state=SessionPackageState.CORRECTION_REQUIRED,
        updated_at=NOW + timedelta(minutes=3),
    )
    unresolved_asset_id = _association(
        repository,
        stage_id=stages[0],
        number=30,
        status=AssociationStatus.UNRESOLVED,
        decided_at=NOW + timedelta(minutes=2),
        source_binding_key="main-source-1",
    )
    conflict_asset_id = _association(
        repository,
        stage_id=stages[1],
        number=40,
        status=AssociationStatus.CONFLICT,
        decided_at=NOW + timedelta(minutes=1),
        source_binding_key="studio-source-1",
    )
    _session(
        repository,
        event_id=other_event_id,
        stage_id=other_stages[0],
        number=110,
        state=SessionPackageState.READY_FOR_REVIEW,
        updated_at=NOW + timedelta(minutes=5),
    )
    return (
        repository,
        event_id,
        ready_session_id,
        correction_session_id,
        unresolved_asset_id,
        conflict_asset_id,
    )


def _client(
    repository: InMemoryEventModeKernelRepository,
) -> SyncHttpClient:
    configuration = cast(
        EffectiveKernelConfiguration,
        cast(
            Any,
            SimpleNamespace(
                deployment=SimpleNamespace(
                    event=SimpleNamespace(key="work-queue-event")
                )
            ),
        ),
    )
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.kernel = KernelComponents(
        configuration=configuration,
        repository=repository,
        kernel=DurableEventModeKernel(
            repository=repository,
            clock=FixedClock(NOW),
        ),
    )
    return cast(SyncHttpClient, TestClient(app))


def test_work_queue_returns_only_four_authorized_types_in_event_scope() -> None:
    repository, event_id, *_ = _world()

    subjects = repository.list_producer_work_queue(event_id)

    assert [subject.decision_type.value for subject in subjects] == [
        "association_conflict",
        "association_unresolved",
        "package_correction_required",
        "package_ready_for_review",
    ]
    assert all(subject.event_id == event_id for subject in subjects)
    assert all(subject.subject_revision >= 1 for subject in subjects)
    assert all(subject.action_reference for subject in subjects)


def test_work_queue_items_follow_authoritative_subject_state() -> None:
    (
        repository,
        event_id,
        ready_session_id,
        correction_session_id,
        unresolved_asset_id,
        conflict_asset_id,
    ) = _world()

    repository.set_package_state(
        ready_session_id,
        SessionPackageState.IN_REVIEW.value,
        NOW + timedelta(minutes=5),
    )
    repository.set_package_state(
        correction_session_id,
        SessionPackageState.ASSEMBLING.value,
        NOW + timedelta(minutes=5),
    )
    for operation, asset_id, session_id in (
        (60, unresolved_asset_id, ready_session_id),
        (61, conflict_asset_id, correction_session_id),
    ):
        current = repository.get_association(asset_id)
        assert current is not None
        repository.put_association(
            MediaAssociation(
                asset_id=asset_id,
                status=AssociationStatus.ASSOCIATED,
                session_id=session_id,
                authority=AssociationAuthority.HUMAN,
                reason_codes=("human_resolution",),
                evidence_ids=(),
                revision=current.revision + 1,
                decided_at=NOW + timedelta(minutes=6),
                actor_id=_id(62),
                operation_id=_id(operation),
                input_references=(
                    AssociationInputReference("session", session_id.value, 2),
                ),
            ),
            request_digest=f"resolve-{operation}",
        )

    assert repository.list_producer_work_queue(event_id) == ()


def test_work_queue_api_is_authenticated_and_keyset_paginated() -> None:
    repository, event_id, *_ = _world()
    client = _client(repository)
    url = f"/api/v1/producer/events/{event_id.value}/work-queue"

    assert client.get(url).status_code == 401
    first = client.get(f"{url}?limit=2", headers=AUTH_HEADERS)

    assert first.status_code == 200
    first_payload = cast(dict[str, Any], first.json())
    first_items = cast(list[dict[str, Any]], first_payload["items"])
    assert [item["decision_type"] for item in first_items] == [
        "association_conflict",
        "association_unresolved",
    ]
    assert first_payload["items_truncated"] is True
    assert first_payload["next_cursor"]
    second = client.get(
        f"{url}?limit=2&cursor={first_payload['next_cursor']}",
        headers=AUTH_HEADERS,
    )
    assert second.status_code == 200
    second_payload = cast(dict[str, Any], second.json())
    second_items = cast(list[dict[str, Any]], second_payload["items"])
    assert [item["decision_type"] for item in second_items] == [
        "package_correction_required",
        "package_ready_for_review",
    ]
    assert second_payload["items_truncated"] is False
    assert second_payload["next_cursor"] is None
    assert {
        item["item_id"]
        for item in (*first_items, *second_items)
    } == {
        subject.projection_id
        for subject in repository.list_producer_work_queue(event_id)
    }
    assert client.get(
        (
            f"/api/v1/producer/events/{EntityId.new().value}/work-queue"
            f"?cursor={first_payload['next_cursor']}"
        ),
        headers=AUTH_HEADERS,
    ).status_code == 422
    assert client.get(
        f"{url}?cursor=not-a-cursor",
        headers=AUTH_HEADERS,
    ).status_code == 422


@pytest.mark.skipif(
    not os.getenv("STAGEFLOW_TEST_POSTGRES_DSN"),
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for durability qualification.",
)
def test_postgres_work_queue_query_is_event_scoped_bounded_and_keyset_paginated() -> None:
    dsn = os.environ["STAGEFLOW_TEST_POSTGRES_DSN"]
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "stageflow_worker_test",
        )
    PostgresMigrationRunner(dsn).apply_event_mode_kernel_v1()
    repository = PostgresEventModeKernelRepository(dsn)
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    suffix = uuid4().hex
    bootstrapped = kernel.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId.new(),
            event_key=f"work-queue-postgres-{suffix}",
            event_name="Work Queue PostgreSQL",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={f"source-{suffix}": "C:/synthetic/main"},
                ),
            ),
            actor_id=EntityId.new(),
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    stage = bootstrapped.stages[0]
    session = repository.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=bootstrapped.event.id,
            stage_id=stage.id,
            actor_id=EntityId.new(),
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    repository.set_package_state(
        session.id,
        SessionPackageState.READY_FOR_REVIEW.value,
        NOW + timedelta(minutes=2),
    )
    candidate = MediaCandidate(
        id=EntityId.new(),
        proposed_asset_id=EntityId.new(),
        stage_id=stage.id,
        source_binding_key=f"source-{suffix}",
        source_reference="C:/synthetic/postgres-work-queue.mkv",
        discovered_at=NOW,
        last_observed_at=NOW,
        state=MediaRegistrationState.READY,
        revision=1,
    )
    repository.register_candidate(candidate)
    asset = RegisteredMediaAsset(
        id=candidate.proposed_asset_id,
        candidate_id=candidate.id,
        manifest_id=EntityId.new(),
        stage_id=stage.id,
        source_binding_key=candidate.source_binding_key,
        registered_at=NOW,
    )
    repository.register_asset(asset)
    repository.put_association(
        MediaAssociation(
            asset_id=asset.id,
            status=AssociationStatus.UNRESOLVED,
            session_id=None,
            authority=AssociationAuthority.DETERMINISTIC,
            reason_codes=("postgres_work_queue_unresolved",),
            evidence_ids=(),
            revision=1,
            decided_at=NOW + timedelta(minutes=1),
            policy_id="test-association-policy",
            policy_version="1",
            input_references=(
                AssociationInputReference(
                    "registered_media_asset",
                    asset.id.value,
                ),
            ),
        )
    )

    first = repository.list_producer_work_queue(
        bootstrapped.event.id,
        limit=1,
    )
    assert [item.decision_type.value for item in first] == [
        "association_unresolved"
    ]
    second = repository.list_producer_work_queue(
        bootstrapped.event.id,
        after=first[0].position,
        limit=1,
    )
    assert [item.decision_type.value for item in second] == [
        "package_ready_for_review"
    ]
    assert repository.list_producer_work_queue(EntityId.new()) == ()
