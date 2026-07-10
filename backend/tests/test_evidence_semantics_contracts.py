from dataclasses import fields, replace
from datetime import UTC, datetime
from inspect import getmembers, isfunction

import pytest

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidenceObservationReference,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceStrength,
    EvidenceSummary,
)
from app.contexts.production.evidence_builder import (
    EvidenceBuilderContext,
    EvidenceBuilderRule,
    ObservationEvidenceBuilder,
)
from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.shared.ids import CorrelationId, EntityId


def _context() -> EvidenceBuilderContext:
    return EvidenceBuilderContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def _observation(observation_type: ObservationType) -> Observation:
    return Observation(
        id=EntityId.new(),
        recording_block_id=None,
        observation_type=observation_type,
        observation_source=ObservationSource.SYSTEM,
        location=ObservationLocation.at_wall_clock(
            datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        ),
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def _builder(*rules: EvidenceBuilderRule) -> ObservationEvidenceBuilder:
    return ObservationEvidenceBuilder(
        id=EntityId.new(),
        name="Semantic Evidence Builder",
        rules=rules,
    )


def test_evidence_concern_allowed_values() -> None:
    assert {concern.value for concern in EvidenceConcern} == {
        "recording_coverage",
        "media_availability",
        "possible_session_start",
        "possible_session_end",
        "transcript_continuity",
        "schedule_alignment",
        "visual_transition_context",
        "editorial_moment",
        "package_preparation",
        "unknown",
    }


def test_evidence_role_allowed_values() -> None:
    assert {role.value for role in EvidenceRole} == {
        "supports",
        "contradicts",
        "contextualizes",
        "neutral",
        "unknown",
    }


def test_evidence_observation_reference_creation_uses_id_only() -> None:
    observation_id = EntityId.new()

    reference = EvidenceObservationReference(
        observation_id=observation_id,
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        weight=0.7,
        rationale="Observation supports recording coverage.",
    )

    assert reference.observation_id == observation_id
    assert reference.role is EvidenceRole.SUPPORTS
    assert reference.strength is EvidenceStrength.STRONG
    assert not any(field.name == "observation" for field in fields(reference))


def test_evidence_observation_reference_rejects_invalid_weight() -> None:
    with pytest.raises(ValueError, match="weight"):
        EvidenceObservationReference(
            observation_id=EntityId.new(),
            role=EvidenceRole.NEUTRAL,
            weight=1.1,
        )


def test_evidence_item_compatibility_and_first_class_role() -> None:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=EvidenceStrength.MODERATE,
    )

    assert item.role is EvidenceRole.UNKNOWN
    assert item.observation_reference.role is EvidenceRole.UNKNOWN


def test_evidence_set_has_explicit_concern_and_purpose() -> None:
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=None,
        concern=EvidenceConcern.RECORDING_COVERAGE,
        purpose=EvidencePurpose.OPERATIONAL_CONTEXT,
        items=[
            EvidenceItem(
                id=EntityId.new(),
                observation_id=EntityId.new(),
                role=EvidenceRole.SUPPORTS,
                strength=EvidenceStrength.MODERATE,
            )
        ],
        correlation_id=CorrelationId.new(),
    )

    assert evidence_set.concern is EvidenceConcern.RECORDING_COVERAGE
    assert evidence_set.purpose is EvidencePurpose.OPERATIONAL_CONTEXT
    assert evidence_set.concern is not EvidenceConcern.POSSIBLE_SESSION_START


def test_mixed_roles_coexist_in_one_evidence_set() -> None:
    support = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    contradiction = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.CONTRADICTS,
        strength=EvidenceStrength.CONTRADICTORY,
    )
    context = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.CONTEXTUALIZES,
        strength=EvidenceStrength.UNKNOWN,
    )
    neutral = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.NEUTRAL,
        strength=EvidenceStrength.UNKNOWN,
    )

    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=None,
        concern=EvidenceConcern.POSSIBLE_SESSION_START,
        purpose=EvidencePurpose.REASONING_INPUT,
        items=[support, contradiction, context, neutral],
        correlation_id=CorrelationId.new(),
    )

    assert support in evidence_set.items
    assert contradiction in evidence_set.items
    assert context in evidence_set.items
    assert neutral in evidence_set.items


def test_evidence_summary_reports_role_counts_and_concern() -> None:
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=None,
        concern=EvidenceConcern.POSSIBLE_SESSION_START,
        purpose=EvidencePurpose.REASONING_INPUT,
        items=[
            EvidenceItem(
                id=EntityId.new(),
                observation_id=EntityId.new(),
                role=EvidenceRole.SUPPORTS,
                strength=EvidenceStrength.STRONG,
            ),
            EvidenceItem(
                id=EntityId.new(),
                observation_id=EntityId.new(),
                role=EvidenceRole.CONTRADICTS,
                strength=EvidenceStrength.CONTRADICTORY,
            ),
        ],
        correlation_id=CorrelationId.new(),
    )

    summary = EvidenceSummary.from_evidence_set(evidence_set)

    assert summary.concern is EvidenceConcern.POSSIBLE_SESSION_START
    assert summary.purpose is EvidencePurpose.REASONING_INPUT
    assert summary.supporting_count == 1
    assert summary.contradicting_count == 1
    assert summary.strongest_strength is EvidenceStrength.STRONG


