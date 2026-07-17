from __future__ import annotations

from dataclasses import fields

from software_agent_runtime_fixtures import (
    make_agent,
    make_running_agent,
    prepare_request,
)

from app.contexts.production.runtime import RuntimeProfile
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeLifecycleState,
    AgentRuntimeOperationOutcome,
    AgentRuntimeSnapshot,
    AgentRuntimeTransition,
)


def test_agent_execution_consumes_ed0050_aggregate_without_mutating_it() -> None:
    agent, _ = make_agent()
    runtime = agent.runtime
    configuration = runtime.configuration

    agent.prepare(prepare_request(agent))

    assert agent.runtime is runtime
    assert agent.execution_configuration is configuration
    assert agent.runtime.configuration == configuration


def test_node_profile_is_rejected_by_agent_adapter_without_semantic_rewrite() -> None:
    agent, _ = make_agent(profile=RuntimeProfile.NODE)
    runtime = agent.runtime

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.INVALID_RUNTIME
    assert agent.runtime is runtime
    assert agent.runtime.profile is RuntimeProfile.NODE
    assert agent.snapshot.deployment_profile is RuntimeProfile.NODE


def test_shared_lifecycle_contracts_have_no_agent_media_semantics() -> None:
    field_names = {
        item.name
        for contract in (AgentRuntimeSnapshot, AgentRuntimeTransition)
        for item in fields(contract)
    }

    assert (
        not {
            "asset",
            "candidate",
            "checksum",
            "filename",
            "media_path",
            "observation",
            "readiness",
            "session",
            "transfer",
        }
        & field_names
    )


def test_profile_does_not_change_readiness_or_asset_behavior() -> None:
    production, _ = make_running_agent(profile=RuntimeProfile.AGENT)
    development, _ = make_running_agent(profile=RuntimeProfile.DEVELOPMENT)

    assert production.snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING
    assert development.snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING
    assert not hasattr(production, "evaluate_readiness")
    assert not hasattr(production, "assemble_asset")
    assert not hasattr(development, "discover_candidates")


def test_runtime_has_no_media_execution_or_external_control_surface() -> None:
    agent, _ = make_agent()
    forbidden = {
        "collect_observations",
        "control_recorder",
        "discover_candidates",
        "enqueue",
        "evaluate_readiness",
        "open_media",
        "persist",
        "transfer",
        "watch",
    }

    assert forbidden.isdisjoint(dir(agent))
