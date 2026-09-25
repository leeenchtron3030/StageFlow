from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from typing import LiteralString, cast

import psycopg
import pytest

from app.contexts.assembly.resolution import resolve_metadata
from app.contexts.assembly.session_contracts import (
    AssemblyMetadataOverride,
    AssemblySlot,
    MetadataField,
    MetadataOverrideAction,
    PlacementRole,
    ValidationReason,
)
from app.contexts.assembly.session_repository import AssemblyConflictError, AssemblyNotFoundError
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.events.kernel_contracts import ProgramExpectation
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import StartSessionRequest
from app.infrastructure.postgres import PostgresEventModeKernelRepository
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.infrastructure.postgres.session_assembly_repository import (
    PostgresSessionAssemblyRepository,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_packaging_asset_foundation import HEADERS
from tests.test_session_assembly_foundation import (
    ACTOR,
    EVENT,
    INPUT,
    NOW,
    SESSION,
    Harness,
    client_for,
)


def entry(number: int = 1, /, **changes: object) -> AssemblyMetadataOverride:
    original = AssemblyMetadataOverride(
        EntityId.new(), SESSION, MetadataField.SESSION_TITLE, MetadataOverrideAction.SET,
        ("Corrected title",), number, ACTOR, NOW, "Operator correction",
    )
    return replace(original, **changes)


def record(
    service: SessionAssemblyService, expected: int = 0, *, session: EntityId = SESSION,
    field: MetadataField = MetadataField.SESSION_TITLE,
    action: MetadataOverrideAction = MetadataOverrideAction.SET,
    values: tuple[str, ...] = ("Corrected title",), operation: EntityId | None = None,
) -> AssemblyMetadataOverride:
    return service.record_metadata_override(
        operation_id=operation or EntityId.new(), actor_id=ACTOR, session_id=session,
        field=field, action=action, values=values, expected_sequence=expected,
        reason="Operator correction",
    )


def test_resolution_latest_sequence_clear_and_session_isolation() -> None:
    first = entry()
    second = entry(2, values=("New title",), recorded_at=NOW - timedelta(days=1))
    unrelated = entry(100, session_id=EntityId.new())
    history = (first, second, unrelated)
    resolved = resolve_metadata(INPUT, history)
    assert resolved == resolve_metadata(INPUT, reversed(history))
    assert resolved[0] == INPUT.metadata[0]
    assert resolved[1].values == ("New title",)
    assert (resolved[1].source, resolved[1].source_id, resolved[1].source_revision) == (
        "operator_override", second.id, 2,
    )
    cleared = entry(3, action=MetadataOverrideAction.CLEAR, values=())
    assert resolve_metadata(INPUT, (*history, cleared)) == INPUT.metadata
    assert resolve_metadata(replace(INPUT, metadata=()), (first, cleared)) == ()


def test_contracts_copy_nested_values_and_require_human_aware_provenance() -> None:
    values = ["Speaker A", "Speaker B"]
    override = entry(values=values)
    values.append("Speaker C")
    assert override.values == ("Speaker A", "Speaker B")
    attribute = "reason"
    with pytest.raises(FrozenInstanceError):
        setattr(override, attribute, "changed")
    for changes in ({"recorded_at": NOW.replace(tzinfo=None)}, {"authority_kind": "automatic"}):
        with pytest.raises(ValueError):
            entry(**changes)
    snapshot = resolve_metadata(INPUT, (override,))[1]
    assert isinstance(snapshot.values, tuple)
    attribute = "values"
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, attribute, ("changed",))


@pytest.mark.parametrize("changes", [
    {"values": ()}, {"values": (" ",)}, {"values": ("bad\x00value",)},
    {"values": ("x" * 1001,)}, {"values": ("x",) * 101}, {"values": "title"},
    {"values": (["nested"],)}, {"field": "unknown"}, {"action": "unknown"},
    {"action": "clear"}, {"reason": " "}, {"sequence": 0}, {"sequence": True},
])
def test_invalid_override_facts_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        entry(**changes)


