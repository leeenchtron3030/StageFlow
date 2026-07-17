from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, cast

import pytest
from runtime_fixtures import (
    AVAILABILITY_AT,
    CONFIGURED_AT,
    HOST_ID,
    RUNTIME_ID,
    STAGE_ID,
    entity_id,
    make_runtime,
)

from app.contexts.production.completed_media_asset import CompletedMediaAssetKind
from app.contexts.production.runtime import (
    RuntimeAssetAssemblyPlan,
    RuntimeAvailabilityStatus,
    RuntimeCapabilitySupportStatus,
    RuntimeConfiguration,
    RuntimeContextSource,
    RuntimeHealthStatus,
    RuntimeHost,
    RuntimeIdentity,
    RuntimeIntegritySource,
    RuntimeProfile,
    RuntimeSourceLocationHandlingPolicy,
    RuntimeSummary,
    RuntimeSummaryPrivacyPolicy,
    RuntimeTechnicalDescriptionSource,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    RuntimeVersion,
    StageFlowRuntime,
    validate_runtime,
)


def test_top_level_runtime_retains_complete_declarative_graph() -> None:
    runtime = make_runtime()

    assert runtime.identity.runtime_id == RUNTIME_ID
    assert runtime.profile is RuntimeProfile.NODE
    assert runtime.host.host_id == HOST_ID
    assert runtime.configuration.runtime_id == RUNTIME_ID
    assert runtime.configuration.capability_set == runtime.capability_set
    assert runtime.configuration.collection_plans == runtime.collection_plans
    assert runtime.configuration.readiness_policy_selections == (
        runtime.readiness_policy_selections
    )
    assert runtime.configuration.asset_assembly_plans == runtime.asset_assembly_plans
    assert runtime.configured_at == CONFIGURED_AT


def test_runtime_identity_is_first_class_and_hostname_is_only_descriptive() -> None:
    identity = make_runtime().identity

    assert identity.runtime_id == RUNTIME_ID
    assert identity.host_id == HOST_ID
    assert identity.logical_name == "Synthetic Stage Runtime"
    assert identity.installation_id is not None
    assert identity.organization_id is not None
    assert identity.event_deployment_id is not None
    assert identity.configured_stage_ids == (STAGE_ID,)
    assert "host_name" not in {field.name for field in fields(RuntimeIdentity)}


def test_runtime_identity_contains_no_session_state_transfer_or_trust_fields() -> None:
    identity_fields = {field.name for field in fields(RuntimeIdentity)}

    assert not {
        "current_asset",
        "operational_state",
        "queue_position",
        "session_id",
        "transfer_state",
        "trust_score",
    } & identity_fields


def test_runtime_profile_vocabulary_is_exact() -> None:
    assert {profile.value for profile in RuntimeProfile} == {
        "agent",
        "node",
        "external_compatible",
        "development",
        "unknown",
    }


def test_runtime_version_retains_explicit_compatibility_schemas_and_build_time() -> None:
    version = make_runtime().software_version

    assert version.semantic_version == "1.0.0"
    assert version.contract_compatibility_version == "1.0"
    assert version.configuration_schema_version == "1.0"
    assert version.capability_schema_version == "1.0"
    assert version.build_identifier == "synthetic-build"
    assert version.build_timestamp is not None


