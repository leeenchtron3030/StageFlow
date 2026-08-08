from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from app.contexts.production.evidence import (
    EvidenceContext,
    EvidenceContextConflict,
    EvidenceSignal,
)
from app.contexts.production.operational_state import (
    OperationalStateKind,
    OperationalStateValue,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .operational_state_acceptance_context import OperationalStateAcceptanceContext
from .operational_state_acceptance_mapping import (
    RECORDING_TRANSITION_POLICY_KIND,
    SESSION_TRANSITION_POLICY_KIND,
)

if TYPE_CHECKING:
    from app.contexts.production.recording_transition_policy import RecordingTransitionResult
    from app.contexts.production.session_transition_policy import SessionTransitionResult


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _unique(values: Sequence[EntityId]) -> tuple[EntityId, ...]:
    return tuple(dict.fromkeys(values))


def _unique_text(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value.strip()))


def _entity(value: object) -> EntityId | None:
    if isinstance(value, EntityId):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return EntityId.parse(value)
        except ValueError:
            return None
    return None


def _entity_sequence(value: object) -> tuple[EntityId, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return _unique(
        tuple(
            parsed
            for item in cast(Sequence[object], value)
            if (parsed := _entity(item)) is not None
        )
    )


def _text_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return _unique_text(
        tuple(item for item in cast(Sequence[object], value) if isinstance(item, str))
    )


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceLineage:
    """First-class ID-only lineage required to accept one evaluation."""

    evaluation_id: EntityId
    policy_kind: str | None
    policy_id: EntityId | None
    applied_rule_id: EntityId | None
    evaluated_state_kind: OperationalStateKind
    current_state_id: EntityId | None
    effective_current_value: OperationalStateValue
    proposed_state_value: OperationalStateValue
    supporting_evidence_set_ids: Sequence[EntityId]
    blocking_evidence_set_ids: Sequence[EntityId] = field(default_factory=tuple)
    contributing_evidence_item_ids: Sequence[EntityId] = field(default_factory=tuple)
    contributing_observation_ids: Sequence[EntityId] = field(default_factory=tuple)
    contributing_production_event_ids: Sequence[EntityId] = field(default_factory=tuple)
    contributing_signals: Sequence[EvidenceSignal] = field(default_factory=tuple)
    satisfied_requirement_ids: Sequence[EntityId] = field(default_factory=tuple)
    unmet_requirement_ids: Sequence[EntityId] = field(default_factory=tuple)
    interpreter_ids: Sequence[EntityId] = field(default_factory=tuple)
    interpretation_rule_ids: Sequence[str] = field(default_factory=tuple)
    organizational_anchors: Sequence[str] = field(default_factory=tuple)
    context: OperationalStateAcceptanceContext = field(
        default_factory=OperationalStateAcceptanceContext.unknown
    )
    evaluation_context: EvidenceContext = field(default_factory=EvidenceContext.unknown)
    context_conflicts: Sequence[EvidenceContextConflict] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for name in (
            "supporting_evidence_set_ids",
            "blocking_evidence_set_ids",
            "contributing_evidence_item_ids",
            "contributing_observation_ids",
            "contributing_production_event_ids",
            "satisfied_requirement_ids",
            "unmet_requirement_ids",
            "interpreter_ids",
        ):
            object.__setattr__(self, name, _unique(getattr(self, name)))
        object.__setattr__(
            self,
            "contributing_signals",
            tuple(dict.fromkeys(self.contributing_signals)),
        )
        object.__setattr__(
            self,
            "interpretation_rule_ids",
            _unique_text(self.interpretation_rule_ids),
        )
        object.__setattr__(
            self,
            "organizational_anchors",
            _unique_text(self.organizational_anchors),
        )
        object.__setattr__(self, "context_conflicts", tuple(self.context_conflicts))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def from_recording_result(
        cls,
        result: RecordingTransitionResult,
    ) -> OperationalStateAcceptanceLineage:
        evaluation = result.evaluation
        profile = result.evidence_profile
        selected_context = profile.selected_context
        policy_id = _entity(evaluation.metadata.get("policy_id"))
        source_event_ids = _entity_sequence(
            evaluation.metadata.get("source_production_event_ids", ())
        )
        interpreter_ids = _entity_sequence(evaluation.metadata.get("source_interpreter_ids", ()))
        signals = tuple(profile.contributing_signals)
        return cls(
            evaluation_id=evaluation.id,
            policy_kind=RECORDING_TRANSITION_POLICY_KIND,
            policy_id=policy_id,
            applied_rule_id=result.applied_rule_id,
            evaluated_state_kind=evaluation.evaluated_state_kind,
            current_state_id=evaluation.current_state.id if evaluation.current_state else None,
            effective_current_value=OperationalStateValue(
                str(evaluation.metadata["effective_current_state_value"])
            ),
            proposed_state_value=evaluation.proposed_state or OperationalStateValue.UNKNOWN,
            supporting_evidence_set_ids=evaluation.supporting_evidence_ids,
            blocking_evidence_set_ids=evaluation.blocking_evidence_ids,
            contributing_evidence_item_ids=profile.contributing_evidence_item_ids,
            contributing_observation_ids=profile.contributing_observation_ids,
            contributing_production_event_ids=source_event_ids,
            contributing_signals=signals,
            interpreter_ids=interpreter_ids,
            interpretation_rule_ids=_text_sequence(
                evaluation.metadata.get("source_interpretation_rule_ids", ())
            ),
            organizational_anchors=(
                (selected_context.organizational_at.isoformat(),)
                if selected_context is not None and selected_context.organizational_at is not None
                else ()
            ),
            context=OperationalStateAcceptanceContext(
                stage_id=selected_context.stage_id if selected_context else None,
                recording_block_id=(
                    selected_context.recording_block_id if selected_context else None
                ),
                media_artifact_ids=(
                    (selected_context.media_artifact_id,)
                    if selected_context is not None
                    and selected_context.media_artifact_id is not None
                    else ()
                ),
                correlation_id=(selected_context.correlation_id if selected_context else None),
                timeline_range_seconds=(
                    selected_context.timeline_range_seconds if selected_context else None
                ),
            ),
            evaluation_context=evaluation.context,
            context_conflicts=evaluation.context_conflicts,
            metadata={"source": "recording_transition_result"},
        )

    @classmethod
    def from_session_result(
        cls,
        result: SessionTransitionResult,
    ) -> OperationalStateAcceptanceLineage:
        evaluation = result.evaluation
        profile = result.evidence_profile
        policy_id = _entity(evaluation.metadata.get("policy_id"))
        effective_value = OperationalStateValue(
            str(evaluation.metadata["effective_current_state_value"])
        )
        return cls(
            evaluation_id=evaluation.id,
            policy_kind=SESSION_TRANSITION_POLICY_KIND,
            policy_id=policy_id,
            applied_rule_id=result.applied_rule_id,
            evaluated_state_kind=evaluation.evaluated_state_kind,
            current_state_id=evaluation.current_state.id if evaluation.current_state else None,
            effective_current_value=effective_value,
            proposed_state_value=evaluation.proposed_state or OperationalStateValue.UNKNOWN,
            supporting_evidence_set_ids=evaluation.supporting_evidence_ids,
            blocking_evidence_set_ids=evaluation.blocking_evidence_ids,
            contributing_evidence_item_ids=(
                profile.contributing_evidence_item_ids if profile is not None else ()
            ),
            contributing_observation_ids=(
                profile.contributing_observation_ids if profile is not None else ()
            ),
            contributing_production_event_ids=_entity_sequence(
                evaluation.metadata.get("source_production_event_ids", ())
            ),
            contributing_signals=(profile.contributing_signals if profile is not None else ()),
            satisfied_requirement_ids=result.satisfied_requirement_ids,
            unmet_requirement_ids=result.unmet_requirement_ids,
            interpreter_ids=_entity_sequence(evaluation.metadata.get("source_interpreter_ids", ())),
            interpretation_rule_ids=_text_sequence(
                evaluation.metadata.get("source_interpretation_rule_ids", ())
            ),
            organizational_anchors=(profile.boundary_anchors if profile else ()),
            context=OperationalStateAcceptanceContext(
                stage_id=(
                    profile.stage_ids[0] if profile and len(profile.stage_ids) == 1 else None
                ),
                recording_block_id=(
                    profile.recording_block_ids[0]
                    if profile and len(profile.recording_block_ids) == 1
                    else None
                ),
                scheduled_activity_id=(
                    profile.scheduled_activity_ids[0]
                    if profile and len(profile.scheduled_activity_ids) == 1
                    else None
                ),
                organizational_anchor=(
                    profile.boundary_anchors[0]
                    if profile and len(profile.boundary_anchors) == 1
                    else None
                ),
            ),
            evaluation_context=evaluation.context,
            context_conflicts=evaluation.context_conflicts,
            metadata={"source": "session_transition_result"},
        )
