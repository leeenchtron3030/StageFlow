from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceRole,
    EvidenceSignal,
)
from app.contexts.production.operational_state import OperationalStateValue
from app.shared.ids import EntityId

from .session_transition_requirement import SessionTransitionRequirement
from .session_transition_rule import (
    SessionTransitionContradictionBehavior,
    SessionTransitionRule,
)


class SessionTransitionEvidenceCategory(StrEnum):
    SESSION_SPECIFIC = "session_specific"
    MEDIA_CORROBORATION = "media_corroboration"
    SCHEDULE_CONTEXT = "schedule_context"
    OPERATOR_CONTEXT = "operator_context"
    END_SPECIFIC = "end_specific"
    END_CORROBORATION = "end_corroboration"
    END_CONTEXT = "end_context"
    CONTINUITY_CONTEXT = "continuity_context"
    CONTRADICTORY = "contradictory"
    UNSUPPORTED = "unsupported"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _stable_id(name: str) -> EntityId:
    return EntityId.parse(str(uuid5(NAMESPACE_URL, f"stageflow:session-transition:{name}")))


@dataclass(frozen=True, slots=True)
class SessionTransitionMapping:
    """Explicit boundary Signal to policy-category mapping."""

    boundary_concern: EvidenceConcern
    signal: EvidenceSignal
    category: SessionTransitionEvidenceCategory
    rationale: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.boundary_concern not in {
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceConcern.POSSIBLE_SESSION_END,
        }:
            raise ValueError("Session transition mapping requires a boundary concern.")
        if self.signal is EvidenceSignal.UNKNOWN:
            raise ValueError("Session transition mapping requires a known Signal.")
        if not self.rationale.strip():
            raise ValueError("Session transition mapping rationale must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


_START_SPECIFIC_SIGNALS = (
    EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
    EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
    EvidenceSignal.SESSION_CONTENT_INDICATED,
)
_START_MEDIA_SIGNALS = (
    EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
    EvidenceSignal.RECORDING_CONTINUITY_RESTORED,
    EvidenceSignal.VISUAL_ACTIVITY_AVAILABLE,
    EvidenceSignal.MEDIA_AVAILABILITY_INDICATED,
)
_START_CONTINUITY_SIGNALS = (
    EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
    EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
)
_START_SCHEDULE_SIGNALS = (EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,)
_START_OPERATOR_SIGNALS = (EvidenceSignal.OPERATOR_ATTENTION_INDICATED,)
_END_SPECIFIC_SIGNALS = (
    EvidenceSignal.SESSION_END_INDICATED,
    EvidenceSignal.TRANSCRIPT_END_INDICATED,
)
_END_CORROBORATION_SIGNALS = (EvidenceSignal.RECORDING_END_INDICATED,)
_END_CONTEXT_SIGNALS = (
    EvidenceSignal.RECORDING_PAUSE_INDICATED,
    EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
)
_END_SCHEDULE_SIGNALS = (
    EvidenceSignal.SCHEDULED_ACTIVITY_CHANGED,
    EvidenceSignal.SCHEDULED_ACTIVITY_CANCELLED,
)
_END_OPERATOR_SIGNALS = (EvidenceSignal.OPERATOR_ATTENTION_INDICATED,)

SESSION_TRANSITION_MAPPINGS: tuple[SessionTransitionMapping, ...] = tuple(
    SessionTransitionMapping(
        boundary_concern=concern,
        signal=signal,
        category=category,
        rationale=rationale,
    )
    for concern, signals, category, rationale in (
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            _START_SPECIFIC_SIGNALS,
            SessionTransitionEvidenceCategory.SESSION_SPECIFIC,
            "Signal is a session-specific possible-start indication.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            _START_MEDIA_SIGNALS,
            SessionTransitionEvidenceCategory.MEDIA_CORROBORATION,
            "Signal provides media corroboration for a possible start.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            _START_CONTINUITY_SIGNALS,
            SessionTransitionEvidenceCategory.CONTINUITY_CONTEXT,
            "Signal provides speech or transcript corroboration for a possible start.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            _START_SCHEDULE_SIGNALS,
            SessionTransitionEvidenceCategory.SCHEDULE_CONTEXT,
            "Signal provides schedule context for a possible start.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            _START_OPERATOR_SIGNALS,
            SessionTransitionEvidenceCategory.OPERATOR_CONTEXT,
            "Signal provides operator context for a possible start.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            _END_SPECIFIC_SIGNALS,
            SessionTransitionEvidenceCategory.END_SPECIFIC,
            "Signal is a session- or transcript-specific possible-end indication.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            _END_CORROBORATION_SIGNALS,
            SessionTransitionEvidenceCategory.END_CORROBORATION,
            "Recording end corroborates a possible end but is not session-specific.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            _END_CONTEXT_SIGNALS,
            SessionTransitionEvidenceCategory.END_CONTEXT,
            "Signal provides operational context for a possible end.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            _END_SCHEDULE_SIGNALS,
            SessionTransitionEvidenceCategory.SCHEDULE_CONTEXT,
            "Signal provides schedule context for a possible end.",
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            _END_OPERATOR_SIGNALS,
            SessionTransitionEvidenceCategory.OPERATOR_CONTEXT,
            "Signal provides operator context for a possible end.",
        ),
    )
    for signal in signals
)


