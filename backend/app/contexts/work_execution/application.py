from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from .contracts import (
    DurableOperation,
    EnqueueTranscriptionOperation,
    PendingOperation,
)
from .repository import WorkExecutionRepository


def _sha(document: object) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def transcription_work_key(request: EnqueueTranscriptionOperation) -> str:
    value = request.input
    return _sha(
        {
            "schema": "stageflow.transcription_operation.work-key.v1",
            "asset_id": value.asset_id.value,
            "manifest_id": value.manifest_id.value,
            "manifest_version": value.manifest_version,
            "asset_format": value.asset_format,
            "execution_profile_id": value.execution_profile_id,
            "execution_profile_version": value.execution_profile_version,
            "requested_language": value.requested_language,
            "request_word_timing": value.request_word_timing,
            "request_speaker_labels": value.request_speaker_labels,
            "requires_cloud": value.requires_cloud,
        }
    )


def enqueue_request_digest(request: EnqueueTranscriptionOperation) -> str:
    value = request.input
    return _sha(
        {
            "schema": "stageflow.transcription_operation.enqueue.v1",
            "operation_id": request.operation_id.value,
            "idempotency_key": request.idempotency_key,
            "deployment_id": request.deployment_id,
            "event_id": None if request.event_id is None else request.event_id.value,
            "input": {
                "asset_id": value.asset_id.value,
                "manifest_id": value.manifest_id.value,
                "manifest_version": value.manifest_version,
                "asset_format": value.asset_format,
                "execution_profile_id": value.execution_profile_id,
                "execution_profile_version": value.execution_profile_version,
                "requested_language": value.requested_language,
                "request_word_timing": value.request_word_timing,
                "request_speaker_labels": value.request_speaker_labels,
                "requires_cloud": value.requires_cloud,
            },
            "priority": request.priority,
            "eligible_at": request.eligible_at.isoformat(),
            "max_attempts": request.max_attempts,
            "retry_delay_microseconds": int(
                request.retry_delay.total_seconds() * 1_000_000
            ),
            "required_for_event": request.required_for_event,
            "requested_at": request.requested_at.isoformat(),
        }
    )


@dataclass(frozen=True, slots=True)
class TranscriptionOperationApplication:
    repository: WorkExecutionRepository

    def enqueue(self, request: EnqueueTranscriptionOperation) -> DurableOperation:
        return self.repository.enqueue(
            PendingOperation(
                request=request,
                request_digest=enqueue_request_digest(request),
                work_key=transcription_work_key(request),
            )
        )


__all__ = [
    "TranscriptionOperationApplication",
    "enqueue_request_digest",
    "transcription_work_key",
]

