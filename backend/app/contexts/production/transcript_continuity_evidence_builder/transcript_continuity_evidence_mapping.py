from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceSignal
from app.contexts.production.observation import Observation


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TranscriptContinuityEvidenceMapping:
    """Declarative mapping from transcript Observation semantics to Evidence Signals."""

    transcript_lifecycle: str
    evidence_signal: EvidenceSignal
    rationale: str
    continuation_signal: EvidenceSignal | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.transcript_lifecycle.strip():
            raise ValueError(
                "TranscriptContinuityEvidenceMapping transcript_lifecycle is required."
            )
        if self.evidence_signal is EvidenceSignal.UNKNOWN:
            raise ValueError(
                "TranscriptContinuityEvidenceMapping must not map to unknown Signal."
            )
        if self.continuation_signal is EvidenceSignal.UNKNOWN:
            raise ValueError(
                "TranscriptContinuityEvidenceMapping continuation Signal must not be unknown."
            )
        if not self.rationale.strip():
            raise ValueError("TranscriptContinuityEvidenceMapping rationale is required.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


TRANSCRIPT_CONTINUITY_EVIDENCE_MAPPINGS: tuple[
    TranscriptContinuityEvidenceMapping,
    ...,
] = (
    TranscriptContinuityEvidenceMapping(
        transcript_lifecycle="segment_available",
        evidence_signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        continuation_signal=EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
        rationale="Transcript segment availability indicates speech activity is available.",
    ),
    TranscriptContinuityEvidenceMapping(
        transcript_lifecycle="transcript_activity_began",
        evidence_signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        rationale="Transcript activity began, indicating speech activity is available.",
    ),
    TranscriptContinuityEvidenceMapping(
        transcript_lifecycle="transcript_content_continued",
        evidence_signal=EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
        rationale="Transcript content continued, indicating transcript continuity.",
    ),
    TranscriptContinuityEvidenceMapping(
        transcript_lifecycle="transcript_activity_interrupted",
        evidence_signal=EvidenceSignal.TRANSCRIPT_INTERRUPTION_INDICATED,
        rationale="Transcript activity interruption was explicitly observed.",
    ),
    TranscriptContinuityEvidenceMapping(
        transcript_lifecycle="transcript_activity_ended",
        evidence_signal=EvidenceSignal.TRANSCRIPT_END_INDICATED,
        rationale="Transcript activity ending was explicitly observed.",
    ),
)


def mapping_for_transcript_observation(
    observation: Observation,
) -> TranscriptContinuityEvidenceMapping | None:
    lifecycle = observation.metadata.get("transcript_lifecycle")
    if isinstance(lifecycle, str):
        return mapping_for_transcript_lifecycle(lifecycle)
    return None


def mapping_for_transcript_lifecycle(
    transcript_lifecycle: str,
) -> TranscriptContinuityEvidenceMapping | None:
    for mapping in TRANSCRIPT_CONTINUITY_EVIDENCE_MAPPINGS:
        if mapping.transcript_lifecycle == transcript_lifecycle:
            return mapping
    return None