def mapping_for_session_signal(
    concern: EvidenceConcern,
    signal: EvidenceSignal,
) -> SessionTransitionMapping | None:
    for mapping in SESSION_TRANSITION_MAPPINGS:
        if mapping.boundary_concern is concern and mapping.signal is signal:
            return mapping
    return None


SUPPORTED_SESSION_TRANSITIONS = frozenset(
    {
        (OperationalStateValue.INACTIVE, OperationalStateValue.ACTIVE),
        (OperationalStateValue.ACTIVE, OperationalStateValue.ENDING),
        (OperationalStateValue.ACTIVE, OperationalStateValue.ENDED),
        (OperationalStateValue.ENDING, OperationalStateValue.ENDED),
        (OperationalStateValue.ENDED, OperationalStateValue.ACTIVE),
        (OperationalStateValue.INACTIVE, OperationalStateValue.INACTIVE),
        (OperationalStateValue.ACTIVE, OperationalStateValue.ACTIVE),
        (OperationalStateValue.ENDING, OperationalStateValue.ENDING),
        (OperationalStateValue.ENDED, OperationalStateValue.ENDED),
    }
)

_START_CORROBORATION_CATEGORIES = (
    SessionTransitionEvidenceCategory.MEDIA_CORROBORATION.value,
    SessionTransitionEvidenceCategory.SCHEDULE_CONTEXT.value,
    SessionTransitionEvidenceCategory.OPERATOR_CONTEXT.value,
    SessionTransitionEvidenceCategory.CONTINUITY_CONTEXT.value,
)
_START_CORROBORATION_SIGNALS = (
    _START_MEDIA_SIGNALS
    + _START_CONTINUITY_SIGNALS
    + _START_SCHEDULE_SIGNALS
    + _START_OPERATOR_SIGNALS
)
_ALL_END_CATEGORIES = (
    SessionTransitionEvidenceCategory.END_SPECIFIC.value,
    SessionTransitionEvidenceCategory.END_CORROBORATION.value,
    SessionTransitionEvidenceCategory.END_CONTEXT.value,
    SessionTransitionEvidenceCategory.SCHEDULE_CONTEXT.value,
    SessionTransitionEvidenceCategory.OPERATOR_CONTEXT.value,
)
_ALL_END_SIGNALS = (
    _END_SPECIFIC_SIGNALS
    + _END_CORROBORATION_SIGNALS
    + _END_CONTEXT_SIGNALS
    + _END_SCHEDULE_SIGNALS
    + _END_OPERATOR_SIGNALS
)
_ADDITIONAL_END_CONTEXT_SIGNALS = (
    _END_CONTEXT_SIGNALS + _END_SCHEDULE_SIGNALS + _END_OPERATOR_SIGNALS
)
_CONTEXT_ROLES = (EvidenceRole.SUPPORTS, EvidenceRole.CONTEXTUALIZES)


def _requirement(
    name: str,
    current: OperationalStateValue,
    proposed: OperationalStateValue,
    categories: tuple[str, ...],
    signals: tuple[EvidenceSignal, ...],
    rationale: str,
    *,
    minimum: int = 1,
    independent: bool = False,
    roles: tuple[EvidenceRole, ...] = (EvidenceRole.SUPPORTS,),
    fresh: bool = False,
) -> SessionTransitionRequirement:
    return SessionTransitionRequirement(
        id=_stable_id(f"requirement:{name}:{current.value}:{proposed.value}"),
        current_state_value=current,
        proposed_state_value=proposed,
        evidence_categories=categories,
        minimum_categorical_count=minimum,
        require_independent_sources=independent,
        allowed_signals=signals,
        allowed_roles=roles,
        requires_fresh_context=fresh,
        rationale=rationale,
    )


