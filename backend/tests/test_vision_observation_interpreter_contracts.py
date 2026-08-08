from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.observation import (
    ObservationLocationKind,
    ObservationSource,
    ObservationType,
)
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
from app.contexts.production.vision_observation_interpreter import (
    VISION_OBSERVATION_MAPPINGS,
    VisionInterpreterRule,
    VisionInterpreterSummary,
    VisionObservationInterpreter,
    VisionObservationMapping,
    mapping_for_vision,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    VisionObservationInterpreter,
    VisionInterpreterRule,
    VisionInterpreterSummary,
    VisionObservationMapping,
)


def _context(recording_block_id: EntityId | None = None) -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 9, 10, 0, 2, tzinfo=UTC),
        recording_block_id=recording_block_id,
        stage_id=EntityId.new(),
        metadata={"mode": "vision-contract"},
    )


def _vision_event(
    detection_type: str,
    event_type: ProductionEventType,
    recording_block_id: EntityId | None = None,
    source: ProductionEventSource = ProductionEventSource.VISION_SYSTEM,
    vision_adapter_event: bool = True,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 9, 10, 0, tzinfo=UTC)
    references = [
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
            external_reference="detection-123",
            label="visual detection",
        ),
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.TIMELINE_RANGE,
            external_reference="range-123",
            label="timeline range",
        ),
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
                "visual_detection_id": "detection-123",
                "visual_detection_type": detection_type,
                "visual_detection_status": "created",
                "timeline_range_reference": "range-123",
                "confidence": 0.76,
                "region_reference": "region-42",
            }
        ),
        references=references,
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=1),
        metadata={"vision_adapter_event": vision_adapter_event},
    )


def _interpreter(
    rules: list[VisionInterpreterRule] | None = None,
) -> VisionObservationInterpreter:
    return VisionObservationInterpreter(
        id=EntityId.new(),
        rules=rules or [],
        metadata={"scope": "vision"},
    )


vision_event_fixture = _vision_event
interpreter_fixture = _interpreter


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for name, value in getmembers(VisionObservationInterpreter)
        if isfunction(value)
    }


def _assert_single_observation(
    event: ProductionEvent,
    expected_note: str,
    recording_block_id: EntityId | None = None,
) -> None:
    result = _interpreter().interpret(event, _context(recording_block_id))

    assert result.source_production_event_ids == (event.id,)
    assert len(result.observations) == 1

    observation = result.observations[0]
    assert observation.observation_type is ObservationType.VISION_ACTIVITY
    assert observation.observation_source is ObservationSource.VISION
    assert observation.notes == expected_note
    assert observation.correlation_id == event.correlation_id
    assert dict(observation.metadata)["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert dict(observation.metadata)["observation_interpreter_id"] == (
        result.interpreter_id.to_json()
    )


def test_vision_observation_interpreter_creation() -> None:
    rule = VisionInterpreterRule(
        id=EntityId.new(),
        description="Translate vision events into objective observations.",
    )
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Vision observation interpreter"
    assert interpreter.status is ObservationInterpreterStatus.ACTIVE
    assert interpreter.supported_event_sources == (ProductionEventSource.VISION_SYSTEM,)
    assert interpreter.intended_observation_types == (ObservationType.VISION_ACTIVITY,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "vision"}


def test_supported_production_event_types_are_vision_related_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supported_event_types == (
        ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        ProductionEventType.SYSTEM_STATUS_CHANGED,
    )
    assert interpreter.supports_event_type(ProductionEventType.VISUAL_DETECTION_AVAILABLE)
    assert not interpreter.supports_event_type(ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE)


def test_supported_production_event_sources_are_vision_system_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.VISION_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.TRANSCRIPT_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.SCHEDULE_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.RECORDING_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.OPERATOR)
    assert not interpreter.supports_source(ProductionEventSource.INTERNAL_SYSTEM)


def test_text_region_mapping_creates_objective_observation() -> None:
    event = _vision_event("text_region", ProductionEventType.VISUAL_DETECTION_AVAILABLE)

    _assert_single_observation(event, "Visual text region was detected.")


def test_slide_change_mapping_creates_objective_observation() -> None:
    event = _vision_event("slide_change", ProductionEventType.VISUAL_DETECTION_AVAILABLE)

    _assert_single_observation(event, "Visual slide change was detected.")


def test_image_change_mapping_creates_objective_observation() -> None:
    event = _vision_event("image_change", ProductionEventType.VISUAL_DETECTION_AVAILABLE)

    _assert_single_observation(event, "Visual image change was detected.")


def test_camera_obstruction_mapping_creates_objective_observation() -> None:
    event = _vision_event(
        "camera_obstruction",
        ProductionEventType.VISUAL_DETECTION_AVAILABLE,
    )

    _assert_single_observation(event, "Visual camera obstruction was detected.")


def test_unknown_detection_type_uses_generic_visual_observation() -> None:
    event = _vision_event("unknown", ProductionEventType.VISUAL_DETECTION_AVAILABLE)

    _assert_single_observation(event, "Visual phenomenon was detected.")


def test_vision_related_system_status_changed_mapping_creates_observation() -> None:
    event = _vision_event(
        "unknown",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        vision_adapter_event=True,
    )

    _assert_single_observation(event, "Vision source status changed.")


