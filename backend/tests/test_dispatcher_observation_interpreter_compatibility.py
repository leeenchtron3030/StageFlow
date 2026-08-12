from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.production.dispatcher import (
    DispatchContext,
    DispatchStatus,
    ObservationInterpreterAdapter,
    ProductionEventDispatcher,
)
from app.contexts.production.dispatcher.compatibility import (
    CompatibleObservationInterpreter,
    map_observation_interpreter_status,
    observation_interpreter_context_from,
)
from app.contexts.production.interpreter import (
    InterpreterContext,
    InterpreterStatus,
)
from app.contexts.production.observation_interpreter import (
    LineageExtractionState,
    ObservationInterpreterContext,
    ObservationInterpreterResult,
    ObservationInterpreterStatus,
    event_observation_lineage_from_event,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventReference,
    ProductionEventReferenceType,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId
from tests import test_media_artifact_observation_interpreter_contracts as media_contracts
from tests import test_recording_activity_observation_interpreter_contracts as recording_contracts
from tests import test_runtime_clock_observation_interpreter_contracts as clock_contracts
from tests import test_schedule_observation_interpreter_contracts as schedule_contracts
from tests import test_transcript_observation_interpreter_contracts as transcript_contracts
from tests import test_vision_observation_interpreter_contracts as vision_contracts


@dataclass(frozen=True)
class FixedObservationInterpreter:
    id: EntityId
    status: ObservationInterpreterStatus
    result: ObservationInterpreterResult
    raises: bool = False

    def can_interpret_event(self, event: ProductionEvent) -> bool:
        return True

    def interpret(
        self,
        events: ProductionEvent | Sequence[ProductionEvent],
        context: ObservationInterpreterContext,
    ) -> ObservationInterpreterResult:
        if self.raises:
            raise RuntimeError("sensitive adapter detail")
        return self.result


def _dispatch_context() -> DispatchContext:
    return DispatchContext(
        correlation_id=CorrelationId.new(),
        timestamp=datetime(2026, 7, 9, 10, 0, 2, tzinfo=UTC),
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        metadata={"mode": "compatibility"},
    )


def _supported_pairs() -> tuple[
    tuple[CompatibleObservationInterpreter, ProductionEvent], ...
]:
    recording_block_id = EntityId.new()
    return (
        (
            recording_contracts.interpreter_fixture(),
            recording_contracts.recording_event_fixture(
                "recording_started",
                ProductionEventType.RECORDING_BLOCK_STARTED,
                recording_block_id,
            ),
        ),
        (
            schedule_contracts.interpreter_fixture(),
            schedule_contracts.schedule_event_fixture(
                "scheduled",
                ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
            ),
        ),
        (
            media_contracts.interpreter_fixture(),
            media_contracts.media_event_fixture(
                "created",
                ProductionEventType.MEDIA_FILE_CREATED,
                recording_block_id,
            ),
        ),
        (
            clock_contracts.interpreter_fixture(),
            clock_contracts.clock_event_fixture(
                "timer_elapsed",
                ProductionEventType.TIMER_ELAPSED,
                recording_block_id,
            ),
        ),
        (
            transcript_contracts.interpreter_fixture(),
            transcript_contracts.transcript_event_fixture(
                "available",
                ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
                recording_block_id,
            ),
        ),
        (
            vision_contracts.interpreter_fixture(),
            vision_contracts.vision_event_fixture(
                "slide_change",
                ProductionEventType.VISUAL_DETECTION_AVAILABLE,
                recording_block_id,
            ),
        ),
    )


@pytest.mark.parametrize(("interpreter", "event"), _supported_pairs())
def test_all_six_concrete_interpreters_dispatch_with_lineage(
    interpreter: CompatibleObservationInterpreter,
    event: ProductionEvent,
) -> None:
    adapter = ObservationInterpreterAdapter(interpreter)
    dispatcher = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Compatibility dispatcher",
        interpreters=(adapter,),
    )

    result = dispatcher.dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.SUCCESS
    assert result.invoked_interpreter_ids == (adapter.id,)
    assert result.interpreter_results[0].source_production_event_id == event.id
    assert result.interpreter_results[0].interpreter_status is InterpreterStatus.ACTIVE
    assert result.observations
    for observation in result.observations:
        assert observation.correlation_id == event.correlation_id
        assert observation.provenance is not None
        assert observation.provenance.source_event_id == event.id
        assert observation.provenance.interpreter_id == adapter.id