def test_validation_staleness_approval_and_frozen_history() -> None:
    h = Harness()
    h.inputs = replace(h.inputs, metadata=())
    original = h.propose()
    assert ValidationReason.MISSING_REQUIRED_METADATA in {
        i.code for i in original.validation.issues
    }
    title = record(h.service)
    names = record(h.service, 1, field=MetadataField.PARTICIPANT_NAMES,
                   values=("Speaker B", "Speaker A"))
    resolved = h.propose(1)
    assert resolved.validation.state == "valid"
    assert resolved.metadata[0].source_id == names.id
    assert resolved.metadata[1].source_id == title.id
    h.decide(2)
    # Same text, new provenance: a new set still makes the older snapshot stale.
    record(h.service, 2)
    page = h.repository.list_revisions(EVENT, SESSION)
    assert all(item.stale for item in page.items)
    assert page.items[0].revision == original and page.items[1].revision == resolved
    with pytest.raises(AssemblyConflictError, match="not_approvable"):
        h.decide(2, 1)
    record(h.service, 3, action=MetadataOverrideAction.CLEAR, values=())
    cleared = h.propose(2)
    assert cleared.metadata == (resolved.metadata[0],)
    assert cleared.validation.issues[-1].subject == "session_title"
    assert h.inputs.metadata == ()  # Assembly never writes its input snapshot.


def test_clear_restores_program_and_program_refresh_never_stales() -> None:
    h = Harness()
    baseline = h.propose()
    record(h.service)
    overridden = h.propose(1)
    record(h.service, 1, action=MetadataOverrideAction.CLEAR, values=())
    page = h.repository.list_revisions(EVENT, SESSION)
    assert not page.items[0].stale and page.items[1].stale
    assert h.propose(2).metadata == baseline.metadata
    assert overridden.metadata != baseline.metadata
    # ED-0077 design decision 7: a Program Expectation refresh never makes a revision stale.
    h.inputs = replace(h.inputs, metadata=tuple(
        replace(value, source_revision=value.source_revision + 1) for value in h.inputs.metadata
    ))
    page = h.repository.list_revisions(EVENT, SESSION)
    assert not page.items[0].stale and page.items[1].stale


def test_overrides_shield_program_refresh_and_clear_uses_latest_program() -> None:
    h = Harness()
    h.propose()
    record(h.service)
    record(h.service, 1, field=MetadataField.PARTICIPANT_NAMES, values=("Speaker C",))
    overridden = h.propose(1)
    h.inputs = replace(h.inputs, metadata=tuple(
        replace(value, source_revision=value.source_revision + 1, values=("Updated display",))
        for value in h.inputs.metadata
    ))
    page = h.repository.list_revisions(EVENT, SESSION)
    assert not page.items[1].stale and page.items[1].revision == overridden
    record(h.service, 2, action=MetadataOverrideAction.CLEAR, values=())
    next_revision = h.propose(2)
    assert next_revision.metadata[1] == h.inputs.metadata[1]
    assert next_revision.metadata[0] == overridden.metadata[0]


def test_replay_sequence_scope_pagination_and_clock() -> None:
    h = Harness()
    with pytest.raises(AssemblyNotFoundError, match="assembly_not_found"):
        record(h.service)
    h.propose()
    operation = EntityId.new()
    first = record(h.service, operation=operation)
    assert first.recorded_at == NOW and first.actor_id == ACTOR
    record(h.service, 1, field=MetadataField.PARTICIPANT_NAMES, values=("Speaker A",))
    h.service.clock = FixedClock(NOW + timedelta(days=1))
    assert record(h.service, operation=operation) == first
    with pytest.raises(AssemblyConflictError, match="operation_id_conflict"):
        record(h.service, values=("Changed",), operation=operation)
    with pytest.raises(AssemblyConflictError, match="sequence_conflict"):
        record(h.service, 1)
    with pytest.raises(AssemblyNotFoundError):
        record(h.service, session=EntityId.new())
    with pytest.raises(AssemblyNotFoundError):
        h.repository.list_metadata_overrides(EntityId.new(), SESSION)
    page = h.repository.list_metadata_overrides(EVENT, SESSION, limit=1)
    assert page.items == (first,) and page.total_count == 2 and page.next_after == 1
    last = h.repository.list_metadata_overrides(EVENT, SESSION, after=1, limit=1)
    assert last.items[0].sequence == 2 and last.next_after is None
    assert h.repository.list_metadata_overrides(EVENT, SESSION, after=2).items == ()
    for limit in (0, 101):
        with pytest.raises(ValueError):
            h.repository.list_metadata_overrides(EVENT, SESSION, limit=limit)


def test_concurrent_sequence_and_identical_replay() -> None:
    h = Harness()
    h.propose()
    def append(_: int) -> str:
        try:
            record(h.service)
            return "created"
        except AssemblyConflictError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sorted(pool.map(append, range(3))) == ["conflict", "conflict", "created"]
    operation = EntityId.new()
    def replay(_: int) -> AssemblyMetadataOverride:
        return record(h.service, 1, operation=operation)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(replay, range(3)))
    assert all(result == results[0] for result in results)


