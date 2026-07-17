from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime
from typing import cast

import pytest
from runtime_fixtures import (
    CONFIGURED_AT,
    HOST_ID,
    RUNTIME_ID,
    SOURCE_CAPABILITY_ID,
    VOLUME_ID,
    capability_id,
    entity_id,
    make_runtime,
    observation_capability_id,
    synchronize_runtime,
    validation_codes,
)

from app.contexts.production.runtime import (
    RuntimeCapability,
    RuntimeCapabilityKind,
    RuntimeCapabilitySet,
    RuntimeCapabilitySupportStatus,
    RuntimeCollectionMode,
    RuntimeObservationType,
    RuntimeSourceAccessMode,
    RuntimeSourceHostScope,
    RuntimeSourceLocationScheme,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    validate_runtime,
)


def test_capability_support_statuses_are_exact_and_categorical() -> None:
    assert {status.value for status in RuntimeCapabilitySupportStatus} == {
        "supported",
        "unsupported",
        "degraded",
        "unknown",
    }


def test_initial_capability_vocabulary_contains_required_declarative_kinds() -> None:
    values = {kind.value for kind in RuntimeCapabilityKind}

    assert {
        "candidate_discovery",
        "resource_snapshot_collection",
        "finalization_observation_collection",
        "write_state_observation_collection",
        "read_access_observation_collection",
        "resource_presence_observation_collection",
        "stable_resource_identity",
        "recorder_finalization_integration",
        "completed_asset_assembly",
        "resource_pressure_awareness",
        "event_mode_support",
        "health_reporting",
    } <= values
    assert "recorder_control" not in values
    assert "livestream_control" not in values
    assert "session_verification" not in values


def test_recorder_control_capability_is_rejected_at_contract_boundary() -> None:
    capability = make_runtime().capability_set.capabilities[0]

    with pytest.raises(ValueError, match="not approved"):
        replace(
            capability,
            kind=cast(RuntimeCapabilityKind, "recorder_control"),
        )


def test_degraded_capability_requires_first_class_limitation() -> None:
    capability = make_runtime().capability_set.capabilities[0]

    with pytest.raises(ValueError, match="requires a limitation"):
        replace(
            capability,
            support_status=RuntimeCapabilitySupportStatus.DEGRADED,
            limitations=(),
        )
    degraded = replace(
        capability,
        support_status=RuntimeCapabilitySupportStatus.DEGRADED,
        limitations=("collector precision reduced",),
    )
    assert degraded.limitations == ("collector precision reduced",)


def test_capability_set_order_is_deterministic() -> None:
    runtime = make_runtime()
    capability_set = runtime.capability_set
    reversed_set = replace(
        capability_set,
        capabilities=tuple(reversed(capability_set.capabilities)),
        source_capabilities=tuple(reversed(capability_set.source_capabilities)),
        observation_capabilities=tuple(
            reversed(capability_set.observation_capabilities)
        ),
    )

    assert reversed_set == capability_set


def test_exact_duplicate_capability_id_collapses_without_conflict() -> None:
    capability_set = make_runtime().capability_set
    capability = capability_set.capabilities[0]
    duplicated = replace(
        capability_set,
        capabilities=(capability, *capability_set.capabilities, capability),
    )

    assert duplicated.conflicting_capability_ids == ()
    assert duplicated.capabilities == capability_set.capabilities