def test_context_conversion_maps_all_fields_exactly() -> None:
    context = InterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        metadata={"nested": {"value": 1}},
    )

    converted = observation_interpreter_context_from(context)

    assert converted.correlation_id == context.correlation_id
    assert converted.current_timestamp == context.current_timestamp
    assert converted.recording_block_id == context.recording_block_id
    assert converted.stage_id == context.stage_id
    assert dict(converted.metadata) == dict(context.metadata)


def test_status_mapping_is_exhaustive_and_preserves_stable_strings() -> None:
    assert set(ObservationInterpreterStatus) == set(
        status for status in ObservationInterpreterStatus
    )
    expected = {
        "unknown": "unknown",
        "configured": "configured",
        "ready": "ready",
        "active": "active",
        "degraded": "degraded",
        "failed": "failed",
        "disabled": "disabled",
        "archived": "archived",
    }
    assert {
        source.value: map_observation_interpreter_status(source).value
        for source in ObservationInterpreterStatus
    } == expected
    assert InterpreterStatus.EXPERIMENTAL.value == "experimental"


def test_multiple_matching_adapters_preserve_registration_order() -> None:
    event = recording_contracts.recording_event_fixture(
        "recording_started",
        ProductionEventType.RECORDING_BLOCK_STARTED,
        EntityId.new(),
    )
    adapters = tuple(
        ObservationInterpreterAdapter(recording_contracts.interpreter_fixture())
        for _ in range(2)
    )
    dispatcher = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Fan-out dispatcher",
        interpreters=adapters,
    )

    result = dispatcher.dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.SUCCESS
    assert result.invoked_interpreter_ids == tuple(adapter.id for adapter in adapters)
    assert len(result.observations) == 2
    provenance = tuple(observation.provenance for observation in result.observations)
    assert all(item is not None for item in provenance)
    assert tuple(item.interpreter_id for item in provenance if item is not None) == tuple(
        adapter.id for adapter in adapters
    )


def test_unsupported_event_is_an_explicit_no_match() -> None:
    interpreter, _ = _supported_pairs()[0]
    event = schedule_contracts.schedule_event_fixture(
        "scheduled",
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    )
    dispatcher = ProductionEventDispatcher(
        id=EntityId.new(),
        name="No-match dispatcher",
        interpreters=(ObservationInterpreterAdapter(interpreter),),
    )

    result = dispatcher.dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.NO_MATCH
    assert result.invoked_interpreter_ids == ()
    assert result.declined_interpreter_count == 1


def _recording_result() -> tuple[
    ProductionEvent,
    ObservationInterpreterResult,
    EntityId,
]:
    recording_block_id = EntityId.new()
    event = recording_contracts.recording_event_fixture(
        "recording_started",
        ProductionEventType.RECORDING_BLOCK_STARTED,
        recording_block_id,
    )
    interpreter = recording_contracts.interpreter_fixture()
    result = interpreter.interpret(
        event,
        ObservationInterpreterContext(
            correlation_id=event.correlation_id,
            current_timestamp=event.received_at,
            recording_block_id=recording_block_id,
        ),
    )
    return event, result, interpreter.id


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (ObservationInterpreterStatus.READY, DispatchStatus.SUCCESS),
        (ObservationInterpreterStatus.ACTIVE, DispatchStatus.SUCCESS),
        (ObservationInterpreterStatus.DEGRADED, DispatchStatus.SUCCESS_WITH_WARNINGS),
        (ObservationInterpreterStatus.UNKNOWN, DispatchStatus.TOTAL_FAILURE),
        (ObservationInterpreterStatus.CONFIGURED, DispatchStatus.TOTAL_FAILURE),
        (ObservationInterpreterStatus.FAILED, DispatchStatus.TOTAL_FAILURE),
        (ObservationInterpreterStatus.DISABLED, DispatchStatus.TOTAL_FAILURE),
        (ObservationInterpreterStatus.ARCHIVED, DispatchStatus.TOTAL_FAILURE),
    ),
)
def test_every_concrete_status_has_fail_closed_dispatch_semantics(
    status: ObservationInterpreterStatus,
    expected: DispatchStatus,
) -> None:
    event, concrete_result, interpreter_id = _recording_result()
    adapter = ObservationInterpreterAdapter(
        FixedObservationInterpreter(interpreter_id, status, concrete_result)
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(), name="Status dispatcher", interpreters=(adapter,)
    ).dispatch(event, _dispatch_context())

    assert result.status is expected
    if expected is DispatchStatus.TOTAL_FAILURE:
        assert result.observations == ()
    else:
        assert result.observations == concrete_result.observations


