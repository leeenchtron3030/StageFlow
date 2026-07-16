from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
    EvidenceStrength,
)
from app.contexts.production.session_boundary_evidence_builder import (
    DEFAULT_BOUNDARY_COMPOSITION_WINDOW,
    SESSION_BOUNDARY_EVIDENCE_MAPPINGS,
    SessionBoundaryEvidenceBuilder,
    SessionBoundaryEvidenceContext,
    SessionBoundaryEvidenceMapping,
    SessionBoundaryEvidenceResult,
    SessionBoundaryEvidenceRule,
    SessionBoundaryEvidenceSummary,
    make_session_boundary_evidence_builder,
    mappings_for_source,
)
from app.shared.ids import CorrelationId, EntityId

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _source_evidence(
    concern: EvidenceConcern,
    signal: EvidenceSignal,
    *,
    at: datetime = BASE_TIME,
    offset: float | None = 10.0,
    recording_block_id: EntityId | None = None,
    stage_id: EntityId | None = None,
    scheduled_activity_id: EntityId | None = None,
    transcript_stream_id: EntityId | str | None = None,
    media_artifact_id: EntityId | str | None = None,
    correlation_id: CorrelationId | None = None,
    evidence_set_id: EntityId | None = None,
    item_id: EntityId | None = None,
    observation_id: EntityId | None = None,
    role: EvidenceRole = EvidenceRole.SUPPORTS,
    strength: EvidenceStrength = EvidenceStrength.MODERATE,
    duplicate_signal_reference: bool = False,
) -> EvidenceSet:
    item_id = item_id or EntityId.new()
    observation_id = observation_id or EntityId.new()
    location: dict[str, object] = {}
    if offset is not None:
        location["timeline_offset_seconds"] = offset
    if stage_id is not None:
        location["stage_id"] = stage_id.to_json()
    item = EvidenceItem(
        id=item_id,
        observation_id=observation_id,
        role=role,
        strength=strength,
        rationale="Structured source Evidence.",
        metadata={
            "observation_observed_at": at.isoformat(),
            "observation_location": location,
        },
    )
    signal_reference = EvidenceSignalReference(
        signal=signal,
        evidence_item_ids=(item.id,),
        observation_ids=(item.observation_id,),
        rationale="Structured source Signal.",
        metadata={
            "stage_id": stage_id.to_json() if stage_id is not None else None,
            "transcript_stream_id": (
                transcript_stream_id.to_json()
                if isinstance(transcript_stream_id, EntityId)
                else transcript_stream_id
            ),
            "media_artifact_id": (
                media_artifact_id.to_json()
                if isinstance(media_artifact_id, EntityId)
                else media_artifact_id
            ),
        },
    )
    metadata = {
        "stage_id": stage_id.to_json() if stage_id is not None else None,
        "scheduled_activity_id": (
            scheduled_activity_id.to_json()
            if scheduled_activity_id is not None
            else None
        ),
    }
    signals = (
        (signal_reference, signal_reference)
        if duplicate_signal_reference
        else (signal_reference,)
    )
    return EvidenceSet(
        id=evidence_set_id or EntityId.new(),
        recording_block_id=recording_block_id,
        concern=concern,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(item,),
        signals=signals,
        correlation_id=correlation_id or CorrelationId.new(),
        created_at=at,
        metadata=metadata,
    )


def _shared_context() -> tuple[EntityId, EntityId, EntityId, CorrelationId]:
    return EntityId.new(), EntityId.new(), EntityId.new(), CorrelationId.new()


