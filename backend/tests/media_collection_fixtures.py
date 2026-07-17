from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from threading import Event

from runtime_fixtures import (
    CONFIGURATION_ID,
    HOST_ID,
    PLAN_ID,
    RUNTIME_ID,
    STAGE_ID,
    VOLUME_ID,
    entity_id,
    make_runtime,
)
from software_agent_runtime_fixtures import STARTED_AT, make_running_agent

from app.contexts.production.asset_readiness import (
    AssetFinalizationObservation,
    AssetReadAccessObservation,
    AssetReadAccessStatus,
    AssetReadinessObservation,
    AssetResourcePresenceObservation,
    AssetResourcePresenceStatus,
    AssetResourceSnapshot,
    AssetWriteStateObservation,
    AssetWriteStateStatus,
    MediaAssetCandidate,
    MediaAssetCandidateResource,
)
from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetContext,
    CompletedMediaAssetKind,
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetRuntimeProfile,
    CompletedMediaAssetSourceLocation,
)
from app.contexts.production.media_collection import (
    AgentExecutionStatePort,
    DiscoveredMediaCandidate,
    FinalizationObservationCollectionPort,
    MediaCandidateCollectionCoordinator,
    MediaCandidateDiscoveryOutcome,
    MediaCandidateDiscoveryPort,
    MediaCandidateDiscoveryRequest,
    MediaCandidateDiscoveryResult,
    MediaCollectionCycleRequest,
    MediaCollectionDependencies,
    MediaObservationCollectionOutcome,
    MediaObservationCollectionRequest,
    MediaObservationCollectionResult,
    ReadAccessObservationCollectionPort,
    ResourcePresenceObservationCollectionPort,
    ResourceSnapshotCollectionPort,
    WriteStateObservationCollectionPort,
)
from app.contexts.production.runtime import (
    RuntimeObservationType,
    RuntimeProfile,
    RuntimeReadinessRoute,
)
from app.contexts.production.software_agent_runtime import AgentRuntimeSnapshot
from app.shared.ids import EntityId

CYCLE_AT = STARTED_AT + timedelta(seconds=10)
COORDINATOR_ID = entity_id(8000)
DISCOVERY_PORT_ID = entity_id(8001)
OBSERVATION_PORT_ID = entity_id(8002)


def make_candidate(number: int = 1) -> MediaAssetCandidate:
    candidate_id = entity_id(8100 + number * 10)
    proposed_id = entity_id(8101 + number * 10)
    resource_id = entity_id(8102 + number * 10)
    location = CompletedMediaAssetSourceLocation(
        location_scheme=CompletedMediaAssetLocationScheme.LOCAL_FILESYSTEM,
        location_value=f"/synthetic/event/recordings/clip-{number}.mov",
        volume_id=VOLUME_ID,
        host_id=HOST_ID,
    )
    return MediaAssetCandidate(
        id=candidate_id,
        proposed_asset_id=proposed_id,
        primary_resource=MediaAssetCandidateResource(
            id=resource_id,
            original_filename=f"clip-{number}.mov",
            source_location=location,
            source_volume_id=VOLUME_ID,
            source_host_id=HOST_ID,
        ),
        source_runtime_id=RUNTIME_ID,
        runtime_profile=CompletedMediaAssetRuntimeProfile.AGENT,
        first_observed_at=CYCLE_AT - timedelta(seconds=1),
        context=CompletedMediaAssetContext(
            stage_id=STAGE_ID,
            recording_block_id=entity_id(25),
        ),
        intended_asset_kind=CompletedMediaAssetKind.RECORDING_SEGMENT,
        source_host_id=HOST_ID,
    )


@dataclass(slots=True)
class RecordingAgentStatePort(AgentExecutionStatePort):
    snapshots: list[AgentRuntimeSnapshot]
    calls: list[EntityId] = field(default_factory=lambda: list[EntityId]())
    entered: Event | None = None
    release: Event | None = None

    def get_current_snapshot(self, runtime_id: EntityId) -> AgentRuntimeSnapshot:
        self.calls.append(runtime_id)
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            self.release.wait(timeout=2)
        index = min(len(self.calls) - 1, len(self.snapshots) - 1)
        return self.snapshots[index]


