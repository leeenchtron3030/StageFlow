from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
    EvidenceStrength,
)
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.contexts.production.session_boundary_evidence_builder import (
    SessionBoundaryEvidenceContext,
)
from app.contexts.production.transition_policy import (
    TransitionEvaluation,
    TransitionPolicyResult,
    TransitionReason,
)
from app.shared.ids import EntityId

from .session_transition_evidence_profile import SessionTransitionEvidenceProfile
from .session_transition_mapping import (
    SESSION_TRANSITION_RULES,
    SUPPORTED_SESSION_TRANSITIONS,
    SessionTransitionEvidenceCategory,
    mapping_for_session_signal,
)
from .session_transition_requirement import SessionTransitionRequirement
from .session_transition_result import SessionTransitionResult
from .session_transition_rule import SessionTransitionRule

_SUPPORTED_SESSION_VALUES = {
    OperationalStateValue.INACTIVE,
    OperationalStateValue.ACTIVE,
    OperationalStateValue.ENDING,
    OperationalStateValue.ENDED,
}
_SUPPORTED_SUBJECT_TYPES = {
    OperationalStateSubjectType.SESSION_CANDIDATE,
    OperationalStateSubjectType.SESSION_PRODUCT,
}
_BOUNDARY_CONCERNS = {
    EvidenceConcern.POSSIBLE_SESSION_START,
    EvidenceConcern.POSSIBLE_SESSION_END,
}


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _stable_entity_id(name: str) -> EntityId:
    return EntityId.parse(str(uuid5(NAMESPACE_URL, f"stageflow:session-transition:{name}")))


@dataclass(frozen=True, slots=True)
class _MergedSignal:
    signal: EvidenceSignal
    evidence_item_ids: tuple[EntityId, ...]
    observation_ids: tuple[EntityId, ...]


@dataclass(frozen=True, slots=True)
class _Contribution:
    evidence_set: EvidenceSet
    evidence_item: EvidenceItem
    signal: EvidenceSignal
    category: SessionTransitionEvidenceCategory
    role: EvidenceRole
    strength: EvidenceStrength
    source_keys: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str, str]:
        return (
            self.evidence_set.id.to_json(),
            self.evidence_item.id.to_json(),
            self.signal.value,
        )


@dataclass(frozen=True, slots=True)
class _EvidenceGroup:
    concern: EvidenceConcern
    contributions: tuple[_Contribution, ...]
    evidence_sets: tuple[EvidenceSet, ...]
    context_key: tuple[str, ...]
    unsupported_count: int


@dataclass(frozen=True, slots=True)
class _RuleAssessment:
    rule: SessionTransitionRule
    satisfied: bool
    satisfied_requirement_ids: tuple[EntityId, ...]
    unmet_requirement_ids: tuple[EntityId, ...]
    used_contributions: tuple[_Contribution, ...]


