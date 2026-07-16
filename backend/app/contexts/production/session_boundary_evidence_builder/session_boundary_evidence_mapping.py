from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceRole,
    EvidenceSignal,
    EvidenceStrength,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionBoundaryEvidenceMapping:
    """One declarative Concern-and-Signal to possible-boundary mapping."""

    source_concern: EvidenceConcern
    source_signal: EvidenceSignal
    target_concern: EvidenceConcern
    target_role: EvidenceRole
    rationale: str
    strength_treatment: EvidenceStrength | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.source_concern is EvidenceConcern.UNKNOWN:
            raise ValueError("Session boundary mappings require a known source concern.")
        if self.source_signal is EvidenceSignal.UNKNOWN:
            raise ValueError("Session boundary mappings require a known source signal.")
        if self.target_concern not in {
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceConcern.POSSIBLE_SESSION_END,
        }:
            raise ValueError("Session boundary mappings must target a possible boundary concern.")
        if self.target_role not in {
            EvidenceRole.SUPPORTS,
            EvidenceRole.CONTRADICTS,
            EvidenceRole.CONTEXTUALIZES,
            EvidenceRole.NEUTRAL,
        }:
            raise ValueError("Session boundary mappings require an explicit Evidence role.")
        if not self.rationale.strip():
            raise ValueError("Session boundary mapping rationale must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def _mapping(
    source_concern: EvidenceConcern,
    source_signal: EvidenceSignal,
    target_concern: EvidenceConcern,
    target_role: EvidenceRole,
    rationale: str,
) -> SessionBoundaryEvidenceMapping:
    return SessionBoundaryEvidenceMapping(
        source_concern=source_concern,
        source_signal=source_signal,
        target_concern=target_concern,
        target_role=target_role,
        rationale=rationale,
    )


SESSION_BOUNDARY_EVIDENCE_MAPPINGS: tuple[SessionBoundaryEvidenceMapping, ...] = (
    _mapping(
        EvidenceConcern.SCHEDULE_ALIGNMENT,
        EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "An active scheduled window provides planned context for a possible session start.",
    ),
    _mapping(
        EvidenceConcern.SCHEDULE_ALIGNMENT,
        EvidenceSignal.SCHEDULED_ACTIVITY_CHANGED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "A scheduled activity change provides planned context near a possible session start.",
    ),
    _mapping(
        EvidenceConcern.SCHEDULE_ALIGNMENT,
        EvidenceSignal.SCHEDULED_ACTIVITY_CHANGED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.CONTEXTUALIZES,
        "A scheduled activity change provides planned context near a possible session end.",
    ),
    _mapping(
        EvidenceConcern.SCHEDULE_ALIGNMENT,
        EvidenceSignal.SCHEDULED_ACTIVITY_CANCELLED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.CONTEXTUALIZES,
        "A scheduled cancellation provides planned context but does not prove production ended.",
    ),
    _mapping(
        EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
        EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.SUPPORTS,
        "A structured speaker-introduction indication supports a possible session start.",
    ),
    _mapping(
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.SUPPORTS,
        "A structured speaker-introduction indication supports a possible session start.",
    ),
    _mapping(
        EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
        EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.SUPPORTS,
        "A presentation transition supports organizing Evidence around a possible session start.",
    ),
    _mapping(
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.SUPPORTS,
        "A presentation transition supports organizing Evidence around a possible session start.",
    ),
    _mapping(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.SUPPORTS,
        "Available speech activity supports a possible session start without identifying content.",
    ),
    _mapping(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "Transcript continuity provides context for a possible session start.",
    ),
    _mapping(
        EvidenceConcern.RECORDING_COVERAGE,
        EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "Established recording continuity provides media context but does not prove "
        "a session began.",
    ),
    _mapping(
        EvidenceConcern.RECORDING_COVERAGE,
        EvidenceSignal.RECORDING_CONTINUITY_RESTORED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "Restored recording continuity provides media context near a possible session start.",
    ),
    _mapping(
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceSignal.SESSION_CONTENT_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.SUPPORTS,
        "Structured session-content Evidence supports a possible session start.",
    ),
    _mapping(
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceSignal.OPERATOR_ATTENTION_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "Operator attention provides context without establishing a session start.",
    ),
    _mapping(
        EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
        EvidenceSignal.VISUAL_ACTIVITY_AVAILABLE,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "Available visual activity provides context without establishing a session start.",
    ),
    _mapping(
        EvidenceConcern.MEDIA_AVAILABILITY,
        EvidenceSignal.MEDIA_AVAILABILITY_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_START,
        EvidenceRole.CONTEXTUALIZES,
        "Media availability provides context without establishing a session start.",
    ),
    _mapping(
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceSignal.SESSION_END_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.SUPPORTS,
        "A structured session-end indication supports a possible session end.",
    ),
    _mapping(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        EvidenceSignal.TRANSCRIPT_END_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.SUPPORTS,
        "An explicit transcript end supports a possible session end without proving why it ended.",
    ),
    _mapping(
        EvidenceConcern.RECORDING_COVERAGE,
        EvidenceSignal.RECORDING_END_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.SUPPORTS,
        "A recording end supports a possible session end but may represent media segmentation.",
    ),
    _mapping(
        EvidenceConcern.RECORDING_COVERAGE,
        EvidenceSignal.RECORDING_PAUSE_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.CONTEXTUALIZES,
        "A recording pause provides boundary context but does not prove a session ended.",
    ),
    _mapping(
        EvidenceConcern.MEDIA_AVAILABILITY,
        EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.CONTEXTUALIZES,
        "Media finalization provides downstream context but does not prove the session boundary.",
    ),
    _mapping(
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceSignal.OPERATOR_ATTENTION_INDICATED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        EvidenceRole.CONTEXTUALIZES,
        "Operator attention provides context without establishing a session end.",
    ),
)


def mappings_for_source(
    concern: EvidenceConcern,
    signal: EvidenceSignal,
    mappings: tuple[SessionBoundaryEvidenceMapping, ...] = (
        SESSION_BOUNDARY_EVIDENCE_MAPPINGS
    ),
) -> tuple[SessionBoundaryEvidenceMapping, ...]:
    return tuple(
        mapping
        for mapping in mappings
        if mapping.source_concern is concern and mapping.source_signal is signal
    )


SUPPORTED_SESSION_BOUNDARY_SOURCE_CONCERNS = frozenset(
    mapping.source_concern for mapping in SESSION_BOUNDARY_EVIDENCE_MAPPINGS
)
