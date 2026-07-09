from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationLocationKind,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId


def _position(recording_block_id: EntityId, seconds: int) -> TimelinePosition:
    return TimelinePosition(
        recording_block_id=recording_block_id,
        offset=timedelta(seconds=seconds),
    )


def test_observation_creation() -> None:
    recording_block_id = EntityId.new()
    observed_at = datetime(2026, 7, 6, 10, 30, tzinfo=UTC)
    observation = Observation(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        observation_type=ObservationType.TITLE_DETECTED,
        observation_source=ObservationSource.GRAPHICS,
        location=ObservationLocation.at_point(_position(recording_block_id, 272)),
        confidence=ObservationConfidence(0.9),
        observed_at=observed_at,
        correlation_id=CorrelationId.new(),
        actor="operator",
        metadata={"label": "opening title"},
        notes="Possible title card.",
    )

    assert observation.recording_block_id == recording_block_id
    assert observation.observation_type is ObservationType.TITLE_DETECTED
    assert observation.observation_source is ObservationSource.GRAPHICS
    assert observation.location.is_point
    assert observation.confidence.value == 0.9
    assert observation.observed_at == observed_at
    assert dict(observation.metadata) == {"label": "opening title"}


def test_observation_type_allowed_values() -> None:
    assert {observation_type.value for observation_type in ObservationType} == {
        "recording_activity",
        "media_artifact",
        "speech_detected",
        "title_detected",
        "graphic_changed",
        "applause_detected",
        "silence_detected",
        "music_detected",
        "operator_marker",
        "schedule_boundary",
        "transcript_text_detected",
        "livestream_status_changed",
        "unknown",
    }


def test_observation_source_allowed_values() -> None:
    assert {source.value for source in ObservationSource} == {
        "human",
        "operator",
        "schedule",
        "transcript",
        "audio",
        "vision",
        "graphics",
        "livestream",
        "system",
        "unknown",
    }


def test_observation_confidence_accepts_bounds() -> None:
    assert ObservationConfidence(0.0).value == 0.0
    assert ObservationConfidence(1.0).value == 1.0
    assert ObservationConfidence(0.8).is_high_confidence()


def test_observation_confidence_rejects_values_below_zero() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        ObservationConfidence(-0.01)


def test_observation_confidence_rejects_values_above_one() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        ObservationConfidence(1.01)


def test_observation_location_accepts_point_location() -> None:
    recording_block_id = EntityId.new()
    location = ObservationLocation.at_point(_position(recording_block_id, 15))

    assert location.kind is ObservationLocationKind.TIMELINE_POSITION
    assert location.is_point
    assert not location.is_range
    assert location.recording_block_id == recording_block_id


def test_observation_location_accepts_range_location() -> None:
    recording_block_id = EntityId.new()
    location = ObservationLocation.over_range(
        TimelineRange(
            start=_position(recording_block_id, 15),
            end=_position(recording_block_id, 25),
        )
    )

    assert location.kind is ObservationLocationKind.TIMELINE_RANGE
    assert location.is_range
    assert not location.is_point
    assert location.recording_block_id == recording_block_id


def test_observation_location_accepts_recording_block_location() -> None:
    recording_block_id = EntityId.new()
    location = ObservationLocation.for_recording_block(recording_block_id)

    assert location.kind is ObservationLocationKind.RECORDING_BLOCK
    assert location.is_recording_block
    assert not location.is_point
    assert location.recording_block_id == recording_block_id


def test_observation_location_accepts_wall_clock_location() -> None:
    timestamp = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    location = ObservationLocation.at_wall_clock(timestamp)

    assert location.kind is ObservationLocationKind.WALL_CLOCK
    assert location.is_wall_clock
    assert location.wall_clock_at == timestamp
    assert location.recording_block_id is None


def test_observation_location_accepts_stage_location() -> None:
    stage_id = EntityId.new()
    location = ObservationLocation.for_stage(stage_id)

    assert location.kind is ObservationLocationKind.STAGE
    assert location.is_stage
    assert location.stage_id == stage_id
    assert location.recording_block_id is None


def test_observation_location_accepts_composite_anchors() -> None:
    recording_block_id = EntityId.new()
    stage_id = EntityId.new()
    timestamp = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    location = ObservationLocation.composite(
        recording_block=recording_block_id,
        wall_clock_at=timestamp,
        stage_id=stage_id,
    )

    assert location.kind is ObservationLocationKind.COMPOSITE
    assert location.is_composite
    assert location.recording_block_id == recording_block_id
    assert location.wall_clock_at == timestamp
    assert location.stage_id == stage_id


def test_observation_location_accepts_explicit_unknown() -> None:
    location = ObservationLocation.unknown()

    assert location.kind is ObservationLocationKind.UNKNOWN
    assert location.is_unknown
    assert location.recording_block_id is None


def test_observation_location_kind_allowed_values() -> None:
    assert {kind.value for kind in ObservationLocationKind} == {
        "timeline_position",
        "timeline_range",
        "recording_block",
        "wall_clock",
        "stage",
        "composite",
        "unknown",
    }


def test_observation_location_rejects_both_point_and_range() -> None:
    recording_block_id = EntityId.new()

    with pytest.raises(ValueError, match="explicit location kind"):
        ObservationLocation(
            point=_position(recording_block_id, 15),
            range=TimelineRange(
                start=_position(recording_block_id, 15),
                end=_position(recording_block_id, 25),
            ),
        )


def test_observation_location_rejects_neither_point_nor_range() -> None:
    with pytest.raises(ValueError, match="explicit location kind"):
        ObservationLocation()


def test_observation_location_rejects_composite_with_one_anchor() -> None:
    with pytest.raises(ValueError, match="at least two anchors"):
        ObservationLocation.composite(recording_block=EntityId.new())


def test_observation_location_rejects_unknown_with_anchors() -> None:
    with pytest.raises(ValueError, match="must not include anchors"):
        ObservationLocation(
            kind=ObservationLocationKind.UNKNOWN,
            recording_block=EntityId.new(),
        )


def test_observation_location_rejects_conflicting_recording_block_anchors() -> None:
    with pytest.raises(ValueError, match="same ID"):
        ObservationLocation.composite(
            point=_position(EntityId.new(), 15),
            recording_block=EntityId.new(),
        )


def test_observation_metadata_is_optional() -> None:
    recording_block_id = EntityId.new()
    observation = Observation(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        observation_type=ObservationType.UNKNOWN,
        observation_source=ObservationSource.UNKNOWN,
        location=ObservationLocation.at_point(_position(recording_block_id, 1)),
        confidence=ObservationConfidence(0.0),
        correlation_id=CorrelationId.new(),
    )

    assert dict(observation.metadata) == {}
    assert observation.actor is None
    assert observation.notes is None


def test_observation_can_be_anchored_to_wall_clock_without_recording_block() -> None:
    timestamp = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    observation = Observation(
        id=EntityId.new(),
        recording_block_id=None,
        observation_type=ObservationType.UNKNOWN,
        observation_source=ObservationSource.SYSTEM,
        location=ObservationLocation.at_wall_clock(timestamp),
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
    )

    assert observation.recording_block_id is None
    assert observation.location.is_wall_clock


def test_observation_derives_recording_block_from_location_when_omitted() -> None:
    recording_block_id = EntityId.new()
    observation = Observation(
        id=EntityId.new(),
        recording_block_id=None,
        observation_type=ObservationType.RECORDING_ACTIVITY,
        observation_source=ObservationSource.SYSTEM,
        location=ObservationLocation.for_recording_block(recording_block_id),
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
    )

    assert observation.recording_block_id == recording_block_id


def test_observation_uses_generic_entity_id_and_correlation_id() -> None:
    recording_block_id = EntityId.new()
    observation_id = EntityId.new()
    correlation_id = CorrelationId.new()
    observation = Observation(
        id=observation_id,
        recording_block_id=recording_block_id,
        observation_type=ObservationType.OPERATOR_MARKER,
        observation_source=ObservationSource.OPERATOR,
        location=ObservationLocation.at_point(_position(recording_block_id, 30)),
        confidence=ObservationConfidence(1.0),
        correlation_id=correlation_id,
    )

    assert observation.id == observation_id
    assert observation.recording_block_id == recording_block_id
    assert observation.correlation_id == correlation_id


def test_observation_rejects_location_from_different_recording_block() -> None:
    with pytest.raises(ValueError, match="recording_block_id"):
        Observation(
            id=EntityId.new(),
            recording_block_id=EntityId.new(),
            observation_type=ObservationType.SPEECH_DETECTED,
            observation_source=ObservationSource.AUDIO,
            location=ObservationLocation.at_point(_position(EntityId.new(), 30)),
            confidence=ObservationConfidence(0.5),
            correlation_id=CorrelationId.new(),
        )


def test_no_provider_specific_names_are_present_in_observation_implementation() -> None:
    enum_values = {item.value for item in ObservationType} | {
        item.value for item in ObservationSource
    }
    field_names = {field.name for field in fields(Observation)} | {
        field.name for field in fields(ObservationLocation)
    }
    forbidden_terms = {
        "provider",
        "vendor",
        "tool",
        "brand",
        "conference",
    }

    assert not any(term in value for value in enum_values | field_names for term in forbidden_terms)


def test_no_conclusion_oriented_types_are_present() -> None:
    forbidden_values = {
        "boundary_concluded",
        "workflow_ready",
        "review_verified",
        "delivery_complete",
    }

    assert forbidden_values.isdisjoint({item.value for item in ObservationType})