@dataclass(frozen=True, slots=True)
class SessionTransitionPolicy:
    """Deterministic policy proposing Session state values from boundary Evidence."""

    id: EntityId
    name: str = "Session Transition Policy"
    rules: Sequence[SessionTransitionRule] = field(
        default_factory=lambda: SESSION_TRANSITION_RULES
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("SessionTransitionPolicy name must not be empty.")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def evaluated_state_kind(self) -> OperationalStateKind:
        return OperationalStateKind.SESSION_STATE

    def evaluate(
        self,
        *,
        current_state: OperationalState | None,
        evidence_sets: Sequence[EvidenceSet],
        evaluation_context: SessionBoundaryEvidenceContext | None = None,
        metadata: Mapping[str, Any] | None = None,
        evaluated_at: datetime | None = None,
    ) -> SessionTransitionResult:
        timestamp = evaluated_at or datetime.now(UTC)
        caller_metadata = dict(metadata or {})
        current_error = self._current_state_error(current_state)
        effective_current = (
            current_state.value
            if current_state is not None and current_error is None
            else OperationalStateValue.INACTIVE
        )
        prepared = self._prepare_evidence(tuple(evidence_sets), evaluation_context)
        groups, ignored_ids, unsupported_ids, duplicate_ids, context_excluded_ids = prepared

        if current_error is not None:
            return self._result(
                current_state=current_state,
                effective_current=None,
                proposed_state=None,
                outcome=TransitionPolicyResult.UNKNOWN,
                rationale=current_error,
                group=None,
                assessment=None,
                supporting=(),
                blocking=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                context_excluded_ids=context_excluded_ids,
                evaluated_at=timestamp,
                caller_metadata=caller_metadata,
            )

        applicable_rules = tuple(
            rule for rule in self.rules if rule.current_state_value is effective_current
        )
        qualifying: list[tuple[_EvidenceGroup, _RuleAssessment]] = []
        for group in groups:
            for rule in applicable_rules:
                if rule.required_boundary_concern is not group.concern:
                    continue
                assessment = self._assess_rule(rule, group, current_state)
                if assessment.satisfied:
                    qualifying.append((group, assessment))
                    break

        if len(qualifying) > 1:
            return self._result(
                current_state=current_state,
                effective_current=effective_current,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                rationale=(
                    "Multiple incompatible boundary contexts independently satisfy Session "
                    "transition rules; no candidate was selected."
                ),
                group=None,
                assessment=None,
                supporting=(),
                blocking=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                context_excluded_ids=context_excluded_ids,
                evaluated_at=timestamp,
                caller_metadata={
                    **caller_metadata,
                    "ambiguous_context_keys": tuple(
                        group.context_key for group, _assessment in qualifying
                    ),
                    "qualifying_rule_ids": tuple(
                        assessment.rule.id.to_json()
                        for _group, assessment in qualifying
                    ),
                },
            )

        if len(qualifying) == 1:
            group, assessment = qualifying[0]
            contradictions = tuple(
                contribution
                for contribution in group.contributions
                if contribution.role is EvidenceRole.CONTRADICTS
            )
            if contradictions:
                return self._result(
                    current_state=current_state,
                    effective_current=effective_current,
                    proposed_state=assessment.rule.proposed_state_value,
                    outcome=TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                    rationale=(
                        "Explicit contradictory Evidence in the same boundary context "
                        "blocks the otherwise satisfied Session transition rule."
                    ),
                    group=group,
                    assessment=assessment,
                    supporting=assessment.used_contributions,
                    blocking=contradictions,
                    ignored_ids=ignored_ids,
                    unsupported_ids=unsupported_ids,
                    duplicate_ids=duplicate_ids,
                    context_excluded_ids=context_excluded_ids,
                    evaluated_at=timestamp,
                    caller_metadata=caller_metadata,
                )

            proposed = assessment.rule.proposed_state_value
            outcome = (
                TransitionPolicyResult.ALREADY_CURRENT
                if proposed is effective_current
                else TransitionPolicyResult.TRANSITION_SUPPORTED
            )
            rationale = (
                "The supported Session value already matches the effective current state."
                if outcome is TransitionPolicyResult.ALREADY_CURRENT
                else assessment.rule.rationale()
            )
            return self._result(
                current_state=current_state,
                effective_current=effective_current,
                proposed_state=proposed,
                outcome=outcome,
                rationale=rationale,
                group=group,
                assessment=assessment,
                supporting=assessment.used_contributions,
                blocking=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                context_excluded_ids=context_excluded_ids,
                evaluated_at=timestamp,
                caller_metadata=caller_metadata,
            )

        blocking_candidate = self._blocking_candidate(
            applicable_rules,
            groups,
            current_state,
        )
        if blocking_candidate is not None:
            group, assessment, contradictions = blocking_candidate
            return self._result(
                current_state=current_state,
                effective_current=effective_current,
                proposed_state=assessment.rule.proposed_state_value,
                outcome=TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                rationale=(
                    "Explicit contradictory Evidence directly addresses the boundary concern "
                    "for the applicable Session transition."
                ),
                group=group,
                assessment=assessment,
                supporting=assessment.used_contributions,
                blocking=contradictions,
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                context_excluded_ids=context_excluded_ids,
                evaluated_at=timestamp,
                caller_metadata=caller_metadata,
            )

        unsupported_transition = self._unsupported_transition_candidate(
            effective_current,
            groups,
            current_state,
        )
        if unsupported_transition is not None:
            group, assessment = unsupported_transition
            return self._result(
                current_state=current_state,
                effective_current=effective_current,
                proposed_state=None,
                outcome=TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                rationale=(
                    f"Boundary Evidence would imply unsupported Session transition "
                    f"{effective_current.value} to "
                    f"{assessment.rule.proposed_state_value.value}."
                ),
                group=group,
                assessment=None,
                supporting=(),
                blocking=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                context_excluded_ids=context_excluded_ids,
                evaluated_at=timestamp,
                caller_metadata={
                    **caller_metadata,
                    "rejected_rule_id": assessment.rule.id.to_json(),
                    "rejected_proposed_state": (
                        assessment.rule.proposed_state_value.value
                    ),
                },
            )

        best_group, best_assessment = self._most_relevant_unmet(
            applicable_rules,
            groups,
            current_state,
        )
        return self._result(
            current_state=current_state,
            effective_current=effective_current,
            proposed_state=None,
            outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
            rationale=(
                "Session Boundary Evidence is absent, contextual only, non-independent, "
                "or missing required categorical corroboration."
            ),
            group=best_group,
            assessment=best_assessment,
            supporting=(),
            blocking=(),
            ignored_ids=ignored_ids,
            unsupported_ids=unsupported_ids,
            duplicate_ids=duplicate_ids,
            context_excluded_ids=context_excluded_ids,
            evaluated_at=timestamp,
            caller_metadata=caller_metadata,
        )

    def evaluate_transition(
        self,
        *,
        current_state: OperationalState | None,
        evidence_sets: Sequence[EvidenceSet],
        evaluation_context: SessionBoundaryEvidenceContext | None = None,
        metadata: Mapping[str, Any] | None = None,
        evaluated_at: datetime | None = None,
    ) -> TransitionEvaluation:
        """Compatibility helper returning only the generic evaluation contract."""
        return self.evaluate(
            current_state=current_state,
            evidence_sets=evidence_sets,
            evaluation_context=evaluation_context,
            metadata=metadata,
            evaluated_at=evaluated_at,
        ).evaluation

    def _current_state_error(self, current_state: OperationalState | None) -> str | None:
        if current_state is None:
            return None
        if current_state.kind is not OperationalStateKind.SESSION_STATE:
            return "Current Operational State is not a Session state."
        if current_state.subject.subject_type not in _SUPPORTED_SUBJECT_TYPES:
            return "Current Session state uses an unsupported Session subject type."
        if current_state.value not in _SUPPORTED_SESSION_VALUES:
            return "Current Session state value is outside the supported lifecycle."
        if current_state.status is OperationalStateStatus.UNKNOWN:
            return "Current Session state status is unknown."
        return None

    def _prepare_evidence(
        self,
        inputs: tuple[EvidenceSet, ...],
        evaluation_context: SessionBoundaryEvidenceContext | None,
    ) -> tuple[
        tuple[_EvidenceGroup, ...],
        tuple[EntityId, ...],
        tuple[EntityId, ...],
        tuple[EntityId, ...],
        tuple[EntityId, ...],
    ]:
        ordered = tuple(
            sorted(
                enumerate(inputs),
                key=lambda pair: (
                    pair[1].created_at,
                    self._anchor_order(pair[1]),
                    pair[1].id.to_json(),
                    pair[0],
                ),
            )
        )
        retained: list[EvidenceSet] = []
        duplicates: list[EntityId] = []
        seen: set[EntityId] = set()
        for _index, evidence_set in ordered:
            if evidence_set.id in seen:
                duplicates.append(evidence_set.id)
                continue
            seen.add(evidence_set.id)
            retained.append(evidence_set)

        ignored: list[EntityId] = []
        unsupported: list[EntityId] = []
        context_excluded: list[EntityId] = []
        grouped: dict[
            tuple[str, ...],
            list[tuple[EvidenceSet, tuple[_Contribution, ...], int]],
        ] = {}
        for evidence_set in retained:
            if evidence_set.concern not in _BOUNDARY_CONCERNS:
                ignored.append(evidence_set.id)
                continue
            if evaluation_context is not None and not self._matches_context(
                evidence_set,
                evaluation_context,
            ):
                context_excluded.append(evidence_set.id)
                continue
            contributions, unsupported_count = self._contributions(evidence_set)
            if not contributions or all(
                contribution.category is SessionTransitionEvidenceCategory.UNSUPPORTED
                for contribution in contributions
            ):
                unsupported.append(evidence_set.id)
                continue
            key = self._context_key(evidence_set)
            grouped.setdefault(key, []).append(
                (evidence_set, contributions, unsupported_count)
            )

        groups: list[_EvidenceGroup] = []
        for key in sorted(grouped):
            entries = grouped[key]
            evidence_sets = tuple(entry[0] for entry in entries)
            contributions = tuple(
                contribution
                for _evidence_set, entry_contributions, _count in entries
                for contribution in entry_contributions
            )
            groups.append(
                _EvidenceGroup(
                    concern=evidence_sets[0].concern,
                    contributions=contributions,
                    evidence_sets=evidence_sets,
                    context_key=key,
                    unsupported_count=sum(entry[2] for entry in entries),
                )
            )
        return (
            tuple(groups),
            tuple(ignored),
            tuple(unsupported),
            tuple(duplicates),
            tuple(context_excluded),
        )

    def _contributions(
        self,
        evidence_set: EvidenceSet,
    ) -> tuple[tuple[_Contribution, ...], int]:
        contributions: list[_Contribution] = []
        unsupported_count = 0
        for source_signal in self._merged_signals(evidence_set.signals):
            items = self._linked_items(evidence_set, source_signal)
            if not items:
                unsupported_count += 1
                continue
            mapping = mapping_for_session_signal(evidence_set.concern, source_signal.signal)
            for item in items:
                if item.role is EvidenceRole.CONTRADICTS:
                    category = SessionTransitionEvidenceCategory.CONTRADICTORY
                elif mapping is None:
                    category = SessionTransitionEvidenceCategory.UNSUPPORTED
                else:
                    category = mapping.category
                contributions.append(
                    _Contribution(
                        evidence_set=evidence_set,
                        evidence_item=item,
                        signal=source_signal.signal,
                        category=category,
                        role=item.role,
                        strength=item.strength,
                        source_keys=self._source_keys(source_signal, item),
                    )
                )
        return tuple(contributions), unsupported_count

    def _merged_signals(
        self,
        references: Sequence[EvidenceSignalReference],
    ) -> tuple[_MergedSignal, ...]:
        grouped: dict[EvidenceSignal, list[EvidenceSignalReference]] = {}
        order: list[EvidenceSignal] = []
        for reference in references:
            if reference.signal not in grouped:
                grouped[reference.signal] = []
                order.append(reference.signal)
            grouped[reference.signal].append(reference)
        return tuple(
            _MergedSignal(
                signal=signal,
                evidence_item_ids=tuple(
                    dict.fromkeys(
                        item_id
                        for reference in grouped[signal]
                        for item_id in reference.evidence_item_ids
                    )
                ),
                observation_ids=tuple(
                    dict.fromkeys(
                        observation_id
                        for reference in grouped[signal]
                        for observation_id in reference.observation_ids
                    )
                ),
            )
            for signal in order
        )

    def _linked_items(
        self,
        evidence_set: EvidenceSet,
        source_signal: _MergedSignal,
    ) -> tuple[EvidenceItem, ...]:
        if source_signal.evidence_item_ids:
            ids = set(source_signal.evidence_item_ids)
            return tuple(item for item in evidence_set.items if item.id in ids)
        if source_signal.observation_ids:
            ids = set(source_signal.observation_ids)
            return tuple(item for item in evidence_set.items if item.observation_id in ids)
        if len(evidence_set.items) == 1:
            return tuple(evidence_set.items)
        return ()

    def _source_keys(
        self,
        source_signal: _MergedSignal,
        item: EvidenceItem,
    ) -> tuple[str, ...]:
        observation_ids = tuple(
            dict.fromkeys(source_signal.observation_ids + (item.observation_id,))
        )
        if observation_ids:
            return tuple(f"observation:{item_id.to_json()}" for item_id in observation_ids)
        return (f"evidence-item:{item.id.to_json()}",)

    def _context_key(self, evidence_set: EvidenceSet) -> tuple[str, ...]:
        block = self._optional_id(evidence_set.recording_block_id)
        stage = self._metadata_id(evidence_set.metadata, "stage_id")
        activity = self._metadata_id(evidence_set.metadata, "scheduled_activity_id")
        boundary_context = self._metadata_text(
            evidence_set.metadata,
            "boundary_context_id",
        )
        discriminator = evidence_set.id.to_json() if boundary_context is None else ""
        return (
            evidence_set.concern.value,
            evidence_set.correlation_id.to_json(),
            block,
            stage,
            activity,
            boundary_context or "",
            discriminator,
        )

    def _matches_context(
        self,
        evidence_set: EvidenceSet,
        context: SessionBoundaryEvidenceContext,
    ) -> bool:
        if evidence_set.concern is not context.boundary_concern:
            return False
        actual_boundary_context = self._metadata_text(
            evidence_set.metadata,
            "boundary_context_id",
        )
        if actual_boundary_context is not None and actual_boundary_context != context.id.to_json():
            return False
        checks = (
            (
                self._optional_id(evidence_set.recording_block_id),
                self._optional_id(context.recording_block_id),
            ),
            (
                self._metadata_id(evidence_set.metadata, "stage_id"),
                self._optional_id(context.stage_id),
            ),
            (
                self._metadata_id(evidence_set.metadata, "scheduled_activity_id"),
                self._optional_id(context.scheduled_activity_id),
            ),
        )
        return all(not expected or actual == expected for actual, expected in checks)

    def _assess_rule(
        self,
        rule: SessionTransitionRule,
        group: _EvidenceGroup,
        current_state: OperationalState | None,
    ) -> _RuleAssessment:
        satisfied: list[EntityId] = []
        unmet: list[EntityId] = []
        candidate_sets: list[tuple[_Contribution, ...]] = []
        for requirement in rule.requirements:
            candidates = self._requirement_candidates(requirement, group)
            count = (
                min(
                    len({contribution.key for contribution in candidates}),
                    len(
                        {
                            source_key
                            for contribution in candidates
                            for source_key in contribution.source_keys
                        }
                    ),
                )
                if requirement.require_independent_sources
                else len({contribution.key for contribution in candidates})
            )
            fresh = (
                self._is_fresh_context(group, current_state)
                if requirement.requires_fresh_context
                else True
            )
            if count >= requirement.minimum_categorical_count and fresh:
                satisfied.append(requirement.id)
            else:
                unmet.append(requirement.id)
            candidate_sets.append(candidates)

        if (
            not unmet
            and rule.requirements_require_distinct_sources
            and not self._requirements_have_distinct_sources(tuple(candidate_sets))
        ):
            last_requirement_id = rule.requirements[-1].id
            satisfied = [item for item in satisfied if item != last_requirement_id]
            unmet.append(last_requirement_id)

        used = self._unique_contributions(
            tuple(
                contribution
                for candidates in candidate_sets
                for contribution in candidates
            )
        )
        return _RuleAssessment(
            rule=rule,
            satisfied=not unmet,
            satisfied_requirement_ids=tuple(satisfied),
            unmet_requirement_ids=tuple(dict.fromkeys(unmet)),
            used_contributions=used,
        )

    def _requirement_candidates(
        self,
        requirement: SessionTransitionRequirement,
        group: _EvidenceGroup,
    ) -> tuple[_Contribution, ...]:
        categories = set(requirement.evidence_categories)
        allowed_signals = set(requirement.allowed_signals)
        disallowed_signals = set(requirement.disallowed_signals)
        allowed_roles = set(requirement.allowed_roles)
        return tuple(
            contribution
            for contribution in group.contributions
            if contribution.category.value in categories
            and contribution.signal in allowed_signals
            and contribution.signal not in disallowed_signals
            and contribution.role in allowed_roles
        )

    def _requirements_have_distinct_sources(
        self,
        candidates: tuple[tuple[_Contribution, ...], ...],
    ) -> bool:
        if len(candidates) < 2:
            return True
        source_sets = tuple(
            {
                source_key
                for contribution in requirement_candidates
                for source_key in contribution.source_keys
            }
            for requirement_candidates in candidates
        )
        if any(not sources for sources in source_sets):
            return False
        first = source_sets[0]
        for later in source_sets[1:]:
            if not any(
                first_source != later_source
                for first_source in first
                for later_source in later
            ):
                return False
        return True

    def _is_fresh_context(
        self,
        group: _EvidenceGroup,
        current_state: OperationalState | None,
    ) -> bool:
        if current_state is None:
            return False
        candidate_sets = {item.id for item in group.evidence_sets}
        prior_sets = set(current_state.basis.evidence_set_ids)
        if prior_sets and candidate_sets.isdisjoint(prior_sets):
            return True
        candidate_block = self._first_known(group, "recording_block_id")
        if (
            current_state.recording_block_id is not None
            and candidate_block is not None
            and candidate_block != current_state.recording_block_id.to_json()
        ):
            return True
        candidate_activity = self._first_known(group, "scheduled_activity_id")
        current_activity = self._metadata_text(
            current_state.metadata,
            "scheduled_activity_id",
        )
        if current_activity and candidate_activity and current_activity != candidate_activity:
            return True
        candidate_context = self._first_known(group, "boundary_context_id")
        current_context = self._metadata_text(current_state.metadata, "boundary_context_id")
        if current_context and candidate_context and current_context != candidate_context:
            return True
        candidate_anchor = self._numeric_anchor(group)
        current_anchor = self._number(current_state.metadata.get("boundary_anchor_seconds"))
        if current_anchor is not None and candidate_anchor is not None:
            return candidate_anchor > current_anchor
        candidate_anchor_at = self._datetime_anchor(group)
        current_anchor_at = self._datetime_value(
            current_state.metadata.get("boundary_anchor_at")
        )
        return bool(
            current_anchor_at is not None
            and candidate_anchor_at is not None
            and candidate_anchor_at > current_anchor_at
        )

    def _blocking_candidate(
        self,
        rules: tuple[SessionTransitionRule, ...],
        groups: tuple[_EvidenceGroup, ...],
        current_state: OperationalState | None,
    ) -> tuple[_EvidenceGroup, _RuleAssessment, tuple[_Contribution, ...]] | None:
        for group in groups:
            contradictions = tuple(
                contribution
                for contribution in group.contributions
                if contribution.role is EvidenceRole.CONTRADICTS
            )
            non_contradictory = tuple(
                contribution
                for contribution in group.contributions
                if contribution.role in {EvidenceRole.SUPPORTS, EvidenceRole.CONTEXTUALIZES}
                and contribution.category is not SessionTransitionEvidenceCategory.UNSUPPORTED
            )
            if not contradictions or not non_contradictory:
                continue
            for rule in rules:
                if rule.required_boundary_concern is group.concern:
                    return group, self._assess_rule(rule, group, current_state), contradictions
        return None

    def _unsupported_transition_candidate(
        self,
        effective_current: OperationalStateValue,
        groups: tuple[_EvidenceGroup, ...],
        current_state: OperationalState | None,
    ) -> tuple[_EvidenceGroup, _RuleAssessment] | None:
        for group in groups:
            for rule in self.rules:
                transition = (effective_current, rule.proposed_state_value)
                if transition in SUPPORTED_SESSION_TRANSITIONS:
                    continue
                if rule.required_boundary_concern is not group.concern:
                    continue
                assessment = self._assess_rule(rule, group, current_state)
                if assessment.satisfied:
                    return group, assessment
        return None

    def _most_relevant_unmet(
        self,
        rules: tuple[SessionTransitionRule, ...],
        groups: tuple[_EvidenceGroup, ...],
        current_state: OperationalState | None,
    ) -> tuple[_EvidenceGroup | None, _RuleAssessment | None]:
        for group in groups:
            for rule in rules:
                if rule.required_boundary_concern is group.concern:
                    return group, self._assess_rule(rule, group, current_state)
        return None, None

    def _result(
        self,
        *,
        current_state: OperationalState | None,
        effective_current: OperationalStateValue | None,
        proposed_state: OperationalStateValue | None,
        outcome: TransitionPolicyResult,
        rationale: str,
        group: _EvidenceGroup | None,
        assessment: _RuleAssessment | None,
        supporting: tuple[_Contribution, ...],
        blocking: tuple[_Contribution, ...],
        ignored_ids: tuple[EntityId, ...],
        unsupported_ids: tuple[EntityId, ...],
        duplicate_ids: tuple[EntityId, ...],
        context_excluded_ids: tuple[EntityId, ...],
        evaluated_at: datetime,
        caller_metadata: Mapping[str, Any],
    ) -> SessionTransitionResult:
        supporting_ids = tuple(
            dict.fromkeys(contribution.evidence_set.id for contribution in supporting)
        )
        blocking_ids = tuple(
            dict.fromkeys(contribution.evidence_set.id for contribution in blocking)
        )
        profile = self._profile(group) if group is not None else None
        applied_rule_id = assessment.rule.id if assessment is not None else None
        satisfied_ids = (
            assessment.satisfied_requirement_ids if assessment is not None else ()
        )
        unmet_ids = assessment.unmet_requirement_ids if assessment is not None else ()
        signal_values = (
            tuple(signal.value for signal in profile.contributing_signals)
            if profile is not None
            else ()
        )
        item_ids = (
            tuple(item.to_json() for item in profile.contributing_evidence_item_ids)
            if profile is not None
            else ()
        )
        observation_ids = (
            tuple(item.to_json() for item in profile.contributing_observation_ids)
            if profile is not None
            else ()
        )
        evidence_ids = (
            tuple(item.to_json() for item in profile.contributing_evidence_set_ids)
            if profile is not None
            else ()
        )
        evaluation_id = _stable_entity_id(
            "evaluation:"
            f"{self.id.to_json()}:{current_state.id.to_json() if current_state else 'none'}:"
            f"{effective_current.value if effective_current else 'unknown'}:"
            f"{proposed_state.value if proposed_state else 'none'}:{outcome.value}:"
            f"{applied_rule_id.to_json() if applied_rule_id else 'none'}:"
            + ":".join(evidence_ids)
        )
        evaluation_metadata: dict[str, Any] = {
            "policy_id": self.id.to_json(),
            "current_state_id": current_state.id.to_json() if current_state else None,
            "current_state_value": current_state.value.value if current_state else None,
            "effective_current_state_value": (
                effective_current.value if effective_current is not None else None
            ),
            "missing_current_state_assumed_inactive": current_state is None,
            "proposed_state_value": proposed_state.value if proposed_state else None,
            "boundary_concern": group.concern.value if group is not None else None,
            "contributing_evidence_item_ids": item_ids,
            "contributing_observation_ids": observation_ids,
            "contributing_signals": signal_values,
            "applied_rule_id": applied_rule_id.to_json() if applied_rule_id else None,
            "satisfied_requirement_ids": tuple(item.to_json() for item in satisfied_ids),
            "unmet_requirement_ids": tuple(item.to_json() for item in unmet_ids),
            "context_key": group.context_key if group is not None else None,
            "context_excluded_evidence_set_ids": tuple(
                item.to_json() for item in context_excluded_ids
            ),
            "organizational_anchors": profile.boundary_anchors if profile else (),
            "final_boundary_timestamp": None,
            "transition_executed": False,
            "caller_metadata": dict(caller_metadata),
        }
        evaluation = TransitionEvaluation(
            id=evaluation_id,
            evaluated_state_kind=OperationalStateKind.SESSION_STATE,
            current_state=current_state,
            proposed_state=proposed_state,
            outcome=outcome,
            supporting_evidence_ids=supporting_ids,
            blocking_evidence_ids=blocking_ids,
            rationale=TransitionReason(
                rationale,
                metadata={
                    "applied_rule_id": (
                        applied_rule_id.to_json() if applied_rule_id else None
                    ),
                    "unmet_requirement_ids": tuple(
                        item.to_json() for item in unmet_ids
                    ),
                },
            ),
            evaluated_at=evaluated_at,
            metadata=evaluation_metadata,
        )
        return SessionTransitionResult(
            evaluation=evaluation,
            applied_rule_id=applied_rule_id,
            evidence_profile=profile,
            satisfied_requirement_ids=satisfied_ids,
            unmet_requirement_ids=unmet_ids,
            ignored_evidence_set_ids=ignored_ids,
            unsupported_evidence_set_ids=unsupported_ids,
            duplicate_evidence_set_ids=duplicate_ids,
            metadata={
                "policy_id": self.id.to_json(),
                "input_classification_is_descriptive": True,
                "context_excluded_evidence_set_ids": tuple(context_excluded_ids),
                "state_mutated": False,
                "evaluation_persisted": False,
            },
        )

    def _profile(
        self,
        group: _EvidenceGroup | None,
    ) -> SessionTransitionEvidenceProfile | None:
        if group is None:
            return None
        contributions = group.contributions
        sets_by_id = {
            contribution.evidence_set.id: contribution.evidence_set
            for contribution in contributions
        }
        items_by_id = {
            contribution.evidence_item.id: contribution.evidence_item
            for contribution in contributions
        }
        sets = tuple(sets_by_id.values())
        items = tuple(items_by_id.values())
        source_keys = {
            source_key
            for contribution in contributions
            for source_key in contribution.source_keys
        }
        return SessionTransitionEvidenceProfile(
            target_boundary_concern=group.concern,
            contributing_evidence_set_ids=tuple(item.id for item in sets),
            contributing_evidence_item_ids=tuple(item.id for item in items),
            contributing_observation_ids=tuple(
                dict.fromkeys(item.observation_id for item in items)
            ),
            contributing_signals=tuple(
                dict.fromkeys(contribution.signal for contribution in contributions)
            ),
            evidence_categories=tuple(
                dict.fromkeys(contribution.category for contribution in contributions)
            ),
            strengths=tuple(contribution.strength for contribution in contributions),
            supporting_count=sum(
                contribution.role is EvidenceRole.SUPPORTS
                for contribution in contributions
            ),
            contradicting_count=sum(
                contribution.role is EvidenceRole.CONTRADICTS
                for contribution in contributions
            ),
            contextual_count=sum(
                contribution.role is EvidenceRole.CONTEXTUALIZES
                for contribution in contributions
            ),
            unsupported_count=group.unsupported_count
            + sum(
                contribution.category is SessionTransitionEvidenceCategory.UNSUPPORTED
                for contribution in contributions
            ),
            independent_source_count=len(source_keys),
            recording_block_ids=self._context_entity_ids(group, "recording_block_id"),
            stage_ids=self._context_entity_ids(group, "stage_id"),
            scheduled_activity_ids=self._context_entity_ids(
                group,
                "scheduled_activity_id",
            ),
            boundary_anchors=self._anchors(group),
            metadata={
                "context_key": group.context_key,
                "strength_used_as_gate": False,
                "source_independence_rule": (
                    "distinct_observation_id_then_evidence_item_id_then_evidence_set_id"
                ),
                "ranking_applied": False,
            },
        )

    def _context_entity_ids(
        self,
        group: _EvidenceGroup,
        key: str,
    ) -> tuple[EntityId, ...]:
        values: list[EntityId] = []
        for evidence_set in group.evidence_sets:
            if key == "recording_block_id":
                value = evidence_set.recording_block_id
            else:
                value = self._entity(evidence_set.metadata.get(key))
            if value is not None and value not in values:
                values.append(value)
        return tuple(values)

    def _anchors(self, group: _EvidenceGroup) -> tuple[str, ...]:
        anchors: list[str] = []
        for evidence_set in group.evidence_sets:
            for key in ("boundary_anchor_seconds", "boundary_anchor_at"):
                value = evidence_set.metadata.get(key)
                if isinstance(value, str | int | float):
                    rendered = str(value)
                    if rendered not in anchors:
                        anchors.append(rendered)
        return tuple(anchors)

    def _unique_contributions(
        self,
        contributions: tuple[_Contribution, ...],
    ) -> tuple[_Contribution, ...]:
        by_key: dict[tuple[str, str, str], _Contribution] = {}
        for contribution in contributions:
            by_key.setdefault(contribution.key, contribution)
        return tuple(by_key.values())

    def _anchor_order(self, evidence_set: EvidenceSet) -> str:
        for key in ("boundary_anchor_at", "boundary_anchor_seconds"):
            value = evidence_set.metadata.get(key)
            if isinstance(value, str | int | float):
                return str(value)
        return ""

    def _first_known(self, group: _EvidenceGroup, key: str) -> str | None:
        for evidence_set in group.evidence_sets:
            if key == "recording_block_id":
                value = self._optional_id(evidence_set.recording_block_id)
            else:
                value = self._metadata_text(evidence_set.metadata, key)
            if value:
                return value
        return None

    def _numeric_anchor(self, group: _EvidenceGroup) -> float | None:
        values = tuple(
            value
            for evidence_set in group.evidence_sets
            for value in (self._number(evidence_set.metadata.get("boundary_anchor_seconds")),)
            if value is not None
        )
        return min(values) if values else None

    def _datetime_anchor(self, group: _EvidenceGroup) -> datetime | None:
        values = tuple(
            value
            for evidence_set in group.evidence_sets
            for value in (
                self._datetime_value(evidence_set.metadata.get("boundary_anchor_at")),
            )
            if value is not None
        )
        return min(values) if values else None

    def _optional_id(self, value: EntityId | None) -> str:
        return value.to_json() if value is not None else ""

    def _metadata_id(self, metadata: Mapping[str, Any], key: str) -> str:
        value = self._entity(metadata.get(key))
        return value.to_json() if value is not None else ""

    def _metadata_text(self, metadata: Mapping[str, Any], key: str) -> str | None:
        value = metadata.get(key)
        if isinstance(value, EntityId):
            return value.to_json()
        if isinstance(value, str) and value.strip():
            return value
        return None

    def _entity(self, value: object) -> EntityId | None:
        if isinstance(value, EntityId):
            return value
        if not isinstance(value, str):
            return None
        try:
            return EntityId.parse(value)
        except ValueError:
            return None

    def _number(self, value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        return None

    def _datetime_value(self, value: object) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
        else:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def make_session_transition_policy(
    *,
    policy_id: EntityId | None = None,
    name: str = "Session Transition Policy",
) -> SessionTransitionPolicy:
    return SessionTransitionPolicy(id=policy_id or EntityId.new(), name=name)
