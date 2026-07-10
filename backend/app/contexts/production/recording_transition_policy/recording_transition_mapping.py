from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.operational_state import OperationalStateValue


@dataclass(frozen=True, slots=True)
class RecordingTransitionMapping:
    """Declarative mapping from recording evidence marker to proposed recording state."""

    evidence_marker: str
    proposed_state: OperationalStateValue
    rationale: str


RECORDING_TRANSITION_MAPPINGS: tuple[RecordingTransitionMapping, ...] = (
    RecordingTransitionMapping(
        evidence_marker="recording_active",
        proposed_state=OperationalStateValue.ACTIVE,
        rationale="Recording Coverage Evidence supports active recording.",
    ),
    RecordingTransitionMapping(
        evidence_marker="recording_paused",
        proposed_state=OperationalStateValue.PAUSED,
        rationale="Recording pause Evidence supports paused recording.",
    ),
    RecordingTransitionMapping(
        evidence_marker="recording_stopped",
        proposed_state=OperationalStateValue.STOPPED,
        rationale="Recording stop Evidence supports stopped recording.",
    ),
)


def mapping_for_recording_marker(
    evidence_marker: str,
) -> RecordingTransitionMapping | None:
    for mapping in RECORDING_TRANSITION_MAPPINGS:
        if mapping.evidence_marker == evidence_marker:
            return mapping
    return None
