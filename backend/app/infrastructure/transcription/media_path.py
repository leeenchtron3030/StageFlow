"""Resolve registered media independently of the transcription engine."""
from __future__ import annotations

import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from app.contexts.production.event_mode_kernel.contracts import MediaRegistrationState
from app.contexts.production.event_mode_kernel.repository import EventModeKernelRepository
from app.contexts.transcription_evidence.application import TranscriptionExecutionError
from app.contexts.work_execution.contracts import (
    MediaSegmentationOperationInput,
    MediaTimingOperationInput,
    TranscriptionOperationInput,
)


class MediaPathResolver(Protocol):
    def resolve(self, input: TranscriptionOperationInput) -> Path: ...


class KernelMediaPathResolver:
    def __init__(
        self,
        repository: EventModeKernelRepository,
        *,
        source_roots: Mapping[str, str],
    ) -> None:
        self._repository = repository
        self._source_roots = dict(source_roots)

    def resolve(
        self, input: TranscriptionOperationInput | MediaTimingOperationInput
        | MediaSegmentationOperationInput,
    ) -> Path:
        asset = self._repository.get_asset(input.asset_id)
        if asset is None:
            raise TranscriptionExecutionError(
                "media_asset_not_found",
                retryable=False,
                diagnostic_summary="registered media asset is unavailable",
            )
        if asset.manifest_id != input.manifest_id:
            raise TranscriptionExecutionError(
                "media_manifest_conflict",
                retryable=False,
                diagnostic_summary="operation manifest does not match registered media",
            )
        candidate = self._repository.get_candidate(asset.candidate_id)
        if candidate is None or candidate.state is not MediaRegistrationState.REGISTERED:
            raise TranscriptionExecutionError(
                "media_candidate_not_registered",
                retryable=False,
                diagnostic_summary="media candidate is not registered",
            )
        configured_root = self._source_roots.get(candidate.source_binding_key)
        if configured_root is None:
            raise TranscriptionExecutionError(
                "media_source_not_configured",
                retryable=False,
                diagnostic_summary="registered media source is not configured",
            )
        try:
            root = Path(configured_root).resolve(strict=True)
            unresolved = Path(candidate.source_reference)
            details = unresolved.lstat()
            if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
                raise OSError("not_regular")
            resolved = unresolved.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise OSError("outside_source")
        except OSError as exc:
            raise TranscriptionExecutionError(
                "media_resource_unavailable",
                retryable=True,
                diagnostic_summary="registered media resource is not safely readable",
            ) from exc
        return resolved
