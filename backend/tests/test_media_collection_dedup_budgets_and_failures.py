from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from media_collection_fixtures import (
    RecordingDiscoveryPort,
    RecordingObservationPorts,
    make_candidate,
    make_coordinator,
    make_cycle_request,
    mismatch_result_candidate,
)

from app.contexts.production.media_collection import (
    MediaCandidateCollectionStatus,
    MediaCandidateConflictCode,
    MediaCandidateDiscoveryResult,
    MediaCollectionCycleOutcome,
    MediaCollectionQueryOutcome,
    MediaObservationCollectionResult,
)
from app.contexts.production.runtime import RuntimeObservationType


def test_exact_candidate_rediscovery_updates_lineage_without_second_record() -> None:
    candidate = make_candidate()
    discovery = RecordingDiscoveryPort((candidate,))
    coordinator, _, _, _ = make_coordinator(discovery=discovery)
    first = coordinator.run_cycle(make_cycle_request())
    second = coordinator.run_cycle(make_cycle_request(number=2, revision=1))

    assert first.outcome is MediaCollectionCycleOutcome.COMPLETED
    assert second.already_known_candidate_ids == (candidate.id,)
    assert len(coordinator.list_candidates().candidates) == 1
    record = coordinator.get_candidate(candidate.id).candidate
    assert record is not None
    assert record.candidate_revision == 2
    assert record.discovery_count == 2
    assert len(record.discovery_ids) == 2
    bundle = coordinator.get_observation_bundle(candidate.id).observation_bundle
    assert bundle is not None
    assert len(bundle.all_observations) == 10


def test_candidate_id_conflict_preserves_original_candidate() -> None:
    original = make_candidate()
    discovery = RecordingDiscoveryPort((original,))
    coordinator, _, _, _ = make_coordinator(discovery=discovery)
    coordinator.run_cycle(make_cycle_request())
    conflicting = replace(original, proposed_asset_id=make_candidate(9).proposed_asset_id)
    discovery.candidates = (conflicting,)

    result = coordinator.run_cycle(make_cycle_request(number=2, revision=1))

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
    record = coordinator.get_candidate(original.id).candidate
    assert record is not None
    assert record.candidate == original
    assert record.collection_status is MediaCandidateCollectionStatus.CONFLICTED
    assert len(record.conflict_ids) == 1
    conflict = coordinator.get_conflict(record.conflict_ids[0]).conflict
    assert conflict is not None
    assert conflict.conflict_code is MediaCandidateConflictCode.CANDIDATE_ID_REUSED


def test_conflicting_duplicate_discovery_id_is_detected() -> None:
    original = make_candidate()

    def duplicate_id(
        result: MediaCandidateDiscoveryResult,
    ) -> MediaCandidateDiscoveryResult:
        first = result.discovered_candidates[0]
        conflicting = replace(
            first,
            candidate=replace(
                first.candidate,
                proposed_asset_id=make_candidate(9).proposed_asset_id,
            ),
        )
        return replace(
            result,
            discovered_candidates=(*result.discovered_candidates, conflicting),
        )

    discovery = RecordingDiscoveryPort((original,), result_mutator=duplicate_id)
    coordinator, _, _, _ = make_coordinator(discovery=discovery)

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
    assert any(
        value.conflict_code is MediaCandidateConflictCode.DUPLICATE_DISCOVERY_ID
        for value in coordinator.list_conflicts().conflicts
    )


def test_proposed_asset_and_resource_conflicts_are_first_class() -> None:
    first = make_candidate(1)
    second = make_candidate(2)
    proposed_conflict = replace(second, proposed_asset_id=first.proposed_asset_id)
    coordinator, _, _, _ = make_coordinator(candidates=(first, proposed_conflict))

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
    codes = {value.conflict_code for value in coordinator.list_conflicts().conflicts}
    assert MediaCandidateConflictCode.PROPOSED_ASSET_ID_REUSED in codes

    third = replace(
        make_candidate(3),
        primary_resource=replace(
            make_candidate(3).primary_resource,
            id=first.primary_resource.id,
        ),
    )
    discovery = RecordingDiscoveryPort((first, third))
    other, _, _, _ = make_coordinator(discovery=discovery)
    other.run_cycle(make_cycle_request())
    codes = {value.conflict_code for value in other.list_conflicts().conflicts}
    assert MediaCandidateConflictCode.RESOURCE_ID_REUSED in codes


