from dataclasses import fields
from datetime import UTC, datetime
from inspect import getmembers, isfunction

import pytest

from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateBasis,
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
    OperationalStateSubjectType,
    OperationalStateSummary,
    OperationalStateValue,
)
from app.shared.ids import EntityId


def _subject(
    subject_type: OperationalStateSubjectType,
    identifier: str | None = None,
    label: str | None = None,
) -> OperationalStateSubject:
    return OperationalStateSubject(
        subject_type=subject_type,
        subject_identifier=identifier or EntityId.new().to_json(),
        label=label,
    )


def _state(
    *,
    family: OperationalStateFamily,
    kind: OperationalStateKind,
    subject: OperationalStateSubject,
    value: OperationalStateValue,
    basis: OperationalStateBasis,
) -> OperationalState:
    return OperationalState(
        id=EntityId.new(),
        family=family,
        kind=kind,
        subject=subject,
        value=value,
        status=OperationalStateStatus.CURRENT,
        basis=basis,
        observed_or_derived_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def test_operational_state_creation() -> None:
    observation_id = EntityId.new()
    state = _state(
        family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
        kind=OperationalStateKind.RECORDING_STATE,
        subject=_subject(OperationalStateSubjectType.RECORDING_BLOCK),
        value=OperationalStateValue.ACTIVE,
        basis=OperationalStateBasis(observation_ids=(observation_id,)),
    )

    assert state.id
    assert state.family is OperationalStateFamily.DIRECTLY_OBSERVABLE
    assert state.kind is OperationalStateKind.RECORDING_STATE
    assert state.value is OperationalStateValue.ACTIVE
    assert state.status is OperationalStateStatus.CURRENT
    assert state.basis.observation_ids == (observation_id,)


def test_operational_state_family_values() -> None:
    assert {family.value for family in OperationalStateFamily} == {
        "directly_observable",
        "evidence_derived",
        "stageflow_readiness",
        "environmental_context",
        "unknown",
    }


def test_operational_state_kind_values() -> None:
    assert {kind.value for kind in OperationalStateKind} == {
        "recording_state",
        "media_availability",
        "transcript_state",
        "vision_availability",
        "session_state",
        "editorial_state",
        "package_state",
        "observation_readiness",
        "reasoning_readiness",
        "environmental_condition",
        "unknown",
    }


def test_operational_state_subject_creation_is_id_only() -> None:
    subject_id = EntityId.new().to_json()
    subject = OperationalStateSubject(
        subject_type=OperationalStateSubjectType.MEDIA_ARTIFACT,
        subject_identifier=subject_id,
        label="Artifact A",
    )

    assert subject.subject_identifier == subject_id
    assert subject.label == "Artifact A"
    assert not any(field.name == "subject" for field in fields(subject))


def test_operational_state_subject_type_values() -> None:
    assert {subject_type.value for subject_type in OperationalStateSubjectType} == {
        "stageflow",
        "recording_block",
        "media_artifact",
        "transcript_stream",
        "stage",
        "scheduled_activity",
        "session_candidate",
        "session_product",
        "editorial_candidate",
        "package_candidate",
        "external_environment",
        "unknown",
    }


def test_operational_state_value_values() -> None:
    assert {value.value for value in OperationalStateValue} == {
        "unknown",
        "unavailable",
        "available",
        "inactive",
        "ready",
        "active",
        "flowing",
        "paused",
        "degraded",
        "interrupted",
        "stopped",
        "ending",
        "ended",
        "complete",
        "insufficient",
        "waiting",
        "candidate",
    }


def test_operational_state_status_values() -> None:
    assert {status.value for status in OperationalStateStatus} == {
        "current",
        "superseded",
        "expired",
        "archived",
        "unknown",
    }


def test_operational_state_basis_with_observation_ids() -> None:
    observation_ids = (EntityId.new(), EntityId.new())

    basis = OperationalStateBasis(
        observation_ids=observation_ids,
        rationale="Recording activity observations support this state.",
    )

    assert basis.observation_ids == observation_ids
    assert basis.evidence_set_ids == ()
    assert not any(field.name == "observation" for field in fields(basis))


def test_operational_state_basis_with_evidence_set_ids() -> None:
    evidence_set_ids = (EntityId.new(),)

    basis = OperationalStateBasis(
        evidence_set_ids=evidence_set_ids,
        rationale="Evidence sets support this derived state.",
    )

    assert basis.observation_ids == ()
    assert basis.evidence_set_ids == evidence_set_ids
    assert not any(field.name == "evidence_set" for field in fields(basis))


def test_operational_state_summary_generation() -> None:
    recording_block_id = EntityId.new()
    stage_id = EntityId.new()
    state = OperationalState(
        id=EntityId.new(),
        family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
        kind=OperationalStateKind.RECORDING_STATE,
        subject=_subject(OperationalStateSubjectType.RECORDING_BLOCK),
        value=OperationalStateValue.ACTIVE,
        status=OperationalStateStatus.CURRENT,
        basis=OperationalStateBasis(
            observation_ids=(EntityId.new(),),
            evidence_set_ids=(EntityId.new(),),
        ),
        observed_or_derived_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        recording_block_id=recording_block_id,
        stage_id=stage_id,
    )

    summary = OperationalStateSummary.from_state(state)

    assert summary.state_id == state.id
    assert summary.family is OperationalStateFamily.DIRECTLY_OBSERVABLE
    assert summary.kind is OperationalStateKind.RECORDING_STATE
    assert summary.subject_type is OperationalStateSubjectType.RECORDING_BLOCK
    assert summary.value is OperationalStateValue.ACTIVE
    assert summary.status is OperationalStateStatus.CURRENT
    assert summary.observation_reference_count == 1
    assert summary.evidence_set_reference_count == 1
    assert summary.recording_block_id == recording_block_id
    assert summary.stage_id == stage_id


def test_directly_observable_recording_state_example() -> None:
    state = _state(
        family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
        kind=OperationalStateKind.RECORDING_STATE,
        subject=_subject(OperationalStateSubjectType.RECORDING_BLOCK),
        value=OperationalStateValue.ACTIVE,
        basis=OperationalStateBasis(observation_ids=(EntityId.new(),)),
    )

    assert state.family is OperationalStateFamily.DIRECTLY_OBSERVABLE
    assert state.kind is OperationalStateKind.RECORDING_STATE
    assert state.value is OperationalStateValue.ACTIVE
    assert state.is_core_stageflow_state


def test_directly_observable_transcript_state_example() -> None:
    state = _state(
        family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
        kind=OperationalStateKind.TRANSCRIPT_STATE,
        subject=_subject(OperationalStateSubjectType.TRANSCRIPT_STREAM),
        value=OperationalStateValue.FLOWING,
        basis=OperationalStateBasis(observation_ids=(EntityId.new(),)),
    )

    assert state.family is OperationalStateFamily.DIRECTLY_OBSERVABLE
    assert state.kind is OperationalStateKind.TRANSCRIPT_STATE
    assert state.value is OperationalStateValue.FLOWING


def test_evidence_derived_session_state_example() -> None:
    state = _state(
        family=OperationalStateFamily.EVIDENCE_DERIVED,
        kind=OperationalStateKind.SESSION_STATE,
        subject=_subject(OperationalStateSubjectType.SESSION_CANDIDATE),
        value=OperationalStateValue.ACTIVE,
        basis=OperationalStateBasis(evidence_set_ids=(EntityId.new(),)),
    )

    assert state.family is OperationalStateFamily.EVIDENCE_DERIVED
    assert state.kind is OperationalStateKind.SESSION_STATE
    assert state.basis.evidence_set_ids


def test_stageflow_readiness_example() -> None:
    state = _state(
        family=OperationalStateFamily.STAGEFLOW_READINESS,
        kind=OperationalStateKind.OBSERVATION_READINESS,
        subject=_subject(OperationalStateSubjectType.STAGEFLOW, "stageflow"),
        value=OperationalStateValue.READY,
        basis=OperationalStateBasis(rationale="StageFlow is ready to observe recorded media."),
    )

    assert state.family is OperationalStateFamily.STAGEFLOW_READINESS
    assert state.kind is OperationalStateKind.OBSERVATION_READINESS
    assert state.value is OperationalStateValue.READY
    assert state.is_core_stageflow_state


def test_environmental_context_example() -> None:
    state = _state(
        family=OperationalStateFamily.ENVIRONMENTAL_CONTEXT,
        kind=OperationalStateKind.ENVIRONMENTAL_CONDITION,
        subject=_subject(
            OperationalStateSubjectType.EXTERNAL_ENVIRONMENT,
            "livestream-health",
            label="Livestream health",
        ),
        value=OperationalStateValue.AVAILABLE,
        basis=OperationalStateBasis(observation_ids=(EntityId.new(),)),
    )

    assert state.family is OperationalStateFamily.ENVIRONMENTAL_CONTEXT
    assert state.kind is OperationalStateKind.ENVIRONMENTAL_CONDITION
    assert not state.is_core_stageflow_state


def test_directly_observable_and_evidence_derived_families_remain_distinct() -> None:
    with pytest.raises(ValueError, match="must not be directly observable"):
        _state(
            family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
            kind=OperationalStateKind.SESSION_STATE,
            subject=_subject(OperationalStateSubjectType.SESSION_CANDIDATE),
            value=OperationalStateValue.ACTIVE,
            basis=OperationalStateBasis(observation_ids=(EntityId.new(),)),
        )


def test_human_production_readiness_is_not_stageflow_readiness() -> None:
    with pytest.raises(ValueError, match="human or external production readiness"):
        _state(
            family=OperationalStateFamily.STAGEFLOW_READINESS,
            kind=OperationalStateKind.OBSERVATION_READINESS,
            subject=_subject(
                OperationalStateSubjectType.EXTERNAL_ENVIRONMENT,
                "speaker-ready",
                label="Speaker ready",
            ),
            value=OperationalStateValue.READY,
            basis=OperationalStateBasis(),
        )


def test_stageflow_readiness_uses_readiness_kind() -> None:
    with pytest.raises(ValueError, match="readiness kind"):
        _state(
            family=OperationalStateFamily.STAGEFLOW_READINESS,
            kind=OperationalStateKind.RECORDING_STATE,
            subject=_subject(OperationalStateSubjectType.STAGEFLOW, "stageflow"),
            value=OperationalStateValue.READY,
            basis=OperationalStateBasis(),
        )


def test_livestream_health_is_not_core_stageflow_state() -> None:
    state = _state(
        family=OperationalStateFamily.ENVIRONMENTAL_CONTEXT,
        kind=OperationalStateKind.ENVIRONMENTAL_CONDITION,
        subject=_subject(OperationalStateSubjectType.EXTERNAL_ENVIRONMENT, "livestream"),
        value=OperationalStateValue.ACTIVE,
        basis=OperationalStateBasis(),
    )

    assert not state.is_core_stageflow_state


def test_environmental_context_uses_environmental_kind() -> None:
    with pytest.raises(ValueError, match="environmental_condition"):
        _state(
            family=OperationalStateFamily.ENVIRONMENTAL_CONTEXT,
            kind=OperationalStateKind.RECORDING_STATE,
            subject=_subject(OperationalStateSubjectType.EXTERNAL_ENVIRONMENT, "livestream"),
            value=OperationalStateValue.ACTIVE,
            basis=OperationalStateBasis(),
        )


def test_no_state_transition_or_downstream_behavior_exists() -> None:
    contract_fields = {
        field.name
        for contract in (
            OperationalState,
            OperationalStateBasis,
            OperationalStateSubject,
            OperationalStateSummary,
        )
        for field in fields(contract)
    }
    contract_fields -= {
        "transition_evaluation_ids",
        "transition_rule_ids",
    }
    method_names = {
        name
        for name, value in getmembers(OperationalState)
        if isfunction(value)
    }
    forbidden_terms = {
        "transition",
        "threshold",
        "state_machine",
        "repository",
        "persist",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "api",
        "queue",
        "worker",
        "frontend",
        "ai",
        "provider",
    }

    assert not any(
        term in name
        for name in contract_fields | method_names
        for term in forbidden_terms
    )
