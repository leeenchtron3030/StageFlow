from dataclasses import fields
from datetime import UTC, datetime
from inspect import getmembers, isfunction

from app.contexts.production.evidence import EvidencePurpose, EvidenceSet, EvidenceStrength
from app.contexts.production.evidence_builder import (
    EvidenceBuilderContext,
    EvidenceBuilderResult,
    EvidenceBuilderRule,
    EvidenceBuilderStatus,
    EvidenceBuilderSummary,
    ObservationEvidenceBuilder,
    make_default_observation_evidence_builder,
)
from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.shared.ids import CorrelationId, EntityId


def _context(recording_block_id: EntityId | None = None) -> EvidenceBuilderContext:
    return EvidenceBuilderContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        recording_block_id=recording_block_id,
    )


def _observation(
    observation_type: ObservationType,
    *,
    recording_block_id: EntityId | None = None,
    metadata: dict[str, object] | None = None,
) -> Observation:
    location = (
        ObservationLocation.for_recording_block(recording_block_id)
        if recording_block_id is not None
        else ObservationLocation.at_wall_clock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    )
    return Observation(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        observation_type=observation_type,
        observation_source=ObservationSource.SYSTEM,
        location=location,
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        metadata=metadata or {},
        notes=f"{observation_type.value} observed.",
    )


def _builder(*rules: EvidenceBuilderRule) -> ObservationEvidenceBuilder:
    return ObservationEvidenceBuilder(
        id=EntityId.new(),
        name="Observation Evidence Builder",
        rules=rules,
    )


def test_observation_evidence_builder_creation() -> None:
    builder = make_default_observation_evidence_builder()

    assert builder.name == "Observation Evidence Builder"
    assert builder.status is EvidenceBuilderStatus.READY
    assert builder.can_build()
    assert builder.rules


def test_builder_returns_zero_evidence_for_zero_observation_input() -> None:
    builder = make_default_observation_evidence_builder()

    result = builder.build((), _context())

    assert isinstance(result, EvidenceBuilderResult)
    assert result.evidence_count == 0
    assert result.source_observation_ids == ()
    assert result.warnings == ("No Observations were provided.",)


def test_builder_groups_single_observation_into_evidence() -> None:
    recording_block_id = EntityId.new()
    observation = _observation(
        ObservationType.RECORDING_ACTIVITY,
        recording_block_id=recording_block_id,
    )
    builder = make_default_observation_evidence_builder()

    result = builder.build((observation,), _context())

    assert result.evidence_count == 1
    evidence = result.evidence_sets[0]
    assert isinstance(evidence, EvidenceSet)
    assert evidence.recording_block_id == recording_block_id
    assert evidence.purpose is EvidencePurpose.GENERAL_CONTEXT
    assert evidence.metadata["operational_concern"] == "recording_activity"
    assert evidence.items[0].observation_id == observation.id
    assert evidence.items[0].strength is EvidenceStrength.MODERATE


def test_builder_groups_multiple_observations_by_independent_concern() -> None:
    recording_observation = _observation(ObservationType.RECORDING_ACTIVITY)
    transcript_observation = _observation(ObservationType.TRANSCRIPT_ACTIVITY)
    vision_observation = _observation(ObservationType.VISION_ACTIVITY)
    builder = make_default_observation_evidence_builder()

    result = builder.build(
        (recording_observation, transcript_observation, vision_observation),
        _context(),
    )

    concerns = {
        evidence.metadata["operational_concern"] for evidence in result.evidence_sets
    }
    assert result.evidence_count == 3
    assert concerns == {"recording_activity", "transcript_activity", "vision_activity"}


def test_builder_may_leave_observations_ungrouped() -> None:
    observation = _observation(ObservationType.UNKNOWN)
    builder = make_default_observation_evidence_builder()

    result = builder.build((observation,), _context())

    assert result.evidence_sets == ()
    assert result.warnings == ("Some Observations did not match an EvidenceBuilderRule.",)
    assert result.metadata["ungrouped_observation_ids"] == (observation.id.to_json(),)


def test_builder_attaches_supporting_contradicting_and_contextual_references() -> None:
    supporting = _observation(ObservationType.RECORDING_ACTIVITY)
    contradicting = _observation(ObservationType.TRANSCRIPT_ACTIVITY)
    contextual = _observation(ObservationType.SCHEDULE_ACTIVITY)
    rule = EvidenceBuilderRule(
        id=EntityId.new(),
        operational_concern="recording_activity",
        supporting_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        contradicting_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
        contextual_observation_types=(ObservationType.SCHEDULE_ACTIVITY,),
    )
    builder = _builder(rule)

    result = builder.build((supporting, contradicting, contextual), _context())

    evidence = result.evidence_sets[0]
    assert evidence.metadata["supporting_observation_ids"] == (supporting.id.to_json(),)
    assert evidence.metadata["contradicting_observation_ids"] == (
        contradicting.id.to_json(),
    )
    assert evidence.metadata["contextual_observation_ids"] == (contextual.id.to_json(),)
    strengths_by_observation = {
        item.observation_id: item.strength for item in evidence.items
    }
    assert strengths_by_observation[supporting.id] is EvidenceStrength.MODERATE
    assert strengths_by_observation[contradicting.id] is EvidenceStrength.CONTRADICTORY
    assert strengths_by_observation[contextual.id] is EvidenceStrength.UNKNOWN


