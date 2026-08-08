from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
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


class LineageExtractionState(StrEnum):
    """Semantic state of one authoritative Event-derived lineage value."""

    ABSENT = "absent"
    VALID = "valid"
    MALFORMED = "malformed"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class LineageExtraction[LineageValue: (EntityId, str)]:
    """A lineage value whose absence cannot conceal invalid authoritative input."""

    state: LineageExtractionState
    value: LineageValue | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class EventObservationLineage:
    """Central extraction result for every Event-derived Observation lineage field."""

    stage_id: LineageExtraction[EntityId]
    recording_block_id: LineageExtraction[EntityId]
    scheduled_activity_id: LineageExtraction[EntityId]
    transcript_stream_id: LineageExtraction[str]
    media_artifact_id: LineageExtraction[str]
    timeline_reference: LineageExtraction[str]
    producer_identifier: LineageExtraction[str]

    @property
    def failure_code(self) -> str | None:
        for field_name, state in self._field_states():
            if state is LineageExtractionState.MALFORMED:
                return f"malformed_event_lineage:{field_name}"
            if state is LineageExtractionState.CONTRADICTORY:
                return f"contradictory_event_lineage:{field_name}"
        return None

    def require_valid(self) -> None:
        """Reject malformed or contradictory input without treating absence as failure."""

        failure_code = self.failure_code
        if failure_code is not None:
            raise ValueError(f"Invalid Event-derived Observation lineage: {failure_code}.")

    def _field_states(self) -> tuple[tuple[str, LineageExtractionState], ...]:
        return (
            ("stage_id", self.stage_id.state),
            ("recording_block_id", self.recording_block_id.state),
            ("scheduled_activity_id", self.scheduled_activity_id.state),
            ("transcript_stream_id", self.transcript_stream_id.state),
            ("media_artifact_id", self.media_artifact_id.state),
            ("timeline_reference", self.timeline_reference.state),
            ("producer_identifier", self.producer_identifier.state),
        )


@dataclass(frozen=True, slots=True)
class _Candidate[LineageValue: (EntityId, str)]:
    source: str
    value: LineageValue | None


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


def _structured_candidates[LineageValue: (EntityId, str)](
    event: ProductionEvent,
    keys: tuple[str, ...],
    parser: Callable[[object], LineageValue | None],
) -> tuple[_Candidate[LineageValue], ...]:
    candidates: list[_Candidate[LineageValue]] = []
    for mapping_name, mapping in (
        ("event_payload", event.payload.data),
        ("event_metadata", event.metadata),
    ):
        for key in keys:
            if key in mapping:
                candidates.append(
                    _Candidate(f"{mapping_name}.{key}", parser(mapping[key]))
                )
    return tuple(candidates)


def _reference_candidates[LineageValue: (EntityId, str)](
    event: ProductionEvent,
    reference_types: Sequence[ProductionEventReferenceType],
    parser: Callable[[object], LineageValue | None],
    source_name: str,
) -> tuple[_Candidate[LineageValue], ...]:
    candidates: list[_Candidate[LineageValue]] = []
    for reference in event.references:
        if reference.reference_type not in reference_types:
            continue
        raw_value: object = (
            reference.referenced_id
            if reference.referenced_id is not None
            else reference.external_reference
        )
        candidates.append(_Candidate(source_name, parser(raw_value)))
    return tuple(candidates)


def _extract[LineageValue: (EntityId, str)](
    candidates: Sequence[_Candidate[LineageValue]],
) -> LineageExtraction[LineageValue]:
    if not candidates:
        return LineageExtraction(LineageExtractionState.ABSENT)
    if any(candidate.value is None for candidate in candidates):
        return LineageExtraction(LineageExtractionState.MALFORMED)

    first = candidates[0]
    if any(candidate.value != first.value for candidate in candidates[1:]):
        return LineageExtraction(LineageExtractionState.CONTRADICTORY)
    return LineageExtraction(
        LineageExtractionState.VALID,
        value=first.value,
        source=first.source,
    )


def _entity_lineage(
    event: ProductionEvent,
    *,
    reference_type: ProductionEventReferenceType,
    structured_keys: tuple[str, ...],
    source_name: str,
) -> LineageExtraction[EntityId]:
    return _extract(
        _reference_candidates(event, (reference_type,), _entity_id, source_name)
        + _structured_candidates(event, structured_keys, _entity_id)
    )


def _string_lineage(
    event: ProductionEvent,
    *,
    structured_keys: tuple[str, ...],
    reference_types: Sequence[ProductionEventReferenceType] = (),
    source_name: str,
) -> LineageExtraction[str]:
    return _extract(
        _reference_candidates(event, reference_types, _string, source_name)
        + _structured_candidates(event, structured_keys, _string)
    )


