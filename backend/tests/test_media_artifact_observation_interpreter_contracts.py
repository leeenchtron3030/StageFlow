from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.media_artifact_observation_interpreter import (
    MEDIA_ARTIFACT_OBSERVATION_MAPPINGS,
    MediaArtifactInterpreterRule,
    MediaArtifactInterpreterSummary,
    MediaArtifactObservationInterpreter,
    MediaArtifactObservationMapping,
    mapping_for_media_artifact,
)
from app.contexts.production.observation import ObservationLocationKind, ObservationType
from app.contexts.production.observation_interpreter import (
    ObservationInterpreterContext,
    ObservationInterpreterStatus,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventReference,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    MediaArtifactObservationInterpreter,
    MediaArtifactInterpreterRule,
    MediaArtifactInterpreterSummary,
    MediaArtifactObservationMapping,
)


def _context(recording_block_id: EntityId | None = None) -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 8, 10, 0, 2, tzinfo=UTC),
        recording_block_id=recording_block_id,
        stage_id=EntityId.new(),
        metadata={"mode": "media-artifact-contract"},
    )


def _media_event(
    artifact_status: str,
    event_type: ProductionEventType,
    recording_block_id: EntityId | None = None,
    source: ProductionEventSource = ProductionEventSource.INTERNAL_SYSTEM,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    references = [
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.MEDIA_FILE,
            external_reference="artifact-123",
            label="media artifact",
        )
    ]
    if recording_block_id is not None:
        references.append(
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
                referenced_id=recording_block_id,
                label="recording block",
            )
        )

    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload(
            {
                "artifact_id": "artifact-123",
                "artifact_type": "video",
                "artifact_status": artifact_status,
            }
        ),
        references=references,
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=1),
    )


def _interpreter(
    rules: list[MediaArtifactInterpreterRule] | None = None,
) -> MediaArtifactObservationInterpreter:
    return MediaArtifactObservationInterpreter(
        id=EntityId.new(),
        rules=rules or [],
        metadata={"scope": "media-artifact"},
    )


media_event_fixture = _media_event
interpreter_fixture = _interpreter


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for name, value in getmembers(MediaArtifactObservationInterpreter)
        if isfunction(value)
    }


def _assert_single_observation(
    event: ProductionEvent,
    recording_block_id: EntityId,
    expected_note: str,
) -> None:
    result = _interpreter().interpret(event, _context(recording_block_id))

    assert result.source_production_event_ids == (event.id,)
    assert len(result.observations) == 1

    observation = result.observations[0]
    assert observation.recording_block_id == recording_block_id
    assert observation.observation_type is ObservationType.MEDIA_ARTIFACT
    assert observation.notes == expected_note
    assert observation.location.kind is ObservationLocationKind.RECORDING_BLOCK
    assert observation.location.is_recording_block
    assert not observation.location.is_point
    assert observation.location.point is None
    assert observation.correlation_id == event.correlation_id
    assert dict(observation.metadata)["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert dict(observation.metadata)["observation_interpreter_id"] == (
        result.interpreter_id.to_json()
    )
    assert dict(observation.metadata)["artifact_id"] == "artifact-123"


def test_media_artifact_observation_interpreter_creation() -> None:
    rule = MediaArtifactInterpreterRule(
        id=EntityId.new(),
        description="Translate media artifact events into objective observations.",
    )
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Media artifact observation interpreter"
    assert interpreter.status is ObservationInterpreterStatus.ACTIVE
    assert interpreter.supported_event_sources == (ProductionEventSource.INTERNAL_SYSTEM,)
    assert interpreter.intended_observation_types == (ObservationType.MEDIA_ARTIFACT,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "media-artifact"}


def test_supported_production_event_types_are_media_artifact_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supported_event_types == (
        ProductionEventType.MEDIA_FILE_CREATED,
        ProductionEventType.MEDIA_FILE_FINALIZED,
        ProductionEventType.MEDIA_FILE_FAILED,
    )
    assert interpreter.supports_event_type(ProductionEventType.MEDIA_FILE_CREATED)
    assert not interpreter.supports_event_type(ProductionEventType.RECORDING_BLOCK_STARTED)


def test_supported_production_event_sources_are_media_adapter_source_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.INTERNAL_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.RECORDING_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.SCHEDULE_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.TRANSCRIPT_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.VISION_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.OPERATOR)
    assert not interpreter.supports_source(ProductionEventSource.FILESYSTEM)


def test_media_file_created_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _media_event(
        "created",
        ProductionEventType.MEDIA_FILE_CREATED,
        recording_block_id,
    )

    _assert_single_observation(event, recording_block_id, "Media artifact was created.")


def test_media_file_finalized_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _media_event(
        "finalized",
        ProductionEventType.MEDIA_FILE_FINALIZED,
        recording_block_id,
    )

    _assert_single_observation(event, recording_block_id, "Media artifact was finalized.")


def test_media_file_failed_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _media_event(
        "failed",
        ProductionEventType.MEDIA_FILE_FAILED,
        recording_block_id,
    )

    _assert_single_observation(event, recording_block_id, "Media artifact failed.")