def test_contradictory_observations_remain_attached() -> None:
    supporting = _observation(ObservationType.SCHEDULE_ACTIVITY)
    contradicting = _observation(ObservationType.TRANSCRIPT_ACTIVITY)
    rule = EvidenceBuilderRule(
        id=EntityId.new(),
        operational_concern="scheduled_activity",
        supporting_observation_types=(ObservationType.SCHEDULE_ACTIVITY,),
        contradicting_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
    )
    builder = _builder(rule)

    evidence = builder.build((supporting, contradicting), _context()).evidence_sets[0]

    assert len(evidence.items) == 2
    assert evidence.metadata["supporting_observation_ids"]
    assert evidence.metadata["contradicting_observation_ids"]


def test_builder_preserves_observation_traceability() -> None:
    source_event_id = EntityId.new()
    observation = _observation(
        ObservationType.MEDIA_ARTIFACT,
        metadata={"source_production_event_ids": (source_event_id.to_json(),)},
    )
    builder = make_default_observation_evidence_builder()

    evidence = builder.build((observation,), _context()).evidence_sets[0]

    assert evidence.items[0].metadata["source_production_event_ids"] == (
        source_event_id.to_json(),
    )
    assert evidence.metadata["observation_traceability"] == {
        observation.id.to_json(): (source_event_id.to_json(),)
    }


def test_evidence_explains_concern_roles_and_observations() -> None:
    observation = _observation(ObservationType.VISION_ACTIVITY)
    builder = make_default_observation_evidence_builder()

    evidence = builder.build((observation,), _context()).evidence_sets[0]

    assert evidence.notes == "Evidence organized for operational concern: vision_activity."
    assert evidence.metadata["operational_concern"] == "vision_activity"
    assert evidence.metadata["supporting_observation_ids"] == (observation.id.to_json(),)
    assert evidence.items[0].metadata["evidence_role"] == "supporting"
    assert evidence.items[0].rationale is not None


def test_evidence_builder_context_creation() -> None:
    recording_block_id = EntityId.new()
    context = _context(recording_block_id)

    assert context.recording_block_id == recording_block_id
    assert context.current_timestamp.tzinfo is UTC


def test_evidence_builder_rule_requires_one_operational_concern() -> None:
    rule = EvidenceBuilderRule(
        id=EntityId.new(),
        operational_concern="transcript_activity",
        supporting_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
    )

    assert rule.role_for(ObservationType.TRANSCRIPT_ACTIVITY) == "supporting"
    assert rule.role_for(ObservationType.VISION_ACTIVITY) is None


def test_evidence_builder_summary_generation() -> None:
    builder = make_default_observation_evidence_builder()

    summary = EvidenceBuilderSummary.from_builder(builder)

    assert summary.builder_id == builder.id
    assert summary.builder_name == builder.name
    assert summary.rule_count == len(builder.rules)
    assert summary.operational_concern_count == len(builder.rules)


def test_evidence_set_can_represent_non_recording_block_observations() -> None:
    observation = _observation(ObservationType.TIME_BOUNDARY)
    builder = make_default_observation_evidence_builder()

    evidence = builder.build((observation,), _context()).evidence_sets[0]

    assert evidence.recording_block_id is None
    assert evidence.metadata["operational_concern"] == "time_boundary"


def test_builder_does_not_create_later_reasoning_artifacts() -> None:
    builder_fields = {field.name for field in fields(ObservationEvidenceBuilder)}
    result_fields = {field.name for field in fields(EvidenceBuilderResult)}
    method_names = {
        name
        for name, value in getmembers(ObservationEvidenceBuilder)
        if isfunction(value)
    }
    forbidden_terms = {
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "operational_state",
    }

    assert not any(
        term in name
        for name in builder_fields | result_fields | method_names
        for term in forbidden_terms
    )


def test_builder_remains_backend_only_and_provider_agnostic() -> None:
    metadata = {
        field.name
        for contract in (
            ObservationEvidenceBuilder,
            EvidenceBuilderRule,
            EvidenceBuilderContext,
            EvidenceBuilderResult,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "api",
        "queue",
        "worker",
        "provider",
        "whisper",
        "deepgram",
        "assemblyai",
        "pretalx",
        "vmix",
        "frontend",
        "model",
    }

    assert not any(term in name for name in metadata for term in forbidden_terms)


def test_builder_does_not_generate_semantic_conclusions() -> None:
    observation = _observation(ObservationType.RECORDING_ACTIVITY)
    builder = make_default_observation_evidence_builder()

    evidence = builder.build((observation,), _context()).evidence_sets[0]

    assert evidence.metadata["semantic_conclusion"] is None
    assert "session started" not in (evidence.notes or "").lower()
    assert "clip" not in (evidence.notes or "").lower()
    assert "package" not in (evidence.notes or "").lower()