def test_builder_rule_mapping_context_result_and_summary_creation() -> None:
    mapping = SessionBoundaryEvidenceMapping(
        source_concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
        source_signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        target_concern=EvidenceConcern.POSSIBLE_SESSION_START,
        target_role=EvidenceRole.SUPPORTS,
        rationale="Speech availability supports possible-start Evidence.",
    )
    rule = SessionBoundaryEvidenceRule(
        id=EntityId.new(),
        accepted_source_concerns=(mapping.source_concern,),
        accepted_signal=mapping.source_signal,
        target_boundary_concern=mapping.target_concern,
        target_role=mapping.target_role,
        rationale_template=mapping.rationale,
    )
    context = SessionBoundaryEvidenceContext(
        id=EntityId.new(),
        boundary_concern=EvidenceConcern.POSSIBLE_SESSION_START,
    )
    result = SessionBoundaryEvidenceResult(
        start_boundary_evidence_sets=(),
        end_boundary_evidence_sets=(),
        consumed_source_evidence_set_ids=(),
        ignored_source_evidence_set_ids=(),
        unsupported_source_evidence_set_ids=(),
        duplicate_source_evidence_set_ids=(),
        applied_rule_ids=(rule.id,),
        generated_boundary_contexts=(context,),
    )
    summary = SessionBoundaryEvidenceSummary.from_result(result)
    builder = make_session_boundary_evidence_builder()

    assert isinstance(builder, SessionBoundaryEvidenceBuilder)
    assert builder.composition_window == DEFAULT_BOUNDARY_COMPOSITION_WINDOW
    assert rule.accepts(mapping.source_concern, mapping.source_signal)
    assert summary.boundary_context_count == 1


@pytest.mark.parametrize(
    ("concern", "signal", "target", "role"),
    [
        (
            EvidenceConcern.SCHEDULE_ALIGNMENT,
            EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceRole.CONTEXTUALIZES,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceRole.SUPPORTS,
        ),
        (
            EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
            EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceRole.SUPPORTS,
        ),
        (
            EvidenceConcern.TRANSCRIPT_CONTINUITY,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceRole.SUPPORTS,
        ),
        (
            EvidenceConcern.TRANSCRIPT_CONTINUITY,
            EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceRole.CONTEXTUALIZES,
        ),
        (
            EvidenceConcern.RECORDING_COVERAGE,
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceRole.CONTEXTUALIZES,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceSignal.SESSION_CONTENT_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceRole.SUPPORTS,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceSignal.SESSION_END_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceRole.SUPPORTS,
        ),
        (
            EvidenceConcern.TRANSCRIPT_CONTINUITY,
            EvidenceSignal.TRANSCRIPT_END_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceRole.SUPPORTS,
        ),
        (
            EvidenceConcern.RECORDING_COVERAGE,
            EvidenceSignal.RECORDING_END_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceRole.SUPPORTS,
        ),
        (
            EvidenceConcern.RECORDING_COVERAGE,
            EvidenceSignal.RECORDING_PAUSE_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceRole.CONTEXTUALIZES,
        ),
        (
            EvidenceConcern.MEDIA_AVAILABILITY,
            EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceRole.CONTEXTUALIZES,
        ),
    ],
)
def test_declarative_signal_treatments(
    concern: EvidenceConcern,
    signal: EvidenceSignal,
    target: EvidenceConcern,
    role: EvidenceRole,
) -> None:
    mappings = mappings_for_source(concern, signal)

    assert any(
        mapping.target_concern is target and mapping.target_role is role
        for mapping in mappings
    )


def test_multiple_compatible_start_signals_group_without_conclusion() -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    inputs = (
        _source_evidence(
            EvidenceConcern.RECORDING_COVERAGE,
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            offset=10,
            recording_block_id=block_id,
            stage_id=stage_id,
            scheduled_activity_id=activity_id,
            correlation_id=correlation_id,
        ),
        _source_evidence(
            EvidenceConcern.TRANSCRIPT_CONTINUITY,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            at=BASE_TIME + timedelta(seconds=20),
            offset=20,
            recording_block_id=block_id,
            stage_id=stage_id,
            scheduled_activity_id=activity_id,
            correlation_id=correlation_id,
        ),
        _source_evidence(
            EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
            EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
            at=BASE_TIME + timedelta(seconds=30),
            offset=30,
            recording_block_id=block_id,
            stage_id=stage_id,
            scheduled_activity_id=activity_id,
            correlation_id=correlation_id,
        ),
    )

    result = make_session_boundary_evidence_builder().build(inputs)
    output = result.start_boundary_evidence_sets[0]

    assert len(result.start_boundary_evidence_sets) == 1
    assert result.end_boundary_evidence_sets == ()
    assert output.concern is EvidenceConcern.POSSIBLE_SESSION_START
    assert output.purpose is EvidencePurpose.TRANSITION_SUPPORT
    assert output.metadata["semantic_conclusion"] is None
    assert output.metadata["final_boundary_timestamp"] is None
    assert output.metadata["boundary_anchor_seconds"] == 10


