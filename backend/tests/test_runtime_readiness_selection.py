from __future__ import annotations

from dataclasses import fields, replace

import pytest
from runtime_fixtures import (
    POLICY_ID,
    capability_id,
    entity_id,
    make_parameters,
    make_runtime,
    synchronize_runtime,
    validation_codes,
)

from app.contexts.production.runtime import (
    RuntimeCapabilityKind,
    RuntimeCapabilitySupportStatus,
    RuntimeContextSource,
    RuntimeReadinessFallback,
    RuntimeReadinessPolicySelection,
    RuntimeReadinessRoute,
    RuntimeSourceLocationHandlingPolicy,
    RuntimeSummaryPrivacyPolicy,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    validate_runtime,
)


def test_ed0049_parameters_are_embedded_explicitly_in_selection() -> None:
    selection = make_runtime().readiness_policy_selections[0]

    assert selection.policy_id == POLICY_ID
    assert selection.policy_version == "1.0"
    assert selection.policy_parameters == make_parameters()
    assert selection.policy_parameters.require_read_access_for_stability is True
    assert selection.policy_parameters.require_inactive_write_when_available is True
    assert selection.policy_parameters.require_post_finalization_presence is True


def test_readiness_selection_rejects_parameter_version_mismatch() -> None:
    selection = make_runtime().readiness_policy_selections[0]

    with pytest.raises(ValueError, match="versions must match"):
        replace(selection, policy_version="2.0")


def test_readiness_required_and_optional_capabilities_cannot_overlap() -> None:
    selection = make_runtime().readiness_policy_selections[0]
    overlapping = selection.required_capability_ids[0]

    with pytest.raises(ValueError, match="required and optional"):
        replace(selection, optional_capability_ids=(overlapping,))


def test_strong_then_stability_route_is_valid_with_complete_capabilities() -> None:
    runtime = make_runtime(route=RuntimeReadinessRoute.STRONG_THEN_STABILITY)

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_stability_route_is_valid_with_explicit_ed0049_requirements() -> None:
    runtime = make_runtime(route=RuntimeReadinessRoute.STABILITY_DERIVED)

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID
    required = runtime.readiness_policy_selections[0].required_capability_ids
    assert capability_id(RuntimeCapabilityKind.STABLE_RESOURCE_IDENTITY) in required


def test_stability_route_without_required_read_access_is_invalid() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STABILITY_DERIVED,
        include_read=False,
    )

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.INVALID
    codes = validation_codes(runtime)
    assert RuntimeValidationReasonCode.CAPABILITY_UNAVAILABLE.value in codes
    assert (
        RuntimeValidationReasonCode.STABILITY_READ_ACCESS_CAPABILITY_MISSING.value
        in codes
    )


def test_stability_route_without_required_write_state_is_invalid() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STABILITY_DERIVED,
        include_write=False,
    )

    assert (
        RuntimeValidationReasonCode.STABILITY_WRITE_STATE_CAPABILITY_MISSING.value
        in validation_codes(runtime)
    )


def test_stability_route_without_stable_identity_is_invalid_without_node_exemption() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STABILITY_DERIVED,
        include_stable_identity=False,
    )

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.INVALID
    assert (
        RuntimeValidationReasonCode.STABILITY_IDENTITY_CAPABILITY_MISSING.value
        in validation_codes(runtime)
    )


def test_strong_route_remains_valid_when_optional_stability_capabilities_are_absent() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STRONG_FINALIZATION,
        include_read=False,
        include_write=False,
    )

    assert validate_runtime(runtime).outcome is (
        RuntimeValidationOutcome.VALID_WITH_LIMITATIONS
    )
    assert RuntimeValidationReasonCode.OPTIONAL_CAPABILITY_UNAVAILABLE.value in (
        validation_codes(runtime)
    )


def test_strong_route_without_accepted_finalization_is_invalid() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STRONG_FINALIZATION,
        include_strong=False,
    )

    assert (
        RuntimeValidationReasonCode.STRONG_FINALIZATION_CAPABILITY_MISSING.value
        in validation_codes(runtime)
    )


def test_strong_route_requires_presence_when_ed0049_parameters_require_it() -> None:
    runtime = make_runtime(route=RuntimeReadinessRoute.STRONG_FINALIZATION)
    readiness = replace(
        runtime.capability_set.readiness_capabilities[0],
        presence_support=False,
    )
    capability_set = replace(
        runtime.capability_set,
        readiness_capabilities=(readiness,),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert RuntimeValidationReasonCode.STRONG_PRESENCE_CAPABILITY_MISSING.value in (
        validation_codes(changed)
    )


def test_strong_first_route_may_declare_stability_fallback() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STRONG_THEN_STABILITY,
        fallback=RuntimeReadinessFallback.USE_STABILITY_ROUTE,
    )

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_unavailable_preferred_strong_route_can_use_complete_stability_fallback() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STRONG_FINALIZATION,
        fallback=RuntimeReadinessFallback.USE_STABILITY_ROUTE,
        include_strong=False,
    )

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID
    assert (
        RuntimeValidationReasonCode.STRONG_FINALIZATION_CAPABILITY_MISSING.value
        not in validation_codes(runtime)
    )