@pytest.mark.parametrize(
    ("mutation", "failure_code"),
    (
        ("event_id", "invalid_observation_source_lineage"),
        ("event_type", "invalid_observation_source_event_type"),
        ("occurred_at", "invalid_observation_source_event_occurred_at"),
        ("interpreter_id", "invalid_observation_interpreter_lineage"),
        ("correlation", "invalid_observation_correlation_lineage"),
        ("context_correlation", "invalid_observation_context_lineage"),
        ("recording_block", "invalid_observation_context_recording_block_id"),
    ),
)
def test_adapter_rejects_each_malformed_first_class_lineage_field_atomically(
    mutation: str,
    failure_code: str,
) -> None:
    event, concrete_result, interpreter_id = _recording_result()
    observation = concrete_result.observations[0]
    assert observation.provenance is not None
    if mutation == "event_id":
        malformed = replace(
            observation,
            provenance=replace(observation.provenance, source_event_id=EntityId.new()),
        )
    elif mutation == "event_type":
        malformed = replace(
            observation,
            provenance=replace(
                observation.provenance,
                source_event_type=ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
            ),
        )
    elif mutation == "occurred_at":
        malformed = replace(
            observation,
            provenance=replace(
                observation.provenance,
                source_event_occurred_at=event.occurred_at + timedelta(seconds=1),
            ),
        )
    elif mutation == "interpreter_id":
        malformed = replace(
            observation,
            provenance=replace(observation.provenance, interpreter_id=EntityId.new()),
        )
    elif mutation == "correlation":
        malformed = replace(observation, correlation_id=CorrelationId.new())
    elif mutation == "context_correlation":
        malformed = replace(
            observation,
            context=replace(observation.context, correlation_id=CorrelationId.new()),
        )
    else:
        malformed = replace(
            observation,
            context=replace(observation.context, recording_block_id=EntityId.new()),
        )
    malformed_result = replace(
        concrete_result,
        observations=(observation, malformed),
    )
    adapter = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            interpreter_id,
            ObservationInterpreterStatus.ACTIVE,
            malformed_result,
        )
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(), name="Lineage dispatcher", interpreters=(adapter,)
    ).dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.TOTAL_FAILURE
    assert result.observations == ()
    assert dict(result.interpreter_results[0].metadata) == {"failure_code": failure_code}


@pytest.mark.parametrize(
    ("mutation", "failure_code"),
    (
        ("result_source", "invalid_source_production_event_lineage"),
        ("result_interpreter", "invalid_interpreter_identity"),
        ("missing_provenance", "invalid_observation_source_lineage"),
    ),
)
def test_adapter_rejects_malformed_result_level_lineage(
    mutation: str,
    failure_code: str,
) -> None:
    event, concrete_result, interpreter_id = _recording_result()
    if mutation == "result_source":
        malformed_result = replace(concrete_result, source_production_event_ids=(EntityId.new(),))
    elif mutation == "result_interpreter":
        malformed_result = replace(concrete_result, interpreter_id=EntityId.new())
    else:
        malformed_result = replace(
            concrete_result,
            observations=(replace(concrete_result.observations[0], provenance=None),),
        )
    adapter = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            interpreter_id,
            ObservationInterpreterStatus.ACTIVE,
            malformed_result,
        )
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(), name="Malformed result dispatcher", interpreters=(adapter,)
    ).dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.TOTAL_FAILURE
    assert result.observations == ()
    assert dict(result.interpreter_results[0].metadata) == {"failure_code": failure_code}