def event_observation_lineage_from_event(event: ProductionEvent) -> EventObservationLineage:
    """Extract all authoritative lineage candidates without precedence-based hiding."""

    return EventObservationLineage(
        stage_id=_entity_lineage(
            event,
            reference_type=ProductionEventReferenceType.STAGE,
            structured_keys=("stage_id",),
            source_name="event.references.stage",
        ),
        recording_block_id=_entity_lineage(
            event,
            reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
            structured_keys=("recording_block_id",),
            source_name="event.references.recording_block",
        ),
        scheduled_activity_id=_entity_lineage(
            event,
            reference_type=ProductionEventReferenceType.SCHEDULE_ARTIFACT,
            structured_keys=("scheduled_activity_id",),
            source_name="event.references.schedule_artifact",
        ),
        transcript_stream_id=_string_lineage(
            event,
            structured_keys=(
                "transcript_stream_id",
                "stream_id",
                "transcript_source_id",
            ),
            source_name="event.references.transcript_stream",
        ),
        media_artifact_id=_string_lineage(
            event,
            reference_types=(ProductionEventReferenceType.MEDIA_FILE,),
            structured_keys=("media_artifact_id", "artifact_id"),
            source_name="event.references.media_file",
        ),
        timeline_reference=_string_lineage(
            event,
            reference_types=(
                ProductionEventReferenceType.TIMELINE_RANGE,
                ProductionEventReferenceType.TIMELINE_POSITION,
            ),
            structured_keys=(
                "timeline_range_reference",
                "timeline_position_reference",
            ),
            source_name="event.references.timeline",
        ),
        producer_identifier=_string_lineage(
            event,
            reference_types=(ProductionEventReferenceType.SYSTEM,),
            structured_keys=(
                "producer_identifier",
                "adapter_id",
                "recording_system_id",
                "transcript_source_id",
                "clock_id",
            ),
            source_name="event.references.system",
        ),
    )


def _value[LineageValue: (EntityId, str)](
    extraction: LineageExtraction[LineageValue],
) -> LineageValue | None:
    if extraction.state is LineageExtractionState.VALID:
        return extraction.value
    return None


def _context_value[LineageValue: (EntityId, str)](
    extraction: LineageExtraction[LineageValue],
    fallback: LineageValue | None,
    fallback_source: str,
) -> tuple[LineageValue | None, str | None]:
    if extraction.state is LineageExtractionState.VALID:
        return extraction.value, extraction.source
    if extraction.state is LineageExtractionState.ABSENT and fallback is not None:
        return fallback, fallback_source
    return None, None


def observation_context_from_event(
    event: ProductionEvent,
    interpreter_context: ObservationInterpreterContext,
) -> ObservationContext:
    """Extract Event context; use dispatcher fallback only for genuine absence."""

    lineage = event_observation_lineage_from_event(event)
    lineage.require_valid()
    field_sources: dict[str, str] = {"correlation_id": "event.correlation_id"}

    stage_id, source = _context_value(
        lineage.stage_id,
        interpreter_context.stage_id,
        "interpreter_context.stage_id",
    )
    if source is not None:
        field_sources["stage_id"] = source

    recording_block_id, source = _context_value(
        lineage.recording_block_id,
        interpreter_context.recording_block_id,
        "interpreter_context.recording_block_id",
    )
    if source is not None:
        field_sources["recording_block_id"] = source

    for field_name, extraction in (
        ("scheduled_activity_id", lineage.scheduled_activity_id),
        ("transcript_stream_id", lineage.transcript_stream_id),
        ("media_artifact_id", lineage.media_artifact_id),
        ("timeline_reference", lineage.timeline_reference),
    ):
        if extraction.source is not None:
            field_sources[field_name] = extraction.source

    return ObservationContext(
        stage_id=stage_id,
        recording_block_id=recording_block_id,
        correlation_id=event.correlation_id,
        scheduled_activity_id=_value(lineage.scheduled_activity_id),
        transcript_stream_id=_value(lineage.transcript_stream_id),
        media_artifact_id=_value(lineage.media_artifact_id),
        timeline_reference=_value(lineage.timeline_reference),
        metadata={f"{name}_source": value for name, value in field_sources.items()},
    )


def observation_provenance_from_event(
    event: ProductionEvent,
    *,
    interpreter_id: EntityId,
    interpreter_kind: str,
    interpretation_rule_id: EntityId | str | None,
) -> ObservationProvenance:
    """Build exact one-Event provenance after validating authoritative candidates."""

    lineage = event_observation_lineage_from_event(event)
    lineage.require_valid()
    producer_identifier = _value(lineage.producer_identifier)
    metadata: Mapping[str, Any] = {
        "source_event_received_at": event.received_at.isoformat(),
        "producer_identifier_source": lineage.producer_identifier.source,
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
