from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from inspect import signature

from app.contexts.production.dispatcher import (
    DispatchContext,
    ProductionEventDispatcher,
)
from app.contexts.production.ingress import (
    DurableIngressDispatcher,
    IngressIdentityKind,
    IngressRegistrationRequest,
    IngressRegistrationResult,
    IngressRegistrationStatus,
    InMemoryIngressRepository,
    StableSourceIdentity,
)
from app.contexts.production.interpreter import (
    InterpreterStatus,
    ProductionEventInterpreter,
)
from app.contexts.production.production_event import (
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.time import FixedClock


def make_ingress_request(
    *,
    source_event_key: str | None = "vendor-event-42",
    payload_value: str = "ready",
    occurred_at: datetime | None = None,
    received_at: datetime | None = None,
) -> IngressRegistrationRequest:
    occurred = occurred_at or datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
    return IngressRegistrationRequest(
        source_identity=StableSourceIdentity("recording-adapter", "recorder-a"),
        source_event_key=source_event_key,
        event_type=ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
        event_source=ProductionEventSource.RECORDING_SYSTEM,
        payload=ProductionEventPayload({"status": payload_value}),
        correlation_id=CorrelationId.parse("42b8c660-8221-4b76-b15a-6714bebac48b"),
        occurred_at=occurred,
        received_at=received_at or occurred + timedelta(seconds=1),
        authoritative_source_facts={"recorder_sequence": 17},
    )


def test_same_source_key_replays_with_stable_ids_and_delivery_evidence() -> None:
    repository = InMemoryIngressRepository()

    created = repository.register(make_ingress_request())
    replayed = repository.register(
        make_ingress_request(
            received_at=datetime(2026, 8, 8, 10, 0, 2, tzinfo=UTC)
        )
    )

    assert created.status is IngressRegistrationStatus.CREATED
    assert replayed.status is IngressRegistrationStatus.REPLAYED
    assert created.record is not None
    assert replayed.record is not None
    assert replayed.record.ingress_id == created.record.ingress_id
    assert replayed.record.production_event_id == created.record.production_event_id
    assert replayed.record.first_received_at == created.record.first_received_at
    assert replayed.record.last_received_at > replayed.record.first_received_at
    assert replayed.record.delivery_count == 2


def test_same_source_key_with_changed_authoritative_facts_is_conflict() -> None:
    repository = InMemoryIngressRepository()
    repository.register(make_ingress_request(payload_value="ready"))

    conflict = repository.register(make_ingress_request(payload_value="failed"))

    assert conflict.status is IngressRegistrationStatus.CONFLICT
    assert conflict.failure_code == "ingress_identity_conflict"
    assert conflict.record is not None
    assert conflict.record.delivery_count == 1


def test_fingerprint_normalizes_equivalent_offsets_and_is_versioned() -> None:
    instant_utc = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
    instant_offset = instant_utc.astimezone(timezone(timedelta(hours=-7)))
    first = make_ingress_request(source_event_key=None, occurred_at=instant_utc)
    second = make_ingress_request(
        source_event_key=None,
        occurred_at=instant_offset,
        received_at=instant_offset + timedelta(seconds=1),
    )

    assert first.identity.kind is IngressIdentityKind.CANONICAL_FINGERPRINT
    assert first.identity.fingerprint_version == "stageflow-ingress-v1"
    assert first.identity == second.identity
    assert first.facts_digest == second.facts_digest


def test_supplementary_metadata_is_not_an_ingress_identity_input() -> None:
    parameters = signature(IngressRegistrationRequest).parameters

    assert "metadata" not in parameters
    assert "authoritative_source_facts" in parameters


def test_backward_receipt_clock_does_not_allocate_new_identity() -> None:
    repository = InMemoryIngressRepository()
    occurred = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
    first_clock = FixedClock(occurred + timedelta(seconds=10))
    replay_clock = FixedClock(occurred + timedelta(seconds=5))
    first = repository.register(
        make_ingress_request(
            occurred_at=occurred,
            received_at=first_clock.now(),
        )
    )
    replay = repository.register(
        make_ingress_request(
            occurred_at=occurred,
            received_at=replay_clock.now(),
        )
    )

    assert first.record is not None
    assert replay.record is not None
    assert replay.status is IngressRegistrationStatus.REPLAYED
    assert replay.record.ingress_id == first.record.ingress_id
    assert replay.record.first_received_at == occurred + timedelta(seconds=10)
    assert replay.record.last_received_at == occurred + timedelta(seconds=5)


def test_concurrent_replays_create_one_record() -> None:
    repository = InMemoryIngressRepository()
    request = make_ingress_request()

    def register_replay(_: int) -> IngressRegistrationResult:
        return repository.register(request)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(register_replay, range(24)))

    assert sum(result.status is IngressRegistrationStatus.CREATED for result in results) == 1
    records = tuple(result.record for result in results)
    assert all(record is not None for record in records)
    assert len({record.ingress_id for record in records if record is not None}) == 1
    assert max(record.delivery_count for record in records if record is not None) == 24


def test_replay_does_not_repeat_dispatch_side_effect_path() -> None:
    interpreter = ProductionEventInterpreter(
        id=EntityId.new(),
        name="Ingress path interpreter",
        supported_event_types=(ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,),
        supported_event_sources=(ProductionEventSource.RECORDING_SYSTEM,),
        status=InterpreterStatus.ACTIVE,
    )
    boundary = DurableIngressDispatcher(
        repository=InMemoryIngressRepository(),
        dispatcher=ProductionEventDispatcher(
            id=EntityId.new(),
            name="Ingress dispatcher",
            interpreters=(interpreter,),
        ),
    )
    context = DispatchContext(
        correlation_id=CorrelationId.new(),
        timestamp=datetime(2026, 8, 8, 10, 0, 3, tzinfo=UTC),
    )

    first = boundary.register_and_dispatch(make_ingress_request(), context)
    replay = boundary.register_and_dispatch(make_ingress_request(), context)

    assert first.registration.status is IngressRegistrationStatus.CREATED
    assert first.dispatch is not None
    assert first.dispatch.invoked_interpreter_ids == (interpreter.id,)
    assert replay.registration.status is IngressRegistrationStatus.REPLAYED
    assert replay.dispatch is None


def test_naive_authoritative_timestamps_are_rejected() -> None:
    naive = datetime(2026, 8, 8, 10, 0)

    try:
        make_ingress_request(
            occurred_at=naive, received_at=naive + timedelta(seconds=1)
        )
    except ValueError as error:
        assert "timezone-aware" in str(error)
    else:
        raise AssertionError("naive ingress timestamps must be rejected")
