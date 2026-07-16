from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.contexts.production.observation import ObservationContext, ObservationProvenance
from app.contexts.production.observation_interpreter.observation_interpreter_context import (
    ObservationInterpreterContext,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventReferenceType,
)
from app.shared.ids import EntityId


def _entity_id(value: object) -> EntityId | None:
    if isinstance(value, EntityId):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return EntityId.parse(value)
        except ValueError:
            return None
    return None


def _string(value: object) -> str | None:
    if isinstance(value, EntityId):
        return value.to_json()
    if isinstance(value, str) and value.strip():
        return value
    return None


def _reference_entity_id(
    event: ProductionEvent,
    reference_type: ProductionEventReferenceType,
) -> EntityId | None:
    for reference in event.references:
        if reference.reference_type is reference_type:
            return reference.referenced_id
    return None


def _reference_string(
    event: ProductionEvent,
    reference_type: ProductionEventReferenceType,
) -> str | None:
    for reference in event.references:
        if reference.reference_type is not reference_type:
            continue
        if reference.referenced_id is not None:
            return reference.referenced_id.to_json()
        if reference.external_reference is not None:
            return reference.external_reference
    return None


def _entity_from_structured_sources(
    event: ProductionEvent,
    keys: tuple[str, ...],
) -> tuple[EntityId | None, str | None]:
    for key in keys:
        value = _entity_id(event.payload.get(key))
        if value is not None:
            return value, f"event_payload.{key}"
    for key in keys:
        value = _entity_id(event.metadata.get(key))
        if value is not None:
            return value, f"event_metadata.{key}"
    return None, None


def _string_from_structured_sources(
    event: ProductionEvent,
    keys: tuple[str, ...],
) -> tuple[str | None, str | None]:
    for key in keys:
        value = _string(event.payload.get(key))
        if value is not None:
            return value, f"event_payload.{key}"
    for key in keys:
        value = _string(event.metadata.get(key))
        if value is not None:
            return value, f"event_metadata.{key}"
    return None, None


def observation_context_from_event(
    event: ProductionEvent,
    interpreter_context: ObservationInterpreterContext,
) -> ObservationContext:
    """Extract known Event context with one deterministic compatibility fallback path."""

    field_sources: dict[str, str] = {"correlation_id": "event.correlation_id"}

    stage_id = _reference_entity_id(event, ProductionEventReferenceType.STAGE)
    if stage_id is not None:
        field_sources["stage_id"] = "event.references.stage"
    else:
        stage_id, source = _entity_from_structured_sources(event, ("stage_id",))
        if stage_id is None:
            stage_id = interpreter_context.stage_id
            source = "interpreter_context.stage_id" if stage_id is not None else None
        if source is not None:
            field_sources["stage_id"] = source

    recording_block_id = _reference_entity_id(
        event,
        ProductionEventReferenceType.RECORDING_BLOCK,
    )
    if recording_block_id is not None:
        field_sources["recording_block_id"] = "event.references.recording_block"
    else:
        recording_block_id, source = _entity_from_structured_sources(
            event,
            ("recording_block_id",),
        )
        if recording_block_id is None:
            recording_block_id = interpreter_context.recording_block_id
            source = (
                "interpreter_context.recording_block_id"
                if recording_block_id is not None
                else None
            )
        if source is not None:
            field_sources["recording_block_id"] = source

    scheduled_activity_id = _reference_entity_id(
        event,
        ProductionEventReferenceType.SCHEDULE_ARTIFACT,
    )
    if scheduled_activity_id is not None:
        field_sources["scheduled_activity_id"] = "event.references.schedule_artifact"
    else:
        scheduled_activity_id, source = _entity_from_structured_sources(
            event,
            ("scheduled_activity_id",),
        )
        if source is not None:
            field_sources["scheduled_activity_id"] = source

    transcript_stream_id, source = _string_from_structured_sources(
        event,
        ("transcript_stream_id", "stream_id", "transcript_source_id"),
    )
    if source is not None:
        field_sources["transcript_stream_id"] = source

    media_artifact_id = _reference_string(
        event,
        ProductionEventReferenceType.MEDIA_FILE,
    )
    if media_artifact_id is not None:
        field_sources["media_artifact_id"] = "event.references.media_file"
    else:
        media_artifact_id, source = _string_from_structured_sources(
            event,
            ("media_artifact_id", "artifact_id"),
        )
        if source is not None:
            field_sources["media_artifact_id"] = source

    timeline_reference = _reference_string(
        event,
        ProductionEventReferenceType.TIMELINE_RANGE,
    ) or _reference_string(event, ProductionEventReferenceType.TIMELINE_POSITION)
    if timeline_reference is not None:
        field_sources["timeline_reference"] = "event.references.timeline"
    else:
        timeline_reference, source = _string_from_structured_sources(
            event,
            ("timeline_range_reference", "timeline_position_reference"),
        )
        if source is not None:
            field_sources["timeline_reference"] = source

    return ObservationContext(
        stage_id=stage_id,
        recording_block_id=recording_block_id,
        correlation_id=event.correlation_id,
        scheduled_activity_id=scheduled_activity_id,
        transcript_stream_id=transcript_stream_id,
        media_artifact_id=media_artifact_id,
        timeline_reference=timeline_reference,
        metadata={f"{name}_source": value for name, value in field_sources.items()},
    )


def observation_provenance_from_event(
    event: ProductionEvent,
    *,
    interpreter_id: EntityId,
    interpreter_kind: str,
    interpretation_rule_id: EntityId | str | None,
) -> ObservationProvenance:
    """Build exact one-Event provenance without embedding the Event."""

    producer_identifier, producer_source = _string_from_structured_sources(
        event,
        (
            "producer_identifier",
            "adapter_id",
            "recording_system_id",
            "transcript_source_id",
            "clock_id",
        ),
    )
    metadata: Mapping[str, Any] = {
        "source_event_received_at": event.received_at.isoformat(),
        "producer_identifier_source": producer_source,
    }
    return ObservationProvenance(
        source_event_id=event.id,
        source_event_type=event.event_type,
        source_event_occurred_at=event.occurred_at,
        interpreter_kind=interpreter_kind,
        interpreter_id=interpreter_id,
        interpretation_rule_id=interpretation_rule_id,
        producer_identifier=producer_identifier,
        metadata=metadata,
    )
