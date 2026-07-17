from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.contexts.production.evidence import (
    EvidenceContext,
    EvidenceContextConflict,
    EvidenceContextConflictResolution,
    EvidenceContextResolution,
    EvidenceContextSource,
    EvidenceItem,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceStrength,
)
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.contexts.production.transition_policy import TransitionEvaluation
from app.shared.ids import CorrelationId, EntityId


def _item() -> EvidenceItem:
    return EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=EvidenceStrength.STRONG,
        role=EvidenceRole.SUPPORTS,
    )


def test_evidence_context_supports_complete_partial_and_empty_context() -> None:
    stage_id = EntityId.new()
    block_id = EntityId.new()
    activity_id = EntityId.new()
    boundary_id = EntityId.new()
    source_ids = [EntityId.new(), EntityId.new()]
    correlations = [CorrelationId.new(), CorrelationId.new()]
    anchor = datetime(2026, 7, 16, 10, 3, 30, tzinfo=UTC)
    timeline = TimelineRange(
        TimelinePosition(block_id, timedelta(seconds=10)),
        TimelinePosition(block_id, timedelta(seconds=14)),
    )

    context = EvidenceContext(
        stage_id=stage_id,
        recording_block_id=block_id,
        scheduled_activity_id=activity_id,
        transcript_stream_ids=("stream-b", "stream-a"),
        media_artifact_ids=("artifact-b", "artifact-a"),
        correlation_ids=correlations,
        timeline_range=timeline,
        organizational_anchor=anchor,
        boundary_context_id=boundary_id,
        source_context_ids=source_ids,
    )

    assert context.stage_id == stage_id
    assert context.recording_block_id == block_id
    assert context.scheduled_activity_id == activity_id
    assert context.transcript_stream_ids == ("stream-a", "stream-b")
    assert context.media_artifact_ids == ("artifact-a", "artifact-b")
    assert context.correlation_ids == tuple(sorted(correlations, key=lambda value: value.to_json()))
    assert context.timeline_range == timeline
    assert context.timeline_range_seconds == (10.0, 14.0)
    assert context.organizational_anchor == anchor
    assert context.boundary_context_id == boundary_id
    assert context.source_context_ids == tuple(
        sorted(source_ids, key=lambda value: value.to_json())
    )
    assert not context.is_empty
    assert EvidenceContext(stage_id=stage_id).stage_id == stage_id
    assert EvidenceContext.unknown().is_empty


def test_evidence_context_normalizes_duplicates_and_is_hash_deterministic() -> None:
    stream_ids = ["stream-b", "stream-a", "stream-b"]
    artifact_ids = ["artifact-b", "artifact-a", "artifact-b"]
    correlation_id = CorrelationId.new()
    source_id = EntityId.new()
    first = EvidenceContext(
        transcript_stream_ids=stream_ids,
        media_artifact_ids=artifact_ids,
        correlation_ids=(correlation_id, correlation_id),
        source_context_ids=(source_id, source_id),
        metadata={"diagnostic": "first"},
    )
    second = EvidenceContext(
        transcript_stream_ids=tuple(reversed(stream_ids)),
        media_artifact_ids=tuple(reversed(artifact_ids)),
        correlation_ids=(correlation_id,),
        source_context_ids=(source_id,),
        metadata={"diagnostic": "second"},
    )

    stream_ids.append("caller-mutation")
    artifact_ids.append("caller-mutation")

    assert first.transcript_stream_ids == ("stream-a", "stream-b")
    assert first.media_artifact_ids == ("artifact-a", "artifact-b")
    assert first == second
    assert hash(first) == hash(second)


def test_evidence_context_metadata_is_defensively_copied_and_immutable() -> None:
    metadata = {"compatibility_key": "stage_id"}
    context = EvidenceContext(metadata=metadata)
    metadata["compatibility_key"] = "recording_block_id"

    assert context.metadata["compatibility_key"] == "stage_id"
    with pytest.raises(TypeError):
        context.metadata["new"] = "value"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        context.stage_id = EntityId.new()  # type: ignore[misc]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: EvidenceContext(transcript_stream_ids=(" ",)),
        lambda: EvidenceContext(media_artifact_ids=("",)),
        lambda: EvidenceContext(organizational_anchor_seconds=float("inf")),
    ],
)
def test_evidence_context_rejects_invalid_values(factory: object) -> None:
    with pytest.raises(ValueError):
        factory()  # type: ignore[operator]