def test_stability_fallback_on_non_strong_route_is_invalid() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STABILITY_DERIVED,
        fallback=RuntimeReadinessFallback.USE_STABILITY_ROUTE,
    )

    assert RuntimeValidationReasonCode.INVALID_READINESS_FALLBACK.value in (
        validation_codes(runtime)
    )


def test_disabled_route_cannot_declare_fallback() -> None:
    runtime = make_runtime(route=RuntimeReadinessRoute.DISABLED)
    selection = replace(
        runtime.readiness_policy_selections[0],
        fallback_behavior=RuntimeReadinessFallback.REMAIN_INSUFFICIENT,
    )
    changed = synchronize_runtime(runtime, readiness_selections=(selection,))

    assert RuntimeValidationReasonCode.INVALID_READINESS_FALLBACK.value in (
        validation_codes(changed)
    )


def test_unknown_readiness_capability_reference_is_invalid() -> None:
    runtime = make_runtime()
    selection = replace(
        runtime.readiness_policy_selections[0],
        readiness_capability_id=entity_id(820),
    )
    changed = synchronize_runtime(runtime, readiness_selections=(selection,))

    assert RuntimeValidationReasonCode.READINESS_CAPABILITY_MISSING.value in (
        validation_codes(changed)
    )


def test_unsupported_policy_identifier_is_invalid() -> None:
    runtime = make_runtime()
    selection = replace(
        runtime.readiness_policy_selections[0],
        policy_id=entity_id(821),
    )
    changed = synchronize_runtime(runtime, readiness_selections=(selection,))

    assert RuntimeValidationReasonCode.READINESS_POLICY_UNSUPPORTED.value in (
        validation_codes(changed)
    )


def test_assembly_plan_requires_declared_assembly_capability() -> None:
    runtime = make_runtime()
    general = tuple(
        replace(
            capability,
            support_status=RuntimeCapabilitySupportStatus.UNSUPPORTED,
        )
        if capability.kind is RuntimeCapabilityKind.COMPLETED_ASSET_ASSEMBLY
        else capability
        for capability in runtime.capability_set.capabilities
    )
    capability_set = replace(runtime.capability_set, capabilities=general)
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert RuntimeValidationReasonCode.ASSET_ASSEMBLY_CAPABILITY_MISSING.value in (
        validation_codes(changed)
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("manifest_schema_name", "stageflow.unknown"),
        ("manifest_schema_version", "2.0"),
    ],
)
def test_assembly_plan_requires_exact_ed0048_manifest_contract(
    field_name: str,
    value: str,
) -> None:
    runtime = make_runtime()
    plan = replace(runtime.asset_assembly_plans[0], **{field_name: value})
    changed = synchronize_runtime(runtime, assembly_plans=(plan,))

    assert RuntimeValidationReasonCode.ASSET_MANIFEST_SCHEMA_MISMATCH.value in (
        validation_codes(changed)
    )


def test_assembly_plan_requires_explicit_source_location_privacy() -> None:
    runtime = make_runtime()
    plan = replace(
        runtime.asset_assembly_plans[0],
        source_location_handling_policy=RuntimeSourceLocationHandlingPolicy.UNKNOWN,
        summary_privacy_policy=RuntimeSummaryPrivacyPolicy.UNKNOWN,
    )
    changed = synchronize_runtime(runtime, assembly_plans=(plan,))

    assert RuntimeValidationReasonCode.ASSET_PRIVACY_POLICY_UNKNOWN.value in (
        validation_codes(changed)
    )


@pytest.mark.parametrize(
    "context_source",
    [RuntimeContextSource.FILENAME_HINT_ONLY, RuntimeContextSource.PATH_HINT_ONLY],
)
def test_filename_and_path_context_remain_non_authoritative_limitations(
    context_source: RuntimeContextSource,
) -> None:
    runtime = make_runtime(context_sources=(context_source,))

    assert validate_runtime(runtime).outcome is (
        RuntimeValidationOutcome.VALID_WITH_LIMITATIONS
    )
    assert RuntimeValidationReasonCode.NON_AUTHORITATIVE_CONTEXT_HINT.value in (
        validation_codes(runtime)
    )


def test_readiness_and_assembly_contracts_do_not_execute_policy_or_build_assets() -> None:
    runtime = make_runtime()
    readiness_fields = {
        field.name
        for field in fields(RuntimeReadinessPolicySelection)
    }
    assembly_fields = {
        field.name for field in fields(type(runtime.asset_assembly_plans[0]))
    }

    assert not {"candidate", "evaluation", "result", "safe_to_read"} & (
        readiness_fields
    )
    assert not {"asset", "checksum", "manifest", "output_path"} & assembly_fields
