from __future__ import annotations

from datetime import timedelta

import pytest
from asset_readiness_fixtures import (
    BASE_TIME,
    COMPLETION_ID,
    EVALUATED_AT,
    MARKER_ID,
    MINIMUM_INTERVAL,
    POLICY_ID,
    READINESS_ID,
    RUNTIME_ID,
    entity_id,
    make_access,
    make_bundle,
    make_candidate,
    make_finalization,
    make_parameters,
    make_policy,
    make_presence,
    make_request,
    make_snapshot,
    make_stability_bundle,
    make_write,
    reason_codes,
)

from app.contexts.production.asset_readiness import (
    AssetReadAccessStatus,
    AssetReadinessOutcome,
    AssetReadinessReasonCode,
    AssetResourcePresenceStatus,
    AssetWriteStateStatus,
)
from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetReadinessStatus,
)


@pytest.mark.parametrize(
    "method,reason_code",
    (
        (
            CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
            AssetReadinessReasonCode.EXPLICIT_RECORDER_FINALIZATION_OBSERVED,
        ),
        (
            CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION,
            AssetReadinessReasonCode.CLOSED_SEGMENT_NOTIFICATION_OBSERVED,
        ),
        (
            CompletedMediaAssetCompletionMethod.ATOMIC_RENAME_OBSERVED,
            AssetReadinessReasonCode.ATOMIC_RENAME_OBSERVED,
        ),
        (
            CompletedMediaAssetCompletionMethod.SIDECAR_COMPLETION_MARKER,
            AssetReadinessReasonCode.COMPLETION_MARKER_OBSERVED,
        ),
    ),
)
def test_every_supported_strong_finalization_route_is_safe(
    method: CompletedMediaAssetCompletionMethod,
    reason_code: AssetReadinessReasonCode,
) -> None:
    finalization = make_finalization(method=method)
    bundle = make_bundle(
        finalizations=(finalization,),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert result.selected_completion_method is method
    assert reason_code.value in reason_codes(result)
    assert result.completion_declaration is not None
    assert result.completion_declaration.id == COMPLETION_ID
    assert result.completion_declaration.finalized_at == BASE_TIME
    assert result.completion_declaration.declaring_runtime_or_adapter_id == (
        finalization.declaring_entity_id
    )
    assert result.readiness_declaration is not None
    assert result.readiness_declaration.id == READINESS_ID
    assert result.readiness_declaration.assessed_at == EVALUATED_AT
    assert result.readiness_declaration.status is (
        CompletedMediaAssetReadinessStatus.SAFE_TO_READ
    )
    if method is CompletedMediaAssetCompletionMethod.SIDECAR_COMPLETION_MARKER:
        assert result.completion_declaration.completion_marker_reference_id == MARKER_ID


def test_strong_route_without_optional_read_or_write_capability_is_safe_with_limitations() -> None:
    bundle = make_bundle(
        finalizations=(make_finalization(),),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
        writes=(
            make_write(
                1,
                BASE_TIME + timedelta(seconds=1),
                AssetWriteStateStatus.UNSUPPORTED,
                limitations=("handle inspection unsupported",),
            ),
        ),
        accesses=(
            make_access(
                1,
                BASE_TIME + timedelta(seconds=1),
                AssetReadAccessStatus.UNSUPPORTED,
                limitations=("read check unsupported",),
            ),
        ),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert "write-state inspection unavailable" in result.limitations
    assert "read access not independently assessed" in result.limitations
    assert result.completion_declaration is not None
    assert result.completion_declaration.limitations == result.limitations
    assert result.readiness_declaration is not None
    assert result.readiness_declaration.limitations == result.limitations


def test_strong_route_requires_post_finalization_presence_under_explicit_parameters() -> None:
    bundle = make_bundle(finalizations=(make_finalization(),))

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION
    assert AssetReadinessReasonCode.RESOURCE_PRESENCE_NOT_CONFIRMED.value in reason_codes(
        result
    )
    assert (
        AssetReadinessReasonCode.REQUIRED_POST_FINALIZATION_OBSERVATION_MISSING.value
        in reason_codes(result)
    )
    assert result.completion_declaration is None


def test_strong_route_can_explicitly_disable_post_finalization_presence_requirement() -> None:
    parameters = make_parameters(require_post_finalization_presence=False)
    bundle = make_bundle(finalizations=(make_finalization(),))

    result = make_policy(parameters).evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ


def test_closed_segment_does_not_require_complete_recording_or_session_identity() -> None:
    finalization = make_finalization(
        method=CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION
    )
    bundle = make_bundle(
        finalizations=(finalization,),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert "session_id" not in result.metadata


def test_complete_stability_route_produces_distinct_completion_and_readiness_times() -> None:
    result = make_policy().evaluate(
        make_candidate(),
        make_stability_bundle(),
        make_request(),
    )

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert result.selected_completion_method is (
        CompletedMediaAssetCompletionMethod.STABLE_FILE_OBSERVATION
    )
    assert result.stability_window is not None
    assert result.stability_window.started_at == BASE_TIME
    assert result.stability_window.ended_at == BASE_TIME + MINIMUM_INTERVAL
    assert result.completion_declaration is not None
    assert result.completion_declaration.finalized_at == BASE_TIME + MINIMUM_INTERVAL
    assert result.readiness_declaration is not None
    assert result.readiness_declaration.assessed_at == EVALUATED_AT
    assert result.completion_declaration.source_reference_ids == (
        result.supporting_observation_ids
    )


def test_stable_size_alone_is_insufficient_and_creates_no_completion() -> None:
    bundle = make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME),
            make_snapshot(2, BASE_TIME + MINIMUM_INTERVAL),
        )
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION
    assert AssetReadinessReasonCode.READ_ACCESS_NOT_ASSESSED.value in reason_codes(result)
    assert AssetReadinessReasonCode.WRITE_STATE_UNKNOWN.value in reason_codes(result)
    assert (
        AssetReadinessReasonCode.RESOURCE_PRESENCE_NOT_CONFIRMED.value
        in reason_codes(result)
    )
    assert result.completion_declaration is None
    assert result.readiness_declaration is not None
    assert result.readiness_declaration.status is CompletedMediaAssetReadinessStatus.UNKNOWN


def test_stable_interval_too_short_is_insufficient() -> None:
    bundle = make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME),
            make_snapshot(2, BASE_TIME + timedelta(seconds=4)),
        )
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION
    assert AssetReadinessReasonCode.STABLE_INTERVAL_TOO_SHORT.value in reason_codes(result)