def _start_requirements(
    current: OperationalStateValue,
    proposed: OperationalStateValue,
    *,
    fresh: bool = False,
) -> tuple[SessionTransitionRequirement, ...]:
    requirements = (
        _requirement(
            "session-specific-start",
            current,
            proposed,
            (SessionTransitionEvidenceCategory.SESSION_SPECIFIC.value,),
            _START_SPECIFIC_SIGNALS,
            "At least one supporting session-specific start Signal is required.",
        ),
        _requirement(
            "start-corroboration",
            current,
            proposed,
            _START_CORROBORATION_CATEGORIES,
            _START_CORROBORATION_SIGNALS,
            "At least one independently traceable corroborating start Signal is required.",
            roles=_CONTEXT_ROLES,
        ),
    )
    if not fresh:
        return requirements
    return requirements + (
        _requirement(
            "fresh-start-context",
            current,
            proposed,
            (
                SessionTransitionEvidenceCategory.SESSION_SPECIFIC.value,
                *_START_CORROBORATION_CATEGORIES,
            ),
            _START_SPECIFIC_SIGNALS + _START_CORROBORATION_SIGNALS,
            "The possible-start context must be explicitly distinct from the prior end.",
            roles=_CONTEXT_ROLES,
            fresh=True,
        ),
    )


def _ended_requirements(
    current: OperationalStateValue,
    proposed: OperationalStateValue,
) -> tuple[SessionTransitionRequirement, ...]:
    return (
        _requirement(
            "end-specific",
            current,
            proposed,
            (SessionTransitionEvidenceCategory.END_SPECIFIC.value,),
            _END_SPECIFIC_SIGNALS,
            "At least one supporting session- or transcript-specific end Signal is required.",
        ),
        _requirement(
            "independent-end-corroboration",
            current,
            proposed,
            _ALL_END_CATEGORIES,
            _ALL_END_SIGNALS,
            "At least two independently traceable end-oriented indications are required.",
            minimum=2,
            independent=True,
            roles=_CONTEXT_ROLES,
        ),
    )


def _explicit_ending_requirements(
    current: OperationalStateValue,
    proposed: OperationalStateValue,
) -> tuple[SessionTransitionRequirement, ...]:
    return (
        _requirement(
            "explicit-ending",
            current,
            proposed,
            (SessionTransitionEvidenceCategory.END_SPECIFIC.value,),
            _END_SPECIFIC_SIGNALS,
            "One supporting session- or transcript-specific end Signal is required.",
        ),
    )


def _recording_ending_requirements(
    current: OperationalStateValue,
    proposed: OperationalStateValue,
) -> tuple[SessionTransitionRequirement, ...]:
    return (
        _requirement(
            "recording-end",
            current,
            proposed,
            (SessionTransitionEvidenceCategory.END_CORROBORATION.value,),
            _END_CORROBORATION_SIGNALS,
            "A supporting recording-end Signal is required.",
        ),
        _requirement(
            "recording-end-context",
            current,
            proposed,
            (
                SessionTransitionEvidenceCategory.END_CONTEXT.value,
                SessionTransitionEvidenceCategory.SCHEDULE_CONTEXT.value,
                SessionTransitionEvidenceCategory.OPERATOR_CONTEXT.value,
            ),
            _ADDITIONAL_END_CONTEXT_SIGNALS,
            "Recording end requires one independently traceable additional end context Signal.",
            roles=_CONTEXT_ROLES,
        ),
    )


def _rule(
    name: str,
    current: OperationalStateValue,
    proposed: OperationalStateValue,
    concern: EvidenceConcern,
    requirements: tuple[SessionTransitionRequirement, ...],
    rationale: str,
    *,
    distinct: bool = False,
) -> SessionTransitionRule:
    return SessionTransitionRule(
        id=_stable_id(f"rule:{name}:{current.value}:{proposed.value}"),
        current_state_value=current,
        proposed_state_value=proposed,
        required_boundary_concern=concern,
        requirements=requirements,
        allowed_evidence_roles=(
            EvidenceRole.SUPPORTS,
            EvidenceRole.CONTEXTUALIZES,
            EvidenceRole.CONTRADICTS,
            EvidenceRole.NEUTRAL,
        ),
        contradiction_behavior=SessionTransitionContradictionBehavior.BLOCK,
        rationale_template=rationale,
        requirements_require_distinct_sources=distinct,
    )


