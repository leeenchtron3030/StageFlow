from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from asset_readiness_fixtures import (
    BASE_TIME,
    MINIMUM_INTERVAL,
    make_bundle,
    make_candidate,
    make_finalization,
    make_parameters,
    make_policy,
    make_presence,
    make_request,
    make_snapshot,
    make_stability_bundle,
)

from app.contexts.production.asset_readiness import (
    AssetReadinessOutcome,
    AssetReadinessSummary,
)
from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetRuntimeProfile,
)


@pytest.mark.parametrize(
    "profile",
    (
        CompletedMediaAssetRuntimeProfile.AGENT,
        CompletedMediaAssetRuntimeProfile.NODE,
        CompletedMediaAssetRuntimeProfile.EXTERNAL_COMPATIBLE_SOURCE,
        CompletedMediaAssetRuntimeProfile.UNKNOWN,
    ),
)
def test_every_runtime_profile_uses_the_same_strong_policy_rules(
    profile: CompletedMediaAssetRuntimeProfile,
) -> None:
    candidate = make_candidate(runtime_profile=profile)
    bundle = make_bundle(
        finalizations=(make_finalization(),),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
    )

    result = make_policy().evaluate(candidate, bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert result.policy_parameters == make_parameters()


def test_agent_and_node_equivalent_inputs_have_equivalent_semantic_results() -> None:
    agent = make_candidate(runtime_profile=CompletedMediaAssetRuntimeProfile.AGENT)
    node = make_candidate(runtime_profile=CompletedMediaAssetRuntimeProfile.NODE)
    bundle = make_stability_bundle()
    request = make_request()

    agent_result = make_policy().evaluate(agent, bundle, request)
    node_result = make_policy().evaluate(node, bundle, request)

    assert agent_result == node_result
    assert AssetReadinessSummary.from_evaluation(agent_result, agent).outcome == (
        AssetReadinessSummary.from_evaluation(node_result, node).outcome
    )


def test_runtime_profile_changes_only_summary_provenance() -> None:
    agent = make_candidate(runtime_profile=CompletedMediaAssetRuntimeProfile.AGENT)
    node = make_candidate(runtime_profile=CompletedMediaAssetRuntimeProfile.NODE)
    bundle = make_stability_bundle()
    result = make_policy().evaluate(agent, bundle, make_request())

    agent_summary = AssetReadinessSummary.from_evaluation(result, agent)
    node_summary = AssetReadinessSummary.from_evaluation(result, node)

    assert replace(agent_summary, runtime_profile=node.runtime_profile) == node_summary


def test_arbitrary_filename_has_no_effect_on_readiness() -> None:
    ordinary = make_candidate(filename="x7q9.mp4")
    suggestive = make_candidate(filename="FINAL_COMPLETE_SESSION_APPROVED.mp4")
    bundle = make_bundle(snapshots=(make_snapshot(1, BASE_TIME),))

    ordinary_result = make_policy().evaluate(ordinary, bundle, make_request())
    suggestive_result = make_policy().evaluate(suggestive, bundle, make_request())

    assert ordinary_result == suggestive_result
    assert ordinary_result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION


def test_node_profile_cannot_make_size_only_stability_safe() -> None:
    node = make_candidate(runtime_profile=CompletedMediaAssetRuntimeProfile.NODE)
    bundle = make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME),
            make_snapshot(2, BASE_TIME + MINIMUM_INTERVAL),
        )
    )

    result = make_policy().evaluate(node, bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.INSUFFICIENT_OBSERVATION


def test_agent_can_use_strong_route_without_handle_inspection_capability() -> None:
    agent = make_candidate(runtime_profile=CompletedMediaAssetRuntimeProfile.AGENT)
    bundle = make_bundle(
        finalizations=(make_finalization(),),
        presences=(make_presence(1, BASE_TIME + timedelta(seconds=1)),),
    )

    result = make_policy().evaluate(agent, bundle, make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert "write-state inspection unavailable" in result.limitations


def test_node_can_use_stability_route_without_recorder_integration() -> None:
    node = make_candidate(runtime_profile=CompletedMediaAssetRuntimeProfile.NODE)

    result = make_policy().evaluate(node, make_stability_bundle(), make_request())

    assert result.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert not make_stability_bundle().finalization_observations


def test_parameter_selection_is_caller_supplied_not_profile_derived() -> None:
    relaxed = make_parameters(
        require_read_access_for_stability=False,
        require_inactive_write_when_available=False,
    )
    policy = make_policy(relaxed)

    assert policy.parameters is relaxed
    assert policy.parameters.minimum_stable_interval == MINIMUM_INTERVAL
