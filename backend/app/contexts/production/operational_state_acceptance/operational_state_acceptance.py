from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import cast

from app.contexts.production.evidence import (
    EvidenceContext,
    EvidenceContextResolution,
    EvidenceContextResolver,
    EvidenceContextSource,
)
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateBasis,
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.contexts.production.transition_policy import TransitionPolicyResult
from app.shared.ids import EntityId

from .operational_state_acceptance_context import OperationalStateAcceptanceContext
from .operational_state_acceptance_mapping import (
    acceptance_rule_for,
    lifecycle_is_supported,
    policy_kind_for_state_kind,
    state_family_for_kind,
    subject_types_for_kind,
)
from .operational_state_acceptance_outcome import OperationalStateAcceptanceOutcome
from .operational_state_acceptance_reason import (
    OperationalStateAcceptanceReason,
    OperationalStateAcceptanceReasonCode,
)
from .operational_state_acceptance_request import OperationalStateAcceptanceRequest
from .operational_state_acceptance_result import OperationalStateAcceptanceResult
from .operational_state_acceptance_rule import OperationalStateAcceptanceRule
from .operational_state_supersession import OperationalStateSupersession

_RECORDING_VALUES = {
    OperationalStateValue.INACTIVE,
    OperationalStateValue.ACTIVE,
    OperationalStateValue.PAUSED,
    OperationalStateValue.STOPPED,
}
_SESSION_VALUES = {
    OperationalStateValue.INACTIVE,
    OperationalStateValue.ACTIVE,
    OperationalStateValue.ENDING,
    OperationalStateValue.ENDED,
}


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptance:
    """Validates one policy evaluation and may create one immutable successor state."""

    def accept(
        self,
        request: OperationalStateAcceptanceRequest,
    ) -> OperationalStateAcceptanceResult:
        evaluation = request.evaluation
        lineage = request.lineage

        if request.history.contains_evaluation(evaluation.id):
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.ALREADY_ACCEPTED,
                OperationalStateAcceptanceReasonCode.EVALUATION_ALREADY_ACCEPTED,
                "Transition Evaluation is already present in supplied acceptance history.",
            )

        if evaluation.outcome is not TransitionPolicyResult.TRANSITION_SUPPORTED:
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INELIGIBLE_EVALUATION,
                OperationalStateAcceptanceReasonCode.EVALUATION_OUTCOME_NOT_SUPPORTED,
                "Only transition_supported evaluations are eligible for acceptance.",
            )
        if evaluation.proposed_state is None:
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INELIGIBLE_EVALUATION,
                OperationalStateAcceptanceReasonCode.MISSING_PROPOSED_STATE,
                "Eligible evaluation must contain an explicit proposed state value.",
            )

        expected_family = state_family_for_kind(evaluation.evaluated_state_kind)
        if expected_family is None:
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_TRANSITION,
                OperationalStateAcceptanceReasonCode.UNSUPPORTED_STATE_KIND,
                "Evaluation state kind is not supported by Operational State Acceptance.",
            )

        lineage_error = self._lineage_error(request)
        if lineage_error is not None:
            code, message = lineage_error
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE,
                code,
                message,
            )

        current_error = self._current_state_error(request, expected_family)
        if current_error is not None:
            code, message = current_error
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_CURRENT_STATE,
                code,
                message,
            )

        subject_error = self._subject_error(request)
        if subject_error is not None:
            code, message = subject_error
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_SUBJECT,
                code,
                message,
            )

        context_error = self._context_error(request)
        if context_error is not None:
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_CONTEXT_MISMATCH,
                OperationalStateAcceptanceReasonCode.CONTEXT_MISMATCH,
                context_error,
            )

        current_value = lineage.effective_current_value
        proposed_value = evaluation.proposed_state
        if not lifecycle_is_supported(
            evaluation.evaluated_state_kind,
            current_value,
            proposed_value,
        ):
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_TRANSITION,
                OperationalStateAcceptanceReasonCode.INVALID_LIFECYCLE_TRANSITION,
                "Proposed lifecycle transition is not acceptance-valid.",
            )

        if lineage.applied_rule_id is None or lineage.policy_kind is None:
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE,
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Acceptance lineage lacks an applied transition rule identity.",
            )
        acceptance_rule = acceptance_rule_for(
            policy_kind=lineage.policy_kind,
            transition_rule_id=lineage.applied_rule_id,
            state_kind=evaluation.evaluated_state_kind,
            effective_current_value=current_value,
            proposed_value=proposed_value,
        )
        if acceptance_rule is None:
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE,
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Applied transition rule does not match the evaluated lifecycle transition.",
            )
        if acceptance_rule.current_state_required and request.current_state is None:
            return self._reject(
                request,
                OperationalStateAcceptanceOutcome.REJECTED_INVALID_CURRENT_STATE,
                OperationalStateAcceptanceReasonCode.EVALUATION_CURRENT_STATE_MISMATCH,
                "Acceptance rule requires a current predecessor state.",
            )

        return self._accepted_result(request, acceptance_rule, expected_family)

    def _lineage_error(
        self,
        request: OperationalStateAcceptanceRequest,
    ) -> tuple[OperationalStateAcceptanceReasonCode, str] | None:
        evaluation = request.evaluation
        lineage = request.lineage
        if lineage.evaluation_id != evaluation.id:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_POLICY_IDENTITY,
                "Lineage Evaluation ID does not match the supplied evaluation.",
            )
        if lineage.evaluated_state_kind is not evaluation.evaluated_state_kind:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_POLICY_IDENTITY,
                "Lineage state kind does not match the supplied evaluation.",
            )
        if lineage.proposed_state_value is not evaluation.proposed_state:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Lineage proposed value does not match the supplied evaluation.",
            )

        expected_policy = policy_kind_for_state_kind(evaluation.evaluated_state_kind)
        if (
            lineage.policy_id is None
            or lineage.policy_kind is None
            or lineage.policy_kind != expected_policy
        ):
            return (
                OperationalStateAcceptanceReasonCode.INVALID_POLICY_IDENTITY,
                "Approved policy identity is missing or incompatible with state kind.",
            )
        if lineage.applied_rule_id is None:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Applied transition rule identity is required.",
            )

        metadata_policy = self._entity(evaluation.metadata.get("policy_id"))
        if metadata_policy is not None and metadata_policy != lineage.policy_id:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_POLICY_IDENTITY,
                "Evaluation metadata policy ID conflicts with first-class lineage.",
            )
        metadata_policy_kind = evaluation.metadata.get("policy_kind")
        if isinstance(metadata_policy_kind, str) and metadata_policy_kind != lineage.policy_kind:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_POLICY_IDENTITY,
                "Evaluation metadata policy kind conflicts with first-class lineage.",
            )
        metadata_rule = self._entity(evaluation.metadata.get("applied_rule_id"))
        if metadata_rule is not None and metadata_rule != lineage.applied_rule_id:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Evaluation metadata rule ID conflicts with first-class lineage.",
            )

        if not lineage.supporting_evidence_set_ids:
            return (
                OperationalStateAcceptanceReasonCode.MISSING_SUPPORTING_EVIDENCE,
                "Acceptance lineage requires supporting EvidenceSet IDs.",
            )
        if self._id_set(lineage.supporting_evidence_set_ids) != self._id_set(
            evaluation.supporting_evidence_ids
        ):
            return (
                OperationalStateAcceptanceReasonCode.MISSING_SUPPORTING_EVIDENCE,
                "Supporting EvidenceSet lineage conflicts with the evaluation.",
            )
        if evaluation.blocking_evidence_ids or lineage.blocking_evidence_set_ids:
            return (
                OperationalStateAcceptanceReasonCode.MISSING_SUPPORTING_EVIDENCE,
                "Supported evaluation must not carry blocking Evidence lineage.",
            )
        if not lineage.contributing_evidence_item_ids:
            return (
                OperationalStateAcceptanceReasonCode.MISSING_SUPPORTING_EVIDENCE,
                "Acceptance lineage requires contributing EvidenceItem IDs.",
            )
        if not lineage.contributing_observation_ids:
            return (
                OperationalStateAcceptanceReasonCode.MISSING_OBSERVATION_LINEAGE,
                "Acceptance lineage requires contributing Observation IDs.",
            )
        if not lineage.contributing_production_event_ids:
            return (
                OperationalStateAcceptanceReasonCode.MISSING_EVENT_LINEAGE,
                "Acceptance lineage requires exact source Production Event IDs.",
            )
        if lineage.unmet_requirement_ids:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Supported evaluation must not carry unmet mandatory requirements.",
            )

        metadata_observations = self._entity_sequence(
            evaluation.metadata.get("contributing_observation_ids")
        )
        if metadata_observations and self._id_set(metadata_observations) != self._id_set(
            lineage.contributing_observation_ids
        ):
            return (
                OperationalStateAcceptanceReasonCode.MISSING_OBSERVATION_LINEAGE,
                "Evaluation metadata Observation lineage conflicts with first-class lineage.",
            )
        metadata_events = self._entity_sequence(
            evaluation.metadata.get(
                "source_production_event_ids",
                evaluation.metadata.get("source_event_ids"),
            )
        )
        if metadata_events and self._id_set(metadata_events) != self._id_set(
            lineage.contributing_production_event_ids
        ):
            return (
                OperationalStateAcceptanceReasonCode.MISSING_EVENT_LINEAGE,
                "Evaluation metadata Event lineage conflicts with first-class lineage.",
            )
        metadata_current = evaluation.metadata.get("effective_current_state_value")
        if (
            isinstance(metadata_current, str)
            and metadata_current != lineage.effective_current_value.value
        ):
            return (
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Evaluation metadata current value conflicts with first-class lineage.",
            )
        metadata_proposed = evaluation.metadata.get("proposed_state_value")
        if (
            isinstance(metadata_proposed, str)
            and metadata_proposed != lineage.proposed_state_value.value
        ):
            return (
                OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY,
                "Evaluation metadata proposed value conflicts with first-class lineage.",
            )
        return None

    def _current_state_error(
        self,
        request: OperationalStateAcceptanceRequest,
        expected_family: OperationalStateFamily,
    ) -> tuple[OperationalStateAcceptanceReasonCode, str] | None:
        evaluation = request.evaluation
        lineage = request.lineage
        current = request.current_state
        evaluated_current = evaluation.current_state
        if current is None:
            if evaluated_current is not None or lineage.current_state_id is not None:
                return (
                    OperationalStateAcceptanceReasonCode.EVALUATION_CURRENT_STATE_MISMATCH,
                    "Evaluation references a current state but request does not supply it.",
                )
            if lineage.effective_current_value is not OperationalStateValue.INACTIVE:
                return (
                    OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_VALUE,
                    "Absent current state is allowed only with effective inactive lineage.",
                )
            if evaluation.metadata.get("missing_current_state_assumed_inactive") is not True:
                return (
                    OperationalStateAcceptanceReasonCode.EVALUATION_CURRENT_STATE_MISMATCH,
                    "Evaluation must explicitly record the absent-state inactive assumption.",
                )
            return None

        if evaluated_current is None or evaluated_current.id != current.id:
            return (
                OperationalStateAcceptanceReasonCode.EVALUATION_CURRENT_STATE_MISMATCH,
                "Request predecessor does not match the state evaluated by policy.",
            )
        if lineage.current_state_id != current.id:
            return (
                OperationalStateAcceptanceReasonCode.EVALUATION_CURRENT_STATE_MISMATCH,
                "Lineage current-state identity does not match request predecessor.",
            )
        if current.kind is not evaluation.evaluated_state_kind:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_KIND,
                "Current state kind does not match evaluation state kind.",
            )
        if current.family is not expected_family:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_KIND,
                "Current state family is incompatible with its accepted state kind.",
            )
        if current.status is not OperationalStateStatus.CURRENT:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_STATUS,
                "Only current Operational State may serve as predecessor.",
            )
        if current.value not in self._values_for_kind(current.kind):
            return (
                OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_VALUE,
                "Current state value is outside the supported lifecycle.",
            )
        if current.value is not lineage.effective_current_value:
            return (
                OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_VALUE,
                "Current state value conflicts with evaluation lineage.",
            )
        if (
            evaluated_current.kind is not current.kind
            or evaluated_current.value is not current.value
            or evaluated_current.subject != current.subject
        ):
            return (
                OperationalStateAcceptanceReasonCode.EVALUATION_CURRENT_STATE_MISMATCH,
                "Embedded evaluated state does not match request predecessor contract.",
            )
        metadata_current_id = self._entity(evaluation.metadata.get("current_state_id"))
        if metadata_current_id is not None and metadata_current_id != current.id:
            return (
                OperationalStateAcceptanceReasonCode.EVALUATION_CURRENT_STATE_MISMATCH,
                "Evaluation metadata current-state ID conflicts with predecessor.",
            )
        return None

    def _subject_error(
        self,
        request: OperationalStateAcceptanceRequest,
    ) -> tuple[OperationalStateAcceptanceReasonCode, str] | None:
        kind = request.evaluation.evaluated_state_kind
        subject = request.target_subject
        if subject.subject_type not in subject_types_for_kind(kind):
            return (
                OperationalStateAcceptanceReasonCode.INVALID_TARGET_SUBJECT,
                "Target subject type is unsupported for the accepted state kind.",
            )
        if subject.subject_type is OperationalStateSubjectType.RECORDING_BLOCK:
            if self._entity(subject.subject_identifier) is None:
                return (
                    OperationalStateAcceptanceReasonCode.INVALID_TARGET_SUBJECT,
                    "Recording-block subject requires a valid EntityId identifier.",
                )
        if (
            subject.subject_type is OperationalStateSubjectType.STAGEFLOW
            and subject.subject_identifier != "stageflow"
        ):
            return (
                OperationalStateAcceptanceReasonCode.INVALID_TARGET_SUBJECT,
                "StageFlow subject must use the stable stageflow identifier.",
            )
        current = request.current_state
        if current is not None and current.subject != subject:
            return (
                OperationalStateAcceptanceReasonCode.SUBJECT_MISMATCH,
                "ED-0044 does not permit Operational State subject migration.",
            )
        return None

    def _context_error(self, request: OperationalStateAcceptanceRequest) -> str | None:
        contexts = tuple(
            context
            for context in (
                OperationalStateAcceptanceContext.from_evidence_context(request.evaluation.context),
                OperationalStateAcceptanceContext.from_evidence_context(
                    request.lineage.evaluation_context
                ),
                request.lineage.context,
                request.context,
                (
                    OperationalStateAcceptanceContext.from_evidence_context(
                        request.current_state.basis.evidence_context
                    )
                    if request.current_state is not None
                    and request.current_state.basis.evidence_context is not None
                    else OperationalStateAcceptanceContext.unknown()
                ),
            )
            if context != OperationalStateAcceptanceContext.unknown()
        )
        scalar_names = (
            "stage_id",
            "recording_block_id",
            "scheduled_activity_id",
            "boundary_evidence_context_id",
            "organizational_anchor",
        )
        for name in scalar_names:
            known = {
                value
                for context in contexts
                for value in (getattr(context, name),)
                if value is not None
            }
            if len(known) > 1:
                return f"Known {name} values conflict between lineage and request context."
        for name in ("transcript_stream_ids", "media_artifact_ids"):
            known_collections = tuple(
                set(getattr(context, name)) for context in contexts if getattr(context, name)
            )
            if any(left.isdisjoint(right) for left, right in combinations(known_collections, 2)):
                return f"Known {name} values conflict between lineage and request context."

        current = request.current_state
        for context in contexts:
            if current is not None:
                if (
                    current.recording_block_id is not None
                    and context.recording_block_id is not None
                    and current.recording_block_id != context.recording_block_id
                ):
                    return "Current state and acceptance context use different recording blocks."
                if (
                    current.stage_id is not None
                    and context.stage_id is not None
                    and current.stage_id != context.stage_id
                ):
                    return "Current state and acceptance context use different stages."
            subject_error = self._subject_context_error(request.target_subject, context)
            if subject_error is not None:
                return subject_error
        return None

    def _subject_context_error(
        self,
        subject: OperationalStateSubject,
        context: OperationalStateAcceptanceContext,
    ) -> str | None:
        if subject.subject_type is OperationalStateSubjectType.RECORDING_BLOCK:
            subject_id = self._entity(subject.subject_identifier)
            if (
                subject_id is not None
                and context.recording_block_id is not None
                and subject_id != context.recording_block_id
            ):
                return "Recording-block subject conflicts with acceptance context."
        if (
            subject.subject_type is OperationalStateSubjectType.MEDIA_ARTIFACT
            and context.media_artifact_ids
            and subject.subject_identifier not in context.media_artifact_ids
        ):
            return "Media-artifact subject conflicts with acceptance context."
        return None

    def _accepted_result(
        self,
        request: OperationalStateAcceptanceRequest,
        acceptance_rule: OperationalStateAcceptanceRule,
        family: OperationalStateFamily,
    ) -> OperationalStateAcceptanceResult:
        evaluation = request.evaluation
        lineage = request.lineage
        accepted_context = self._accepted_evidence_context(request)
        acceptance_id = EntityId.new()
        successor_id = EntityId.new()
        recording_block_id = accepted_context.recording_block_id or self._recording_block_id(
            request
        )
        stage_id = accepted_context.stage_id or request.context.stage_id or lineage.context.stage_id
        successor = OperationalState(
            id=successor_id,
            family=family,
            kind=evaluation.evaluated_state_kind,
            subject=request.target_subject,
            value=lineage.proposed_state_value,
            status=OperationalStateStatus.CURRENT,
            basis=OperationalStateBasis(
                observation_ids=lineage.contributing_observation_ids,
                evidence_set_ids=lineage.supporting_evidence_set_ids,
                transition_evaluation_ids=(evaluation.id,),
                policy_ids=(lineage.policy_id,) if lineage.policy_id is not None else (),
                transition_rule_ids=(
                    (lineage.applied_rule_id,) if lineage.applied_rule_id is not None else ()
                ),
                evidence_context=accepted_context,
                rationale=acceptance_rule.rationale,
                metadata={
                    "acceptance_id": acceptance_id.to_json(),
                    "contributing_evidence_item_ids": tuple(
                        item.to_json() for item in lineage.contributing_evidence_item_ids
                    ),
                    "contributing_production_event_ids": tuple(
                        item.to_json() for item in lineage.contributing_production_event_ids
                    ),
                    "contributing_signals": tuple(
                        signal.value for signal in lineage.contributing_signals
                    ),
                },
            ),
            observed_or_derived_at=evaluation.evaluated_at,
            recording_block_id=recording_block_id,
            stage_id=stage_id,
            timeline_range=accepted_context.timeline_range,
            metadata={
                "operational_state_acceptance_id": acceptance_id.to_json(),
                "accepted_transition_evaluation_id": evaluation.id.to_json(),
                "policy_kind": lineage.policy_kind,
                "policy_id": lineage.policy_id.to_json() if lineage.policy_id else None,
                "transition_rule_id": (
                    lineage.applied_rule_id.to_json()
                    if lineage.applied_rule_id is not None
                    else None
                ),
                "source_production_event_ids": tuple(
                    item.to_json() for item in lineage.contributing_production_event_ids
                ),
                "organizational_anchors": tuple(lineage.organizational_anchors),
                "scheduled_activity_id": (
                    accepted_context.scheduled_activity_id.to_json()
                    if accepted_context.scheduled_activity_id is not None
                    else None
                ),
                "transcript_stream_ids": accepted_context.transcript_stream_ids,
                "media_artifact_ids": accepted_context.media_artifact_ids,
                "boundary_context_id": (
                    accepted_context.boundary_context_id.to_json()
                    if accepted_context.boundary_context_id is not None
                    else None
                ),
                "boundary_anchor_verified": False,
                "accepted_at": request.accepted_at.isoformat(),
                "persisted": False,
            },
        )
        current = request.current_state
        supersession = (
            OperationalStateSupersession(
                predecessor_state_id=current.id,
                successor_state_id=successor.id,
                transition_evaluation_id=evaluation.id,
                accepted_at=request.accepted_at,
                predecessor_status_before_acceptance=current.status,
                successor_status=successor.status,
                reason="Accepted successor is intended to supersede the prior current state.",
                metadata={"persisted": False, "predecessor_mutated": False},
            )
            if current is not None
            else None
        )
        reason = OperationalStateAcceptanceReason(
            code=OperationalStateAcceptanceReasonCode.SUCCESSOR_CREATED,
            message="Evaluation passed acceptance invariants and successor state was created.",
            evaluation_id=evaluation.id,
            current_state_id=current.id if current is not None else None,
            subject_identifier=request.target_subject.subject_identifier,
            related_lineage_ids=(
                *lineage.supporting_evidence_set_ids,
                *lineage.contributing_observation_ids,
                *lineage.contributing_production_event_ids,
            ),
        )
        return OperationalStateAcceptanceResult(
            id=acceptance_id,
            outcome=OperationalStateAcceptanceOutcome.ACCEPTED,
            accepted_evaluation_id=evaluation.id,
            reasons=(reason,),
            current_state_id=current.id if current is not None else None,
            target_subject=request.target_subject,
            successor_state=successor,
            supersession=supersession,
            lineage=lineage,
            applied_acceptance_rule_id=acceptance_rule.id,
            accepted_at=request.accepted_at,
            metadata={
                "state_persisted": False,
                "transition_executed": False,
                "supersession_persisted": False,
            },
        )

    def _reject(
        self,
        request: OperationalStateAcceptanceRequest,
        outcome: OperationalStateAcceptanceOutcome,
        code: OperationalStateAcceptanceReasonCode,
        message: str,
    ) -> OperationalStateAcceptanceResult:
        current = request.current_state
        reason = OperationalStateAcceptanceReason(
            code=code,
            message=message,
            evaluation_id=request.evaluation.id,
            current_state_id=current.id if current is not None else None,
            subject_identifier=request.target_subject.subject_identifier,
        )
        return OperationalStateAcceptanceResult(
            id=EntityId.new(),
            outcome=outcome,
            accepted_evaluation_id=request.evaluation.id,
            reasons=(reason,),
            current_state_id=current.id if current is not None else None,
            target_subject=request.target_subject,
            successor_state=None,
            supersession=None,
            lineage=request.lineage,
            applied_acceptance_rule_id=None,
            accepted_at=request.accepted_at,
            metadata={
                "state_persisted": False,
                "transition_executed": False,
                "known_history_only": True,
            },
        )

    def _recording_block_id(
        self,
        request: OperationalStateAcceptanceRequest,
    ) -> EntityId | None:
        direct = request.context.recording_block_id or request.lineage.context.recording_block_id
        if direct is not None:
            return direct
        if request.current_state is not None:
            if request.current_state.recording_block_id is not None:
                return request.current_state.recording_block_id
        if request.target_subject.subject_type is OperationalStateSubjectType.RECORDING_BLOCK:
            return self._entity(request.target_subject.subject_identifier)
        return None

    def _accepted_evidence_context(
        self,
        request: OperationalStateAcceptanceRequest,
    ) -> EvidenceContext:
        supplemental_contexts = [
            request.lineage.context.to_evidence_context(),
            request.context.to_evidence_context(),
        ]
        if request.lineage.evaluation_context != EvidenceContext.unknown():
            supplemental_contexts.append(request.lineage.evaluation_context)
        if (
            request.current_state is not None
            and request.current_state.basis.evidence_context is not None
        ):
            supplemental_contexts.append(request.current_state.basis.evidence_context)
        supplemental = EvidenceContextResolver().compose(
            tuple(
                EvidenceContextResolution(context=context)
                for context in supplemental_contexts
                if context != EvidenceContext.unknown()
            )
        )
        if request.evaluation.context == EvidenceContext.unknown():
            return supplemental.context
        return (
            EvidenceContextResolver()
            .resolve(
                first_class=request.evaluation.context,
                first_class_source=EvidenceContextSource.EVIDENCE_FIRST_CLASS,
                structured_legacy=supplemental.context,
            )
            .context
        )

    def _values_for_kind(
        self,
        kind: OperationalStateKind,
    ) -> set[OperationalStateValue]:
        if kind is OperationalStateKind.RECORDING_STATE:
            return _RECORDING_VALUES
        if kind is OperationalStateKind.SESSION_STATE:
            return _SESSION_VALUES
        return set()

    def _entity(self, value: object) -> EntityId | None:
        if isinstance(value, EntityId):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return EntityId.parse(value)
            except ValueError:
                return None
        return None

    def _entity_sequence(self, value: object) -> tuple[EntityId, ...]:
        if not isinstance(value, Sequence) or isinstance(value, str | bytes):
            return ()
        return tuple(
            dict.fromkeys(
                parsed
                for item in cast(Sequence[object], value)
                if (parsed := self._entity(item)) is not None
            )
        )

    def _id_set(self, values: Sequence[EntityId]) -> frozenset[EntityId]:
        return frozenset(values)
