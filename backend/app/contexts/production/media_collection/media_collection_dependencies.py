from __future__ import annotations

from dataclasses import dataclass

from .ports import (
    AgentExecutionStatePort,
    FinalizationObservationCollectionPort,
    MediaCandidateDiscoveryPort,
    ReadAccessObservationCollectionPort,
    ResourcePresenceObservationCollectionPort,
    ResourceSnapshotCollectionPort,
    WriteStateObservationCollectionPort,
)


@dataclass(frozen=True, slots=True)
class MediaCollectionDependencies:
    agent_execution_state_port: AgentExecutionStatePort | None
    media_candidate_discovery_port: MediaCandidateDiscoveryPort | None
    resource_snapshot_collection_port: ResourceSnapshotCollectionPort | None
    finalization_observation_collection_port: FinalizationObservationCollectionPort | None
    write_state_observation_collection_port: WriteStateObservationCollectionPort | None
    read_access_observation_collection_port: ReadAccessObservationCollectionPort | None
    resource_presence_observation_collection_port: ResourcePresenceObservationCollectionPort | None


__all__ = ["MediaCollectionDependencies"]