def test_empty_bundle_is_insufficient_with_no_completion_basis() -> None:
    result = make_policy().evaluate(make_candidate(), make_bundle(), make_request())

    assert result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION
    assert reason_codes(result) == (AssetReadinessReasonCode.NO_COMPLETION_BASIS.value,)
    assert result.completion_declaration is None


def test_one_snapshot_is_insufficient() -> None:
    bundle = make_bundle(snapshots=(make_snapshot(1, BASE_TIME),))

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION
    assert AssetReadinessReasonCode.INSUFFICIENT_SNAPSHOTS.value in reason_codes(result)


def test_continued_growth_is_current_not_safe_condition() -> None:
    bundle = make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME, size_bytes=1000),
            make_snapshot(2, BASE_TIME + MINIMUM_INTERVAL, size_bytes=1200),
        )
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.NOT_SAFE_TO_READ
    assert AssetReadinessReasonCode.RESOURCE_CONTINUED_GROWING.value in reason_codes(result)
    assert result.completion_declaration is None
    assert result.readiness_declaration is not None
    assert result.readiness_declaration.status is (
        CompletedMediaAssetReadinessStatus.NOT_SAFE_TO_READ
    )


@pytest.mark.parametrize(
    "bundle,reason",
    (
        (
            make_bundle(
                finalizations=(make_finalization(),),
                presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
                accesses=(
                    make_access(
                        1,
                        BASE_TIME + timedelta(seconds=1),
                        AssetReadAccessStatus.UNREADABLE,
                    ),
                ),
            ),
            AssetReadinessReasonCode.READ_ACCESS_FAILED,
        ),
        (
            make_bundle(
                finalizations=(make_finalization(),),
                presences=(
                    make_presence(
                        1,
                        BASE_TIME + timedelta(seconds=1),
                        AssetResourcePresenceStatus.MISSING,
                    ),
                ),
            ),
            AssetReadinessReasonCode.RESOURCE_MISSING,
        ),
    ),
)
def test_explicit_read_or_presence_failure_blocks_strong_route(
    bundle: object,
    reason: AssetReadinessReasonCode,
) -> None:
    from app.contexts.production.asset_readiness import AssetReadinessObservationBundle

    assert isinstance(bundle, AssetReadinessObservationBundle)
    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.NOT_SAFE_TO_READ
    assert reason.value in reason_codes(result)
    assert result.completion_declaration is None


