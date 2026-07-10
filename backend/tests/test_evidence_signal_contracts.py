from dataclasses import fields

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
from app.shared.ids import CorrelationId, EntityId


def _item(observation_id: EntityId | None = None) -> EvidenceItem:
    return EvidenceItem(
        id=EntityId.new(),
        observation_id=observation_id or EntityId.new(),
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.MODERATE,
    )


def test_evidence_signal_allowed_values() -> None:
    assert {signal.value for signal in EvidenceSignal} == {
        "recording_continuity_established",
        "recording_pause_indicated",
        "recording_continuity_restored",
        "recording_end_indicated",
        "media_availability_indicated",
        "media_finalization_indicated",
        "media_failure_indicated",
        "scheduled_window_active",
        "scheduled_activity_changed",
        "scheduled_activity_cancelled",
        "speech_activity_available",
        "transcript_continuity_indicated",
        "visual_activity_available",
        "presentation_transition_indicated",
        "visual_obstruction_indicated",
        "operator_attention_indicated",
        "speaker_introduction_indicated",
        "session_content_indicated",
        "session_end_indicated",
        "editorial_interest_indicated",
        "package_inputs_available",
        "unknown",
    }


def test_evidence_signal_rejects_invalid_operational_state_name() -> None:
    with pytest.raises(ValueError):
        EvidenceSignal("recording_active")


def test_evidence_signal_reference_creation() -> None:
    evidence_item_id = EntityId.new()
    observation_id = EntityId.new()

    reference = EvidenceSignalReference(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        evidence_item_ids=(evidence_item_id,),
        observation_ids=(observation_id,),
        rationale="Pause indication is attached to recording coverage Evidence.",
    )

    assert reference.signal is EvidenceSignal.RECORDING_PAUSE_INDICATED
    assert reference.evidence_item_ids == (evidence_item_id,)
    assert reference.observation_ids == (observation_id,)
    assert reference.rationale is not None
    assert dict(reference.metadata) == {}


def test_signal_references_remain_id_only() -> None:
    field_names = {field.name for field in fields(EvidenceSignalReference)}

    assert "evidence_item_ids" in field_names
    assert "observation_ids" in field_names
    assert "evidence_item" not in field_names
    assert "observation" not in field_names


def test_evidence_set_with_one_signal() -> None:
    item = _item()
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        concern=EvidenceConcern.RECORDING_COVERAGE,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(item,),
        signals=(
            EvidenceSignalReference(
                signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
                evidence_item_ids=(item.id,),
                observation_ids=(item.observation_id,),
            ),
        ),
        correlation_id=CorrelationId.new(),
    )

    assert evidence_set.signals[0].signal is EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED
    assert evidence_set.signals[0].evidence_item_ids == (item.id,)


def test_evidence_set_with_multiple_signals() -> None:
    item = _item()
    evidence_set = EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        concern=EvidenceConcern.POSSIBLE_SESSION_START,
        purpose=EvidencePurpose.REASONING_INPUT,
        items=(item,),
        signals=(
            EvidenceSignalReference(
                signal=EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
                observation_ids=(item.observation_id,),
            ),
            EvidenceSignalReference(
                signal=EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
                observation_ids=(item.observation_id,),
            ),
        ),
        correlation_id=CorrelationId.new(),
    )

    assert {reference.signal for reference in evidence_set.signals} == {
        EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
        EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
    }


def test_one_signal_can_reference_multiple_evidence_items() -> None:
    first = _item()
    second = _item()

    reference = EvidenceSignalReference(
        signal=EvidenceSignal.PACKAGE_INPUTS_AVAILABLE,
        evidence_item_ids=(first.id, second.id),
        observation_ids=(first.observation_id, second.observation_id),
    )

    assert reference.evidence_item_ids == (first.id, second.id)
    assert reference.observation_ids == (first.observation_id, second.observation_id)


def test_one_observation_can_contribute_to_multiple_signals_without_mutation() -> None:
    observation_id = EntityId.new()
    first = EvidenceSignalReference(
        signal=EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
        observation_ids=(observation_id,),
    )
    second = EvidenceSignalReference(
        signal=EvidenceSignal.SESSION_CONTENT_INDICATED,
        observation_ids=(observation_id,),
    )

    assert first.observation_ids == second.observation_ids == (observation_id,)
    assert first.signal is not second.signal


def test_signal_and_concern_remain_distinct() -> None:
    assert EvidenceConcern.RECORDING_COVERAGE.value != (
        EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED.value
    )


def test_signal_role_and_strength_remain_distinct() -> None:
    assert EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED.value != EvidenceRole.SUPPORTS.value
    assert EvidenceSignal.PRESENTATION_TRANSITION_INDICATED.value != (
        EvidenceStrength.MODERATE.value
    )


def test_metadata_not_required_for_core_signal_meaning() -> None:
    reference = EvidenceSignalReference(
        signal=EvidenceSignal.RECORDING_END_INDICATED,
        evidence_item_ids=(EntityId.new(),),
        observation_ids=(EntityId.new(),),
    )

    assert reference.signal is EvidenceSignal.RECORDING_END_INDICATED
    assert dict(reference.metadata) == {}


def test_possible_session_start_signal_vocabulary_exists_without_policy() -> None:
    possible_session_start_signals = {
        EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
        EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
        EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
        EvidenceSignal.SESSION_CONTENT_INDICATED,
    }

    assert all(isinstance(signal, EvidenceSignal) for signal in possible_session_start_signals)


def test_signal_contract_has_no_downstream_or_infrastructure_behavior() -> None:
    field_names = {field.name for field in fields(EvidenceSignalReference)}
    forbidden_terms = {
        "operational_state",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "api",
        "queue",
        "worker",
        "frontend",
        "execute",
        "mutate",
    }

    assert not any(term in name for name in field_names for term in forbidden_terms)
