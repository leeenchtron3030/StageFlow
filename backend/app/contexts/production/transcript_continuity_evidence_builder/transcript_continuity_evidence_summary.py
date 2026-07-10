from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.evidence import EvidenceSignal

from .transcript_continuity_evidence_result import TranscriptContinuityEvidenceResult


@dataclass(frozen=True, slots=True)
class TranscriptContinuityEvidenceSummary:
    """Concise diagnostics for transcript continuity Evidence building."""

    input_observation_count: int
    recognized_transcript_observation_count: int
    ignored_observation_count: int
    unsupported_transcript_observation_count: int
    duplicate_observation_count: int
    produced_evidence_set_count: int
    produced_evidence_item_count: int
    produced_signal_count: int
    signals: tuple[EvidenceSignal, ...]
    transcript_stream_count: int = 0
    recording_block_count: int = 0
    stage_count: int = 0
    timeline_span_seconds: tuple[float, float] | None = None

    @classmethod
    def from_result(
        cls,
        result: TranscriptContinuityEvidenceResult,
    ) -> TranscriptContinuityEvidenceSummary:
        signals = tuple(
            signal_reference.signal
            for evidence_set in result.evidence_sets
            for signal_reference in evidence_set.signals
        )
        stream_ids = {
            signal_reference.metadata.get("transcript_stream_id")
            for evidence_set in result.evidence_sets
            for signal_reference in evidence_set.signals
            if signal_reference.metadata.get("transcript_stream_id") is not None
        }
        recording_block_ids = {
            evidence_set.recording_block_id
            for evidence_set in result.evidence_sets
            if evidence_set.recording_block_id is not None
        }
        stage_ids = {
            signal_reference.metadata.get("stage_id")
            for evidence_set in result.evidence_sets
            for signal_reference in evidence_set.signals
            if signal_reference.metadata.get("stage_id") is not None
        }

        return cls(
            input_observation_count=int(result.metadata.get("input_observation_count", 0)),
            recognized_transcript_observation_count=len(result.consumed_observation_ids),
            ignored_observation_count=len(result.ignored_observation_ids),
            unsupported_transcript_observation_count=len(
                result.unsupported_observation_ids
            ),
            duplicate_observation_count=len(result.duplicate_observation_ids),
            produced_evidence_set_count=len(result.evidence_sets),
            produced_evidence_item_count=sum(
                len(evidence_set.items) for evidence_set in result.evidence_sets
            ),
            produced_signal_count=len(signals),
            signals=signals,
            transcript_stream_count=len(stream_ids),
            recording_block_count=len(recording_block_ids),
            stage_count=len(stage_ids),
            timeline_span_seconds=result.metadata.get("timeline_span_seconds"),
        )
