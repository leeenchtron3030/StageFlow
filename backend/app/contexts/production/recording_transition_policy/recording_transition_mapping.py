from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.evidence import EvidenceSignal
from app.contexts.production.operational_state import OperationalStateValue


@dataclass(frozen=True, slots=True)
class RecordingTransitionMapping:
    """Declarative mapping from Evidence Signal to proposed recording state."""

    evidence_signal: EvidenceSignal
    proposed_state: OperationalStateValue
    rationale: str
    allowed_current_values: tuple[OperationalStateValue, ...]
    legacy_evidence_marker: str | None = None


RECORDING_TRANSITION_MAPPINGS: tuple[RecordingTransitionMapping, ...] = (
    RecordingTransitionMapping(
        evidence_signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        proposed_state=OperationalStateValue.ACTIVE,
        rationale="Recording Coverage Evidence supports active recording.",
        allowed_current_values=(
            OperationalStateValue.INACTIVE,
            OperationalStateValue.ACTIVE,
        ),
        legacy_evidence_marker="recording_active",
    ),
    RecordingTransitionMapping(
        evidence_signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        proposed_state=OperationalStateValue.PAUSED,
        rationale="Recording pause Evidence supports paused recording.",
        allowed_current_values=(
            OperationalStateValue.ACTIVE,
            OperationalStateValue.PAUSED,
        ),
        legacy_evidence_marker="recording_paused",
    ),
    RecordingTransitionMapping(
        evidence_signal=EvidenceSignal.RECORDING_CONTINUITY_RESTORED,
        proposed_state=OperationalStateValue.ACTIVE,
        rationale="Recording continuity restoration Evidence supports active recording.",
        allowed_current_values=(
            OperationalStateValue.PAUSED,
            OperationalStateValue.ACTIVE,
        ),
    ),
    RecordingTransitionMapping(
        evidence_signal=EvidenceSignal.RECORDING_END_INDICATED,
        proposed_state=OperationalStateValue.STOPPED,
        rationale="Recording stop Evidence supports stopped recording.",
        allowed_current_values=(
            OperationalStateValue.ACTIVE,
            OperationalStateValue.PAUSED,
            OperationalStateValue.STOPPED,
        ),
        legacy_evidence_marker="recording_stopped",
    ),
)


def mapping_for_recording_signal(
    evidence_signal: EvidenceSignal,
) -> RecordingTransitionMapping | None:
    for mapping in RECORDING_TRANSITION_MAPPINGS:
        if mapping.evidence_signal is evidence_signal:
            return mapping
    return None


def mapping_for_recording_marker(
    evidence_marker: str,
) -> RecordingTransitionMapping | None:
    for mapping in RECORDING_TRANSITION_MAPPINGS:
        if mapping.legacy_evidence_marker == evidence_marker:
            return mapping
    return None