def test_non_vision_system_status_changed_is_ignored_when_distinguishable() -> None:
    event = _vision_event(
        "unknown",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        vision_adapter_event=False,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()


def test_unknown_event_handling_returns_zero_observations() -> None:
    event = _vision_event("text_region", ProductionEventType.UNKNOWN)

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_wrong_source_returns_zero_observations() -> None:
    event = _vision_event(
        "text_region",
        ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        source=ProductionEventSource.TRANSCRIPT_SYSTEM,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_recording_block_location_is_used_when_available() -> None:
    recording_block_id = EntityId.new()
    event = _vision_event(
        "text_region",
        ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        recording_block_id,
    )

    result = _interpreter().interpret(event, _context())
    observation = result.observations[0]

    assert observation.recording_block_id == recording_block_id
    assert observation.location.kind is ObservationLocationKind.RECORDING_BLOCK
    assert observation.location.recording_block_id == recording_block_id
    assert observation.location.point is None


def test_wall_clock_location_is_used_without_recording_block() -> None:
    event = _vision_event("text_region", ProductionEventType.VISUAL_DETECTION_AVAILABLE)

    result = _interpreter().interpret(event, _context())
    observation = result.observations[0]

    assert observation.recording_block_id is None
    assert observation.location.kind is ObservationLocationKind.WALL_CLOCK
    assert observation.location.wall_clock_at == event.occurred_at
    assert observation.location.point is None
    assert observation.location.range is None


def test_visual_metadata_is_preserved_as_observed_data() -> None:
    event = _vision_event("text_region", ProductionEventType.VISUAL_DETECTION_AVAILABLE)

    result = _interpreter().interpret(event, _context())
    metadata = dict(result.observations[0].metadata)

    assert metadata["vision_is_not_meaning"] is True
    assert metadata["visual_detection_id"] == "detection-123"
    assert metadata["visual_detection_type"] == "text_region"
    assert metadata["visual_detection_status"] == "created"
    assert metadata["timeline_range_reference"] == "range-123"
    assert metadata["confidence"] == 0.76
    assert metadata["region_reference"] == "region-42"


def test_interpreter_can_return_multiple_observations_for_multiple_events() -> None:
    first = _vision_event("text_region", ProductionEventType.VISUAL_DETECTION_AVAILABLE)
    second = _vision_event("slide_change", ProductionEventType.VISUAL_DETECTION_AVAILABLE)

    result = _interpreter().interpret([first, second], _context())

    assert len(result.observations) == 2
    assert result.source_production_event_ids == (first.id, second.id)
    for observation in result.observations:
        assert dict(observation.metadata)["source_production_event_ids"] == (
            first.id.to_json(),
            second.id.to_json(),
        )


def test_mapping_contract_documents_supported_translations() -> None:
    text_region_mapping = mapping_for_vision(
        ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        visual_detection_type="text_region",
    )
    status_mapping = mapping_for_vision(ProductionEventType.SYSTEM_STATUS_CHANGED)

    assert text_region_mapping is not None
    assert text_region_mapping.observation_note == "Visual text region was detected."
    assert status_mapping is not None
    assert status_mapping.requires_vision_metadata


def test_vision_rule_creation() -> None:
    rule = VisionInterpreterRule(
        id=EntityId.new(),
        description="Vision source events only.",
        metadata={"scope": "visual-phenomena"},
    )
    base_rule = rule.to_observation_interpreter_rule()

    assert rule.supported_event_sources == (ProductionEventSource.VISION_SYSTEM,)
    assert rule.intended_observation_types == (ObservationType.VISION_ACTIVITY,)
    assert base_rule.supported_event_types == rule.supported_event_types
    assert dict(base_rule.metadata) == {"scope": "visual-phenomena"}


def test_vision_summary_generation() -> None:
    rule = VisionInterpreterRule(id=EntityId.new())
    interpreter = _interpreter(rules=[rule])

    summary = VisionInterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.interpreter_name == interpreter.name
    assert summary.status is ObservationInterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 2
    assert summary.supported_source_count == 1
    assert summary.intended_observation_type_count == 1
    assert summary.mapping_count == 6
    assert summary.rule_count == 1


def test_observation_wording_stays_about_visual_phenomena() -> None:
    objective_notes = {mapping.observation_note for mapping in VISION_OBSERVATION_MAPPINGS}
    forbidden_terms = {
        "session title",
        "keynote slide",
        "speaker identity",
        "logo identity",
        "person identity",
        "clip-worthy",
        "production state",
    }

    assert {
        "Visual text region was detected.",
        "Visual slide change was detected.",
        "Visual image change was detected.",
        "Visual camera obstruction was detected.",
        "Visual phenomenon was detected.",
        "Vision source status changed.",
    }.issubset(objective_notes)
    assert not any(term in note.lower() for term in forbidden_terms for note in objective_notes)


def test_no_ocr_identity_session_clip_or_reasoning_exists() -> None:
    forbidden_terms = {
        "ocr",
        "interpret_detected_text",
        "logo",
        "face",
        "person",
        "scene",
        "session",
        "clip",
        "production_state",
        "evidence",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "reasoning",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_cross_domain_interpretation_exists() -> None:
    forbidden_terms = {
        "recording_activity",
        "media_artifact",
        "schedule",
        "transcript",
        "operator",
        "runtime_clock",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_behavior_exists() -> None:
    lifecycle_values = {mapping.vision_lifecycle for mapping in VISION_OBSERVATION_MAPPINGS}
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
