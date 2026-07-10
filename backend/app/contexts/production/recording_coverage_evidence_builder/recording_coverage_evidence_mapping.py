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
class RecordingCoverageEvidenceMapping:
    """Declarative mapping from recording Observation semantics to Evidence Signals."""

    recording_activity: str
    recording_event_kind: str
    evidence_signal: EvidenceSignal
    rationale: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.recording_activity.strip():
            raise ValueError(
                "RecordingCoverageEvidenceMapping recording_activity must not be empty."
            )
        if not self.recording_event_kind.strip():
            raise ValueError(
                "RecordingCoverageEvidenceMapping recording_event_kind must not be empty."
            )
        if self.evidence_signal is EvidenceSignal.UNKNOWN:
            raise ValueError(
                "RecordingCoverageEvidenceMapping must not map to unknown EvidenceSignal."
            )
        if not self.rationale.strip():
            raise ValueError("RecordingCoverageEvidenceMapping rationale must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


RECORDING_COVERAGE_EVIDENCE_MAPPINGS: tuple[
    RecordingCoverageEvidenceMapping,
    ...,
] = (
    RecordingCoverageEvidenceMapping(
        recording_activity="began",
        recording_event_kind="recording_started",
        evidence_signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        rationale="Recording activity began, indicating recording continuity was established.",
    ),
    RecordingCoverageEvidenceMapping(
        recording_activity="paused",
        recording_event_kind="recording_paused",
        evidence_signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        rationale="Recording activity paused, indicating recording coverage paused.",
    ),
    RecordingCoverageEvidenceMapping(
        recording_activity="resumed",
        recording_event_kind="recording_resumed",
        evidence_signal=EvidenceSignal.RECORDING_CONTINUITY_RESTORED,
        rationale="Recording activity resumed, indicating recording continuity was restored.",
    ),
    RecordingCoverageEvidenceMapping(
        recording_activity="ended",
        recording_event_kind="recording_stopped",
        evidence_signal=EvidenceSignal.RECORDING_END_INDICATED,
        rationale="Recording activity ended, indicating recording coverage ended.",
    ),
)


def mapping_for_recording_observation(
    observation: Observation,
) -> RecordingCoverageEvidenceMapping | None:
    """Return the supported recording coverage mapping for an Observation."""

    activity = observation.metadata.get("recording_activity")
    if isinstance(activity, str):
        mapping = mapping_for_recording_activity(activity)
        if mapping is not None:
            return mapping

    event_kind = observation.metadata.get("recording_event_kind")
    if isinstance(event_kind, str):
        return mapping_for_recording_event_kind(event_kind)

    return None


def mapping_for_recording_activity(
    recording_activity: str,
) -> RecordingCoverageEvidenceMapping | None:
    for mapping in RECORDING_COVERAGE_EVIDENCE_MAPPINGS:
        if mapping.recording_activity == recording_activity:
            return mapping
    return None


def mapping_for_recording_event_kind(
    recording_event_kind: str,
) -> RecordingCoverageEvidenceMapping | None:
    for mapping in RECORDING_COVERAGE_EVIDENCE_MAPPINGS:
        if mapping.recording_event_kind == recording_event_kind:
            return mapping
    return None
