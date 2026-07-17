from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.contexts.production.evidence import EvidenceSignal
from app.contexts.production.operational_state import (
    OperationalStateBasis,
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.contexts.production.operational_state_acceptance import (
    OPERATIONAL_STATE_ACCEPTANCE_RULES,
    RECORDING_ACCEPTANCE_RULES,
    SESSION_ACCEPTANCE_RULES,
    OperationalStateAcceptance,
    OperationalStateAcceptanceContext,
    OperationalStateAcceptanceHistory,
    OperationalStateAcceptanceLineage,
    OperationalStateAcceptanceOutcome,
    OperationalStateAcceptanceReason,
    OperationalStateAcceptanceReasonCode,
    OperationalStateAcceptanceRequest,
    OperationalStateAcceptanceResult,
    OperationalStateAcceptanceRule,
    OperationalStateAcceptanceSummary,
    OperationalStateSupersession,
    acceptance_rule_for,
    lifecycle_is_supported,
    policy_kind_for_state_kind,
    state_family_for_kind,
    subject_types_for_kind,
)
from app.contexts.production.recording_transition_policy import (
    default_recording_transition_rules,
    recording_transition_rule_id,
)
from app.shared.ids import EntityId

ACCEPTANCE_PACKAGE = (
    Path(__file__).parents[1] / "app" / "contexts" / "production" / "operational_state_acceptance"
)


def test_acceptance_component_and_all_public_contracts_are_frozen_dataclasses() -> None:
    contracts = (
        OperationalStateAcceptance,
        OperationalStateAcceptanceContext,
        OperationalStateAcceptanceHistory,
        OperationalStateAcceptanceLineage,
        OperationalStateAcceptanceReason,
        OperationalStateAcceptanceRequest,
        OperationalStateAcceptanceResult,
        OperationalStateAcceptanceRule,
        OperationalStateAcceptanceSummary,
        OperationalStateSupersession,
    )

    assert all(is_dataclass(contract) for contract in contracts)
    assert all(cast(Any, contract).__dataclass_params__.frozen for contract in contracts)
    acceptance = OperationalStateAcceptance()
    with pytest.raises(FrozenInstanceError):
        acceptance.extra = True  # type: ignore[attr-defined]


def test_outcome_values_are_exactly_the_approved_initial_values() -> None:
    assert tuple(outcome.value for outcome in OperationalStateAcceptanceOutcome) == (
        "accepted",
        "rejected_ineligible_evaluation",
        "rejected_invalid_lineage",
        "rejected_invalid_current_state",
        "rejected_invalid_subject",
        "rejected_context_mismatch",
        "rejected_invalid_transition",
        "already_accepted",
        "unknown",
    )


def test_reason_codes_are_exactly_the_approved_initial_values() -> None:
    assert tuple(code.value for code in OperationalStateAcceptanceReasonCode) == (
        "evaluation_outcome_not_supported",
        "missing_proposed_state",
        "unsupported_state_kind",
        "invalid_policy_identity",
        "invalid_rule_identity",
        "missing_supporting_evidence",
        "missing_observation_lineage",
        "missing_event_lineage",
        "evaluation_current_state_mismatch",
        "invalid_current_state_kind",
        "invalid_current_state_status",
        "invalid_current_state_value",
        "invalid_current_state_subject",
        "invalid_target_subject",
        "subject_mismatch",
        "context_mismatch",
        "invalid_lifecycle_transition",
        "evaluation_already_accepted",
        "successor_created",
        "unknown",
    )


def test_request_holds_exactly_one_evaluation_and_id_only_lineage() -> None:
    request_fields = {field.name: field.type for field in fields(OperationalStateAcceptanceRequest)}
    lineage_fields = {
        field.name: str(field.type) for field in fields(OperationalStateAcceptanceLineage)
    }

    assert request_fields["evaluation"] == "TransitionEvaluation"
    assert "evaluations" not in request_fields
    for name in (
        "supporting_evidence_set_ids",
        "blocking_evidence_set_ids",
        "contributing_evidence_item_ids",
        "contributing_observation_ids",
        "contributing_production_event_ids",
        "satisfied_requirement_ids",
        "unmet_requirement_ids",
        "interpreter_ids",
    ):
        assert "EntityId" in lineage_fields[name]
    assert not {
        "evidence_sets",
        "evidence_items",
        "observations",
        "production_events",
        "policy",
        "rule",
    } & set(lineage_fields)


def test_lineage_normalizes_duplicate_references_and_defensively_copies_metadata() -> None:
    evaluation_id = EntityId.new()
    policy_id = EntityId.new()
    rule_id = EntityId.new()
    shared_id = EntityId.new()
    metadata = {"source": "test"}
    lineage = OperationalStateAcceptanceLineage(
        evaluation_id=evaluation_id,
        policy_kind="recording_transition_policy",
        policy_id=policy_id,
        applied_rule_id=rule_id,
        evaluated_state_kind=OperationalStateKind.RECORDING_STATE,
        current_state_id=None,
        effective_current_value=OperationalStateValue.INACTIVE,
        proposed_state_value=OperationalStateValue.ACTIVE,
        supporting_evidence_set_ids=(shared_id, shared_id),
        contributing_evidence_item_ids=(shared_id, shared_id),
        contributing_observation_ids=(shared_id, shared_id),
        contributing_production_event_ids=(shared_id, shared_id),
        contributing_signals=(
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        ),
        satisfied_requirement_ids=(shared_id, shared_id),
        interpreter_ids=(shared_id, shared_id),
        interpretation_rule_ids=("rule-a", "rule-a"),
        organizational_anchors=("anchor-a", "anchor-a"),
        metadata=metadata,
    )
    metadata["source"] = "mutated"

    assert lineage.supporting_evidence_set_ids == (shared_id,)
    assert lineage.contributing_evidence_item_ids == (shared_id,)
    assert lineage.contributing_observation_ids == (shared_id,)
    assert lineage.contributing_production_event_ids == (shared_id,)
    assert lineage.satisfied_requirement_ids == (shared_id,)
    assert lineage.interpreter_ids == (shared_id,)
    assert lineage.interpretation_rule_ids == ("rule-a",)
    assert lineage.organizational_anchors == ("anchor-a",)
    assert lineage.metadata["source"] == "test"
    with pytest.raises(TypeError):
        lineage.metadata["source"] = "forbidden"  # type: ignore[index]


def test_context_is_partial_id_only_and_normalizes_repeated_identifiers() -> None:
    stage_id = EntityId.new()
    context = OperationalStateAcceptanceContext(
        stage_id=stage_id,
        transcript_stream_ids=("stream-a", "stream-a"),
        media_artifact_ids=("artifact-a", "artifact-a"),
        timeline_range_seconds=(1, 4),
    )

    assert context.stage_id == stage_id
    assert context.transcript_stream_ids == ("stream-a",)
    assert context.media_artifact_ids == ("artifact-a",)
    assert context.timeline_range_seconds == (1.0, 4.0)
    assert OperationalStateAcceptanceContext.unknown() == OperationalStateAcceptanceContext()
    with pytest.raises(ValueError, match="ordered"):
        OperationalStateAcceptanceContext(timeline_range_seconds=(4, 1))


def test_history_is_explicit_immutable_and_relative_to_caller_supplied_ids() -> None:
    evaluation_id = EntityId.new()
    acceptance_id = EntityId.new()
    successor_id = EntityId.new()
    history = OperationalStateAcceptanceHistory(
        accepted_evaluation_ids=(evaluation_id, evaluation_id),
        prior_acceptance_ids=(acceptance_id, acceptance_id),
        successor_state_ids=(successor_id, successor_id),
        metadata={"scope": "known_history_only"},
    )

    assert OperationalStateAcceptanceHistory().accepted_evaluation_ids == ()
    assert history.accepted_evaluation_ids == (evaluation_id,)
    assert history.prior_acceptance_ids == (acceptance_id,)
    assert history.successor_state_ids == (successor_id,)
    assert history.contains_evaluation(evaluation_id)
    with pytest.raises(FrozenInstanceError):
        history.accepted_evaluation_ids = ()  # type: ignore[misc]


def test_recording_rule_ids_are_stable_and_acceptance_mapping_is_static() -> None:
    first = default_recording_transition_rules()
    second = default_recording_transition_rules()

    assert tuple(rule.id for rule in first) == tuple(rule.id for rule in second)
    assert all(rule.id == recording_transition_rule_id(rule.evidence_signal) for rule in first)
    assert len(RECORDING_ACCEPTANCE_RULES) == 5
    assert len(SESSION_ACCEPTANCE_RULES) == 6
    assert OPERATIONAL_STATE_ACCEPTANCE_RULES == (
        *RECORDING_ACCEPTANCE_RULES,
        *SESSION_ACCEPTANCE_RULES,
    )
    assert all(rule.required_lineage_fields for rule in OPERATIONAL_STATE_ACCEPTANCE_RULES)


def test_mapping_exposes_family_policy_subject_and_lifecycle_compatibility() -> None:
    recording_rule = RECORDING_ACCEPTANCE_RULES[0]

    assert (
        state_family_for_kind(OperationalStateKind.RECORDING_STATE)
        is OperationalStateFamily.DIRECTLY_OBSERVABLE
    )
    assert (
        state_family_for_kind(OperationalStateKind.SESSION_STATE)
        is OperationalStateFamily.EVIDENCE_DERIVED
    )
    assert state_family_for_kind(OperationalStateKind.TRANSCRIPT_STATE) is None
    assert (
        policy_kind_for_state_kind(OperationalStateKind.RECORDING_STATE)
        == "recording_transition_policy"
    )
    assert OperationalStateSubjectType.RECORDING_BLOCK in subject_types_for_kind(
        OperationalStateKind.RECORDING_STATE
    )
    assert OperationalStateSubjectType.SESSION_CANDIDATE in subject_types_for_kind(
        OperationalStateKind.SESSION_STATE
    )
    assert lifecycle_is_supported(
        OperationalStateKind.RECORDING_STATE,
        OperationalStateValue.INACTIVE,
        OperationalStateValue.ACTIVE,
    )
    assert not lifecycle_is_supported(
        OperationalStateKind.RECORDING_STATE,
        OperationalStateValue.STOPPED,
        OperationalStateValue.ACTIVE,
    )
    assert (
        acceptance_rule_for(
            policy_kind=recording_rule.supported_policy_kind,
            transition_rule_id=recording_rule.supported_transition_rule_id,
            state_kind=recording_rule.state_kind,
            effective_current_value=recording_rule.effective_current_value,
            proposed_value=recording_rule.proposed_value,
        )
        is recording_rule
    )


def test_basis_refinement_is_backward_compatible_and_normalizes_ids() -> None:
    shared_id = EntityId.new()
    legacy = OperationalStateBasis(
        observation_ids=(shared_id,),
        evidence_set_ids=(shared_id,),
        rationale="Legacy-compatible basis.",
    )
    refined = OperationalStateBasis(
        transition_evaluation_ids=(shared_id, shared_id),
        policy_ids=(shared_id, shared_id),
        transition_rule_ids=(shared_id, shared_id),
    )

    assert legacy.transition_evaluation_ids == ()
    assert legacy.policy_ids == ()
    assert legacy.transition_rule_ids == ()
    assert refined.transition_evaluation_ids == (shared_id,)
    assert refined.policy_ids == (shared_id,)
    assert refined.transition_rule_ids == (shared_id,)


def test_reason_and_supersession_validate_descriptive_contracts() -> None:
    evaluation_id = EntityId.new()
    predecessor_id = EntityId.new()
    successor_id = EntityId.new()
    reason = OperationalStateAcceptanceReason(
        code=OperationalStateAcceptanceReasonCode.SUCCESSOR_CREATED,
        message="One successor was created.",
        evaluation_id=evaluation_id,
        current_state_id=predecessor_id,
        subject_identifier="subject-a",
        related_lineage_ids=(evaluation_id, evaluation_id),
    )
    supersession = OperationalStateSupersession(
        predecessor_state_id=predecessor_id,
        successor_state_id=successor_id,
        transition_evaluation_id=evaluation_id,
        accepted_at=datetime(2026, 7, 16, tzinfo=UTC),
        predecessor_status_before_acceptance=OperationalStateStatus.CURRENT,
        successor_status=OperationalStateStatus.CURRENT,
        reason="The accepted successor is intended to supersede the predecessor.",
        metadata={"persisted": False},
    )

    assert reason.related_lineage_ids == (evaluation_id,)
    assert supersession.metadata["persisted"] is False
    with pytest.raises(ValueError, match="distinct"):
        OperationalStateSupersession(
            predecessor_state_id=predecessor_id,
            successor_state_id=predecessor_id,
            transition_evaluation_id=evaluation_id,
            accepted_at=datetime(2026, 7, 16, tzinfo=UTC),
            predecessor_status_before_acceptance=OperationalStateStatus.CURRENT,
            successor_status=OperationalStateStatus.CURRENT,
            reason="Invalid identity.",
        )


def test_acceptance_result_invariants_are_declared_in_the_contract() -> None:
    source = (ACCEPTANCE_PACKAGE / "operational_state_acceptance_result.py").read_text()

    assert "requires at least one reason" in source
    assert "Accepted result Evaluation ID must match lineage" in source
    assert "Accepted result requires successor state and acceptance rule" in source
    assert "Accepted result with a predecessor requires supersession" in source
    assert "Non-accepted result must not contain successor or supersession" in source


def test_acceptance_package_has_no_runtime_boundary_dependencies() -> None:
    forbidden_import_names = {
        "EvidenceItem",
        "EvidenceSet",
        "Observation",
        "ProductionEvent",
        "RecordingTransitionPolicy",
        "SessionTransitionPolicy",
        "Session",
        "Repository",
    }
    forbidden_modules = {
        "fastapi",
        "sqlalchemy",
        "openai",
        "celery",
        "redis",
    }
    found_names: set[str] = set()
    found_modules: set[str] = set()

    for path in ACCEPTANCE_PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                found_modules.add(node.module or "")
                found_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                found_modules.update(alias.name for alias in node.names)

    assert not forbidden_import_names & found_names
    assert not any(
        module == forbidden or module.startswith(f"{forbidden}.")
        for module in found_modules
        for forbidden in forbidden_modules
    )


def test_acceptance_has_no_persistence_execution_or_publication_methods() -> None:
    public_methods: set[str] = set()
    for path in ACCEPTANCE_PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text())
        public_methods.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        )

    assert (
        not {
            "persist",
            "save",
            "execute",
            "publish",
            "enqueue",
            "schedule",
            "create_session",
            "verify_boundary",
        }
        & public_methods
    )


def test_rule_contract_requires_first_class_policy_rule_state_and_subject_fields() -> None:
    contract_fields = {field.name for field in fields(OperationalStateAcceptanceRule)}

    assert {
        "id",
        "supported_policy_kind",
        "supported_transition_rule_id",
        "state_kind",
        "effective_current_value",
        "proposed_value",
        "required_subject_types",
        "required_state_family",
        "current_state_required",
        "supersession_expected",
        "required_lineage_fields",
        "rationale",
    } <= contract_fields


def test_subject_contract_itself_prevents_absent_explicit_identifier() -> None:
    with pytest.raises(ValueError, match="subject identifier"):
        OperationalStateSubject(
            OperationalStateSubjectType.RECORDING_BLOCK,
            " ",
        )