def test_unknown_event_handling_returns_zero_observations() -> None:
    recording_block_id = EntityId.new()
    event = _media_event(
        "deleted",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        recording_block_id,
    )

    result = _interpreter().interpret(event, _context(recording_block_id))

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_wrong_source_returns_zero_observations() -> None:
    event = _media_event(
        "created",
        ProductionEventType.MEDIA_FILE_CREATED,
        source=ProductionEventSource.FILESYSTEM,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_missing_recording_block_uses_wall_clock_location() -> None:
    event = _media_event(
        "created",
        ProductionEventType.MEDIA_FILE_CREATED,
    )

    result = _interpreter().interpret(event, _context())

    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.recording_block_id is None
    assert observation.location.kind is ObservationLocationKind.WALL_CLOCK
    assert observation.location.wall_clock_at == event.occurred_at
    assert not observation.location.is_point


def test_context_recording_block_can_supply_location_when_event_lacks_reference() -> None:
    recording_block_id = EntityId.new()
    event = _media_event(
        "created",
        ProductionEventType.MEDIA_FILE_CREATED,
    )

    _assert_single_observation(event, recording_block_id, "Media artifact was created.")


def test_interpreter_can_return_multiple_observations_for_multiple_events() -> None:
    recording_block_id = EntityId.new()
    created = _media_event(
        "created",
        ProductionEventType.MEDIA_FILE_CREATED,
        recording_block_id,
    )
    finalized = _media_event(
        "finalized",
        ProductionEventType.MEDIA_FILE_FINALIZED,
        recording_block_id,
    )

    result = _interpreter().interpret([created, finalized], _context(recording_block_id))

    assert len(result.observations) == 2
    assert result.source_production_event_ids == (created.id, finalized.id)
    for observation in result.observations:
        assert dict(observation.metadata)["source_production_event_ids"] == (
            created.id.to_json(),
            finalized.id.to_json(),
        )
        assert observation.location.kind is ObservationLocationKind.RECORDING_BLOCK


def test_mapping_contract_documents_supported_translations() -> None:
    event_types = {
        mapping.production_event_type for mapping in MEDIA_ARTIFACT_OBSERVATION_MAPPINGS
    }
    created_mapping = mapping_for_media_artifact(
        ProductionEventType.MEDIA_FILE_CREATED,
    )

    assert event_types == {
        ProductionEventType.MEDIA_FILE_CREATED,
        ProductionEventType.MEDIA_FILE_FINALIZED,
        ProductionEventType.MEDIA_FILE_FAILED,
    }
    assert created_mapping is not None
    assert created_mapping.observation_note == "Media artifact was created."


def test_media_artifact_rule_creation() -> None:
    rule = MediaArtifactInterpreterRule(
        id=EntityId.new(),
        description="Media artifact lifecycle only.",
        metadata={"scope": "artifact"},
    )
    base_rule = rule.to_observation_interpreter_rule()

    assert rule.supported_event_sources == (ProductionEventSource.INTERNAL_SYSTEM,)
    assert rule.intended_observation_types == (ObservationType.MEDIA_ARTIFACT,)
    assert base_rule.supported_event_types == rule.supported_event_types
    assert dict(base_rule.metadata) == {"scope": "artifact"}


def test_media_artifact_summary_generation() -> None:
    rule = MediaArtifactInterpreterRule(id=EntityId.new())
    interpreter = _interpreter(rules=[rule])

    summary = MediaArtifactInterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.interpreter_name == interpreter.name
    assert summary.status is ObservationInterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 3
    assert summary.supported_source_count == 1
    assert summary.intended_observation_type_count == 1
    assert summary.mapping_count == 3
    assert summary.rule_count == 1


def test_observation_wording_stays_objective() -> None:
    objective_notes = {
        mapping.observation_note for mapping in MEDIA_ARTIFACT_OBSERVATION_MAPPINGS
    }
    forbidden_terms = {
        "valid",
        "codec",
        "chunk",
        "complete",
        "transcript",
        "session",
        "clip",
        "package",
        "ready",
    }

    assert objective_notes == {
        "Media artifact was created.",
        "Media artifact was finalized.",
        "Media artifact failed.",
    }
    assert not any(term in note.lower() for term in forbidden_terms for note in objective_notes)


def test_no_fake_zero_offset_locations_are_created() -> None:
    recording_block_id = EntityId.new()
    event = _media_event(
        "created",
        ProductionEventType.MEDIA_FILE_CREATED,
        recording_block_id,
    )

    result = _interpreter().interpret(event, _context(recording_block_id))

    assert result.observations[0].location.kind is ObservationLocationKind.RECORDING_BLOCK
    assert result.observations[0].location.point is None


def test_no_media_validation_chunk_registration_file_inspection_or_reasoning_exists() -> None:
    forbidden_terms = {
        "validate",
        "codec",
        "register",
        "chunk",
        "inspect",
        "evidence",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "conclusion",
        "reasoning",
        "decision",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_cross_domain_interpretation_exists() -> None:
    forbidden_terms = {
        "recording_activity",
        "transcript",
        "schedule",
        "vision",
        "operator",
        "ocr",
        "speaker",
        "session",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_behavior_exists() -> None:
    lifecycle_values = {
        mapping.artifact_lifecycle for mapping in MEDIA_ARTIFACT_OBSERVATION_MAPPINGS
    }
    forbidden_terms = {
        "pretalx",
        "whisper",
        "deepgram",
        "assemblyai",
        "opencv",
        "vmix",
        "youtube",
        "provider",
        "vendor",
        "brand",
    }

    assert not any(term in value for term in forbidden_terms for value in lifecycle_values)
    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )
