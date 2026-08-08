from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.production.evidence import (
    EvidenceContext,
    EvidenceContextConflictResolution,
    EvidenceContextResolver,
    EvidenceContextSource,
    EvidenceItem,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceStrength,
    resolve_evidence_set_context,
    resolve_observation_evidence_context,
)
from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationContext,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.timeline import TimelinePosition
from app.shared.ids import CorrelationId, EntityId
from tests.timestamp_fixtures import AWARE_TIMESTAMP


def _observation(
    *,
    context: ObservationContext | None = None,
    legacy_block_id: EntityId | None = None,
    legacy_stage_id: EntityId | None = None,
    metadata: dict[str, object] | None = None,
) -> Observation:
    location = (
        ObservationLocation.composite(
            recording_block=legacy_block_id,
            stage_id=legacy_stage_id,
        )
        if legacy_block_id is not None and legacy_stage_id is not None
        else (
            ObservationLocation.for_recording_block(legacy_block_id)
            if legacy_block_id is not None
            else (
                ObservationLocation.for_stage(legacy_stage_id)
                if legacy_stage_id is not None
                else ObservationLocation.unknown()
            )
        )
    )
    return Observation(
        id=EntityId.new(),
        recording_block_id=legacy_block_id,
        observation_type=ObservationType.RECORDING_ACTIVITY,
        observation_source=ObservationSource.SYSTEM,
        location=location,
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
        metadata=metadata or {},
        context=context or ObservationContext.unknown(),
    )


def _legacy_evidence(metadata: dict[str, object]) -> EvidenceSet:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=EvidenceStrength.MODERATE,
        role=EvidenceRole.SUPPORTS,
    )
    return EvidenceSet(
               created_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        recording_block_id=None,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(item,),
        correlation_id=CorrelationId.new(),
        metadata=metadata,
    )


def test_observation_context_is_authoritative_and_conflicts_remain_visible() -> None:
    first_class_stage = EntityId.new()
    first_class_block = EntityId.new()
    legacy_stage = EntityId.new()
    legacy_block = EntityId.new()
    metadata_stage = EntityId.new()
    observation = _observation(
        context=ObservationContext(
            stage_id=first_class_stage,
            recording_block_id=first_class_block,
            transcript_stream_id="first-class-stream",
            media_artifact_id="first-class-artifact",
        ),
        legacy_block_id=legacy_block,
        legacy_stage_id=legacy_stage,
        metadata={
            "stage_id": metadata_stage.to_json(),
            "recording_block_id": EntityId.new().to_json(),
            "transcript_stream_id": "metadata-stream",
            "media_artifact_id": "metadata-artifact",
        },
    )

    resolution = resolve_observation_evidence_context(observation)

    assert observation.context.stage_id == first_class_stage
    assert observation.context.recording_block_id == first_class_block
    assert observation.recording_block_id == legacy_block
    assert resolution.context.stage_id == first_class_stage
    assert resolution.context.recording_block_id == first_class_block
    assert resolution.context.transcript_stream_ids == ("first-class-stream",)
    assert resolution.context.media_artifact_ids == ("first-class-artifact",)
    assert resolution.sources["stage_id"] is EvidenceContextSource.OBSERVATION_FIRST_CLASS
    assert {conflict.field_name for conflict in resolution.conflicts} >= {
        "stage_id",
        "recording_block_id",
        "transcript_stream_ids",
        "media_artifact_ids",
    }
    assert all(
        conflict.resolution is EvidenceContextConflictResolution.FIRST_CLASS_VALUE_RETAINED
        for conflict in resolution.conflicts
        if conflict.field_name in {"stage_id", "recording_block_id"}
    )


def test_observation_legacy_field_and_metadata_fallback_precedence() -> None:
    legacy_block = EntityId.new()
    metadata_block = EntityId.new()
    stage = EntityId.new()
    observation = _observation(
        legacy_block_id=legacy_block,
        metadata={
            "recording_block_id": metadata_block.to_json(),
            "stage_id": stage.to_json(),
        },
    )

    resolution = resolve_observation_evidence_context(observation)

    assert resolution.context.recording_block_id == legacy_block
    assert resolution.sources["recording_block_id"] in {
        EvidenceContextSource.OBSERVATION_FIRST_CLASS,
        EvidenceContextSource.STRUCTURED_LEGACY_FIELD,
    }
    assert resolution.context.stage_id == stage
    assert resolution.sources["stage_id"] is EvidenceContextSource.STRUCTURED_METADATA_FALLBACK
    assert any(conflict.field_name == "recording_block_id" for conflict in resolution.conflicts)


def test_evidence_first_class_context_wins_over_metadata() -> None:
    stage_a = EntityId.new()
    stage_b = EntityId.new()
    evidence = _legacy_evidence({"stage_id": stage_b.to_json()})
    evidence = EvidenceSet(
                   created_at=AWARE_TIMESTAMP,

        id=evidence.id,
        recording_block_id=evidence.recording_block_id,
        purpose=evidence.purpose,
        items=evidence.items,
        correlation_id=evidence.correlation_id,
        metadata=evidence.metadata,
        context=EvidenceContext(stage_id=stage_a),
    )

    resolution = resolve_evidence_set_context(evidence)

    assert resolution.context.stage_id == stage_a
    assert resolution.sources["stage_id"] is EvidenceContextSource.EVIDENCE_FIRST_CLASS
    assert resolution.conflicts[0].field_name == "stage_id"
    assert (
        resolution.conflicts[0].resolution
        is EvidenceContextConflictResolution.FIRST_CLASS_VALUE_RETAINED
    )


@pytest.mark.parametrize(
    ("metadata", "field_name", "expected"),
    [
        ({"stage_id": None}, "stage_id", None),
        ({"transcript_stream_id": "stream-a"}, "transcript_stream_ids", ("stream-a",)),
        ({"stream_id": "stream-a"}, "transcript_stream_ids", ("stream-a",)),
        ({"transcript_source_id": "stream-a"}, "transcript_stream_ids", ("stream-a",)),
        (
            {"transcript_stream_ids": ["stream-b", "stream-a"]},
            "transcript_stream_ids",
            ("stream-a", "stream-b"),
        ),
        ({"media_artifact_id": "artifact-a"}, "media_artifact_ids", ("artifact-a",)),
        ({"artifact_id": "artifact-a"}, "media_artifact_ids", ("artifact-a",)),
        (
            {"media_artifact_ids": ["artifact-b", "artifact-a"]},
            "media_artifact_ids",
            ("artifact-a", "artifact-b"),
        ),
    ],
)
def test_documented_text_aliases_remain_compatible(
    metadata: dict[str, object],
    field_name: str,
    expected: object,
) -> None:
    resolution = resolve_evidence_set_context(_legacy_evidence(metadata))

    assert getattr(resolution.context, field_name) == expected
    if expected is not None:
        assert resolution.sources[field_name] is EvidenceContextSource.STRUCTURED_METADATA_FALLBACK


@pytest.mark.parametrize(
    ("key", "context_field"),
    [
        ("stage_id", "stage_id"),
        ("recording_block_id", "recording_block_id"),
        ("scheduled_activity_id", "scheduled_activity_id"),
        ("schedule_activity_id", "scheduled_activity_id"),
        ("boundary_context_id", "boundary_context_id"),
        ("boundary_evidence_context_id", "boundary_context_id"),
    ],
)
def test_documented_entity_aliases_remain_compatible(
    key: str,
    context_field: str,
) -> None:
    entity_id = EntityId.new()
    resolution = resolve_evidence_set_context(_legacy_evidence({key: entity_id.to_json()}))

    assert getattr(resolution.context, context_field) == entity_id
    assert resolution.sources[context_field] is EvidenceContextSource.STRUCTURED_METADATA_FALLBACK


def test_timeline_anchor_and_correlation_fallbacks_are_centralized() -> None:
    block_id = EntityId.new()
    boundary_at = datetime(2026, 7, 16, 10, 3, 30, tzinfo=UTC)
    correlation_id = CorrelationId.new()
    evidence = _legacy_evidence(
        {
            "recording_block_id": block_id.to_json(),
            "timeline_range_start_seconds": 10,
            "timeline_range_end_seconds": 20,
            "boundary_anchor_at": boundary_at.isoformat(),
            "boundary_anchor_seconds": 12.5,
            "correlation_ids": (correlation_id.to_json(),),
        }
    )

    resolution = resolve_evidence_set_context(evidence)
    context = resolution.context

    assert context.recording_block_id == block_id
    assert context.timeline_range_seconds == (10.0, 20.0)
    assert context.organizational_anchor == boundary_at
    assert context.organizational_anchor_seconds == 12.5
    assert context.correlation_ids == (evidence.correlation_id,)
    assert any(
        conflict.field_name == "correlation_ids"
        and correlation_id.to_json() in conflict.conflicting_value
        for conflict in resolution.conflicts
    )


def test_malformed_identifiers_are_ignored_without_identity_invention() -> None:
    evidence = _legacy_evidence(
        {
            "stage_id": "not-an-entity-id",
            "recording_block_id": "also-invalid",
            "correlation_id": "not-a-correlation-id",
            "media_artifact_id": "artifact-only",
            "scheduled_activity_id": EntityId.new().to_json(),
        }
    )

    resolution = resolve_evidence_set_context(evidence)

    assert resolution.context.stage_id is None
    assert resolution.context.recording_block_id is None
    assert resolution.context.media_artifact_ids == ("artifact-only",)
    assert resolution.context.scheduled_activity_id is not None
    assert resolution.context.correlation_ids == (evidence.correlation_id,)
    assert set(resolution.ignored_values) >= {
        "stage_id",
        "recording_block_id",
        "correlation_ids",
    }


def test_metadata_entity_conflicts_have_no_arbitrary_winner() -> None:
    stage_a = EntityId.new()
    stage_b = EntityId.new()
    resolution = EvidenceContextResolver().resolve(
        metadata_sources=(
            {"stage_id": stage_b.to_json()},
            {"stage_id": stage_a.to_json()},
        )
    )

    assert resolution.context.stage_id is None
    assert resolution.unresolved_fields == ("stage_id",)
    assert resolution.conflicts[0].field_name == "stage_id"
    assert resolution.conflicts[0].resolution is EvidenceContextConflictResolution.INPUT_IGNORED


def test_metadata_anchor_conflicts_have_no_arbitrary_winner() -> None:
    resolution = EvidenceContextResolver().resolve(
        metadata_sources=(
            {"boundary_anchor_seconds": 10.0},
            {"organizational_anchor_seconds": 20.0},
        )
    )

    assert resolution.context.organizational_anchor_seconds is None
    assert resolution.unresolved_fields == ("organizational_anchor_seconds",)
    assert resolution.conflicts[0].field_name == "organizational_anchor_seconds"
    assert resolution.conflicts[0].resolution is EvidenceContextConflictResolution.INPUT_IGNORED


def test_compose_unions_collections_and_ranges_deterministically() -> None:
    stage_id = EntityId.new()
    block_id = EntityId.new()
    source_a = EntityId.new()
    source_b = EntityId.new()
    correlation_a = CorrelationId.new()
    correlation_b = CorrelationId.new()
    resolver = EvidenceContextResolver()
    first = resolver.resolve(
        first_class=EvidenceContext(
            stage_id=stage_id,
            recording_block_id=block_id,
            transcript_stream_ids=("stream-b",),
            media_artifact_ids=("artifact-a",),
            correlation_ids=(correlation_a,),
            timeline_position=TimelinePosition(block_id, timedelta(seconds=20)),
        )
    )
    second = resolver.resolve(
        first_class=EvidenceContext(
            stage_id=stage_id,
            recording_block_id=block_id,
            transcript_stream_ids=("stream-a",),
            media_artifact_ids=("artifact-b",),
            correlation_ids=(correlation_b,),
            timeline_position=TimelinePosition(block_id, timedelta(seconds=10)),
        )
    )

    forward = resolver.compose((first, second), source_context_ids=(source_b, source_a))
    reverse = resolver.compose((second, first), source_context_ids=(source_a, source_b))

    assert forward == reverse
    assert forward.context.transcript_stream_ids == ("stream-a", "stream-b")
    assert forward.context.media_artifact_ids == ("artifact-a", "artifact-b")
    assert set(forward.context.correlation_ids) == {correlation_a, correlation_b}
    assert forward.context.timeline_range_seconds == (10.0, 20.0)
    assert set(forward.context.source_context_ids) == {source_a, source_b}
    assert all(
        source is EvidenceContextSource.COMPOSED_FROM_SOURCES for source in forward.sources.values()
    )


def test_compose_rejects_conflicting_known_singular_context() -> None:
    resolver = EvidenceContextResolver()
    stage_a = resolver.resolve(first_class=EvidenceContext(stage_id=EntityId.new()))
    stage_b = resolver.resolve(first_class=EvidenceContext(stage_id=EntityId.new()))

    resolution = resolver.compose((stage_b, stage_a))

    assert resolution.context.stage_id is None
    assert resolution.unresolved_fields == ("stage_id",)
    assert resolution.conflicts[0].field_name == "stage_id"
    assert (
        resolution.conflicts[0].resolution is EvidenceContextConflictResolution.COMPOSITION_REJECTED
    )


def test_resolution_is_independent_of_metadata_mapping_order() -> None:
    stage_id = EntityId.new()
    correlation_id = CorrelationId.new()
    first = {
        "stage_id": stage_id.to_json(),
        "transcript_stream_id": "stream-a",
        "correlation_id": correlation_id.to_json(),
    }
    second = dict(reversed(tuple(first.items())))

    assert EvidenceContextResolver().resolve(metadata_sources=(first,)) == (
        EvidenceContextResolver().resolve(metadata_sources=(second,))
    )
