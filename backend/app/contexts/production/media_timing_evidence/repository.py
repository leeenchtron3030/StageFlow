from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from app.shared.ids import EntityId

from .contracts import MediaTimingEvidence, PendingMediaTimingEvidence


class MediaTimingEvidenceConflictError(RuntimeError):
    pass


class MediaTimingEvidenceNotFoundError(LookupError):
    pass


class MediaTimingEvidenceStorageUnavailableError(RuntimeError):
    pass


class MediaTimingEvidenceRepository(ABC):
    @abstractmethod
    def append(self, pending: PendingMediaTimingEvidence) -> MediaTimingEvidence: ...

    @abstractmethod
    def get_active(self, asset_id: EntityId) -> MediaTimingEvidence | None: ...

    @abstractmethod
    def history(self, asset_id: EntityId) -> tuple[MediaTimingEvidence, ...]: ...


class InMemoryMediaTimingEvidenceRepository(MediaTimingEvidenceRepository):
    """Process-local test double. Never use as durable evidence authority."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._assets: dict[EntityId, EntityId] = {}
        self._history: dict[EntityId, list[MediaTimingEvidence]] = {}
        self._operations: dict[EntityId, MediaTimingEvidence] = {}

    def register_asset(self, asset_id: EntityId, manifest_id: EntityId) -> None:
        with self._lock:
            existing = self._assets.get(asset_id)
            if existing is not None and existing != manifest_id:
                raise MediaTimingEvidenceConflictError("asset_manifest_conflict")
            self._assets[asset_id] = manifest_id

    def append(self, pending: PendingMediaTimingEvidence) -> MediaTimingEvidence:
        request = pending.request
        with self._lock:
            replay = self._operations.get(request.operation_id)
            if replay is not None:
                if replay.request_digest != pending.request_digest:
                    raise MediaTimingEvidenceConflictError("application_identity_conflict")
                return replay
            manifest_id = self._assets.get(request.asset_id)
            if manifest_id is None:
                raise MediaTimingEvidenceNotFoundError("completed_media_asset_not_found")
            if manifest_id != request.manifest_id:
                raise MediaTimingEvidenceConflictError("asset_manifest_identity_conflict")
            history = self._history.setdefault(request.asset_id, [])
            predecessor = history[-1] if history else None
            evidence = MediaTimingEvidence(
                id=pending.id,
                asset_id=request.asset_id,
                manifest_id=request.manifest_id,
                manifest_version=request.manifest_version,
                revision=len(history) + 1,
                predecessor_evidence_id=None if predecessor is None else predecessor.id,
                operation_id=request.operation_id,
                request_digest=pending.request_digest,
                applied_at=request.applied_at,
                result=request.result,
            )
            history.append(evidence)
            self._operations[request.operation_id] = evidence
            return evidence

    def get_active(self, asset_id: EntityId) -> MediaTimingEvidence | None:
        with self._lock:
            values = self._history.get(asset_id, [])
            return None if not values else values[-1]

    def history(self, asset_id: EntityId) -> tuple[MediaTimingEvidence, ...]:
        with self._lock:
            return tuple(self._history.get(asset_id, ()))


__all__ = [
    "InMemoryMediaTimingEvidenceRepository",
    "MediaTimingEvidenceConflictError",
    "MediaTimingEvidenceNotFoundError",
    "MediaTimingEvidenceRepository",
    "MediaTimingEvidenceStorageUnavailableError",
]
