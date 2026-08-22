from __future__ import annotations

import logging
from dataclasses import replace

from app.contexts.production.asset_readiness import AssetReadinessObservation
from app.contexts.production.runtime import (
    RuntimeCollectionTarget,
    RuntimeObservationType,
    StageFlowRuntime,
)

from ._media_collection_state import OBSERVATION_CLASSES, derived_id
from .media_collection_contracts import (
    DiscoveredMediaCandidate,
    MediaCandidateDiscoveryRequest,
    MediaCandidateDiscoveryResult,
    MediaObservationCollectionRequest,
    MediaObservationCollectionResult,
)
from .media_collection_dependencies import MediaCollectionDependencies
from .media_collection_lifecycle import (
    MediaCandidateDiscoveryOutcome,
    MediaObservationCollectionOutcome,
)

_logger = logging.getLogger(__name__)


class MediaCollectionPortGateway:
    """Invoke injected collection ports and validate their returned contracts."""

    def __init__(
        self,
        *,
        runtime: StageFlowRuntime,
        dependencies: MediaCollectionDependencies,
    ) -> None:
        self._runtime = runtime
        self._dependencies = dependencies

    def observation_port(self, observation_type: RuntimeObservationType) -> object | None:
        if observation_type is RuntimeObservationType.RESOURCE_SNAPSHOT:
            return self._dependencies.resource_snapshot_collection_port
        if observation_type is RuntimeObservationType.FINALIZATION:
            return self._dependencies.finalization_observation_collection_port
        if observation_type is RuntimeObservationType.WRITE_STATE:
            return self._dependencies.write_state_observation_collection_port
        if observation_type is RuntimeObservationType.READ_ACCESS:
            return self._dependencies.read_access_observation_collection_port
        if observation_type is RuntimeObservationType.RESOURCE_PRESENCE:
            return self._dependencies.resource_presence_observation_collection_port
        return None

    def invoke_discovery(
        self,
        request: MediaCandidateDiscoveryRequest,
    ) -> MediaCandidateDiscoveryResult:
        port = self._dependencies.media_candidate_discovery_port
        if port is None:
            return MediaCandidateDiscoveryResult(
                discovery_request_id=request.discovery_request_id,
                cycle_id=request.collection_cycle_id,
                port_id=derived_id("missing-discovery-port"),
                outcome=MediaCandidateDiscoveryOutcome.FAILED,
                reasons=("required discovery port is absent",),
                started_at=request.requested_at,
                completed_at=request.requested_at,
            )
        try:
            return self._require_discovery_result(port.discover(request))
        except Exception as error:
            _logger.error(
                "media_collection_discovery_failed request_id=%s cycle_id=%s exception_type=%s",
                request.discovery_request_id.value,
                request.collection_cycle_id.value,
                type(error).__name__,
            )
            return MediaCandidateDiscoveryResult(
                discovery_request_id=request.discovery_request_id,
                cycle_id=request.collection_cycle_id,
                port_id=derived_id("failed-discovery-port"),
                outcome=MediaCandidateDiscoveryOutcome.FAILED,
                reasons=(f"discovery_port_exception:{type(error).__name__}",),
                started_at=request.requested_at,
                completed_at=request.requested_at,
            )

    @staticmethod
    def _require_discovery_result(result: object) -> MediaCandidateDiscoveryResult:
        if not isinstance(result, MediaCandidateDiscoveryResult):
            raise TypeError("Discovery port returned an unsupported result type.")
        return result

    def normalize_discovery_result(
        self,
        request: MediaCandidateDiscoveryRequest,
        result: MediaCandidateDiscoveryResult,
        target: RuntimeCollectionTarget,
    ) -> tuple[MediaCandidateDiscoveryResult, list[DiscoveredMediaCandidate]]:
        conflicting_discovery_ids = result.conflicting_discovery_ids
        valid = (
            result.discovery_request_id == request.discovery_request_id
            and result.cycle_id == request.collection_cycle_id
            and not result.conflicting_discovery_ids
        )
        candidates: list[DiscoveredMediaCandidate] = []
        for discovered in result.discovered_candidates:
            candidate = discovered.candidate
            resource = candidate.primary_resource
            wrapper_valid = (
                discovered.discovery_request_id == request.discovery_request_id
                and discovered.cycle_id == request.collection_cycle_id
                and discovered.collection_plan_id == request.collection_plan_id
                and discovered.collection_target_id == request.collection_target_id
                and discovered.discovery_port_id == result.port_id
            )
            candidate_valid = (
                candidate.source_runtime_id == request.runtime_id
                and candidate.runtime_profile.value == self._runtime.profile.value
                and (
                    candidate.source_host_id is None
                    or candidate.source_host_id == target.source_host_id
                )
                and (
                    resource.source_host_id is None
                    or resource.source_host_id == target.source_host_id
                )
                and (
                    target.source_volume_id is None
                    or resource.source_volume_id is None
                    or resource.source_volume_id == target.source_volume_id
                )
                and (
                    candidate.context.stage_id is None
                    or target.configured_stage_id is None
                    or candidate.context.stage_id == target.configured_stage_id
                )
                and (
                    candidate.context.recording_block_id is None
                    or target.configured_recording_block_id is None
                    or candidate.context.recording_block_id
                    == target.configured_recording_block_id
                )
            )
            if wrapper_valid and candidate_valid:
                candidates.append(discovered)
            else:
                valid = False
        count_exceeded = len(candidates) > request.maximum_candidate_count
        if count_exceeded:
            valid = False
        if result.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED and not candidates:
            valid = False
        if result.outcome is MediaCandidateDiscoveryOutcome.NO_CANDIDATES and candidates:
            valid = False
        if not valid:
            result = replace(
                result,
                outcome=MediaCandidateDiscoveryOutcome.INVALID_RESULT,
                reasons=(
                    *result.reasons,
                    "discovery result violated request identity or limit",
                ),
                limitations=(
                    *result.limitations,
                    *(("candidate_limit_exceeded",) if count_exceeded else ()),
                ),
            )
            object.__setattr__(
                result,
                "conflicting_discovery_ids",
                conflicting_discovery_ids,
            )
        return result, candidates

    def invoke_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        port = self.observation_port(request.observation_type)
        try:
            if request.observation_type is RuntimeObservationType.RESOURCE_SNAPSHOT:
                collector = self._dependencies.resource_snapshot_collection_port
                if collector is None:
                    raise RuntimeError("Resource snapshot port is absent.")
                result: object = collector.collect_resource_snapshot(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.FINALIZATION:
                collector = self._dependencies.finalization_observation_collection_port
                if collector is None:
                    raise RuntimeError("Finalization port is absent.")
                result = collector.collect_finalization_observation(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.WRITE_STATE:
                collector = self._dependencies.write_state_observation_collection_port
                if collector is None:
                    raise RuntimeError("Write-state port is absent.")
                result = collector.collect_write_state_observation(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.READ_ACCESS:
                collector = self._dependencies.read_access_observation_collection_port
                if collector is None:
                    raise RuntimeError("Read-access port is absent.")
                result = collector.collect_read_access_observation(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.RESOURCE_PRESENCE:
                collector = self._dependencies.resource_presence_observation_collection_port
                if collector is None:
                    raise RuntimeError("Resource-presence port is absent.")
                result = collector.collect_resource_presence_observation(request)
                return self._require_observation_result(result)
            raise ValueError("Unsupported observation type.")
        except Exception as error:
            _logger.error(
                (
                    "media_collection_observation_failed candidate_id=%s "
                    "resource_id=%s observation_type=%s exception_type=%s"
                ),
                request.candidate_id.value,
                request.resource_id.value,
                request.observation_type.value,
                type(error).__name__,
            )
            return MediaObservationCollectionResult(
                collection_request_id=request.collection_request_id,
                cycle_id=request.collection_cycle_id,
                candidate_id=request.candidate_id,
                resource_id=request.resource_id,
                observation_type=request.observation_type,
                port_id=(
                    derived_id("missing-observation-port", request.observation_type.value)
                    if port is None
                    else request.observation_capability_id
                ),
                outcome=MediaObservationCollectionOutcome.FAILED,
                reasons=(f"observation_port_exception:{type(error).__name__}",),
                started_at=request.requested_at,
                completed_at=request.requested_at,
            )

    @staticmethod
    def _require_observation_result(result: object) -> MediaObservationCollectionResult:
        if not isinstance(result, MediaObservationCollectionResult):
            raise TypeError("Observation port returned an unsupported result type.")
        return result

    @staticmethod
    def normalize_observation_result(
        request: MediaObservationCollectionRequest,
        result: MediaObservationCollectionResult,
    ) -> tuple[MediaObservationCollectionResult, tuple[AssetReadinessObservation, ...]]:
        conflicting_observation_ids = result.conflicting_observation_ids
        valid = (
            result.collection_request_id == request.collection_request_id
            and result.cycle_id == request.collection_cycle_id
            and result.candidate_id == request.candidate_id
            and result.resource_id == request.resource_id
            and result.observation_type is request.observation_type
        )
        expected_class = OBSERVATION_CLASSES[request.observation_type]
        observations: list[AssetReadinessObservation] = []
        conflicting_values = set(result.conflicting_observation_ids)
        for observation in result.observations:
            observation_valid = (
                isinstance(observation, expected_class)
                and observation.candidate_id == request.candidate_id
                and observation.resource_id == request.resource_id
                and (
                    observation.source_runtime_id is None
                    or observation.source_runtime_id == request.runtime_id
                )
            )
            if not observation_valid:
                valid = False
            elif observation.id not in conflicting_values:
                observations.append(observation)
        if conflicting_values:
            valid = False
        if result.outcome is MediaObservationCollectionOutcome.COLLECTED and not observations:
            valid = False
        if result.outcome is MediaObservationCollectionOutcome.NO_OBSERVATION and observations:
            valid = False
        if not valid:
            result = replace(
                result,
                outcome=MediaObservationCollectionOutcome.INVALID_RESULT,
                reasons=(*result.reasons, "observation result violated request identity"),
            )
            object.__setattr__(
                result,
                "conflicting_observation_ids",
                conflicting_observation_ids,
            )
        return result, tuple(observations)


__all__ = ["MediaCollectionPortGateway"]