def test_runtime_version_rejects_invalid_semver_and_naive_build_time() -> None:
    with pytest.raises(ValueError, match="semantic versioning"):
        RuntimeVersion(
            product_name="StageFlow Runtime",
            semantic_version="version-one",
            contract_compatibility_version="1.0",
            configuration_schema_version="1.0",
            capability_schema_version="1.0",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        RuntimeVersion(
            product_name="StageFlow Runtime",
            semantic_version="1.0.0",
            contract_compatibility_version="1.0",
            configuration_schema_version="1.0",
            capability_schema_version="1.0",
            build_timestamp=datetime(2026, 7, 17, 12),
        )


def test_host_description_is_supplied_and_does_not_inventory_hardware() -> None:
    host = make_runtime().host

    assert host.operating_system_family == "synthetic-os"
    assert host.architecture == "arm64"
    assert host.cpu_logical_count == 8
    assert host.memory_capacity_bytes == 16_000_000_000
    assert host.gpu_identifiers == ("synthetic-gpu",)
    assert host.local_volume_ids
    assert host.network_interface_ids
    assert not {"serial_number", "inventory_service", "benchmark"} & {
        field.name for field in fields(RuntimeHost)
    }


def test_host_rejects_nonpositive_capacity_declarations() -> None:
    host = make_runtime().host

    with pytest.raises(ValueError, match="positive"):
        replace(host, cpu_logical_count=0)
    with pytest.raises(ValueError, match="positive"):
        replace(host, memory_capacity_bytes=-1)


def test_runtime_configuration_is_distinct_from_runtime_identity() -> None:
    runtime = make_runtime()
    configuration = runtime.configuration

    assert configuration.id != runtime.identity.runtime_id
    assert configuration.runtime_id == runtime.identity.runtime_id
    assert configuration.enabled is True
    assert configuration.configured_at == CONFIGURED_AT
    assert configuration.configured_by_id is not None
    assert not {"persistence", "remote_update", "settings_service"} & {
        field.name for field in fields(RuntimeConfiguration)
    }


def test_reconfiguration_is_a_new_immutable_value() -> None:
    configuration = make_runtime().configuration
    replacement = replace(configuration, id=entity_id(900))

    assert replacement.id != configuration.id
    assert replacement.runtime_id == configuration.runtime_id
    with pytest.raises(FrozenInstanceError):
        configuration.enabled = False  # type: ignore[misc]


def test_assembly_plan_reuses_ed0048_vocabulary_without_constructing_an_asset() -> None:
    plan = make_runtime().asset_assembly_plans[0]

    assert plan.manifest_schema_name == "stageflow.completed_media_asset"
    assert plan.manifest_schema_version == "1.0"
    assert plan.supported_asset_kinds == (CompletedMediaAssetKind.RECORDING_SEGMENT,)
    assert plan.context_sources == (
        RuntimeContextSource.EXPLICIT_RUNTIME_CONFIGURATION,
    )
    assert plan.technical_description_sources == (
        RuntimeTechnicalDescriptionSource.RECORDER_STRUCTURED_METADATA,
    )
    assert plan.integrity_sources == (RuntimeIntegritySource.NONE,)
    assert plan.source_location_handling_policy is (
        RuntimeSourceLocationHandlingPolicy.READ_ONLY_REFERENCE
    )
    assert plan.summary_privacy_policy is (
        RuntimeSummaryPrivacyPolicy.OMIT_FULL_SOURCE_PATHS
    )
    assert "session_id" not in {field.name for field in fields(RuntimeAssetAssemblyPlan)}


def test_runtime_summary_is_privacy_safe_and_deterministic() -> None:
    runtime = make_runtime()
    validation = validate_runtime(runtime)

    first = RuntimeSummary.from_runtime(runtime, validation)
    second = RuntimeSummary.from_runtime(runtime, validation)

    assert first == second
    assert first.validation_outcome is RuntimeValidationOutcome.VALID
    assert first.enabled_collection_plan_count == 1
    assert first.configured_stage_ids == (STAGE_ID,)
    assert first.warning_codes == ()
    assert first.availability is RuntimeAvailabilityStatus.AVAILABLE
    assert first.health is RuntimeHealthStatus.HEALTHY
    assert not {
        "metadata",
        "opaque_location_reference",
        "serial_number",
        "source_path",
    } & {field.name for field in fields(RuntimeSummary)}


def test_runtime_summary_rejects_validation_for_another_runtime() -> None:
    runtime = make_runtime()
    validation = replace(validate_runtime(runtime), runtime_id=entity_id(999))

    with pytest.raises(ValueError, match="must match"):
        RuntimeSummary.from_runtime(runtime, validation)


def test_runtime_metadata_is_recursively_frozen_and_rejects_credentials() -> None:
    metadata: dict[str, Any] = {"nested": {"values": [1, 2]}}
    identity = replace(make_runtime().identity, metadata=metadata)
    cast(list[int], cast(dict[str, Any], metadata["nested"])["values"]).append(3)

    assert isinstance(identity.metadata, MappingProxyType)
    assert identity.metadata["nested"]["values"] == (1, 2)
    with pytest.raises(ValueError, match="credential"):
        replace(identity, metadata={"access_token": "synthetic-secret"})


def test_all_runtime_wall_clock_contracts_reject_naive_timestamps() -> None:
    runtime = make_runtime()

    with pytest.raises(ValueError, match="timezone-aware"):
        replace(runtime, configured_at=datetime(2026, 7, 17, 12))
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(runtime.health, assessed_at=datetime(2026, 7, 17, 12))
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(runtime.availability, declared_at=datetime(2026, 7, 17, 12))
    assert runtime.availability.declared_at == AVAILABILITY_AT


def test_top_level_contract_is_frozen_and_has_no_active_runtime_objects() -> None:
    runtime = make_runtime()
    forbidden = {
        "background_task",
        "collector",
        "database_connection",
        "filesystem_watcher",
        "network_client",
        "policy_object",
        "service_loop",
    }

    assert forbidden.isdisjoint(field.name for field in fields(StageFlowRuntime))
    with pytest.raises(FrozenInstanceError):
        runtime.profile = RuntimeProfile.AGENT  # type: ignore[misc]


def test_configuration_time_health_time_and_availability_time_are_distinct() -> None:
    runtime = make_runtime()

    assert runtime.configured_at < runtime.health.assessed_at
    assert runtime.health.assessed_at < runtime.availability.declared_at
    assert runtime.software_version.build_timestamp != runtime.configured_at
    assert runtime.capability_set.declared_at < runtime.configured_at
    assert runtime.event_mode.active_until is not None
    assert runtime.event_mode.active_until - runtime.configured_at == timedelta(hours=12)


def test_runtime_id_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    health = replace(runtime.health, runtime_id=entity_id(920))
    changed = replace(runtime, health=health)
    result = validate_runtime(changed)

    assert result.outcome is RuntimeValidationOutcome.INVALID
    assert any(
        reason.code is RuntimeValidationReasonCode.RUNTIME_ID_MISMATCH
        for reason in result.reasons
    )


def test_profile_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    identity = replace(runtime.identity, deployment_profile=RuntimeProfile.AGENT)
    changed = replace(runtime, identity=identity)

    assert any(
        reason.code is RuntimeValidationReasonCode.PROFILE_MISMATCH
        for reason in validate_runtime(changed).reasons
    )


def test_host_identity_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    identity = replace(runtime.identity, host_id=entity_id(921))
    changed = replace(runtime, identity=identity)

    assert any(
        reason.code is RuntimeValidationReasonCode.HOST_ID_MISMATCH
        for reason in validate_runtime(changed).reasons
    )


def test_configuration_schema_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    version = replace(runtime.software_version, configuration_schema_version="2.0")
    changed = replace(runtime, software_version=version)

    assert any(
        reason.code is RuntimeValidationReasonCode.CONFIGURATION_SCHEMA_MISMATCH
        for reason in validate_runtime(changed).reasons
    )


def test_capability_schema_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    version = replace(runtime.software_version, capability_schema_version="2.0")
    changed = replace(runtime, software_version=version)

    assert any(
        reason.code is RuntimeValidationReasonCode.CAPABILITY_SCHEMA_MISMATCH
        for reason in validate_runtime(changed).reasons
    )


def test_top_level_configuration_graph_drift_is_invalid() -> None:
    runtime = make_runtime()
    capability_set = replace(runtime.capability_set, id=entity_id(922))
    changed = replace(runtime, capability_set=capability_set)

    assert any(
        reason.code is RuntimeValidationReasonCode.CONFIGURATION_GRAPH_MISMATCH
        for reason in validate_runtime(changed).reasons
    )


def test_validation_reason_order_is_independent_of_capability_input_order() -> None:
    runtime = make_runtime()
    capability = runtime.capability_set.capabilities[0]
    conflicting = replace(
        capability,
        support_status=RuntimeCapabilitySupportStatus.UNSUPPORTED,
    )
    first_set = replace(
        runtime.capability_set,
        capabilities=(conflicting, *runtime.capability_set.capabilities),
    )
    second_set = replace(
        runtime.capability_set,
        capabilities=(*reversed(runtime.capability_set.capabilities), conflicting),
    )
    first = replace(
        runtime,
        capability_set=first_set,
        configuration=replace(runtime.configuration, capability_set=first_set),
    )
    second = replace(
        runtime,
        capability_set=second_set,
        configuration=replace(runtime.configuration, capability_set=second_set),
    )

    assert validate_runtime(first) == validate_runtime(second)
