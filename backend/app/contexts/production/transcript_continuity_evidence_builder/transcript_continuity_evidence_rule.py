from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceRole,
    EvidenceSignal,
    EvidenceStrength,
)
from app.contexts.production.observation import ObservationType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TranscriptContinuityEvidenceRule:
    """Declarative rule for one supported transcript continuity signal."""

    id: EntityId
    recognized_observation_type: ObservationType
    recognized_transcript_lifecycle: str
    target_signal: EvidenceSignal
    target_concern: EvidenceConcern = EvidenceConcern.TRANSCRIPT_CONTINUITY
    evidence_role: EvidenceRole = EvidenceRole.SUPPORTS
    evidence_strength: EvidenceStrength = EvidenceStrength.STRONG
    rationale_template: str = (
        "Transcript lifecycle '{transcript_lifecycle}' supports "
        "{evidence_signal} for transcript continuity."
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.recognized_observation_type is not ObservationType.TRANSCRIPT_ACTIVITY:
            raise ValueError(
                "TranscriptContinuityEvidenceRule only supports transcript Observations."
            )
        if not self.recognized_transcript_lifecycle.strip():
            raise ValueError(
                "TranscriptContinuityEvidenceRule recognized lifecycle is required."
            )
        if self.target_concern is not EvidenceConcern.TRANSCRIPT_CONTINUITY:
            raise ValueError(
                "TranscriptContinuityEvidenceRule must target transcript continuity."
            )
        if self.target_signal is EvidenceSignal.UNKNOWN:
            raise ValueError("TranscriptContinuityEvidenceRule must not target unknown Signal.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def rationale(self) -> str:
        return self.rationale_template.format(
            transcript_lifecycle=self.recognized_transcript_lifecycle,
            evidence_signal=self.target_signal.value,
        )
