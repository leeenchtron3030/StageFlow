from __future__ import annotations

from dataclasses import fields, replace

import pytest
from runtime_fixtures import entity_id, make_runtime, synchronize_runtime

from app.contexts.production.runtime import (
    RuntimeLimitationSeverity,
    RuntimeProfile,
    RuntimeReadinessRoute,
    RuntimeSourceLocationScheme,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    validate_runtime,
)


@pytest.mark.parametrize(
    "profile",
    [
        RuntimeProfile.AGENT,
        RuntimeProfile.NODE,
        RuntimeProfile.EXTERNAL_COMPATIBLE,
        RuntimeProfile.DEVELOPMENT,
    ],
)
def test_known_profiles_share_one_contract_and_can_be_valid(
    profile: RuntimeProfile,
) -> None:
    runtime = make_runtime(profile=profile)

    assert runtime.profile is profile
    assert runtime.identity.deployment_profile is profile
    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_unknown_profile_produces_explicit_unknown_outcome() -> None:
    runtime = make_runtime(profile=RuntimeProfile.UNKNOWN)
    result = validate_runtime(runtime)

    assert result.outcome is RuntimeValidationOutcome.UNKNOWN
    assert result.reasons[-1].code is RuntimeValidationReasonCode.UNKNOWN_RUNTIME_PROFILE


def test_nonblocking_limitation_precedes_unknown_profile() -> None:
    runtime = make_runtime(
        profile=RuntimeProfile.UNKNOWN,
        limitation_severity=RuntimeLimitationSeverity.NON_BLOCKING,
    )

    assert validate_runtime(runtime).outcome is (
        RuntimeValidationOutcome.VALID_WITH_LIMITATIONS
    )


def test_agent_with_broad_capabilities_supports_stability_route() -> None:
    runtime = make_runtime(
        profile=RuntimeProfile.AGENT,
        route=RuntimeReadinessRoute.STABILITY_DERIVED,
    )

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_agent_with_limited_stability_capabilities_can_use_strong_route() -> None:
    runtime = make_runtime(
        profile=RuntimeProfile.AGENT,
        route=RuntimeReadinessRoute.STRONG_FINALIZATION,
        include_read=False,
        include_write=False,
    )

    assert validate_runtime(runtime).outcome is (
        RuntimeValidationOutcome.VALID_WITH_LIMITATIONS
    )


def test_node_without_stable_identity_gets_no_profile_exemption() -> None:
    runtime = make_runtime(
        profile=RuntimeProfile.NODE,
        route=RuntimeReadinessRoute.STABILITY_DERIVED,
        include_stable_identity=False,
    )

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.INVALID


def test_profile_does_not_change_capability_combination_semantics() -> None:
    agent = make_runtime(profile=RuntimeProfile.AGENT)
    node = make_runtime(profile=RuntimeProfile.NODE)
    external = make_runtime(profile=RuntimeProfile.EXTERNAL_COMPATIBLE)

    assert {
        validate_runtime(agent).outcome,
        validate_runtime(node).outcome,
        validate_runtime(external).outcome,
    } == {RuntimeValidationOutcome.VALID}
    assert agent.capability_set == node.capability_set == external.capability_set


def test_two_runtime_instances_retain_independent_identity_graphs() -> None:
    first_id = entity_id(860)
    second_id = entity_id(861)
    first = make_runtime(runtime_id=first_id, profile=RuntimeProfile.AGENT)
    second = make_runtime(runtime_id=second_id, profile=RuntimeProfile.NODE)

    assert first.identity.runtime_id == first_id
    assert second.identity.runtime_id == second_id
    assert first.capability_set.runtime_id == first_id
    assert second.capability_set.runtime_id == second_id
    assert first.configuration.runtime_id == first_id
    assert second.configuration.runtime_id == second_id
    assert validate_runtime(first).runtime_id != validate_runtime(second).runtime_id


def test_runtime_identity_never_uses_session_identity() -> None:
    identity_fields = {field.name for field in fields(type(make_runtime().identity))}

    assert "session_id" not in identity_fields
    assert "active_session" not in identity_fields
    assert "session_authority" not in identity_fields


def test_profile_is_descriptive_not_a_trust_or_authority_rank() -> None:
    profile_values = {profile.value for profile in RuntimeProfile}
    identity_fields = {field.name for field in fields(type(make_runtime().identity))}

    assert "trusted" not in profile_values
    assert "authoritative" not in profile_values
    assert not {"authority_rank", "trust_level", "trust_score"} & identity_fields


def test_invalid_configuration_precedes_unknown_profile() -> None:
    runtime = make_runtime(profile=RuntimeProfile.UNKNOWN)
    target = replace(
        runtime.collection_plans[0].targets[0],
        source_location_scheme=RuntimeSourceLocationScheme.NETWORK_SHARE,
    )
    plan = replace(runtime.collection_plans[0], targets=(target,))
    changed = synchronize_runtime(runtime, collection_plans=(plan,))
    result = validate_runtime(changed)

    assert result.outcome is RuntimeValidationOutcome.INVALID
    assert any(
        reason.code is RuntimeValidationReasonCode.SOURCE_SCHEME_UNSUPPORTED
        for reason in result.reasons
    )


def test_runtime_configuration_contains_no_process_lifecycle() -> None:
    configuration_fields = {
        field.name for field in fields(type(make_runtime().configuration))
    }

    assert not {
        "daemon_pid",
        "process",
        "service_status",
        "start_command",
        "worker_count",
    } & configuration_fields


def test_runtime_contract_contains_no_deployment_specific_network_client() -> None:
    runtime_fields = {field.name for field in fields(type(make_runtime()))}

    assert not {
        "api_client",
        "agent_client",
        "external_endpoint",
        "node_client",
        "remote_repository",
    } & runtime_fields
