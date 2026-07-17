from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime

import pytest
from runtime_fixtures import (
    HOST_ID,
    PLAN_ID,
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
    RuntimeCapabilityKind,
    RuntimeCapabilitySupportStatus,
    RuntimeCollectionMode,
    RuntimeObservationType,
    RuntimeSourceLocationScheme,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    validate_runtime,
)


def test_collection_target_is_an_explicit_non_authoritative_source_declaration() -> None:
    target = make_runtime().collection_plans[0].targets[0]

    assert target.source_capability_id == SOURCE_CAPABILITY_ID
    assert target.source_location_scheme is RuntimeSourceLocationScheme.LOCAL_FILE
    assert target.source_host_id == HOST_ID
    assert target.source_volume_id == VOLUME_ID
    assert target.configured_stage_id is not None
    assert target.configured_recording_block_id is not None
    assert target.opaque_location_reference == "/synthetic/event/recordings"
    assert "session_id" not in {field.name for field in fields(type(target))}


@pytest.mark.parametrize(
    "reference",
    [
        "https://operator:secret@example.invalid/recording",
        "/recording?access_token=synthetic-secret",
        "/recording?api_key=synthetic-secret",
        "/recording?password=synthetic-secret",
    ],
)
def test_collection_target_rejects_credential_bearing_references(
    reference: str,
) -> None:
    target = make_runtime().collection_plans[0].targets[0]

    with pytest.raises(ValueError, match="credential"):
        replace(target, opaque_location_reference=reference)


def test_collection_plan_references_policies_and_capabilities_by_id() -> None:
    runtime = make_runtime()
    plan = runtime.collection_plans[0]

    assert plan.id == PLAN_ID
    assert plan.resource_policy_id == runtime.resource_policy.id
    assert plan.event_mode_id == runtime.event_mode.id
    assert plan.readiness_policy_selection_id == runtime.readiness_policy_selections[0].id
    assert set(plan.observation_capability_ids) == {
        observation_capability_id(value)
        for value in RuntimeObservationType
    }


def test_enabled_collection_plan_requires_targets_and_observations() -> None:
    plan = make_runtime().collection_plans[0]

    with pytest.raises(ValueError, match="requires targets"):
        replace(plan, targets=())
    with pytest.raises(ValueError, match="requires targets"):
        replace(plan, observation_capability_ids=())


def test_collection_plan_rejects_naive_time_boundaries() -> None:
    plan = make_runtime().collection_plans[0]

    with pytest.raises(ValueError, match="timezone-aware"):
        replace(plan, starts_at=datetime(2026, 7, 17, 12))


def test_collection_reference_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    plan = replace(runtime.collection_plans[0], resource_policy_id=entity_id(800))
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.COLLECTION_REFERENCE_MISMATCH.value in (
        validation_codes(changed)
    )


def test_unknown_source_capability_is_invalid() -> None:
    runtime = make_runtime()
    target = replace(
        runtime.collection_plans[0].targets[0],
        source_capability_id=entity_id(801),
    )
    plan = replace(runtime.collection_plans[0], targets=(target,))
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.SOURCE_CAPABILITY_MISSING.value in (
        validation_codes(changed)
    )


def test_unsupported_source_scheme_is_invalid() -> None:
    runtime = make_runtime()
    target = replace(
        runtime.collection_plans[0].targets[0],
        source_location_scheme=RuntimeSourceLocationScheme.NETWORK_SHARE,
    )
    plan = replace(runtime.collection_plans[0], targets=(target,))
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.SOURCE_SCHEME_UNSUPPORTED.value in (
        validation_codes(changed)
    )


def test_unsupported_source_host_is_invalid() -> None:
    runtime = make_runtime()
    target = replace(
        runtime.collection_plans[0].targets[0],
        source_host_id=entity_id(802),
    )
    plan = replace(runtime.collection_plans[0], targets=(target,))
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.SOURCE_HOST_UNSUPPORTED.value in (
        validation_codes(changed)
    )


def test_unsupported_source_volume_is_invalid() -> None:
    runtime = make_runtime()
    target = replace(
        runtime.collection_plans[0].targets[0],
        source_volume_id=entity_id(803),
    )
    plan = replace(runtime.collection_plans[0], targets=(target,))
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.SOURCE_VOLUME_UNSUPPORTED.value in (
        validation_codes(changed)
    )


def test_unknown_observation_capability_is_invalid() -> None:
    runtime = make_runtime()
    plan = replace(
        runtime.collection_plans[0],
        observation_capability_ids=(entity_id(804),),
    )
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.OBSERVATION_CAPABILITY_MISSING.value in (
        validation_codes(changed)
    )


def test_unavailable_selected_observation_capability_is_invalid() -> None:
    runtime = make_runtime()
    general = tuple(
        replace(
            capability,
            support_status=RuntimeCapabilitySupportStatus.UNSUPPORTED,
        )
        if capability.id
        == capability_id(RuntimeCapabilityKind.RESOURCE_SNAPSHOT_COLLECTION)
        else capability
        for capability in runtime.capability_set.capabilities
    )
    capability_set = replace(runtime.capability_set, capabilities=general)
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert RuntimeValidationReasonCode.CAPABILITY_UNAVAILABLE.value in (
        validation_codes(changed)
    )


def test_unavailable_selected_source_capability_is_invalid() -> None:
    runtime = make_runtime()
    general = tuple(
        replace(
            capability,
            support_status=RuntimeCapabilitySupportStatus.UNSUPPORTED,
        )
        if capability.id
        == capability_id(RuntimeCapabilityKind.LOCAL_FILESYSTEM_ACCESS)
        else capability
        for capability in runtime.capability_set.capabilities
    )
    capability_set = replace(runtime.capability_set, capabilities=general)
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert RuntimeValidationReasonCode.CAPABILITY_UNAVAILABLE.value in (
        validation_codes(changed)
    )


def test_collection_mode_mismatch_is_invalid() -> None:
    runtime = make_runtime()
    plan = replace(
        runtime.collection_plans[0],
        collection_modes=(RuntimeCollectionMode.EVENT_DRIVEN,),
    )
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.COLLECTION_MODE_UNSUPPORTED.value in (
        validation_codes(changed)
    )


def test_target_observation_type_must_be_selected_and_supported() -> None:
    runtime = make_runtime()
    plan = replace(
        runtime.collection_plans[0],
        observation_capability_ids=(
            observation_capability_id(RuntimeObservationType.RESOURCE_SNAPSHOT),
        ),
    )
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.OBSERVATION_TYPE_UNSUPPORTED.value in (
        validation_codes(changed)
    )


def test_collection_plan_input_order_does_not_change_normalized_value() -> None:
    runtime = make_runtime()
    plan = runtime.collection_plans[0]
    second_target = replace(plan.targets[0], id=entity_id(805))
    reordered = replace(
        plan,
        targets=(second_target, *plan.targets),
        observation_capability_ids=tuple(reversed(plan.observation_capability_ids)),
        collection_modes=tuple(reversed(plan.collection_modes)),
    )
    canonical = replace(plan, targets=(*plan.targets, second_target))

    assert reordered == canonical


def test_disabled_collection_plan_does_not_execute_or_claim_observations() -> None:
    runtime = make_runtime()
    plan = replace(
        runtime.collection_plans[0],
        enabled=False,
        targets=(),
        observation_capability_ids=(),
    )
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert validate_runtime(changed).outcome is RuntimeValidationOutcome.VALID
    assert not {
        "collected_facts",
        "execute",
        "poll_interval",
        "results",
        "watcher",
    } & {field.name for field in fields(type(plan))}