SESSION_TRANSITION_RULES: tuple[SessionTransitionRule, ...] = (
    _rule(
        "inactive-active",
        OperationalStateValue.INACTIVE,
        OperationalStateValue.ACTIVE,
        EvidenceConcern.POSSIBLE_SESSION_START,
        _start_requirements(OperationalStateValue.INACTIVE, OperationalStateValue.ACTIVE),
        "Session-specific start Evidence and independent corroboration support proposing active.",
        distinct=True,
    ),
    _rule(
        "active-ended",
        OperationalStateValue.ACTIVE,
        OperationalStateValue.ENDED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        _ended_requirements(OperationalStateValue.ACTIVE, OperationalStateValue.ENDED),
        "Session-specific end Evidence and independent corroboration support proposing ended.",
    ),
    _rule(
        "active-ending-explicit",
        OperationalStateValue.ACTIVE,
        OperationalStateValue.ENDING,
        EvidenceConcern.POSSIBLE_SESSION_END,
        _explicit_ending_requirements(
            OperationalStateValue.ACTIVE,
            OperationalStateValue.ENDING,
        ),
        "Explicit session- or transcript-end Evidence supports proposing ending.",
    ),
    _rule(
        "active-ending-recording",
        OperationalStateValue.ACTIVE,
        OperationalStateValue.ENDING,
        EvidenceConcern.POSSIBLE_SESSION_END,
        _recording_ending_requirements(
            OperationalStateValue.ACTIVE,
            OperationalStateValue.ENDING,
        ),
        "Recording-end Evidence plus independent end context supports proposing ending.",
        distinct=True,
    ),
    _rule(
        "active-active",
        OperationalStateValue.ACTIVE,
        OperationalStateValue.ACTIVE,
        EvidenceConcern.POSSIBLE_SESSION_START,
        _start_requirements(OperationalStateValue.ACTIVE, OperationalStateValue.ACTIVE),
        "Possible-start Evidence proposes the already-current active value.",
        distinct=True,
    ),
    _rule(
        "ending-ended",
        OperationalStateValue.ENDING,
        OperationalStateValue.ENDED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        _ended_requirements(OperationalStateValue.ENDING, OperationalStateValue.ENDED),
        "Session-specific end Evidence and independent corroboration support proposing ended.",
    ),
    _rule(
        "ending-ending-explicit",
        OperationalStateValue.ENDING,
        OperationalStateValue.ENDING,
        EvidenceConcern.POSSIBLE_SESSION_END,
        _explicit_ending_requirements(
            OperationalStateValue.ENDING,
            OperationalStateValue.ENDING,
        ),
        "Explicit end Evidence proposes the already-current ending value.",
    ),
    _rule(
        "ending-ending-recording",
        OperationalStateValue.ENDING,
        OperationalStateValue.ENDING,
        EvidenceConcern.POSSIBLE_SESSION_END,
        _recording_ending_requirements(
            OperationalStateValue.ENDING,
            OperationalStateValue.ENDING,
        ),
        "Corroborated recording-end Evidence proposes the already-current ending value.",
        distinct=True,
    ),
    _rule(
        "ended-active",
        OperationalStateValue.ENDED,
        OperationalStateValue.ACTIVE,
        EvidenceConcern.POSSIBLE_SESSION_START,
        _start_requirements(
            OperationalStateValue.ENDED,
            OperationalStateValue.ACTIVE,
            fresh=True,
        ),
        "Fresh start Evidence and independent corroboration support proposing active.",
        distinct=True,
    ),
    _rule(
        "ended-ended",
        OperationalStateValue.ENDED,
        OperationalStateValue.ENDED,
        EvidenceConcern.POSSIBLE_SESSION_END,
        _ended_requirements(OperationalStateValue.ENDED, OperationalStateValue.ENDED),
        "Corroborated end Evidence proposes the already-current ended value.",
    ),
)