def test_api_authentication_validation_event_pages_and_revision_sources() -> None:
    h = Harness()
    h.propose()
    client = client_for(h)
    url = f"/api/v1/assembly/sessions/{SESSION}/metadata-overrides"
    history = f"/api/v1/assembly/events/{EVENT}/sessions/{SESSION}/metadata-overrides"
    body = {"operation_id": EntityId.new().value, "actor_id": ACTOR.value,
            "confirmed": "confirmed", "field": "session_title", "action": "set",
            "values": ["Corrected title"], "expected_sequence": 0, "reason": "Correction"}
    assert client.post(url, json=body).status_code == 401
    assert client.get(history).status_code == 401
    response = client.post(url, json=body, headers=HEADERS)
    assert response.status_code == 200 and response.json()["authority_kind"] == "human"
    assert client.post(url, json=body, headers=HEADERS).json() == response.json()
    invalid_bodies: tuple[dict[str, object], ...] = (
        {"values": []}, {"values": [" "]}, {"action": "clear"},
                    {"field": "unknown"}, {"authority_kind": "automatic"},
                    {"confirmed": "no"}, {"recorded_at": NOW.isoformat()},
                    {"expected_sequence": True})
    for invalid in invalid_bodies:
        assert client.post(url, json={**body, **invalid}, headers=HEADERS).status_code == 422
    assert client.post(url, json={**body, "operation_id": EntityId.new().value},
                       headers=HEADERS).status_code == 409
    assert client.get(history + "?limit=101", headers=HEADERS).status_code == 422
    assert client.get(history.replace(EVENT.value, EntityId.new().value),
                      headers=HEADERS).status_code == 404
    assert client.get(history, headers=HEADERS).json()["items"] == [response.json()]
    h.propose(1)
    revisions = client.get(history.replace("metadata-overrides", "revisions"), headers=HEADERS)
    items = revisions.json()["items"]
    assert items[0]["stale"] and not items[1]["stale"]
    sources = {m["field"]: m["source"] for m in items[1]["revision"]["metadata"]}
    assert sources == {"session_title": "operator_override",
                       "participant_names": "program_expectation"}


@pytest.fixture
def postgres_dsn() -> str:
    dsn = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("STAGEFLOW_TEST_POSTGRES_DSN is required for real PostgreSQL validation")
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            pass
    except psycopg.OperationalError:
        pytest.skip("Real PostgreSQL is unreachable from this sandbox")
    return dsn


