from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest
from media_collection_fixtures import (
    CYCLE_AT,
    make_candidate,
    make_coordinator,
    make_cycle_request,
)

from app.contexts.production.media_collection import (
    MediaCandidateCollectionStatus,
    MediaCandidateDiscoveryOutcome,
    MediaCollectionCycleOutcome,
    MediaCollectionCycleSummary,
    MediaCollectionQueryOutcome,
    MediaObservationCollectionOutcome,
)
from app.contexts.production.runtime import RuntimeObservationType


def test_approved_enum_values_are_exact() -> None:
    assert tuple(value.value for value in MediaCandidateDiscoveryOutcome) == (
        "discovered",
        "no_candidates",
        "partial",
        "unsupported",
        "deferred",
        "blocked",
        "failed",
        "invalid_result",
        "unknown",
    )
    assert tuple(value.value for value in MediaObservationCollectionOutcome) == (
        "collected",
        "no_observation",
        "unsupported",
        "deferred",
        "blocked",
        "failed",
        "invalid_result",
        "unknown",
    )
    assert tuple(value.value for value in MediaCandidateCollectionStatus) == (
        "discovered",
        "observations_available",
        "partially_observed",
        "deferred",
        "blocked",
        "conflicted",
    )


def test_cycle_request_rejects_naive_time_and_nonpositive_bounds() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_cycle_request(requested_at=datetime(2026, 7, 17, 12))
    with pytest.raises(ValueError, match="positive"):
        make_cycle_request(maximum_candidates=0)
    with pytest.raises(ValueError, match="positive"):
        make_cycle_request(maximum_observation_calls=0)


def test_construction_is_inert_and_snapshot_starts_at_zero() -> None:
    coordinator, agent, discovery, observations = make_coordinator(candidates=(make_candidate(),))

    assert agent.calls == []
    assert discovery.calls == []
    assert observations.calls == []
    assert coordinator.snapshot.coordinator_revision == 0
    assert coordinator.snapshot.active_cycle_id is None


def test_normal_cycle_collects_in_required_deterministic_order() -> None:
    candidate = make_candidate()
    coordinator, agent, _discovery, observations = make_coordinator(candidates=(candidate,))

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED
    assert result.newly_discovered_candidate_ids == (candidate.id,)
    assert result.total_candidates_considered == 1
    assert result.total_observation_calls_attempted == 5
    assert result.total_observations_retained == 5
    assert result.completed_at == CYCLE_AT.replace() + (result.completed_at - CYCLE_AT)
    assert [request.observation_type for request in observations.calls] == [
        RuntimeObservationType.RESOURCE_PRESENCE,
        RuntimeObservationType.RESOURCE_SNAPSHOT,
        RuntimeObservationType.FINALIZATION,
        RuntimeObservationType.WRITE_STATE,
        RuntimeObservationType.READ_ACCESS,
    ]
    assert all(request.required for request in observations.calls)
    assert len(agent.calls) == 10
    assert result.current_coordinator_snapshot.coordinator_revision == 1
    assert result.current_coordinator_snapshot.active_cycle_id is None

    candidate_query = coordinator.get_candidate(candidate.id)
    assert candidate_query.outcome is MediaCollectionQueryOutcome.FOUND
    assert candidate_query.candidate is not None
    assert (
        candidate_query.candidate.collection_status
        is MediaCandidateCollectionStatus.OBSERVATIONS_AVAILABLE
    )
    bundle_query = coordinator.get_observation_bundle(candidate.id)
    assert bundle_query.outcome is MediaCollectionQueryOutcome.FOUND
    assert bundle_query.observation_bundle is not None
    assert len(bundle_query.observation_bundle.all_observations) == 5


def test_no_candidate_cycle_commits_history_without_candidate_state() -> None:
    coordinator, _, discovery, observations = make_coordinator()

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.NO_CANDIDATES
    assert len(discovery.calls) == 1
    assert observations.calls == []
    assert coordinator.snapshot.coordinator_revision == 1
    assert coordinator.list_candidates().candidates == ()
    assert coordinator.list_cycle_history().cycle_history == (result,)


def test_public_results_and_query_collections_are_immutable() -> None:
    coordinator, _, _, _ = make_coordinator(candidates=(make_candidate(),))
    result = coordinator.run_cycle(make_cycle_request())

    with pytest.raises(FrozenInstanceError):
        result.outcome = MediaCollectionCycleOutcome.FAILED  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.metadata["mutable"] = True  # type: ignore[index]
    assert isinstance(coordinator.list_candidates().candidates, tuple)


def test_routine_query_absence_is_typed_not_found() -> None:
    candidate = make_candidate(9)
    coordinator, _, _, _ = make_coordinator()

    assert coordinator.get_candidate(candidate.id).outcome is MediaCollectionQueryOutcome.NOT_FOUND
    assert (
        coordinator.get_observation_bundle(candidate.id).outcome
        is MediaCollectionQueryOutcome.NOT_FOUND
    )
    assert (
        coordinator.get_cycle_result(candidate.id).outcome is MediaCollectionQueryOutcome.NOT_FOUND
    )


def test_cycle_summary_is_privacy_safe_and_uses_committed_result() -> None:
    coordinator, _, _, _ = make_coordinator(candidates=(make_candidate(),))
    request = make_cycle_request()
    result = coordinator.run_cycle(request)

    summary = coordinator.summarize_cycle(request.operation_id)

    assert isinstance(summary, MediaCollectionCycleSummary)
    assert summary.cycle_id == result.cycle_id
    assert summary.candidates_discovered == 1
    assert summary.observations_retained == 5
    assert "/synthetic/" not in repr(summary)