def test_conflicting_duplicate_capability_id_is_invalid_deterministically() -> None:
    runtime = make_runtime()
    capability = runtime.capability_set.capabilities[0]
    conflicting = replace(
        capability,
        support_status=RuntimeCapabilitySupportStatus.UNSUPPORTED,
    )
    capability_set = replace(
        runtime.capability_set,
        capabilities=(conflicting, *runtime.capability_set.capabilities),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    result = validate_runtime(changed)

    assert result.outcome is RuntimeValidationOutcome.INVALID
    assert RuntimeValidationReasonCode.DUPLICATE_CAPABILITY_ID.value in validation_codes(
        changed
    )


def test_same_kind_scope_with_conflicting_states_is_invalid() -> None:
    runtime = make_runtime()
    original = runtime.capability_set.capabilities[0]
    conflicting = RuntimeCapability(
        id=entity_id(880),
        runtime_id=RUNTIME_ID,
        kind=original.kind,
        support_status=RuntimeCapabilitySupportStatus.UNSUPPORTED,
        capability_version=original.capability_version,
        scope=original.scope,
    )
    capability_set = replace(
        runtime.capability_set,
        capabilities=(*runtime.capability_set.capabilities, conflicting),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert validate_runtime(changed).outcome is RuntimeValidationOutcome.INVALID
    assert (
        RuntimeValidationReasonCode.CONFLICTING_CAPABILITY_KIND.value
        in validation_codes(changed)
    )


def test_same_kind_and_scope_with_separate_ids_is_invalid_even_if_status_matches() -> None:
    runtime = make_runtime()
    original = runtime.capability_set.capabilities[0]
    duplicate_scope = replace(original, id=entity_id(882))
    capability_set = replace(
        runtime.capability_set,
        capabilities=(*runtime.capability_set.capabilities, duplicate_scope),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert (
        RuntimeValidationReasonCode.CONFLICTING_CAPABILITY_KIND.value
        in validation_codes(changed)
    )


def test_duplicate_capability_id_with_different_parameters_is_invalid() -> None:
    runtime = make_runtime()
    original = runtime.capability_set.capabilities[0]
    conflicting = replace(original, parameters={"mode": "alternate"})
    capability_set = replace(
        runtime.capability_set,
        capabilities=(*runtime.capability_set.capabilities, conflicting),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert RuntimeValidationReasonCode.DUPLICATE_CAPABILITY_ID.value in validation_codes(
        changed
    )


def test_conflicting_specialized_capability_id_is_not_silently_overridden() -> None:
    runtime = make_runtime()
    source = runtime.capability_set.source_capabilities[0]
    conflicting = replace(
        source,
        supported_location_schemes=(RuntimeSourceLocationScheme.NETWORK_SHARE,),
    )
    capability_set = replace(
        runtime.capability_set,
        source_capabilities=(source, conflicting),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert source.id in capability_set.conflicting_capability_ids
    assert RuntimeValidationReasonCode.DUPLICATE_CAPABILITY_ID.value in validation_codes(
        changed
    )


def test_same_kind_may_have_distinct_scoped_declarations() -> None:
    runtime = make_runtime()
    original = runtime.capability_set.capabilities[0]
    scoped = replace(original, id=entity_id(881), scope="stage-b")
    capability_set = replace(
        runtime.capability_set,
        capabilities=(*runtime.capability_set.capabilities, scoped),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert capability_set.conflicting_capability_keys == ()
    assert validate_runtime(changed).outcome is RuntimeValidationOutcome.VALID


def test_source_capability_is_read_only_and_explicitly_scoped() -> None:
    source = make_runtime().capability_set.source_capabilities[0]

    assert source.id == SOURCE_CAPABILITY_ID
    assert source.runtime_capability_id == capability_id(
        RuntimeCapabilityKind.LOCAL_FILESYSTEM_ACCESS
    )
    assert source.supported_location_schemes == (
        RuntimeSourceLocationScheme.LOCAL_FILE,
    )
    assert source.supported_host_scope is RuntimeSourceHostScope.CONFIGURED_HOSTS
    assert source.supported_host_ids == (HOST_ID,)
    assert source.supported_volume_ids == (VOLUME_ID,)
    assert source.access_mode is RuntimeSourceAccessMode.READ_ONLY


def test_configured_source_host_scope_requires_host_ids() -> None:
    source = make_runtime().capability_set.source_capabilities[0]

    with pytest.raises(ValueError, match="requires at least one host"):
        replace(source, supported_host_ids=())


def test_observation_capabilities_map_all_ed0049_resource_fact_types() -> None:
    capabilities = make_runtime().capability_set.observation_capabilities

    assert {capability.observation_type for capability in capabilities} == set(
        RuntimeObservationType
    )
    assert all(
        capability.collection_mode is RuntimeCollectionMode.SUPPLIED_BY_ADAPTER
        for capability in capabilities
    )
    assert all(
        capability.supported_source_schemes
        == (RuntimeSourceLocationScheme.LOCAL_FILE,)
        for capability in capabilities
    )


def test_observation_capability_kind_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    observations = list(runtime.capability_set.observation_capabilities)
    observations[0] = replace(
        observations[0],
        runtime_capability_id=capability_id(
            RuntimeCapabilityKind.CANDIDATE_DISCOVERY
        ),
    )
    capability_set = replace(
        runtime.capability_set,
        observation_capabilities=observations,
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert validate_runtime(changed).outcome is RuntimeValidationOutcome.INVALID
    assert (
        RuntimeValidationReasonCode.SPECIALIZED_CAPABILITY_MISMATCH.value
        in validation_codes(changed)
    )


def test_readiness_capability_declares_routes_without_claiming_safety() -> None:
    readiness = make_runtime().capability_set.readiness_capabilities[0]

    assert readiness.snapshot_support is True
    assert readiness.write_state_support is True
    assert readiness.read_access_support is True
    assert readiness.presence_support is True
    assert readiness.stable_identity_support is True
    assert readiness.supported_policy_ids
    assert readiness.supported_policy_versions == ("1.0",)
    assert not {"outcome", "safe_to_read", "evaluation"} & {
        field.name for field in fields(type(readiness))
    }


def test_capability_timestamps_are_timezone_aware() -> None:
    capability_set = make_runtime().capability_set

    with pytest.raises(ValueError, match="timezone-aware"):
        replace(capability_set, declared_at=datetime(2026, 7, 17, 12))
    assert capability_set.declared_at < CONFIGURED_AT


def test_capability_set_is_frozen_and_defensively_copies_sequences() -> None:
    runtime = make_runtime()
    capabilities = list(runtime.capability_set.capabilities)
    capability_set = RuntimeCapabilitySet(
        id=runtime.capability_set.id,
        runtime_id=RUNTIME_ID,
        capability_schema_version="1.0",
        capabilities=capabilities,
        source_capabilities=runtime.capability_set.source_capabilities,
        observation_capabilities=runtime.capability_set.observation_capabilities,
        readiness_capabilities=runtime.capability_set.readiness_capabilities,
        declared_at=runtime.capability_set.declared_at,
    )
    capabilities.clear()

    assert capability_set.capabilities
    assert observation_capability_id(RuntimeObservationType.READ_ACCESS) in {
        capability.id for capability in capability_set.observation_capabilities
    }
