from __future__ import annotations

from abc import ABC, abstractmethod

from ..media_collection_contracts import (
    MediaObservationCollectionRequest,
    MediaObservationCollectionResult,
)


class ResourceSnapshotCollectionPort(ABC):
    @abstractmethod
    def collect_resource_snapshot(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        """Supply objective resource-snapshot facts for one candidate."""


class FinalizationObservationCollectionPort(ABC):
    @abstractmethod
    def collect_finalization_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        """Supply objective finalization facts for one candidate."""


class WriteStateObservationCollectionPort(ABC):
    @abstractmethod
    def collect_write_state_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        """Supply objective write-state facts for one candidate."""


class ReadAccessObservationCollectionPort(ABC):
    @abstractmethod
    def collect_read_access_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        """Supply objective read-access facts for one candidate."""


class ResourcePresenceObservationCollectionPort(ABC):
    @abstractmethod
    def collect_resource_presence_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        """Supply objective resource-presence facts for one candidate."""


__all__ = [
    "FinalizationObservationCollectionPort",
    "ReadAccessObservationCollectionPort",
    "ResourcePresenceObservationCollectionPort",
    "ResourceSnapshotCollectionPort",
    "WriteStateObservationCollectionPort",
]
