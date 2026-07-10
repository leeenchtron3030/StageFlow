from dataclasses import fields

import pytest

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidenceObservationReference,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
    EvidenceStrength,
    EvidenceSummary,
)
from app.shared.ids import CorrelationId, EntityId


def _item(strength: EvidenceStrength = EvidenceStrength.MODERATE) -> EvidenceItem:
    return EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=strength,
    )


def test_evidence_item_creation() -> None:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=EvidenceStrength.STRONG,
    )

    assert item.strength is EvidenceStrength.STRONG
    assert item.role is EvidenceRole.UNKNOWN
    assert item.weight is None
    assert item.rationale is None
    assert dict(item.metadata) == {}


def test_evidence_item_references_an_observation_id() -> None:
    observation_id = EntityId.new()
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=observation_id,
        strength=EvidenceStrength.WEAK,
    )

    assert item.observation_id == observation_id
    assert "observation" not in {
        field.name for field in fields(EvidenceItem) if field.name != "observation_id"
    }


def test_evidence_item_accepts_optional_rationale() -> None:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=EvidenceStrength.MODERATE,
        rationale="Several nearby observations support this purpose.",
    )

    assert item.rationale == "Several nearby observations support this purpose."


def test_evidence_item_exposes_observation_reference() -> None:
    observation_id = EntityId.new()
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=observation_id,
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        rationale="Observation supports the concern.",
    )

    reference = item.observation_reference

    assert isinstance(reference, EvidenceObservationReference)
    assert reference.observation_id == observation_id
    assert reference.role is EvidenceRole.SUPPORTS
    assert reference.strength is EvidenceStrength.STRONG


def test_evidence_item_accepts_optional_weight() -> None:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=EvidenceStrength.STRONG,
        weight=0.7,
    )

    assert item.weight == 0.7


def test_evidence_item_rejects_invalid_weight() -> None:
    with pytest.raises(ValueError, match="weight"):
        EvidenceItem(
            id=EntityId.new(),
            observation_id=EntityId.new(),
            strength=EvidenceStrength.UNKNOWN,
            weight=1.1,
        )


def test_evidence_strength_allowed_values() -> None:
    assert {strength.value for strength in EvidenceStrength} == {
        "weak",
        "moderate",
        "strong",
        "contradictory",
        "unknown",
    }


def test_evidence_purpose_allowed_values() -> None:
    assert {purpose.value for purpose in EvidencePurpose} == {
        "operational_context",
        "transition_support",
        "historical_explanation",
        "reasoning_input",
        "review_support",
        "potential_session_start",
        "potential_session_end",
        "potential_session_continuation",
        "potential_transition",
        "potential_schedule_conflict",
        "general_context",
        "unknown",
    }


def test_evidence_set_requires_at_least_one_evidence_item() -> None:
    with pytest.raises(ValueError, match="at least one"):
        EvidenceSet(
            id=EntityId.new(),
            recording_block_id=EntityId.new(),
            purpose=EvidencePurpose.GENERAL_CONTEXT,
            items=[],
            correlation_id=CorrelationId.new(),
        )


def test_evidence_set_uses_generic_entity_id_and_correlation_id() -> None:
    evidence_set_id = EntityId.new()
    recording_block_id = EntityId.new()
    correlation_id = CorrelationId.new()
    evidence_set = EvidenceSet(
        id=evidence_set_id,
        recording_block_id=recording_block_id,
        concern=EvidenceConcern.POSSIBLE_SESSION_START,
        purpose=EvidencePurpose.POTENTIAL_TRANSITION,
        items=[_item()],
        correlation_id=correlation_id,
    )

    assert evidence_set.id == evidence_set_id
    assert evidence_set.recording_block_id == recording_block_id
    assert evidence_set.concern is EvidenceConcern.POSSIBLE_SESSION_START
    assert evidence_set.correlation_id == correlation_id
    assert isinstance(evidence_set.items, tuple)


