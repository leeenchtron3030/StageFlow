from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import datetime

import pytest
from software_agent_runtime_fixtures import (
    AGENT_INSTANCE_ID,
    CREATED_AT,
    PREPARED_AT,
    make_agent,
    make_pressure,
    operation_id,
    prepare_request,
)

from app.contexts.production.runtime import (
    RuntimeAvailabilityStatus,
    RuntimeHealthStatus,
    RuntimePressureState,
    RuntimeProfile,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeCancellation,
    AgentRuntimeExecutionPermission,
    AgentRuntimeFailure,
    AgentRuntimeLifecycleState,
    AgentRuntimeNotificationFailure,
    AgentRuntimeOperation,
    AgentRuntimeOperationOutcome,
    AgentRuntimeOperationResult,
    AgentRuntimePrepareRequest,
    AgentRuntimePressureDeclaration,
    AgentRuntimePressureUpdate,
    AgentRuntimeResumeRequest,
    AgentRuntimeSnapshot,
    AgentRuntimeStartRequest,
    AgentRuntimeStopRequest,
    AgentRuntimeSummary,
    AgentRuntimeTransition,
    AgentRuntimeTransitionReasonCode,
    SoftwareAgentRuntime,
)


def test_lifecycle_state_vocabulary_is_exact() -> None:
    assert {state.value for state in AgentRuntimeLifecycleState} == {
        "created",
        "validated",
        "ready",
        "running",
        "yielding",
        "suspended",
        "stopping",
        "stopped",
        "failed",
        "disabled",
    }


def test_execution_permission_vocabulary_is_exact() -> None:
    assert {permission.value for permission in AgentRuntimeExecutionPermission} == {
        "none",
        "essential_only",
        "reduced",
        "normal",
    }


def test_operation_and_outcome_vocabularies_are_explicit() -> None:
    assert {operation.value for operation in AgentRuntimeOperation} == {
        "prepare",
        "start",
        "pressure_update",
        "resume",
        "cancel",
        "stop",
        "fail",
    }
    assert {
        "applied",
        "already_applied",
        "disabled",
        "rejected",
        "stale_revision",
        "operation_conflict",
        "invalid_runtime",
        "invalid_configuration",
        "invalid_transition",
        "dependency_failure",
        "applied_with_notification_failure",
        "failed",
        "unknown",
    } == {outcome.value for outcome in AgentRuntimeOperationOutcome}


def test_public_agent_contracts_are_immutable_dataclasses() -> None:
    contracts = (
        AgentRuntimeCancellation,
        AgentRuntimeFailure,
        AgentRuntimeNotificationFailure,
        AgentRuntimeOperationResult,
        AgentRuntimePrepareRequest,
        AgentRuntimePressureDeclaration,
        AgentRuntimePressureUpdate,
        AgentRuntimeResumeRequest,
        AgentRuntimeSnapshot,
        AgentRuntimeStartRequest,
        AgentRuntimeStopRequest,
        AgentRuntimeSummary,
        AgentRuntimeTransition,
    )

    assert all(is_dataclass(contract) for contract in contracts)
    request = prepare_request(make_agent()[0])
    with pytest.raises(FrozenInstanceError):
        request.allow_development_profile = True  # type: ignore[misc]


def test_constructor_creates_only_the_initial_created_snapshot() -> None:
    agent, sink = make_agent()
    snapshot = agent.snapshot

    assert snapshot.agent_instance_id == AGENT_INSTANCE_ID
    assert snapshot.lifecycle_state is AgentRuntimeLifecycleState.CREATED
    assert snapshot.lifecycle_revision == 0
    assert snapshot.previous_lifecycle_state is None
    assert snapshot.state_entered_at == CREATED_AT
    assert snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE
    assert snapshot.health.status is RuntimeHealthStatus.UNKNOWN
    assert snapshot.availability.status is RuntimeAvailabilityStatus.UNAVAILABLE
    assert snapshot.transition_lineage_ids == ()
    assert agent.transition_history == ()
    assert agent.validation_result is None
    assert sink.publications == []


def test_constructor_does_not_validate_or_start_implicitly() -> None:
    agent, _ = make_agent(profile=RuntimeProfile.NODE)

    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.CREATED
    assert agent.validation_result is None
    assert agent.snapshot.latest_operation_id is None