def test_compatible_end_signals_group_and_use_latest_anchor() -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    inputs = (
        _source_evidence(
            EvidenceConcern.TRANSCRIPT_CONTINUITY,
            EvidenceSignal.TRANSCRIPT_END_INDICATED,
            offset=100,
            recording_block_id=block_id,
            stage_id=stage_id,
            scheduled_activity_id=activity_id,
            correlation_id=correlation_id,
        ),
        _source_evidence(
            EvidenceConcern.RECORDING_COVERAGE,
            EvidenceSignal.RECORDING_END_INDICATED,
            at=BASE_TIME + timedelta(seconds=20),
            offset=120,
            recording_block_id=block_id,
            stage_id=stage_id,
            scheduled_activity_id=activity_id,
            correlation_id=correlation_id,
        ),
    )

    result = make_session_boundary_evidence_builder().build(inputs)

    assert len(result.end_boundary_evidence_sets) == 1
    assert result.end_boundary_evidence_sets[0].metadata["boundary_anchor_seconds"] == 120
    assert result.end_boundary_evidence_sets[0].metadata["semantic_conclusion"] is None


def test_start_and_end_signals_are_never_grouped_together() -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    start = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )
    end = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.TRANSCRIPT_END_INDICATED,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )

    result = make_session_boundary_evidence_builder().build((start, end))

    assert len(result.start_boundary_evidence_sets) == 1
    assert len(result.end_boundary_evidence_sets) == 1
    assert all(
        evidence_set.concern is EvidenceConcern.POSSIBLE_SESSION_START
        for evidence_set in result.start_boundary_evidence_sets
    )
    assert all(
        evidence_set.concern is EvidenceConcern.POSSIBLE_SESSION_END
        for evidence_set in result.end_boundary_evidence_sets
    )


@pytest.mark.parametrize("dimension", ["stage", "block", "activity"])
def test_different_known_context_dimensions_do_not_merge(dimension: str) -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    changed_id = EntityId.new()
    first = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        correlation_id=correlation_id,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
    )
    second = _source_evidence(
        EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
        EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
        at=BASE_TIME + timedelta(seconds=10),
        offset=20,
        correlation_id=correlation_id,
        recording_block_id=changed_id if dimension == "block" else block_id,
        stage_id=changed_id if dimension == "stage" else stage_id,
        scheduled_activity_id=(
            changed_id if dimension == "activity" else activity_id
        ),
    )

    result = make_session_boundary_evidence_builder().build((first, second))

    assert len(result.start_boundary_evidence_sets) == 2


def test_partial_context_is_supported_and_no_session_identity_is_invented() -> None:
    source = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        recording_block_id=None,
        stage_id=None,
        scheduled_activity_id=None,
    )

    result = make_session_boundary_evidence_builder().build((source,))
    context = result.generated_boundary_contexts[0]

    assert context.recording_block_id is None
    assert context.stage_id is None
    assert context.scheduled_activity_id is None
    assert context.metadata["session_id"] is None
    assert "session_id" not in {field.name for field in fields(SessionBoundaryEvidenceContext)}


def test_stream_and_artifact_references_are_preserved_without_defining_grouping() -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    stream_id = EntityId.new()
    artifact_id = EntityId.new()
    transcript = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        transcript_stream_id=stream_id,
        correlation_id=correlation_id,
    )
    media = _source_evidence(
        EvidenceConcern.MEDIA_AVAILABILITY,
        EvidenceSignal.MEDIA_AVAILABILITY_INDICATED,
        at=BASE_TIME + timedelta(seconds=10),
        offset=20,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        media_artifact_id=artifact_id,
        correlation_id=correlation_id,
    )

    result = make_session_boundary_evidence_builder().build((transcript, media))
    context = result.generated_boundary_contexts[0]

    assert len(result.start_boundary_evidence_sets) == 1
    assert context.transcript_stream_ids == (stream_id.to_json(),)
    assert context.media_artifact_ids == (artifact_id.to_json(),)


