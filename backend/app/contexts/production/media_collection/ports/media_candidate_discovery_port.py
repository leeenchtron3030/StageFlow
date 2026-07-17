from __future__ import annotations

from abc import ABC, abstractmethod

from ..media_collection_contracts import (
    MediaCandidateDiscoveryRequest,
    MediaCandidateDiscoveryResult,
)


class MediaCandidateDiscoveryPort(ABC):
    """One-shot synchronous boundary for objective candidate discovery facts."""

    @abstractmethod
    def discover(
        self,
        request: MediaCandidateDiscoveryRequest,
    ) -> MediaCandidateDiscoveryResult:
        """Discover at most the explicitly requested number of candidates."""


__all__ = ["MediaCandidateDiscoveryPort"]
