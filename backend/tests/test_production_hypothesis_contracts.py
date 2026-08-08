from dataclasses import fields

import pytest

from app.contexts.production.hypothesis import (
    Hypothesis,
    HypothesisConfidence,
    HypothesisStatus,
    HypothesisSupport,
    HypothesisType,
)
from app.shared.ids import CorrelationId, EntityId
from tests.timestamp_fixtures import AWARE_TIMESTAMP


def _support() -> HypothesisSupport:
    return HypothesisSupport(supporting_evidence_set_ids=[EntityId.new()])


def test_hypothesis_creation() -> None:
    hypothesis = Hypothesis(
                     created_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        hypothesis_type=HypothesisType.POSSIBLE_TRANSITION,
        hypothesis_status=HypothesisStatus.ACTIVE,
        confidence=HypothesisConfidence(0.62),
        support=_support(),
        correlation_id=CorrelationId.new(),
        notes="Potential transition region.",
        metadata={"reason": "nearby support"},
    )

    assert hypothesis.hypothesis_type is HypothesisType.POSSIBLE_TRANSITION
    assert hypothesis.hypothesis_status is HypothesisStatus.ACTIVE
    assert hypothesis.confidence.value == 0.62
    assert hypothesis.support.supporting_count == 1
    assert dict(hypothesis.metadata) == {"reason": "nearby support"}


def test_hypothesis_type_allowed_values() -> None:
    assert {hypothesis_type.value for hypothesis_type in HypothesisType} == {
        "possible_session_start",
        "possible_session_end",
        "possible_transition",
        "possible_schedule_conflict",
        "possible_recording_anomaly",
        "general_context",
        "unknown",
    }


def test_hypothesis_status_allowed_values() -> None:
    assert {status.value for status in HypothesisStatus} == {
        "draft",
        "active",
        "superseded",
        "dismissed",
        "archived",
    }


def test_hypothesis_confidence_accepts_bounds() -> None:
    assert HypothesisConfidence(0.0).value == 0.0
    assert HypothesisConfidence(1.0).value == 1.0


def test_hypothesis_confidence_rejects_below_zero() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        HypothesisConfidence(-0.01)


def test_hypothesis_confidence_rejects_above_one() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        HypothesisConfidence(1.01)


def test_hypothesis_support_references_evidence_set_ids_only() -> None:
    supporting_id = EntityId.new()
    contradicting_id = EntityId.new()
    neutral_id = EntityId.new()
    support = HypothesisSupport(
        supporting_evidence_set_ids=[supporting_id],
        contradicting_evidence_set_ids=[contradicting_id],
        neutral_evidence_set_ids=[neutral_id],
    )

    assert support.supporting_evidence_set_ids == (supporting_id,)
    assert support.contradicting_evidence_set_ids == (contradicting_id,)
    assert support.neutral_evidence_set_ids == (neutral_id,)
    assert "evidence_sets" not in {field.name for field in fields(HypothesisSupport)}


def test_hypothesis_support_counts_supporting_evidence() -> None:
    support = HypothesisSupport(
        supporting_evidence_set_ids=[EntityId.new(), EntityId.new()],
    )

    assert support.supporting_count == 2
    assert support.total_count == 2


def test_hypothesis_support_counts_contradicting_evidence() -> None:
    support = HypothesisSupport(
        supporting_evidence_set_ids=[EntityId.new()],
        contradicting_evidence_set_ids=[EntityId.new(), EntityId.new()],
        neutral_evidence_set_ids=[EntityId.new()],
    )

    assert support.contradicting_count == 2
    assert support.neutral_count == 1
    assert support.total_count == 4


def test_hypothesis_can_represent_possible_session_start() -> None:
    hypothesis = Hypothesis(
                     created_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        hypothesis_type=HypothesisType.POSSIBLE_SESSION_START,
        hypothesis_status=HypothesisStatus.DRAFT,
        confidence=HypothesisConfidence(0.5),
        support=_support(),
        correlation_id=CorrelationId.new(),
    )

    assert hypothesis.hypothesis_type is HypothesisType.POSSIBLE_SESSION_START


def test_hypothesis_can_represent_possible_session_end() -> None:
    hypothesis = Hypothesis(
                     created_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        hypothesis_type=HypothesisType.POSSIBLE_SESSION_END,
        hypothesis_status=HypothesisStatus.ACTIVE,
        confidence=HypothesisConfidence(0.58),
        support=_support(),
        correlation_id=CorrelationId.new(),
    )

    assert hypothesis.hypothesis_type is HypothesisType.POSSIBLE_SESSION_END


def test_non_general_hypothesis_requires_evidence_reference() -> None:
    with pytest.raises(ValueError, match="requires at least one EvidenceSet reference"):
        Hypothesis(
            created_at=AWARE_TIMESTAMP,

            id=EntityId.new(),
            recording_block_id=EntityId.new(),
            hypothesis_type=HypothesisType.POSSIBLE_RECORDING_ANOMALY,
            hypothesis_status=HypothesisStatus.DRAFT,
            confidence=HypothesisConfidence(0.2),
            support=HypothesisSupport(),
            correlation_id=CorrelationId.new(),
        )


def test_general_hypothesis_may_have_no_evidence_reference() -> None:
    hypothesis = Hypothesis(
                     created_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        hypothesis_type=HypothesisType.GENERAL_CONTEXT,
        hypothesis_status=HypothesisStatus.DRAFT,
        confidence=HypothesisConfidence(0.0),
        support=HypothesisSupport(),
        correlation_id=CorrelationId.new(),
    )

    assert hypothesis.support.total_count == 0


def test_hypothesis_does_not_create_actionable_outputs() -> None:
    field_names = {field.name for field in fields(Hypothesis)}
    forbidden_terms = {
        "proposal",
        "window",
        "verification",
        "action",
        "workflow",
    }

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_provider_specific_names_appear_in_hypothesis_contracts() -> None:
    enum_values = {item.value for item in HypothesisType} | {
        item.value for item in HypothesisStatus
    }
    field_names = {field.name for field in fields(Hypothesis)} | {
        field.name for field in fields(HypothesisSupport)
    }
    forbidden_terms = {
        "provider",
        "vendor",
        "tool",
        "brand",
        "conference",
    }

    assert not any(term in value for value in enum_values | field_names for term in forbidden_terms)


def test_no_confirmed_conclusion_names_appear() -> None:
    enum_values = {item.value for item in HypothesisType} | {
        item.value for item in HypothesisStatus
    }
    forbidden_terms = {
        "confirmed",
        "verified",
        "decided",
        "generated",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