def test_adapter_exception_isolated_and_later_adapter_retains_output() -> None:
    event, concrete_result, interpreter_id = _recording_result()
    failing = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            EntityId.new(), ObservationInterpreterStatus.ACTIVE, concrete_result, raises=True
        )
    )
    succeeding = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            interpreter_id, ObservationInterpreterStatus.ACTIVE, concrete_result
        )
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(), name="Isolation dispatcher", interpreters=(failing, succeeding)
    ).dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.PARTIAL_FAILURE
    assert result.invoked_interpreter_ids == (failing.id, succeeding.id)
    assert result.observations == concrete_result.observations
    assert "sensitive adapter detail" not in " ".join(result.warnings)


@pytest.mark.parametrize(
    ("field_name", "reference_type", "payload_key", "source_value"),
    (
        ("stage_id", ProductionEventReferenceType.STAGE, None, EntityId.new()),
        (
            "scheduled_activity_id",
            ProductionEventReferenceType.SCHEDULE_ARTIFACT,
            None,
            EntityId.new(),
        ),
        (
            "media_artifact_id",
            ProductionEventReferenceType.MEDIA_FILE,
            None,
            "media-source-1",
        ),
        (
            "timeline_reference",
            ProductionEventReferenceType.TIMELINE_RANGE,
            None,
            "timeline-source-1",
        ),
        ("transcript_stream_id", None, "transcript_stream_id", "stream-source-1"),
    ),
)
def test_adapter_validates_each_event_derived_first_class_context_reference(
    field_name: str,
    reference_type: ProductionEventReferenceType | None,
    payload_key: str | None,
    source_value: EntityId | str,
) -> None:
    event, _, _ = _recording_result()
    payload = dict(event.payload.data)
    references = list(event.references)
    if payload_key is not None:
        payload[payload_key] = source_value
    if reference_type is not None:
        references.append(
            ProductionEventReference(
                reference_type=reference_type,
                referenced_id=source_value if isinstance(source_value, EntityId) else None,
                external_reference=source_value if isinstance(source_value, str) else None,
            )
        )
    event = replace(
        event,
        payload=ProductionEventPayload(payload),
        references=tuple(references),
    )
    interpreter = recording_contracts.interpreter_fixture()
    interpreter_id = interpreter.id
    concrete_result = interpreter.interpret(
        event,
        ObservationInterpreterContext(
            correlation_id=event.correlation_id,
            current_timestamp=event.received_at,
        ),
    )
    observation = concrete_result.observations[0]
    malformed_context = replace(
        observation.context,
        **{field_name: EntityId.new() if isinstance(source_value, EntityId) else "wrong"},
    )
    malformed_result = replace(
        concrete_result,
        observations=(replace(observation, context=malformed_context),),
    )
    adapter = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            interpreter_id,
            ObservationInterpreterStatus.ACTIVE,
            malformed_result,
        )
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(), name="Reference dispatcher", interpreters=(adapter,)
    ).dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.TOTAL_FAILURE
    assert dict(result.interpreter_results[0].metadata) == {
        "failure_code": f"invalid_observation_context_{field_name}"
    }


def test_adapter_validates_event_derived_source_producer_identifier() -> None:
    event, _, _ = _recording_result()
    event = replace(
        event,
        payload=ProductionEventPayload(
            {**dict(event.payload.data), "producer_identifier": "recording-source-1"}
        ),
    )
    interpreter = recording_contracts.interpreter_fixture()
    interpreter_id = interpreter.id
    concrete_result = interpreter.interpret(
        event,
        ObservationInterpreterContext(
            correlation_id=event.correlation_id,
            current_timestamp=event.received_at,
        ),
    )
    observation = concrete_result.observations[0]
    assert observation.provenance is not None
    malformed_result = replace(
        concrete_result,
        observations=(
            replace(
                observation,
                provenance=replace(
                    observation.provenance,
                    producer_identifier="another-source",
                ),
            ),
        ),
    )
    adapter = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            interpreter_id,
            ObservationInterpreterStatus.ACTIVE,
            malformed_result,
        )
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(), name="Producer dispatcher", interpreters=(adapter,)
    ).dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.TOTAL_FAILURE
    assert dict(result.interpreter_results[0].metadata) == {
        "failure_code": "invalid_observation_source_producer_identifier"
    }