def test_evidence_context_rejects_ambiguous_or_cross_block_timeline() -> None:
    block_a = EntityId.new()
    block_b = EntityId.new()
    point = TimelinePosition(block_a, timedelta(seconds=1))
    time_range = TimelineRange(
        TimelinePosition(block_a, timedelta(seconds=1)),
        TimelinePosition(block_a, timedelta(seconds=2)),
    )

    with pytest.raises(ValueError, match="both timeline_position and timeline_range"):
        EvidenceContext(timeline_position=point, timeline_range=time_range)
    with pytest.raises(ValueError, match="belong to recording_block_id"):
        EvidenceContext(recording_block_id=block_b, timeline_position=point)


def test_context_source_and_conflict_contracts_are_categorical_and_immutable() -> None:
    assert {source.value for source in EvidenceContextSource} == {
        "observation_first_class",
        "evidence_first_class",
        "structured_legacy_field",
        "structured_metadata_fallback",
        "composed_from_sources",
        "explicit_builder_input",
        "unknown",
    }
    assert {resolution.value for resolution in EvidenceContextConflictResolution} == {
        "first_class_value_retained",
        "evidence_isolated",
        "input_ignored",
        "build_rejected",
        "composition_rejected",
        "unknown",
    }
    source_id = EntityId.new()
    conflict = EvidenceContextConflict(
        field_name="stage_id",
        authoritative_value=("stage-b", "stage-a", "stage-a"),
        conflicting_value=("stage-c",),
        authoritative_source=EvidenceContextSource.EVIDENCE_FIRST_CLASS,
        conflicting_source=EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
        contributing_reference_ids=(source_id, source_id),
        resolution=EvidenceContextConflictResolution.FIRST_CLASS_VALUE_RETAINED,
        metadata={"visible": True},
    )

    assert conflict.authoritative_value == ("stage-a", "stage-b")
    assert conflict.contributing_reference_ids == (source_id,)
    with pytest.raises(TypeError):
        conflict.metadata["visible"] = False  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        conflict.field_name = "recording_block_id"  # type: ignore[misc]


def test_resolution_contract_normalizes_diagnostics_immutably() -> None:
    conflict = EvidenceContextConflict(
        field_name="stage_id",
        authoritative_value=("a",),
        conflicting_value=("b",),
        authoritative_source=EvidenceContextSource.EVIDENCE_FIRST_CLASS,
        conflicting_source=EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
    )
    resolution = EvidenceContextResolution(
        context=EvidenceContext.unknown(),
        sources={"stage_id": EvidenceContextSource.EVIDENCE_FIRST_CLASS},
        conflicts=(conflict,),
        ignored_values={"stage_id": ("bad", "bad")},
        unresolved_fields=("stage_id", "stage_id"),
    )

    assert resolution.has_conflicts
    assert resolution.ignored_values["stage_id"] == ("bad",)
    assert resolution.unresolved_fields == ("stage_id",)
    with pytest.raises(TypeError):
        resolution.sources["stage_id"] = EvidenceContextSource.UNKNOWN  # type: ignore[index]


def test_evidence_set_and_transition_evaluation_context_defaults_are_compatible() -> None:
    evidence = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=None,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(_item(),),
        correlation_id=CorrelationId.new(),
    )
    evaluation_context_field = next(
        field for field in fields(TransitionEvaluation) if field.name == "context"
    )

    assert evidence.context.is_empty
    assert evidence.context_resolution is None
    assert evaluation_context_field.default_factory().is_empty  # type: ignore[misc]


def test_context_layer_has_no_forbidden_architectural_dependencies() -> None:
    evidence_dir = Path(__file__).parents[1] / "app" / "contexts" / "production" / "evidence"
    sources = "\n".join(
        path.read_text()
        for path in (
            evidence_dir / "evidence_context.py",
            evidence_dir / "evidence_context_conflict.py",
            evidence_dir / "evidence_context_resolution.py",
            evidence_dir / "evidence_context_source.py",
        )
    )

    forbidden_imports = (
        "repository",
        "sqlalchemy",
        "fastapi",
        "worker",
        "queue",
        "transition_policy",
        "session",
        "confidence",
        "scoring",
        "openai",
    )
    import_lines = tuple(
        line.lower()
        for line in sources.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    )
    assert all(forbidden not in line for forbidden in forbidden_imports for line in import_lines)