def test_invalid_observation_identity_creates_conflict_and_no_misleading_bundle() -> None:
    observations = RecordingObservationPorts(result_mutator=mismatch_result_candidate)
    candidate = make_candidate()
    coordinator, _, _, _ = make_coordinator(
        candidates=(candidate,),
        observations=observations,
    )

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
    record = coordinator.get_candidate(candidate.id).candidate
    assert record is not None
    assert record.collection_status is MediaCandidateCollectionStatus.CONFLICTED
    assert coordinator.get_observation_bundle(candidate.id).outcome in (
        MediaCollectionQueryOutcome.FOUND,
        MediaCollectionQueryOutcome.NOT_FOUND,
    )
    assert any(
        value.conflict_code is MediaCandidateConflictCode.OBSERVATION_CANDIDATE_MISMATCH
        for value in coordinator.list_conflicts().conflicts
    )


def test_conflicting_duplicate_observation_id_is_retained_as_conflict() -> None:
    def duplicate_id(
        result: MediaObservationCollectionResult,
    ) -> MediaObservationCollectionResult:
        if not result.observations:
            return result
        first = result.observations[0]
        return replace(
            result,
            observations=(
                first,
                replace(first, observed_at=first.observed_at + timedelta(milliseconds=1)),
            ),
        )

    observations = RecordingObservationPorts(result_mutator=duplicate_id)
    coordinator, _, _, _ = make_coordinator(
        candidates=(make_candidate(),),
        observations=observations,
    )

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
    assert any(
        value.conflict_code is MediaCandidateConflictCode.DUPLICATE_OBSERVATION_ID
        for value in coordinator.list_conflicts().conflicts
    )


def test_discovery_exception_is_typed_failure_and_committed_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    discovery = RecordingDiscoveryPort((), fail=True)
    coordinator, _, _, observations = make_coordinator(discovery=discovery)

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.DISCOVERY_FAILED
    assert observations.calls == []
    assert result.discovery_results[0].outcome.value == "failed"
    assert coordinator.snapshot.coordinator_revision == 1
    assert "media_collection_discovery_failed" in caplog.text
    assert "exception_type=RuntimeError" in caplog.text
    assert "synthetic discovery failure" not in caplog.text



def test_one_observation_exception_does_not_stop_later_required_calls() -> None:
    observations = RecordingObservationPorts(
        failed_types=frozenset((RuntimeObservationType.RESOURCE_SNAPSHOT,))
    )
    coordinator, _, _, _ = make_coordinator(
        candidates=(make_candidate(),),
        observations=observations,
    )

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
    assert len(observations.calls) == 5
    assert any(item.outcome.value == "failed" for item in result.observation_collection_results)
    assert result.total_observations_retained == 4


def test_candidate_budget_never_exceeds_bound_and_retains_deterministic_subset() -> None:
    candidates = (make_candidate(3), make_candidate(1), make_candidate(2))
    coordinator, _, discovery, observations = make_coordinator(candidates=candidates)

    result = coordinator.run_cycle(make_cycle_request(maximum_candidates=2))

    assert discovery.calls[0].maximum_candidate_count == 2
    assert result.total_candidates_considered == 2
    assert result.remaining_candidate_budget == 0
    assert result.outcome is MediaCollectionCycleOutcome.BUDGET_EXHAUSTED
    assert len(observations.calls) <= 10
    assert tuple(value.value for value in result.affected_candidate_ids) == tuple(
        sorted(value.value for value in result.affected_candidate_ids)
    )


def test_observation_budget_stops_calls_and_marks_candidate_deferred() -> None:
    candidate = make_candidate()
    coordinator, _, _, observations = make_coordinator(candidates=(candidate,))

    result = coordinator.run_cycle(make_cycle_request(maximum_observation_calls=2))

    assert result.outcome is MediaCollectionCycleOutcome.BUDGET_EXHAUSTED
    assert len(observations.calls) == 2
    assert result.total_observation_calls_attempted == 2
    assert result.remaining_observation_call_budget == 0
    assert result.deferred_candidate_ids == (candidate.id,)


def test_queries_are_deterministically_ordered_and_do_not_call_ports() -> None:
    coordinator, agent, discovery, observations = make_coordinator(
        candidates=(make_candidate(3), make_candidate(1), make_candidate(2))
    )
    coordinator.run_cycle(make_cycle_request())
    counts = (len(agent.calls), len(discovery.calls), len(observations.calls))

    candidates = coordinator.list_candidates().candidates
    conflicts = coordinator.list_conflicts().conflicts
    history = coordinator.list_cycle_history().cycle_history

    assert tuple(item.candidate.id.value for item in candidates) == tuple(
        sorted(item.candidate.id.value for item in candidates)
    )
    assert tuple(item.id.value for item in conflicts) == tuple(
        sorted(item.id.value for item in conflicts)
    )
    assert len(history) == 1
    assert (len(agent.calls), len(discovery.calls), len(observations.calls)) == counts