@pytest.mark.parametrize(
    ("payload_key", "malformed_value", "lineage_field"),
    (
        ("stage_id", "not-an-entity-id", "stage_id"),
        ("recording_block_id", "not-an-entity-id", "recording_block_id"),
        ("scheduled_activity_id", "not-an-entity-id", "scheduled_activity_id"),
        ("transcript_stream_id", 17, "transcript_stream_id"),
        ("media_artifact_id", 17, "media_artifact_id"),
        ("timeline_range_reference", 17, "timeline_reference"),
        ("producer_identifier", 17, "producer_identifier"),
    ),
)
def test_malformed_structured_event_lineage_is_not_treated_as_absent(
    payload_key: str,
    malformed_value: str | int,
    lineage_field: str,
) -> None:
    event, _, _ = _recording_result()
    event = replace(
        event,
        payload=ProductionEventPayload(
            {**dict(event.payload.data), payload_key: malformed_value}
        ),
    )
    adapters = tuple(
        ObservationInterpreterAdapter(recording_contracts.interpreter_fixture())
        for _ in range(2)
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(), name="Malformed lineage dispatcher", interpreters=adapters
    ).dispatch(event, _dispatch_context())

    extraction = event_observation_lineage_from_event(event)
    assert getattr(extraction, lineage_field).state is LineageExtractionState.MALFORMED
    assert result.status is DispatchStatus.TOTAL_FAILURE
    assert result.invoked_interpreter_ids == tuple(adapter.id for adapter in adapters)
    assert result.observations == ()
    assert all(
        dict(interpreter_result.metadata)
        == {"failure_code": f"malformed_event_lineage:{lineage_field}"}
        for interpreter_result in result.interpreter_results
    )


@pytest.mark.parametrize(
    ("field_name", "reference_type"),
    (
        ("stage_id", ProductionEventReferenceType.STAGE),
        ("recording_block_id", ProductionEventReferenceType.RECORDING_BLOCK),
    ),
)
def test_context_fallback_is_permitted_only_for_genuinely_absent_event_lineage(
    field_name: str,
    reference_type: ProductionEventReferenceType,
) -> None:
    context = _dispatch_context()
    fallback_value = getattr(context, field_name)
    assert fallback_value is not None
    event = recording_contracts.recording_event_fixture(
        "recording_started",
        ProductionEventType.RECORDING_BLOCK_STARTED,
        None if field_name == "recording_block_id" else EntityId.new(),
    )
    interpreter = recording_contracts.interpreter_fixture()

    absent_result = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Absent lineage dispatcher",
        interpreters=(ObservationInterpreterAdapter(interpreter),),
    ).dispatch(event, context)

    assert absent_result.status is DispatchStatus.SUCCESS
    assert getattr(absent_result.observations[0].context, field_name) == fallback_value

    malformed_event = replace(
        event,
        payload=ProductionEventPayload(
            {**dict(event.payload.data), field_name: "not-an-entity-id"}
        ),
    )
    malformed_result = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Malformed fallback dispatcher",
        interpreters=(ObservationInterpreterAdapter(interpreter),),
    ).dispatch(malformed_event, context)

    assert malformed_result.status is DispatchStatus.TOTAL_FAILURE
    assert malformed_result.observations == ()
    assert dict(malformed_result.interpreter_results[0].metadata) == {
        "failure_code": f"malformed_event_lineage:{field_name}"
    }

    first = EntityId.new()
    second = EntityId.new()
    conflicting_references = tuple(
        reference
        for reference in event.references
        if reference.reference_type is not reference_type
    ) + (
        ProductionEventReference(reference_type=reference_type, referenced_id=first),
    )
    contradictory_event = replace(
        event,
        references=conflicting_references,
        payload=ProductionEventPayload(
            {**dict(event.payload.data), field_name: second.to_json()}
        ),
    )
    contradictory_result = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Contradictory fallback dispatcher",
        interpreters=(ObservationInterpreterAdapter(interpreter),),
    ).dispatch(contradictory_event, context)

    assert contradictory_result.status is DispatchStatus.TOTAL_FAILURE
    assert contradictory_result.observations == ()
    assert dict(contradictory_result.interpreter_results[0].metadata) == {
        "failure_code": f"contradictory_event_lineage:{field_name}"
    }