def test_existing_non_uuid_stream_and_artifact_ids_remain_traceable() -> None:
    source = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        transcript_stream_id="stream-a",
        media_artifact_id="artifact-123",
    )

    context = make_session_boundary_evidence_builder().build(
        (source,)
    ).generated_boundary_contexts[0]

    assert context.transcript_stream_ids == ("stream-a",)
    assert context.media_artifact_ids == ("artifact-123",)


def test_composition_window_groups_nearby_and_separates_widely_spaced_signals() -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    inputs = tuple(
        _source_evidence(
            EvidenceConcern.TRANSCRIPT_CONTINUITY,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            at=BASE_TIME + timedelta(seconds=offset),
            offset=float(offset),
            recording_block_id=block_id,
            stage_id=stage_id,
            scheduled_activity_id=activity_id,
            correlation_id=correlation_id,
        )
        for offset in (0, 60, 601)
    )

    result = make_session_boundary_evidence_builder().build(inputs)

    assert len(result.start_boundary_evidence_sets) == 2
    assert len(result.start_boundary_evidence_sets[0].items) == 2


def test_missing_timeline_uses_wall_clock_conservatively() -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    first = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        offset=None,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )
    second = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        at=BASE_TIME + timedelta(minutes=10),
        offset=None,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )

    result = make_session_boundary_evidence_builder().build((first, second))

    assert len(result.start_boundary_evidence_sets) == 2
    assert all(
        context.boundary_anchor_seconds is None
        for context in result.generated_boundary_contexts
    )


def test_input_classification_and_duplicate_handling() -> None:
    supported = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
    )
    unsupported = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.VISUAL_OBSTRUCTION_INDICATED,
    )
    ignored = _source_evidence(
        EvidenceConcern.EDITORIAL_MOMENT,
        EvidenceSignal.EDITORIAL_INTEREST_INDICATED,
    )

    result = make_session_boundary_evidence_builder().build(
        (supported, supported, unsupported, ignored)
    )

    assert result.consumed_source_evidence_set_ids == (supported.id,)
    assert result.duplicate_source_evidence_set_ids == (supported.id,)
    assert result.unsupported_source_evidence_set_ids == (unsupported.id,)
    assert result.ignored_source_evidence_set_ids == (ignored.id,)
    assert len(result.start_boundary_evidence_sets[0].signals) == 1


def test_duplicate_signal_references_within_source_do_not_duplicate_output() -> None:
    source = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        duplicate_signal_reference=True,
    )

    result = make_session_boundary_evidence_builder().build((source,))

    assert len(result.start_boundary_evidence_sets[0].signals) == 1
    assert len(result.start_boundary_evidence_sets[0].items) == 1


def test_traceability_strength_and_source_role_are_preserved() -> None:
    source = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        role=EvidenceRole.CONTEXTUALIZES,
        strength=EvidenceStrength.WEAK,
    )

    result = make_session_boundary_evidence_builder().build((source,))
    output = result.start_boundary_evidence_sets[0]
    item = output.items[0]
    reference = output.signals[0]

    assert item.strength is EvidenceStrength.WEAK
    assert item.metadata["source_role"] == EvidenceRole.CONTEXTUALIZES.value
    assert item.metadata["source_evidence_set_id"] == source.id.to_json()
    assert item.metadata["source_evidence_item_id"] == source.items[0].id.to_json()
    assert item.observation_id == source.items[0].observation_id
    assert reference.signal is EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE
    assert reference.metadata["session_boundary_rule_id"] in output.metadata[
        "applied_rule_ids"
    ]