def test_recording_coverage_reference_scenario() -> None:
    observation = _observation(ObservationType.RECORDING_ACTIVITY)
    rule = EvidenceBuilderRule(
        id=EntityId.new(),
        operational_concern=EvidenceConcern.RECORDING_COVERAGE,
        evidence_purpose=EvidencePurpose.OPERATIONAL_CONTEXT,
        supporting_observation_types=(ObservationType.RECORDING_ACTIVITY,),
    )
    builder = _builder(rule)

    evidence = builder.build((observation,), _context()).evidence_sets[0]

    assert evidence.concern is EvidenceConcern.RECORDING_COVERAGE
    assert evidence.purpose is EvidencePurpose.OPERATIONAL_CONTEXT
    assert evidence.items[0].role is EvidenceRole.SUPPORTS
    assert evidence.metadata["semantic_conclusion"] is None


def test_possible_session_start_with_mixed_roles_remains_below_conclusion() -> None:
    schedule = _observation(ObservationType.SCHEDULE_ACTIVITY)
    vision = _observation(ObservationType.VISION_ACTIVITY)
    transcript = _observation(ObservationType.TRANSCRIPT_ACTIVITY)
    rule = EvidenceBuilderRule(
        id=EntityId.new(),
        operational_concern=EvidenceConcern.POSSIBLE_SESSION_START,
        evidence_purpose=EvidencePurpose.REASONING_INPUT,
        supporting_observation_types=(ObservationType.VISION_ACTIVITY,),
        contextual_observation_types=(ObservationType.SCHEDULE_ACTIVITY,),
        neutral_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
    )
    builder = _builder(rule)

    evidence = builder.build((schedule, vision, transcript), _context()).evidence_sets[0]

    roles = {item.observation_id: item.role for item in evidence.items}
    assert roles[schedule.id] is EvidenceRole.CONTEXTUALIZES
    assert roles[vision.id] is EvidenceRole.SUPPORTS
    assert roles[transcript.id] is EvidenceRole.NEUTRAL
    assert "session started" not in (evidence.notes or "").lower()


def test_contradiction_does_not_remove_support() -> None:
    host_intro = _observation(ObservationType.TRANSCRIPT_ACTIVITY)
    expected_speaker_missing = _observation(ObservationType.UNKNOWN)
    rule = EvidenceBuilderRule(
        id=EntityId.new(),
        operational_concern=EvidenceConcern.POSSIBLE_SESSION_START,
        evidence_purpose=EvidencePurpose.REASONING_INPUT,
        supporting_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
        contradicting_observation_types=(ObservationType.UNKNOWN,),
    )
    builder = _builder(rule)

    evidence = builder.build((host_intro, expected_speaker_missing), _context()).evidence_sets[0]
    roles = {item.observation_id: item.role for item in evidence.items}

    assert roles[host_intro.id] is EvidenceRole.SUPPORTS
    assert roles[expected_speaker_missing.id] is EvidenceRole.CONTRADICTS
    assert len(evidence.items) == 2


def test_observation_reused_across_multiple_concerns_without_mutation() -> None:
    observation = _observation(ObservationType.RECORDING_ACTIVITY)
    original_observation = replace(observation)
    builder = _builder(
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern=EvidenceConcern.RECORDING_COVERAGE,
            supporting_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        ),
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern=EvidenceConcern.POSSIBLE_SESSION_START,
            supporting_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        ),
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern=EvidenceConcern.PACKAGE_PREPARATION,
            contextual_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        ),
    )

    result = builder.build((observation,), _context())

    assert {evidence.concern for evidence in result.evidence_sets} == {
        EvidenceConcern.RECORDING_COVERAGE,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceConcern.PACKAGE_PREPARATION,
    }
    assert observation == original_observation


def test_concern_purpose_role_strength_and_weight_remain_distinct() -> None:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.WEAK,
        weight=0.2,
    )
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=None,
        concern=EvidenceConcern.MEDIA_AVAILABILITY,
        purpose=EvidencePurpose.HISTORICAL_EXPLANATION,
        items=[item],
        correlation_id=CorrelationId.new(),
    )

    assert evidence_set.concern is EvidenceConcern.MEDIA_AVAILABILITY
    assert evidence_set.purpose is EvidencePurpose.HISTORICAL_EXPLANATION
    assert item.role is EvidenceRole.SUPPORTS
    assert item.strength is EvidenceStrength.WEAK
    assert item.weight == 0.2


def test_metadata_is_not_required_for_core_evidence_semantics() -> None:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.MODERATE,
    )
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=None,
        concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
        purpose=EvidencePurpose.REVIEW_SUPPORT,
        items=[item],
        correlation_id=CorrelationId.new(),
    )

    assert dict(item.metadata) == {}
    assert dict(evidence_set.metadata) == {}
    assert evidence_set.concern is EvidenceConcern.TRANSCRIPT_CONTINUITY
    assert item.role is EvidenceRole.SUPPORTS


def test_no_downstream_or_infrastructure_behavior_exists() -> None:
    contracts = (
        EvidenceObservationReference,
        EvidenceItem,
        EvidenceSet,
        EvidenceSummary,
        EvidenceBuilderRule,
        ObservationEvidenceBuilder,
    )
    names = {
        field.name
        for contract in contracts
        for field in fields(contract)
    } | {
        name
        for name, value in getmembers(ObservationEvidenceBuilder)
        if isfunction(value)
    }
    forbidden_terms = {
        "operational_state",
        "hypothesis",
        "finding",
        "verification_decision",
        "operational_product",
        "confidence_formula",
        "api",
        "persistence",
        "queue",
        "worker",
        "frontend",
        "provider",
        "ai",
    }

    assert not any(term in name for name in names for term in forbidden_terms)