def test_active_write_after_strong_finalization_is_conflicting() -> None:
    bundle = make_bundle(
        finalizations=(make_finalization(),),
        writes=(
            make_write(
                1,
                BASE_TIME + timedelta(seconds=1),
                AssetWriteStateStatus.ACTIVE,
            ),
        ),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=2)),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert AssetReadinessReasonCode.FINALIZATION_CONTRADICTED.value in reason_codes(result)
    assert AssetReadinessReasonCode.ACTIVE_WRITE_OBSERVED.value in reason_codes(result)


def test_active_write_before_finalization_does_not_become_a_later_contradiction() -> None:
    bundle = make_bundle(
        writes=(
            make_write(
                1,
                BASE_TIME - timedelta(seconds=1),
                AssetWriteStateStatus.ACTIVE,
            ),
        ),
        finalizations=(make_finalization(),),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ


def test_manual_declaration_requires_all_technical_safeguards() -> None:
    window_end = BASE_TIME + MINIMUM_INTERVAL
    manual_at = window_end
    bundle = make_bundle(
        snapshots=(make_snapshot(1, BASE_TIME), make_snapshot(2, window_end)),
        finalizations=(
            make_finalization(
                method=CompletedMediaAssetCompletionMethod.MANUAL_DECLARATION,
                observed_at=manual_at,
            ),
        ),
        writes=(make_write(1, manual_at, AssetWriteStateStatus.INACTIVE),),
        accesses=(make_access(1, manual_at, AssetReadAccessStatus.READABLE),),
        presences=(make_presence(1, manual_at),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert result.selected_completion_method is (
        CompletedMediaAssetCompletionMethod.MANUAL_DECLARATION
    )
    assert AssetReadinessReasonCode.MANUAL_DECLARATION_OBSERVED.value in reason_codes(
        result
    )


def test_manual_declaration_cannot_override_active_write() -> None:
    window_end = BASE_TIME + MINIMUM_INTERVAL
    bundle = make_bundle(
        snapshots=(make_snapshot(1, BASE_TIME), make_snapshot(2, window_end)),
        finalizations=(
            make_finalization(
                method=CompletedMediaAssetCompletionMethod.MANUAL_DECLARATION,
                observed_at=window_end,
            ),
        ),
        writes=(make_write(1, window_end, AssetWriteStateStatus.ACTIVE),),
        accesses=(make_access(1, window_end, AssetReadAccessStatus.READABLE),),
        presences=(make_presence(1, window_end),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.NOT_SAFE_TO_READ
    assert AssetReadinessReasonCode.ACTIVE_WRITE_OBSERVED.value in reason_codes(result)


@pytest.mark.parametrize(
    "method,reason",
    (
        (
            CompletedMediaAssetCompletionMethod.UNKNOWN,
            AssetReadinessReasonCode.FINALIZATION_METHOD_UNKNOWN,
        ),
        (
            CompletedMediaAssetCompletionMethod.OTHER_SUPPORTED_METHOD,
            AssetReadinessReasonCode.UNSUPPORTED_COMPLETION_METHOD,
        ),
    ),
)
def test_uninterpretable_completion_only_source_is_typed_as_unsupported(
    method: CompletedMediaAssetCompletionMethod,
    reason: AssetReadinessReasonCode,
) -> None:
    bundle = make_bundle(finalizations=(make_finalization(method=method),))

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.UNSUPPORTED_SOURCE
    assert reason.value in reason_codes(result)
    assert AssetReadinessReasonCode.UNSUPPORTED_SOURCE_CAPABILITY.value in reason_codes(
        result
    )


@pytest.mark.parametrize(
    "evaluation_request",
    (
        make_request(policy_id=entity_id(701)),
        make_request(policy_version="2.0"),
        make_request(candidate_id=entity_id(702)),
        make_request(resource_id=entity_id(703)),
    ),
)
def test_inconsistent_request_is_invalid(evaluation_request: object) -> None:
    from app.contexts.production.asset_readiness import AssetReadinessEvaluationRequest

    assert isinstance(evaluation_request, AssetReadinessEvaluationRequest)
    result = make_policy().evaluate(
        make_candidate(),
        make_bundle(),
        evaluation_request,
    )

    assert result.outcome is AssetReadinessOutcome.INVALID_REQUEST
    assert result.completion_declaration is None
    assert result.readiness_declaration is None


def test_observation_after_evaluation_is_invalid_without_wall_clock_substitution() -> None:
    evaluated_at = BASE_TIME
    observation_at = BASE_TIME + timedelta(seconds=1)
    request = make_request(evaluated_at=evaluated_at)
    bundle = make_bundle(
        finalizations=(make_finalization(observed_at=observation_at),),
        created_at=observation_at,
    )

    result = make_policy().evaluate(make_candidate(), bundle, request)

    assert result.outcome is AssetReadinessOutcome.INVALID_REQUEST
    assert AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT.value in reason_codes(
        result
    )


def test_runtime_mismatch_is_invalid() -> None:
    bundle = make_bundle(
        snapshots=(make_snapshot(1, BASE_TIME, source_runtime_id=entity_id(880)),)
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INVALID_REQUEST
    assert AssetReadinessReasonCode.SOURCE_RUNTIME_MISMATCH.value in reason_codes(result)


def test_latest_favorable_write_and_read_states_override_older_blockers_for_stability() -> None:
    window_end = BASE_TIME + MINIMUM_INTERVAL
    bundle = make_bundle(
        snapshots=(make_snapshot(1, BASE_TIME), make_snapshot(2, window_end)),
        writes=(
            make_write(1, window_end, AssetWriteStateStatus.ACTIVE),
            make_write(2, window_end + timedelta(seconds=1), AssetWriteStateStatus.INACTIVE),
        ),
        accesses=(
            make_access(1, window_end, AssetReadAccessStatus.UNREADABLE),
            make_access(2, window_end + timedelta(seconds=1), AssetReadAccessStatus.READABLE),
        ),
        presences=(make_presence(1, window_end + timedelta(seconds=1)),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ


def test_latest_unfavorable_read_state_blocks_earlier_success() -> None:
    bundle = make_bundle(
        finalizations=(make_finalization(),),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
        accesses=(
            make_access(1, BASE_TIME, AssetReadAccessStatus.READABLE),
            make_access(
                2,
                BASE_TIME + timedelta(seconds=2),
                AssetReadAccessStatus.UNREADABLE,
            ),
        ),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.NOT_SAFE_TO_READ
    assert AssetReadinessReasonCode.READ_ACCESS_FAILED.value in reason_codes(result)


def test_explicit_parameter_can_relax_optional_stability_capabilities_but_not_presence() -> None:
    parameters = make_parameters(
        require_read_access_for_stability=False,
        require_inactive_write_when_available=False,
    )
    window_end = BASE_TIME + MINIMUM_INTERVAL
    bundle = make_bundle(
        snapshots=(make_snapshot(1, BASE_TIME), make_snapshot(2, window_end)),
        presences=(make_presence(1, window_end),),
    )

    result = make_policy(parameters).evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert "read access not independently assessed" in result.limitations
    assert "write state not independently assessed" in result.limitations


def test_policy_never_intentionally_uses_unknown_for_classified_reference_scenarios() -> None:
    scenarios = (
        make_bundle(),
        make_stability_bundle(),
        make_bundle(finalizations=(make_finalization(),)),
        make_bundle(
            snapshots=(
                make_snapshot(1, BASE_TIME),
                make_snapshot(2, BASE_TIME + MINIMUM_INTERVAL, size_bytes=1200),
            )
        ),
    )

    outcomes = {
        make_policy().evaluate(make_candidate(), bundle, make_request()).outcome
        for bundle in scenarios
    }

    assert AssetReadinessOutcome.UNKNOWN not in outcomes
    assert POLICY_ID == make_policy().policy_id
    assert RUNTIME_ID == make_candidate().source_runtime_id
