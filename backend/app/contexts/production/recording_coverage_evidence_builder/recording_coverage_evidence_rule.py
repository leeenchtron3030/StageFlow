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
class RecordingCoverageEvidenceRule:
    """Declarative rule for one supported recording coverage signal."""

    id: EntityId
    recognized_observation_type: ObservationType
    recognized_recording_activity: str
    target_signal: EvidenceSignal
    target_concern: EvidenceConcern = EvidenceConcern.RECORDING_COVERAGE
    evidence_role: EvidenceRole = EvidenceRole.SUPPORTS
    evidence_strength: EvidenceStrength = EvidenceStrength.STRONG
    rationale_template: str = (
        "Recording activity '{recording_activity}' supports "
        "{evidence_signal} for recording coverage."
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.recognized_observation_type is not ObservationType.RECORDING_ACTIVITY:
            raise ValueError(
                "RecordingCoverageEvidenceRule only supports recording activity Observations."
            )
        if not self.recognized_recording_activity.strip():
            raise ValueError(
                "RecordingCoverageEvidenceRule recognized_recording_activity must not be empty."
            )
        if self.target_concern is not EvidenceConcern.RECORDING_COVERAGE:
            raise ValueError(
                "RecordingCoverageEvidenceRule must target recording coverage Evidence."
            )
        if self.target_signal is EvidenceSignal.UNKNOWN:
            raise ValueError("RecordingCoverageEvidenceRule must not target unknown Signal.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def rationale(self) -> str:
        return self.rationale_template.format(
            recording_activity=self.recognized_recording_activity,
            evidence_signal=self.target_signal.value,
        )