@pytest.mark.parametrize(
    ("reference_order", "expected_state"),
    (
        ("equivalent", LineageExtractionState.VALID),
        ("conflicting", LineageExtractionState.CONTRADICTORY),
        ("malformed_then_valid", LineageExtractionState.MALFORMED),
        ("valid_then_malformed", LineageExtractionState.MALFORMED),
    ),
)
def test_duplicate_stage_references_are_resolved_without_order_precedence(
    reference_order: str,
    expected_state: LineageExtractionState,
) -> None:
    event, _, _ = _recording_result()
    first_id = EntityId.new()
    second_id = first_id if reference_order == "equivalent" else EntityId.new()
    valid_first = ProductionEventReference(
        reference_type=ProductionEventReferenceType.STAGE,
        referenced_id=first_id,
    )
    valid_second = ProductionEventReference(
        reference_type=ProductionEventReferenceType.STAGE,
        referenced_id=second_id,
    )
    malformed = ProductionEventReference(
        reference_type=ProductionEventReferenceType.STAGE,
        external_reference="not-an-entity-id",
    )
    if reference_order == "malformed_then_valid":
        stage_references = (malformed, valid_first)
    elif reference_order == "valid_then_malformed":
        stage_references = (valid_first, malformed)
    else:
        stage_references = (valid_first, valid_second)
    event = replace(event, references=tuple(event.references) + stage_references)

    extraction = event_observation_lineage_from_event(event).stage_id
    result = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Duplicate reference dispatcher",
        interpreters=(
            ObservationInterpreterAdapter(recording_contracts.interpreter_fixture()),
        ),
    ).dispatch(event, _dispatch_context())

    assert extraction.state is expected_state
    if expected_state is LineageExtractionState.VALID:
        assert extraction.value == first_id
        assert result.status is DispatchStatus.SUCCESS
    else:
        assert result.status is DispatchStatus.TOTAL_FAILURE
        assert result.observations == ()


def test_conflicting_structured_and_reference_producer_identifiers_fail_closed() -> None:
    event, _, _ = _recording_result()
    event = replace(
        event,
        payload=ProductionEventPayload(
            {**dict(event.payload.data), "producer_identifier": "producer-a"}
        ),
        references=tuple(event.references)
        + (
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.SYSTEM,
                external_reference="producer-b",
            ),
        ),
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Producer conflict dispatcher",
        interpreters=(
            ObservationInterpreterAdapter(recording_contracts.interpreter_fixture()),
        ),
    ).dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.TOTAL_FAILURE
    assert result.observations == ()
    assert dict(result.interpreter_results[0].metadata) == {
        "failure_code": "contradictory_event_lineage:producer_identifier"
    }


def test_malformed_adapter_result_is_atomic_and_later_adapter_output_survives() -> None:
    event, concrete_result, interpreter_id = _recording_result()
    observation = concrete_result.observations[0]
    assert observation.provenance is not None
    malformed_result = replace(
        concrete_result,
        observations=(
            observation,
            replace(
                observation,
                provenance=replace(
                    observation.provenance,
                    source_event_id=EntityId.new(),
                ),
            ),
        ),
    )
    failing = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            interpreter_id, ObservationInterpreterStatus.ACTIVE, malformed_result
        )
    )
    succeeding = ObservationInterpreterAdapter(
        FixedObservationInterpreter(
            interpreter_id, ObservationInterpreterStatus.ACTIVE, concrete_result
        )
    )

    result = ProductionEventDispatcher(
        id=EntityId.new(),
        name="Atomic continuation dispatcher",
        interpreters=(failing, succeeding),
    ).dispatch(event, _dispatch_context())

    assert result.status is DispatchStatus.PARTIAL_FAILURE
    assert result.invoked_interpreter_ids == (failing.id, succeeding.id)
    assert result.interpreter_results[0].observations == ()
    assert result.observations == concrete_result.observations