def test_evidence_set_does_not_create_windows_or_proposals() -> None:
    field_names = {field.name for field in fields(EvidenceSet)}
    forbidden_terms = {"proposal", "window", "verification", "decision"}

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_evidence_summary_counts_evidence_items() -> None:
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        purpose=EvidencePurpose.POTENTIAL_SESSION_START,
        items=[
            _item(EvidenceStrength.STRONG),
            _item(EvidenceStrength.MODERATE),
            _item(EvidenceStrength.STRONG),
        ],
        correlation_id=CorrelationId.new(),
    )

    summary = EvidenceSummary.from_evidence_set(evidence_set)

    assert summary.total_item_count == 3
    assert summary.concern is EvidenceConcern.UNKNOWN
    assert summary.count_by_strength[EvidenceStrength.STRONG] == 2
    assert summary.count_by_strength[EvidenceStrength.MODERATE] == 1
    assert summary.strongest_strength is EvidenceStrength.STRONG


def test_evidence_summary_counts_contradictory_evidence() -> None:
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        purpose=EvidencePurpose.POTENTIAL_SCHEDULE_CONFLICT,
        items=[
            _item(EvidenceStrength.CONTRADICTORY),
            _item(EvidenceStrength.WEAK),
            _item(EvidenceStrength.CONTRADICTORY),
        ],
        correlation_id=CorrelationId.new(),
    )

    summary = EvidenceSummary.from_evidence_set(evidence_set)

    assert summary.contradictory_count == 2


def test_evidence_summary_counts_roles() -> None:
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        concern=EvidenceConcern.RECORDING_COVERAGE,
        purpose=EvidencePurpose.OPERATIONAL_CONTEXT,
        items=[
            EvidenceItem(
                id=EntityId.new(),
                observation_id=EntityId.new(),
                role=EvidenceRole.SUPPORTS,
                strength=EvidenceStrength.MODERATE,
            ),
            EvidenceItem(
                id=EntityId.new(),
                observation_id=EntityId.new(),
                role=EvidenceRole.CONTRADICTS,
                strength=EvidenceStrength.CONTRADICTORY,
            ),
            EvidenceItem(
                id=EntityId.new(),
                observation_id=EntityId.new(),
                role=EvidenceRole.CONTEXTUALIZES,
                strength=EvidenceStrength.UNKNOWN,
            ),
            EvidenceItem(
                id=EntityId.new(),
                observation_id=EntityId.new(),
                role=EvidenceRole.NEUTRAL,
                strength=EvidenceStrength.UNKNOWN,
            ),
        ],
        correlation_id=CorrelationId.new(),
    )

    summary = EvidenceSummary.from_evidence_set(evidence_set)

    assert summary.supporting_count == 1
    assert summary.contradicting_count == 1
    assert summary.contextual_count == 1
    assert summary.neutral_count == 1


def test_evidence_summary_reports_signals() -> None:
    first_item = _item(EvidenceStrength.STRONG)
    second_item = _item(EvidenceStrength.MODERATE)
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        concern=EvidenceConcern.RECORDING_COVERAGE,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(first_item, second_item),
        signals=(
            EvidenceSignalReference(
                signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
                evidence_item_ids=(first_item.id, second_item.id),
                observation_ids=(first_item.observation_id, second_item.observation_id),
            ),
        ),
        correlation_id=CorrelationId.new(),
    )

    summary = EvidenceSummary.from_evidence_set(evidence_set)

    assert summary.signal_count == 1
    assert summary.signals == (EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,)
    assert (
        summary.item_count_by_signal[EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED]
        == 2
    )


def test_evidence_summary_does_not_produce_decision_metric() -> None:
    summary_fields = {field.name for field in fields(EvidenceSummary)}
    forbidden_decision_metric = "_".join(("final", "confidence"))
    forbidden_ranking_metric = "".join(("sc", "ore"))

    assert "confidence" not in summary_fields
    assert forbidden_ranking_metric not in summary_fields
    assert not hasattr(EvidenceSummary, forbidden_decision_metric)


def test_no_conclusion_oriented_names_are_present_in_evidence_implementation() -> None:
    purpose_values = {purpose.value for purpose in EvidencePurpose}
    field_names = {
        field.name
        for contract in (EvidenceItem, EvidenceSet, EvidenceSummary)
        for field in fields(contract)
    }
    forbidden_terms = {
        "confirmed",
        "decided",
        "verified",
        "generated",
        "final",
        "".join(("sc", "ore")),
    }

    assert not any(
        term in value
        for value in purpose_values | field_names
        for term in forbidden_terms
    )