def test_prepare_result_retains_both_intermediate_transitions() -> None:
    agent, _ = make_agent()
    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert [transition.next_state for transition in result.transitions] == [
        AgentRuntimeLifecycleState.VALIDATED,
        AgentRuntimeLifecycleState.READY,
    ]
    assert result.transition == result.transitions[-1]
    assert result.previous_snapshot.lifecycle_revision == 0
    assert result.current_snapshot.lifecycle_revision == 2
    assert result.occurred_at == PREPARED_AT


def test_transition_records_permission_health_availability_and_lineage() -> None:
    agent, _ = make_agent()
    result = agent.prepare(prepare_request(agent))
    transition = result.transitions[-1]

    assert transition.runtime_id == agent.runtime.identity.runtime_id
    assert transition.configuration_id == agent.runtime.configuration.id
    assert transition.lifecycle_revision == result.current_snapshot.lifecycle_revision
    assert transition.health_declaration_id == result.current_snapshot.health.id
    assert transition.availability_declaration_id == (result.current_snapshot.availability.id)
    assert transition.id in result.current_snapshot.transition_lineage_ids
    assert transition.execution_permission_after is AgentRuntimeExecutionPermission.NONE


def test_pressure_declaration_is_categorical_and_timezone_aware() -> None:
    pressure = make_pressure(RuntimePressureState.ELEVATED)

    assert pressure.pressure_state is RuntimePressureState.ELEVATED
    assert pressure.source_id is not None
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(pressure, assessed_at=datetime(2026, 7, 17, 12))


def test_all_operation_requests_reject_negative_revisions() -> None:
    agent, _ = make_agent()

    with pytest.raises(ValueError, match="negative"):
        replace(prepare_request(agent), expected_lifecycle_revision=-1)


def test_operation_metadata_rejects_credentials_and_is_frozen() -> None:
    agent, _ = make_agent()
    request = replace(
        prepare_request(agent),
        metadata={"nested": {"values": [1, 2]}},
    )

    assert request.metadata["nested"]["values"] == (1, 2)
    with pytest.raises(ValueError, match="credential"):
        replace(request, metadata={"access_token": "synthetic-secret"})


def test_agent_summary_is_privacy_safe() -> None:
    agent, _ = make_agent()
    summary = agent.summary()
    summary_fields = {item.name for item in fields(type(summary))}

    assert summary.agent_instance_id == AGENT_INSTANCE_ID
    assert summary.lifecycle_state is AgentRuntimeLifecycleState.CREATED
    assert summary.transition_count == 0
    assert (
        not {
            "credentials",
            "filename",
            "media",
            "metadata",
            "recorder_configuration",
            "session_id",
            "source_path",
        }
        & summary_fields
    )


def test_software_agent_runtime_is_the_only_concrete_runtime_object() -> None:
    assert SoftwareAgentRuntime.__name__ == "SoftwareAgentRuntime"
    assert not is_dataclass(SoftwareAgentRuntime)
    assert "run_forever" not in dir(SoftwareAgentRuntime)
    assert "start_background_thread" not in dir(SoftwareAgentRuntime)


def test_reason_vocabulary_contains_required_conflict_and_safety_reasons() -> None:
    values = {reason.value for reason in AgentRuntimeTransitionReasonCode}

    assert {
        "runtime_validation_failed",
        "unsupported_runtime_profile",
        "recording_safety_uncertain",
        "explicit_resume_required",
        "stale_lifecycle_revision",
        "operation_identity_conflict",
        "dependency_publication_failure",
        "shutdown_complete",
    } <= values


def test_public_contracts_have_no_session_media_or_work_payload_fields() -> None:
    contracts = (
        AgentRuntimeSnapshot,
        AgentRuntimeTransition,
        AgentRuntimeOperationResult,
        AgentRuntimeSummary,
    )
    names = {item.name for contract in contracts for item in fields(contract)}

    assert (
        not {
            "candidate",
            "completed_media_asset",
            "evidence",
            "media_bytes",
            "observation_bundle",
            "operational_state",
            "session_id",
            "transfer",
        }
        & names
    )


def test_request_identity_is_supplied_not_allocated_by_constructor() -> None:
    agent, _ = make_agent()
    request = prepare_request(agent, number=42)

    assert request.operation_id == operation_id(42)
    assert agent.snapshot.latest_operation_id is None
