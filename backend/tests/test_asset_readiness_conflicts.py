from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from asset_readiness_fixtures import (
    BASE_TIME,
    FILESYSTEM_TIME,
    HOST_ID,
    MINIMUM_INTERVAL,
    VOLUME_ID,
    entity_id,
    make_access,
    make_bundle,
    make_candidate,
    make_finalization,
    make_policy,
    make_presence,
    make_request,
    make_snapshot,
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


def test_same_observation_id_with_different_facts_is_a_deterministic_conflict() -> None:
    original = make_snapshot(1, BASE_TIME, size_bytes=1000)
    conflicting = replace(original, size_bytes=1200)
    forward = make_bundle(snapshots=(original, conflicting))
    reverse = make_bundle(snapshots=(conflicting, original))

    first = make_policy().evaluate(make_candidate(), forward, make_request())
    second = make_policy().evaluate(make_candidate(), reverse, make_request())

    assert first == second
    assert first.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert first.blocking_observation_ids == (original.id,)
    assert reason_codes(first) == (
        AssetReadinessReasonCode.DUPLICATE_OBSERVATION_ID.value,
    )


def test_resource_identity_token_change_is_conflicting_not_insufficient() -> None:
    bundle = make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME, identity_token="generation-a"),
            make_snapshot(
                2,
                BASE_TIME + MINIMUM_INTERVAL,
                identity_token="generation-b",
            ),
        )
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert AssetReadinessReasonCode.RESOURCE_IDENTITY_CHANGED.value in reason_codes(result)


@pytest.mark.parametrize(
    "snapshot",
    (
        make_snapshot(1, BASE_TIME, source_host_id=entity_id(901)),
        make_snapshot(1, BASE_TIME, source_volume_id=entity_id(902)),
    ),
)
def test_authoritative_host_or_volume_mismatch_is_conflicting(snapshot: object) -> None:
    from app.contexts.production.asset_readiness import AssetResourceSnapshot

    assert isinstance(snapshot, AssetResourceSnapshot)
    bundle = make_bundle(snapshots=(snapshot,))

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert AssetReadinessReasonCode.RESOURCE_IDENTITY_CHANGED.value in reason_codes(result)


def test_replacement_never_silently_reuses_the_candidate() -> None:
    bundle = make_bundle(
        presences=(
            make_presence(
                1,
                BASE_TIME,
                AssetResourcePresenceStatus.REPLACED,
                identity_token="generation-b",
            ),
        )
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert AssetReadinessReasonCode.RESOURCE_REPLACED.value in reason_codes(result)


@pytest.mark.parametrize(
    "bundle",
    (
        make_bundle(
            writes=(
                make_write(1, BASE_TIME, AssetWriteStateStatus.ACTIVE),
                make_write(2, BASE_TIME, AssetWriteStateStatus.INACTIVE),
            )
        ),
        make_bundle(
            accesses=(
                make_access(1, BASE_TIME, AssetReadAccessStatus.READABLE),
                make_access(2, BASE_TIME, AssetReadAccessStatus.UNREADABLE),
            )
        ),
        make_bundle(
            presences=(
                make_presence(1, BASE_TIME, AssetResourcePresenceStatus.PRESENT),
                make_presence(2, BASE_TIME, AssetResourcePresenceStatus.MISSING),
            )
        ),
    ),
)
def test_same_time_incompatible_state_claims_are_conflicting(bundle: object) -> None:
    from app.contexts.production.asset_readiness import AssetReadinessObservationBundle

    assert isinstance(bundle, AssetReadinessObservationBundle)
    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT.value in reason_codes(
        result
    )


def test_size_growth_after_strong_finalization_is_conflicting_even_with_one_later_sample() -> None:
    bundle = make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME - timedelta(seconds=1), size_bytes=1000),
            make_snapshot(2, BASE_TIME + timedelta(seconds=1), size_bytes=1200),
        ),
        finalizations=(make_finalization(),),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=2)),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert AssetReadinessReasonCode.FINALIZATION_CONTRADICTED.value in reason_codes(result)
    assert AssetReadinessReasonCode.RESOURCE_CONTINUED_GROWING.value in reason_codes(result)


def test_modification_change_after_strong_finalization_is_conflicting() -> None:
    bundle = make_bundle(
        snapshots=(
            make_snapshot(
                1,
                BASE_TIME - timedelta(seconds=1),
                filesystem_modified_at=FILESYSTEM_TIME,
            ),
            make_snapshot(
                2,
                BASE_TIME + timedelta(seconds=1),
                filesystem_modified_at=FILESYSTEM_TIME + timedelta(seconds=1),
            ),
        ),
        finalizations=(make_finalization(),),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=2)),),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION
    assert AssetReadinessReasonCode.MODIFICATION_TIMESTAMP_CHANGED.value in reason_codes(
        result
    )


def test_latest_presence_missing_blocks_earlier_present() -> None:
    bundle = make_bundle(
        finalizations=(make_finalization(),),
        presences=(
            make_presence(1, BASE_TIME, AssetResourcePresenceStatus.PRESENT),
            make_presence(
                2,
                BASE_TIME + timedelta(seconds=1),
                AssetResourcePresenceStatus.MISSING,
            ),
        ),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.NOT_SAFE_TO_READ
    assert AssetReadinessReasonCode.RESOURCE_MISSING.value in reason_codes(result)


def test_later_present_state_can_replace_an_older_missing_state_without_identity_change() -> None:
    bundle = make_bundle(
        finalizations=(make_finalization(),),
        presences=(
            make_presence(
                1,
                BASE_TIME - timedelta(seconds=1),
                AssetResourcePresenceStatus.MISSING,
            ),
            make_presence(
                2,
                BASE_TIME + timedelta(seconds=1),
                AssetResourcePresenceStatus.PRESENT,
            ),
        ),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ


def test_conflict_reason_order_is_semantic_not_input_order() -> None:
    first = make_snapshot(1, BASE_TIME, identity_token="generation-a")
    second = make_snapshot(
        2,
        BASE_TIME + MINIMUM_INTERVAL,
        identity_token="generation-b",
        source_host_id=entity_id(950),
    )
    replacement = make_presence(
        1,
        BASE_TIME + timedelta(seconds=1),
        AssetResourcePresenceStatus.REPLACED,
        identity_token="generation-c",
    )
    bundle = make_bundle(
        snapshots=(second, first),
        presences=(replacement,),
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert reason_codes(result) == (
        AssetReadinessReasonCode.RESOURCE_IDENTITY_CHANGED.value,
        AssetReadinessReasonCode.RESOURCE_REPLACED.value,
    )


def test_known_matching_host_and_volume_are_not_conflicts() -> None:
    bundle = make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME, source_host_id=HOST_ID, source_volume_id=VOLUME_ID),
        )
    )

    result = make_policy().evaluate(make_candidate(), bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION


def test_candidate_runtime_identity_is_not_inferred_from_profile() -> None:
    candidate = make_candidate()
    changed_runtime = replace(candidate, source_runtime_id=entity_id(970))
    bundle = make_bundle(snapshots=(make_snapshot(1, BASE_TIME),))

    result = make_policy().evaluate(changed_runtime, bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INVALID_REQUEST
    assert AssetReadinessReasonCode.SOURCE_RUNTIME_MISMATCH.value in reason_codes(result)