@dataclass(slots=True)
class RecordingDiscoveryPort(MediaCandidateDiscoveryPort):
    candidates: Sequence[MediaAssetCandidate]
    outcome: MediaCandidateDiscoveryOutcome = MediaCandidateDiscoveryOutcome.DISCOVERED
    calls: list[MediaCandidateDiscoveryRequest] = field(
        default_factory=lambda: list[MediaCandidateDiscoveryRequest]()
    )
    fail: bool = False
    entered: Event | None = None
    release: Event | None = None
    result_mutator: (
        Callable[[MediaCandidateDiscoveryResult], MediaCandidateDiscoveryResult] | None
    ) = None

    def discover(
        self,
        request: MediaCandidateDiscoveryRequest,
    ) -> MediaCandidateDiscoveryResult:
        self.calls.append(request)
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            self.release.wait(timeout=2)
        if self.fail:
            raise RuntimeError("synthetic discovery failure")
        discovered = tuple(
            DiscoveredMediaCandidate(
                discovery_id=entity_id(8200 + len(self.calls) * 100 + index),
                discovery_request_id=request.discovery_request_id,
                cycle_id=request.collection_cycle_id,
                collection_plan_id=request.collection_plan_id,
                collection_target_id=request.collection_target_id,
                discovery_port_id=DISCOVERY_PORT_ID,
                candidate=candidate,
                discovered_at=request.requested_at + timedelta(seconds=1),
            )
            for index, candidate in enumerate(self.candidates)
        )
        result = MediaCandidateDiscoveryResult(
            discovery_request_id=request.discovery_request_id,
            cycle_id=request.collection_cycle_id,
            port_id=DISCOVERY_PORT_ID,
            outcome=(
                MediaCandidateDiscoveryOutcome.NO_CANDIDATES
                if not discovered and self.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED
                else self.outcome
            ),
            discovered_candidates=discovered,
            started_at=request.requested_at,
            completed_at=request.requested_at + timedelta(seconds=1),
        )
        return result if self.result_mutator is None else self.result_mutator(result)


