from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.evidence import EvidenceConcern
from app.contexts.production.operational_state import OperationalStateValue
from app.contexts.production.transition_policy import TransitionPolicyResult
from app.shared.ids import EntityId

from .session_transition_result import SessionTransitionResult


@dataclass(frozen=True, slots=True)
class SessionTransitionSummary:
    """Concise non-executing summary of a Session transition evaluation."""

    current_session_state_value: OperationalStateValue | None
    effective_current_session_state_value: OperationalStateValue | None
    proposed_session_state_value: OperationalStateValue | None
    evaluation_outcome: TransitionPolicyResult
    boundary_concern_evaluated: EvidenceConcern | None
    contributing_evidence_set_count: int
    supporting_signal_count: int
    contextual_signal_count: int
    contradictory_signal_count: int
    independent_source_count: int
    satisfied_requirement_count: int
    unmet_requirement_count: int
    applied_rule_id: EntityId | None
    recording_block_ids: tuple[EntityId, ...]
    stage_ids: tuple[EntityId, ...]
    scheduled_activity_ids: tuple[EntityId, ...]
    organizational_anchors: tuple[str, ...]

    @classmethod
    def from_result(cls, result: SessionTransitionResult) -> SessionTransitionSummary:
        profile = result.evidence_profile
        current_state = result.evaluation.current_state
        effective_raw = result.evaluation.metadata.get("effective_current_state_value")
        effective_value: OperationalStateValue | None = None
        if isinstance(effective_raw, str):
            try:
                effective_value = OperationalStateValue(effective_raw)
            except ValueError:
                pass
        return cls(
            current_session_state_value=(
                current_state.value if current_state is not None else None
            ),
            effective_current_session_state_value=effective_value,
            proposed_session_state_value=result.evaluation.proposed_state,
            evaluation_outcome=result.evaluation.outcome,
            boundary_concern_evaluated=(
                profile.target_boundary_concern if profile is not None else None
            ),
            contributing_evidence_set_count=(
                len(profile.contributing_evidence_set_ids) if profile is not None else 0
            ),
            supporting_signal_count=profile.supporting_count if profile is not None else 0,
            contextual_signal_count=profile.contextual_count if profile is not None else 0,
            contradictory_signal_count=(
                profile.contradicting_count if profile is not None else 0
            ),
            independent_source_count=(
                profile.independent_source_count if profile is not None else 0
            ),
            satisfied_requirement_count=len(result.satisfied_requirement_ids),
            unmet_requirement_count=len(result.unmet_requirement_ids),
            applied_rule_id=result.applied_rule_id,
            recording_block_ids=(
                tuple(profile.recording_block_ids) if profile is not None else ()
            ),
            stage_ids=tuple(profile.stage_ids) if profile is not None else (),
            scheduled_activity_ids=(
                tuple(profile.scheduled_activity_ids) if profile is not None else ()
            ),
            organizational_anchors=(
                tuple(profile.boundary_anchors) if profile is not None else ()
            ),
        )