def test_postgres_persistence_reconstruction_immutability_and_migration(postgres_dsn: str) -> None:
    runner = PostgresMigrationRunner(postgres_dsn)
    runner.apply_event_mode_kernel_v1()
    kernel_repo = PostgresEventModeKernelRepository(postgres_dsn)
    kernel = DurableEventModeKernel(repository=kernel_repo, clock=FixedClock(NOW))
    boot = kernel.bootstrap(EventStageBootstrapRequest(
        EntityId.new(), "overrides-" + EntityId.new().value, "Example Event",
        (StageBootstrapDefinition("main", "Example Stage", {}),), ACTOR, NOW,
    ))
    assert boot.event is not None
    event, stage = boot.event.id, boot.stages[0].id
    program = kernel_repo.put_program_expectation(ProgramExpectation(
        EntityId.new(), event, "example-program", stage, "Original title", ("Speaker A",),
        NOW, NOW + timedelta(hours=1), {}, 1, NOW,
    ))
    session = kernel.start_session(StartSessionRequest(
        EntityId.new(), event, stage, ACTOR, NOW, NOW, program.id,
    ))
    def service() -> SessionAssemblyService:
        return SessionAssemblyService(
            PostgresSessionAssemblyRepository(postgres_dsn), FixedClock(NOW),
        )
    svc = service()
    template = svc.create_template(
        operation_id=EntityId.new(), actor_id=ACTOR, event_id=event, template_key="example",
        expected_version=0, name="Example", slots=(
            AssemblySlot("media", PlacementRole.SESSION_MEDIA, True),),
        required_metadata=(MetadataField.SESSION_TITLE,),
    )
    def propose(expected: int, operation: EntityId | None = None):
        return service().propose(
            operation_id=operation or EntityId.new(), actor_id=ACTOR, session_id=session.id,
            template_id=template.id, expected_revision=expected,
            expected_package_revision=session.package_revision,
        )
    with psycopg.connect(postgres_dsn) as conn:
        before = conn.execute("SELECT * FROM stageflow.program_expectation_revision "
                              "WHERE expectation_id=%s", (program.id.value,)).fetchall()
        current_before = conn.execute("SELECT * FROM stageflow.program_expectation "
                                      "WHERE expectation_id=%s", (program.id.value,)).fetchall()
    with pytest.raises(AssemblyNotFoundError):
        record(svc, session=session.id)
    baseline = propose(0)
    operation = EntityId.new()
    first = record(svc, session=session.id, operation=operation)
    proposal_op = EntityId.new()
    overridden = propose(1, proposal_op)
    assert overridden.metadata[0] == baseline.metadata[0]
    assert overridden.metadata[1].source_id == first.id
    assert overridden.metadata[1].source == "operator_override"
    assert propose(1, proposal_op) == overridden
    after_set = service().repository.list_revisions(event, session.id)
    assert after_set.items[1].revision == overridden
    # The Program-sourced baseline is stale once an override governs its field; the
    # override-sourced proposal is current.
    assert after_set.items[0].stale and not after_set.items[1].stale
    record(service(), 1, session=session.id, action=MetadataOverrideAction.CLEAR, values=())
    projected = service().repository.list_revisions(event, session.id)
    assert not projected.items[0].stale and projected.items[1].stale
    assert projected.items[1].revision == overridden
    assert record(service(), session=session.id, operation=operation) == first
    with pytest.raises(AssemblyConflictError, match="operation_id_conflict"):
        record(service(), session=session.id, operation=operation, values=("Changed",))
    with pytest.raises(AssemblyConflictError, match="sequence_conflict"):
        record(service(), session=session.id)
    assert propose(2).metadata == baseline.metadata
    page = service().repository.list_metadata_overrides(event, session.id, limit=1)
    assert page.items == (first,) and page.next_after == 1 and page.total_count == 2
    last = service().repository.list_metadata_overrides(event, session.id, after=1, limit=1)
    assert last.items[0].sequence == 2 and last.next_after is None
    with pytest.raises(AssemblyNotFoundError):
        service().repository.list_metadata_overrides(EntityId.new(), session.id)
    with psycopg.connect(postgres_dsn) as conn:
        assert conn.execute("SELECT field FROM stageflow.assembly_metadata_snapshot "
                            "WHERE revision_id=%s", (overridden.id.value,)).fetchall() == [
                                ("participant_names",)]
        assert conn.execute("SELECT * FROM stageflow.program_expectation_revision "
                            "WHERE expectation_id=%s", (program.id.value,)).fetchall() == before
        assert conn.execute(
            "SELECT * FROM stageflow.program_expectation WHERE expectation_id=%s",
            (program.id.value,),
        ).fetchall() == current_before
    assert kernel_repo.get_session(session.id) == session
    def concurrent_append(_: int) -> str:
        try:
            record(service(), 2, session=session.id)
            return "created"
        except AssemblyConflictError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sorted(pool.map(concurrent_append, range(3))) == ["conflict", "conflict", "created"]
    replay_op = EntityId.new()
    def concurrent_replay(_: int) -> AssemblyMetadataOverride:
        return record(service(), 3, session=session.id, operation=replay_op)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(concurrent_replay, range(3)))
    assert all(result == results[0] for result in results)
    for statement in (
        "UPDATE stageflow.assembly_metadata_override SET reason=reason WHERE override_id=%s",
        "DELETE FROM stageflow.assembly_metadata_override WHERE override_id=%s",
        "UPDATE stageflow.assembly_metadata_override_snapshot SET field=field WHERE override_id=%s",
        "DELETE FROM stageflow.assembly_metadata_override_snapshot WHERE override_id=%s",
    ):
        with pytest.raises(psycopg.errors.RaiseException, match="assembly_history_is_immutable"):
            with psycopg.connect(postgres_dsn) as conn:
                conn.execute(cast(LiteralString, statement), (first.id.value,))
    # Explicitly isolated test database; reverse only the new slice, preserving all 0013 rows.
    runner.reverse_assembly_metadata_overrides_v1()
    with psycopg.connect(postgres_dsn) as conn:
        assert conn.execute(
            "SELECT to_regclass('stageflow.assembly_metadata_override')",
        ).fetchone() == (None,)
        assert conn.execute("SELECT count(*) FROM stageflow.assembly_revision WHERE revision_id=%s",
                            (overridden.id.value,)).fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM stageflow.assembly_metadata_snapshot "
                            "WHERE revision_id=%s", (baseline.id.value,)).fetchone() == (2,)
    runner.apply_assembly_metadata_overrides_v1()
    runner.apply_assembly_metadata_overrides_v1()
    assert service().repository.list_metadata_overrides(event, session.id).total_count == 0
    assert service().repository.list_revisions(event, session.id).items[0].revision == baseline
    assert record(service(), session=session.id).sequence == 1