@dataclass(slots=True)
class RecordingObservationPorts(
    ResourceSnapshotCollectionPort,
    FinalizationObservationCollectionPort,
    WriteStateObservationCollectionPort,
    ReadAccessObservationCollectionPort,
    ResourcePresenceObservationCollectionPort,
):
    calls: list[MediaObservationCollectionRequest] = field(
        default_factory=lambda: list[MediaObservationCollectionRequest]()
    )
    failed_types: frozenset[RuntimeObservationType] = field(
        default_factory=lambda: frozenset[RuntimeObservationType]()
    )
    no_observation_types: frozenset[RuntimeObservationType] = field(
        default_factory=lambda: frozenset[RuntimeObservationType]()
    )
    result_mutator: (
        Callable[[MediaObservationCollectionResult], MediaObservationCollectionResult] | None
    ) = None

    def collect_resource_snapshot(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        return self._collect(request)

    def collect_finalization_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        return self._collect(request)

    def collect_write_state_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        return self._collect(request)

    def collect_read_access_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        return self._collect(request)

    def collect_resource_presence_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        return self._collect(request)

    def _collect(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        self.calls.append(request)
        if request.observation_type in self.failed_types:
            raise RuntimeError("synthetic observation failure")
        no_observation = request.observation_type in self.no_observation_types
        result = MediaObservationCollectionResult(
            collection_request_id=request.collection_request_id,
            cycle_id=request.collection_cycle_id,
            candidate_id=request.candidate_id,
            resource_id=request.resource_id,
            observation_type=request.observation_type,
            port_id=OBSERVATION_PORT_ID,
            outcome=(
                MediaObservationCollectionOutcome.NO_OBSERVATION
                if no_observation
                else MediaObservationCollectionOutcome.COLLECTED
            ),
            observations=(() if no_observation else (make_observation(request, len(self.calls)),)),
            started_at=request.requested_at + timedelta(seconds=1),
            completed_at=request.requested_at + timedelta(seconds=2),
        )
        return result if self.result_mutator is None else self.result_mutator(result)


def make_observation(
    request: MediaObservationCollectionRequest,
    number: int = 1,
) -> AssetReadinessObservation:
    observation_id = entity_id(8300 + number)
    observed_at = request.requested_at + timedelta(seconds=2)
    if request.observation_type is RuntimeObservationType.RESOURCE_SNAPSHOT:
        return AssetResourceSnapshot(
            id=observation_id,
            candidate_id=request.candidate_id,
            resource_id=request.resource_id,
            observed_at=observed_at,
            observer_id=OBSERVATION_PORT_ID,
            source_runtime_id=request.runtime_id,
            size_bytes=100,
        )
    if request.observation_type is RuntimeObservationType.FINALIZATION:
        return AssetFinalizationObservation(
            id=observation_id,
            candidate_id=request.candidate_id,
            resource_id=request.resource_id,
            observed_at=observed_at,
            observer_id=OBSERVATION_PORT_ID,
            source_runtime_id=request.runtime_id,
            completion_method=(CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION),
            declaring_entity_id=entity_id(8400),
        )
    if request.observation_type is RuntimeObservationType.WRITE_STATE:
        return AssetWriteStateObservation(
            id=observation_id,
            candidate_id=request.candidate_id,
            resource_id=request.resource_id,
            observed_at=observed_at,
            observer_id=OBSERVATION_PORT_ID,
            source_runtime_id=request.runtime_id,
            status=AssetWriteStateStatus.INACTIVE,
            assessment_mechanism_id="synthetic-write-state",
        )
    if request.observation_type is RuntimeObservationType.READ_ACCESS:
        return AssetReadAccessObservation(
            id=observation_id,
            candidate_id=request.candidate_id,
            resource_id=request.resource_id,
            observed_at=observed_at,
            observer_id=OBSERVATION_PORT_ID,
            source_runtime_id=request.runtime_id,
            status=AssetReadAccessStatus.READABLE,
            assessment_method_id="synthetic-read-access",
            access_scope="candidate-resource",
        )
    return AssetResourcePresenceObservation(
        id=observation_id,
        candidate_id=request.candidate_id,
        resource_id=request.resource_id,
        observed_at=observed_at,
        observer_id=OBSERVATION_PORT_ID,
        source_runtime_id=request.runtime_id,
        status=AssetResourcePresenceStatus.PRESENT,
    )


def make_cycle_request(
    *,
    number: int = 1,
    revision: int = 0,
    maximum_candidates: int = 10,
    maximum_observation_calls: int = 20,
    permit_reduced: bool = True,
    requested_at: datetime = CYCLE_AT,
) -> MediaCollectionCycleRequest:
    return MediaCollectionCycleRequest(
        cycle_id=entity_id(8500 + number * 2),
        operation_id=entity_id(8501 + number * 2),
        runtime_id=RUNTIME_ID,
        configuration_id=CONFIGURATION_ID,
        collection_plan_id=PLAN_ID,
        expected_coordinator_revision=revision,
        requested_at=requested_at,
        maximum_total_candidates=maximum_candidates,
        maximum_total_observation_port_calls=maximum_observation_calls,
        permit_reduced_execution=permit_reduced,
    )


def make_coordinator(
    *,
    candidates: Sequence[MediaAssetCandidate] = (),
    agent_snapshots: Sequence[AgentRuntimeSnapshot] | None = None,
    discovery: RecordingDiscoveryPort | None = None,
    observations: RecordingObservationPorts | None = None,
    allow_development: bool = False,
    profile: RuntimeProfile = RuntimeProfile.AGENT,
    route: RuntimeReadinessRoute = RuntimeReadinessRoute.STRONG_THEN_STABILITY,
) -> tuple[
    MediaCandidateCollectionCoordinator,
    RecordingAgentStatePort,
    RecordingDiscoveryPort,
    RecordingObservationPorts,
]:
    runtime = make_runtime(profile=profile, route=route)
    agent, _ = make_running_agent(runtime=runtime, profile=profile)
    state_port = RecordingAgentStatePort(
        list(agent_snapshots) if agent_snapshots is not None else [agent.snapshot]
    )
    discovery_port = discovery or RecordingDiscoveryPort(candidates)
    observation_ports = observations or RecordingObservationPorts()
    dependencies = MediaCollectionDependencies(
        agent_execution_state_port=state_port,
        media_candidate_discovery_port=discovery_port,
        resource_snapshot_collection_port=observation_ports,
        finalization_observation_collection_port=observation_ports,
        write_state_observation_collection_port=observation_ports,
        read_access_observation_collection_port=observation_ports,
        resource_presence_observation_collection_port=observation_ports,
    )
    return (
        MediaCandidateCollectionCoordinator(
            coordinator_id=COORDINATOR_ID,
            runtime=runtime,
            dependencies=dependencies,
            allow_development_profile=allow_development,
        ),
        state_port,
        discovery_port,
        observation_ports,
    )


def mismatch_result_candidate(
    result: MediaObservationCollectionResult,
) -> MediaObservationCollectionResult:
    return replace(result, candidate_id=entity_id(8999))