def test_existing_explicit_contradiction_is_preserved_but_absence_creates_none() -> None:
    contradictory = _source_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceSignal.SESSION_END_INDICATED,
        role=EvidenceRole.CONTRADICTS,
        strength=EvidenceStrength.CONTRADICTORY,
    )

    result = make_session_boundary_evidence_builder().build((contradictory,))

    assert result.end_boundary_evidence_sets[0].items[0].role is EvidenceRole.CONTRADICTS
    assert result.end_boundary_evidence_sets[0].items[0].strength is (
        EvidenceStrength.CONTRADICTORY
    )
    assert (
        result.end_boundary_evidence_sets[0].signals[0].metadata[
            "assigned_boundary_role"
        ]
        == EvidenceRole.CONTRADICTS.value
    )
    assert not any(
        item.role is EvidenceRole.CONTRADICTS
        for evidence_set in make_session_boundary_evidence_builder().build(()).evidence_sets
        for item in evidence_set.items
    )


def test_repeated_builds_are_deterministic_and_do_not_mutate_sources() -> None:
    source = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
    )
    builder = make_session_boundary_evidence_builder(builder_id=EntityId.new())
    source_items_before = source.items
    source_signals_before = source.signals

    first = builder.build((source,))
    second = builder.build((source,))

    assert first.evidence_sets == second.evidence_sets
    assert first.generated_boundary_contexts == second.generated_boundary_contexts
    assert first.applied_rule_ids == second.applied_rule_ids
    assert source.items == source_items_before
    assert source.signals == source_signals_before


def test_equal_timestamps_order_by_source_evidence_set_id() -> None:
    block_id, stage_id, activity_id, correlation_id = _shared_context()
    lower_id = EntityId.parse("00000000-0000-0000-0000-000000000001")
    higher_id = EntityId.parse("00000000-0000-0000-0000-000000000002")
    higher = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        evidence_set_id=higher_id,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )
    lower = _source_evidence(
        EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
        EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
        evidence_set_id=lower_id,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )

    result = make_session_boundary_evidence_builder().build((higher, lower))

    assert result.start_boundary_evidence_sets[0].metadata["source_evidence_set_ids"] == (
        lower_id.to_json(),
        higher_id.to_json(),
    )


def test_summary_is_descriptive_without_ranking_or_confidence() -> None:
    source = _source_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
    )
    result = make_session_boundary_evidence_builder().build((source, source))
    summary = SessionBoundaryEvidenceSummary.from_result(result)

    assert summary.total_input_evidence_set_count == 2
    assert summary.consumed_count == 1
    assert summary.duplicate_count == 1
    assert summary.possible_start_evidence_set_count == 1
    assert summary.contributing_signals == (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,)
    assert summary.source_strength_distribution[EvidenceStrength.MODERATE] == 1
    forbidden = {"score", "confidence", "probability", "rank", "recommendation"}
    assert not any(term in field.name for field in fields(summary) for term in forbidden)


def test_contracts_are_immutable_and_id_only() -> None:
    context = SessionBoundaryEvidenceContext(
        id=EntityId.new(),
        boundary_concern=EvidenceConcern.POSSIBLE_SESSION_START,
    )
    with pytest.raises(FrozenInstanceError):
        context.context_label = "changed"  # type: ignore[misc]

    field_names = {field.name for field in fields(SessionBoundaryEvidenceContext)}
    assert "recording_block" not in field_names
    assert "stage" not in field_names
    assert "scheduled_activity" not in field_names
    assert "transcript_streams" not in field_names
    assert "media_artifacts" not in field_names


def test_builder_has_no_downstream_or_runtime_dependencies() -> None:
    package = (
        Path(__file__).parents[1]
        / "app"
        / "contexts"
        / "production"
        / "session_boundary_evidence_builder"
    )
    implementation = (package / "session_boundary_evidence_builder.py").read_text()
    forbidden_imports = (
        "production_event",
        "observation import",
        "transition_policy",
        "operational_state",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "repository",
        "queue",
        "worker",
        "fastapi",
    )

    assert not any(term in implementation.lower() for term in forbidden_imports)
    builder_fields = {field.name for field in fields(SessionBoundaryEvidenceBuilder)}
    assert not builder_fields.intersection(
        {"model", "repository", "policy", "state", "queue", "worker"}
    )
    assert len(SESSION_BOUNDARY_EVIDENCE_MAPPINGS) > 0
