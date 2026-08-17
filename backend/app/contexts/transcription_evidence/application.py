from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import TYPE_CHECKING, Protocol

from app.contexts.production.media_timing_evidence import MediaTimingEvidence
from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

if TYPE_CHECKING:
    from app.contexts.work_execution.contracts import (
        OperationClaim,
        TranscriptionOperationInput,
    )

from .contracts import (
    DerivedTranscriptAlignment,
    NormalizedTranscriptResult,
    PendingTranscriptEvidence,
)


@dataclass(frozen=True, slots=True)
class TranscriptionExecutionRequest:
    operation_id: EntityId
    attempt_id: EntityId
    fence_generation: int
    work_key: str
    input: TranscriptionOperationInput

    def __post_init__(self) -> None:
        if self.fence_generation < 1:
            raise ValueError("fence_generation must be positive.")


class TranscriptionExecutionPort(Protocol):
    def execute(
        self,
        request: TranscriptionExecutionRequest,
        renew_lease: Callable[[], None],
    ) -> NormalizedTranscriptResult: ...


class TranscriptionExecutionError(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        *,
        retryable: bool,
        diagnostic_summary: str,
    ) -> None:
        self.reason_code = reason_code
        self.retryable = retryable
        self.diagnostic_summary = diagnostic_summary
        super().__init__(reason_code)


def _sha(document: object) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def transcript_result_digest(result: NormalizedTranscriptResult) -> str:
    return _sha(
        {
            "schema": "stageflow.transcript-evidence.normalized-result.v1",
            "status": result.status.value,
            "language": result.language,
            "provenance": {
                "provider_id": result.provenance.provider_id,
                "provider_version": result.provenance.provider_version,
                "model_id": result.provenance.model_id,
                "model_version": result.provenance.model_version,
                "execution_tool_id": result.provenance.execution_tool_id,
                "execution_tool_version": result.provenance.execution_tool_version,
                "execution_revision": result.provenance.execution_revision,
                "produced_at": result.provenance.produced_at.isoformat(),
            },
            "segments": [
                {
                    "id": segment.id.value,
                    "ordinal": segment.ordinal,
                    "text": segment.text,
                    "asset_start_microseconds": segment.asset_start_microseconds,
                    "asset_end_microseconds": segment.asset_end_microseconds,
                    "speaker_label": segment.speaker_label,
                    "speaker_evidence_kind": (
                        None
                        if segment.speaker_evidence_kind is None
                        else segment.speaker_evidence_kind.value
                    ),
                    "confidence": segment.confidence,
                    "confidence_semantics": segment.confidence_semantics,
                    "words": [
                        {
                            "id": word.id.value,
                            "ordinal": word.ordinal,
                            "text": word.text,
                            "asset_start_microseconds": word.asset_start_microseconds,
                            "asset_end_microseconds": word.asset_end_microseconds,
                            "confidence": word.confidence,
                            "confidence_semantics": word.confidence_semantics,
                            "limitations": word.limitations,
                        }
                        for word in segment.words
                    ],
                    "limitations": segment.limitations,
                }
                for segment in result.segments
            ],
            "limitations": result.limitations,
            "partial_reason": result.partial_reason,
            "failure_reason": result.failure_reason,
        }
    )


def prepare_transcript_evidence(
    claim: OperationClaim,
    result: NormalizedTranscriptResult,
    *,
    alignments: tuple[DerivedTranscriptAlignment, ...] = (),
) -> PendingTranscriptEvidence:
    value = claim.operation.input
    return PendingTranscriptEvidence(
        id=EntityId.new(),
        operation_id=claim.operation.id,
        work_key=claim.operation.work_key,
        result_digest=transcript_result_digest(result),
        asset_id=value.asset_id,
        manifest_id=value.manifest_id,
        manifest_version=value.manifest_version,
        result=result,
        alignments=alignments,
    )


def align_with_media_timing(
    result: NormalizedTranscriptResult,
    evidence: MediaTimingEvidence,
    *,
    derived_at: datetime,
) -> tuple[DerivedTranscriptAlignment, ...]:
    require_aware_datetime(derived_at, "derived_at")
    if len(evidence.result.derivations) != 1:
        raise ValueError("MTE alignment requires exactly one unambiguous candidate interval.")
    basis = evidence.result.derivations[0]
    qualification = evidence.result.qualification.status
    alignments: list[DerivedTranscriptAlignment] = []
    for segment in result.segments:
        started = basis.candidate_started_at + timedelta(
            microseconds=segment.asset_start_microseconds
        )
        ended = basis.candidate_started_at + timedelta(
            microseconds=segment.asset_end_microseconds
        )
        limitations = list(basis.limitations)
        if qualification.value != "qualified":
            limitations.append("recorder_profile_unqualified")
        if ended > basis.candidate_ended_at:
            limitations.append("extends_beyond_mte_candidate_interval")
        alignments.append(
            DerivedTranscriptAlignment(
                id=EntityId.new(),
                segment_id=segment.id,
                media_timing_evidence_id=evidence.id,
                qualification_status=qualification,
                wall_clock_started_at=started,
                wall_clock_ended_at=ended,
                derived_at=derived_at,
                limitations=tuple(limitations),
            )
        )
    return tuple(alignments)


__all__ = [
    "TranscriptionExecutionError",
    "TranscriptionExecutionPort",
    "TranscriptionExecutionRequest",
    "align_with_media_timing",
    "prepare_transcript_evidence",
    "transcript_result_digest",
]

