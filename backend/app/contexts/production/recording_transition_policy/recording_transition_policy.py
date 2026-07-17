from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from types import MappingProxyType
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
)
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.contexts.production.recording_transition_policy.recording_transition_mapping import (
    RECORDING_TRANSITION_MAPPINGS,
    RecordingTransitionMapping,
    mapping_for_recording_marker,
    mapping_for_recording_signal,
)
from app.contexts.production.transition_policy import (
    TransitionEvaluation,
    TransitionPolicyResult,
    TransitionReason,
)
from app.shared.ids import EntityId

from .recording_transition_context import RecordingTransitionContext
from .recording_transition_evidence_profile import RecordingTransitionEvidenceProfile
from .recording_transition_result import RecordingTransitionResult
from .recording_transition_rule import RecordingTransitionRule

_SUPPORTED_RECORDING_VALUES = {
    OperationalStateValue.INACTIVE,
    OperationalStateValue.ACTIVE,
    OperationalStateValue.PAUSED,
    OperationalStateValue.STOPPED,
}
_SUPPORTED_SUBJECT_TYPES = {
    OperationalStateSubjectType.RECORDING_BLOCK,
    OperationalStateSubjectType.MEDIA_ARTIFACT,
    OperationalStateSubjectType.STAGEFLOW,
}


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def recording_transition_rule_id(signal: EvidenceSignal) -> EntityId:
    """Return the stable identity for one recording transition Signal rule."""

    return EntityId.parse(
        str(uuid5(NAMESPACE_URL, f"stageflow:recording-transition:rule:{signal.value}"))
    )


def default_recording_transition_rules() -> tuple[RecordingTransitionRule, ...]:
    return tuple(
        RecordingTransitionRule(
            id=recording_transition_rule_id(mapping.evidence_signal),
            evidence_signal=mapping.evidence_signal,
            proposed_state=mapping.proposed_state,
            legacy_evidence_marker=mapping.legacy_evidence_marker,
            description=mapping.rationale,
        )
        for mapping in RECORDING_TRANSITION_MAPPINGS
    )


@dataclass(frozen=True, slots=True)
class _SignalContribution:
    evidence_set: EvidenceSet
    context: RecordingTransitionContext
    evidence_item: EvidenceItem
    signal: EvidenceSignal
    rule: RecordingTransitionRule
    mapping: RecordingTransitionMapping
    is_legacy_marker: bool

    @property
    def key(self) -> tuple[str, str, str]:
        return (
            self.evidence_set.id.to_json(),
            self.evidence_item.id.to_json(),
            self.signal.value,
        )


@dataclass(frozen=True, slots=True)
class _PreparedEvidence:
    evidence_set: EvidenceSet
    context: RecordingTransitionContext
    contributions: tuple[_SignalContribution, ...]


@dataclass(frozen=True, slots=True)
class _ContextGroup:
    entries: tuple[_PreparedEvidence, ...]

    @property
    def contexts(self) -> tuple[RecordingTransitionContext, ...]:
        return tuple(entry.context for entry in self.entries)

    @property
    def contributions(self) -> tuple[_SignalContribution, ...]:
        return tuple(
            contribution
            for entry in self.entries
            for contribution in entry.contributions
        )

    @property
    def has_recording_identity(self) -> bool:
        return any(context.has_recording_identity for context in self.contexts)


@dataclass(frozen=True, slots=True)
class _CurrentStateValidation:
    status: str
    effective_value: OperationalStateValue | None
    context: RecordingTransitionContext | None
    error: str | None


@dataclass(frozen=True, slots=True)
class RecordingTransitionPolicy:
    """Conservative policy proposing one recording state within one context only."""

    id: EntityId
    name: str = "Recording Transition Policy"
    rules: Sequence[RecordingTransitionRule] = field(
        default_factory=default_recording_transition_rules
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("RecordingTransitionPolicy name must not be empty.")
        rules = tuple(self.rules)
        if len({rule.evidence_signal for rule in rules}) != len(rules):
            raise ValueError("RecordingTransitionPolicy rules must not repeat an Evidence Signal.")
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def evaluated_state_kind(self) -> OperationalStateKind:
        return OperationalStateKind.RECORDING_STATE

    def evaluate(
        self,
        *,
        current_state: OperationalState | None,
        evidence_sets: Sequence[EvidenceSet],
    ) -> TransitionEvaluation:
        """Compatibility entry point returning the generic evaluation contract."""
        return self.evaluate_result(
            current_state=current_state,
            evidence_sets=evidence_sets,
        ).evaluation

    def evaluate_result(
        self,
        *,
        current_state: OperationalState | None,
        evidence_sets: Sequence[EvidenceSet],
        evaluated_at: datetime | None = None,
    ) -> RecordingTransitionResult:
        """Evaluate recording Evidence with policy-local context diagnostics."""
        timestamp = evaluated_at or datetime.now(UTC)
        prepared, ignored_ids, unsupported_ids, duplicate_ids = self._prepare_evidence(
            tuple(evidence_sets)
        )
        all_contexts = tuple(entry.context for entry in prepared)
        validation = self._validate_current_state(current_state)
        groups = self._groups(prepared)

        if validation.error is not None:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=TransitionPolicyResult.UNKNOWN,
                rationale=validation.error,
                selected_group=None,
                conflicting_groups=(),
                selected_contributions=(),
                blocking_contributions=(),
                ordered_signals=(),
                applied_rule=None,
                ambiguity_reasons=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        if len(groups) > 1:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                rationale=(
                    "Multiple incompatible recording contexts contain qualifying Evidence; "
                    "no recording transition was selected."
                ),
                selected_group=None,
                conflicting_groups=groups,
                selected_contributions=(),
                blocking_contributions=(),
                ordered_signals=(),
                applied_rule=None,
                ambiguity_reasons=("multiple_incompatible_recording_contexts",),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        if not groups:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                rationale="Recording Evidence is absent, unrelated, or lacks a supported Signal.",
                selected_group=None,
                conflicting_groups=(),
                selected_contributions=(),
                blocking_contributions=(),
                ordered_signals=(),
                applied_rule=None,
                ambiguity_reasons=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        group = groups[0]
        selected_context = self._combined_context(group)
        context_error = self._state_context_error(validation.context, selected_context)
        if context_error is not None:
            outcome, rationale = context_error
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=outcome,
                rationale=rationale,
                selected_group=group,
                conflicting_groups=(),
                selected_contributions=(),
                blocking_contributions=(),
                ordered_signals=(),
                applied_rule=None,
                ambiguity_reasons=("current_state_context_not_compatible",),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        blocking = self._unique_contributions(
            tuple(
                contribution
                for contribution in group.contributions
                if contribution.evidence_item.role is EvidenceRole.CONTRADICTS
            )
        )
        if blocking:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                rationale=(
                    "Compatible recording Evidence explicitly contradicts the requested "
                    "transition."
                ),
                selected_group=group,
                conflicting_groups=(),
                selected_contributions=(),
                blocking_contributions=blocking,
                ordered_signals=(),
                applied_rule=None,
                ambiguity_reasons=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        supporting = self._unique_contributions(
            tuple(
                contribution
                for contribution in group.contributions
                if contribution.evidence_item.role is EvidenceRole.SUPPORTS
            )
        )
        if not supporting:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                rationale="Recording Evidence has no supporting Signal contribution.",
                selected_group=group,
                conflicting_groups=(),
                selected_contributions=(),
                blocking_contributions=(),
                ordered_signals=(),
                applied_rule=None,
                ambiguity_reasons=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        selected, ordered_signals, ambiguity_reason = self._select_signal(
            group,
            supporting,
        )
        if selected is None:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                rationale=(
                    "Compatible recording Evidence contains conflicting lifecycle Signals "
                    "without a safe chronological resolution."
                ),
                selected_group=group,
                conflicting_groups=(),
                selected_contributions=(),
                blocking_contributions=(),
                ordered_signals=ordered_signals,
                applied_rule=None,
                ambiguity_reasons=(ambiguity_reason or "unresolved_lifecycle_signals",),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        if (
            len(set(ordered_signals)) > 1
            and validation.effective_value not in selected.mapping.allowed_current_values
        ):
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                rationale=(
                    "Accumulated recording lifecycle Signals require an unaccepted "
                    "intermediate transition; the policy does not replay state history."
                ),
                selected_group=group,
                conflicting_groups=(),
                selected_contributions=(),
                blocking_contributions=(),
                ordered_signals=ordered_signals,
                applied_rule=None,
                ambiguity_reasons=("unaccepted_intermediate_transition",),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        if validation.effective_value is selected.mapping.proposed_state:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=selected.mapping.proposed_state,
                outcome=TransitionPolicyResult.ALREADY_CURRENT,
                rationale="Current recording state already matches compatible supporting Evidence.",
                selected_group=group,
                conflicting_groups=(),
                selected_contributions=tuple(
                    contribution
                    for contribution in supporting
                    if contribution.signal is selected.signal
                ),
                blocking_contributions=(),
                ordered_signals=ordered_signals,
                applied_rule=selected.rule,
                ambiguity_reasons=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        if validation.effective_value not in selected.mapping.allowed_current_values:
            return self._result(
                current_state=current_state,
                validation=validation,
                proposed_state=selected.mapping.proposed_state,
                outcome=TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                rationale=(
                    "Compatible recording Evidence indicates a lifecycle value that is not "
                    "allowed from the current recording state."
                ),
                selected_group=group,
                conflicting_groups=(),
                selected_contributions=tuple(
                    contribution
                    for contribution in supporting
                    if contribution.signal is selected.signal
                ),
                blocking_contributions=(),
                ordered_signals=ordered_signals,
                applied_rule=selected.rule,
                ambiguity_reasons=(),
                ignored_ids=ignored_ids,
                unsupported_ids=unsupported_ids,
                duplicate_ids=duplicate_ids,
                all_contexts=all_contexts,
                evaluated_at=timestamp,
            )

        return self._result(
            current_state=current_state,
            validation=validation,
            proposed_state=selected.mapping.proposed_state,
            outcome=TransitionPolicyResult.TRANSITION_SUPPORTED,
            rationale=selected.mapping.rationale,
            selected_group=group,
            conflicting_groups=(),
            selected_contributions=tuple(
                contribution
                for contribution in supporting
                if contribution.signal is selected.signal
            ),
            blocking_contributions=(),
            ordered_signals=ordered_signals,
            applied_rule=selected.rule,
            ambiguity_reasons=(),
            ignored_ids=ignored_ids,
            unsupported_ids=unsupported_ids,
            duplicate_ids=duplicate_ids,
            all_contexts=all_contexts,
            evaluated_at=timestamp,
        )

    def _prepare_evidence(
        self,
        inputs: tuple[EvidenceSet, ...],
    ) -> tuple[
        tuple[_PreparedEvidence, ...],
        tuple[EntityId, ...],
        tuple[EntityId, ...],
        tuple[EntityId, ...],
    ]:
        candidates = tuple(
            _PreparedEvidence(
                evidence_set=evidence_set,
                context=self._extract_context(evidence_set),
                contributions=(),
            )
            for evidence_set in inputs
        )
        ordered = tuple(
            sorted(
                enumerate(candidates),
                key=lambda pair: self._evidence_order_key(
                    pair[1].evidence_set,
                    pair[1].context,
                    pair[0],
                ),
            )
        )
        retained: list[_PreparedEvidence] = []
        duplicate_ids: list[EntityId] = []
        seen: set[EntityId] = set()
        for _index, candidate in ordered:
            if candidate.evidence_set.id in seen:
                duplicate_ids.append(candidate.evidence_set.id)
                continue
            seen.add(candidate.evidence_set.id)
            retained.append(candidate)

        prepared: list[_PreparedEvidence] = []
        ignored_ids: list[EntityId] = []
        unsupported_ids: list[EntityId] = []
        for candidate in retained:
            evidence_set = candidate.evidence_set
            if evidence_set.concern is not EvidenceConcern.RECORDING_COVERAGE:
                ignored_ids.append(evidence_set.id)
                continue
            contributions = self._contributions(evidence_set, candidate.context)
            if not contributions:
                unsupported_ids.append(evidence_set.id)
                continue
            prepared.append(
                _PreparedEvidence(
                    evidence_set=evidence_set,
                    context=candidate.context,
                    contributions=contributions,
                )
            )
        return (
            tuple(prepared),
            tuple(ignored_ids),
            tuple(unsupported_ids),
            tuple(duplicate_ids),
        )

    def _contributions(
        self,
        evidence_set: EvidenceSet,
        context: RecordingTransitionContext,
    ) -> tuple[_SignalContribution, ...]:
        contributions: list[_SignalContribution] = []
        if evidence_set.signals:
            for reference in evidence_set.signals:
                rule, mapping = self._rule_and_mapping(reference.signal)
                if rule is None or mapping is None:
                    continue
                for item in self._linked_items(evidence_set, reference):
                    contributions.append(
                        _SignalContribution(
                            evidence_set=evidence_set,
                            context=context,
                            evidence_item=item,
                            signal=reference.signal,
                            rule=rule,
                            mapping=mapping,
                            is_legacy_marker=False,
                        )
                    )
        else:
            marker = evidence_set.metadata.get("recording_transition_marker")
            if isinstance(marker, str):
                mapping = mapping_for_recording_marker(marker)
                rule = (
                    self._rule_for_signal(mapping.evidence_signal)
                    if mapping is not None
                    else None
                )
                if mapping is not None and rule is not None and len(evidence_set.items) == 1:
                    contributions.append(
                        _SignalContribution(
                            evidence_set=evidence_set,
                            context=context,
                            evidence_item=evidence_set.items[0],
                            signal=mapping.evidence_signal,
                            rule=rule,
                            mapping=mapping,
                            is_legacy_marker=True,
                        )
                    )
        return self._unique_contributions(tuple(contributions))

    def _linked_items(
        self,
        evidence_set: EvidenceSet,
        reference: EvidenceSignalReference,
    ) -> tuple[EvidenceItem, ...]:
        if reference.evidence_item_ids:
            item_ids = set(reference.evidence_item_ids)
            return tuple(item for item in evidence_set.items if item.id in item_ids)
        if reference.observation_ids:
            observation_ids = set(reference.observation_ids)
            return tuple(
                item for item in evidence_set.items if item.observation_id in observation_ids
            )
        if len(evidence_set.items) == 1:
            return tuple(evidence_set.items)
        return ()

    def _groups(
        self,
        prepared: tuple[_PreparedEvidence, ...],
    ) -> tuple[_ContextGroup, ...]:
        known_groups: list[list[_PreparedEvidence]] = []
        unknown_entries: list[_PreparedEvidence] = []
        for entry in prepared:
            if not entry.context.has_recording_identity:
                unknown_entries.append(entry)
                continue
            matching_groups = tuple(
                group
                for group in known_groups
                if all(
                    self._contexts_compatible(entry.context, existing.context)
                    for existing in group
                )
            )
            if len(matching_groups) == 1:
                matching_groups[0].append(entry)
            else:
                # A partial context that could bridge groups remains separate rather than
                # becoming a path that merges otherwise incompatible recording contexts.
                known_groups.append([entry])
        groups = [_ContextGroup(entries=tuple(group)) for group in known_groups]
        if unknown_entries:
            groups.append(_ContextGroup(entries=tuple(unknown_entries)))
        return tuple(
            sorted(
                groups,
                key=lambda group: tuple(
                    context.compatibility_key()
                    for context in group.contexts
                ),
            )
        )

    def _contexts_compatible(
        self,
        left: RecordingTransitionContext,
        right: RecordingTransitionContext,
    ) -> bool:
        if (
            left.recording_block_id is not None
            and right.recording_block_id is not None
            and left.recording_block_id != right.recording_block_id
        ):
            return False
        if (
            left.stage_id is not None
            and right.stage_id is not None
            and left.stage_id != right.stage_id
        ):
            return False
        if (
            left.media_artifact_id is not None
            and right.media_artifact_id is not None
            and left.media_artifact_id != right.media_artifact_id
            and not (
                left.recording_block_id is not None
                and left.recording_block_id == right.recording_block_id
            )
        ):
            return False
        return True

    def _select_signal(
        self,
        group: _ContextGroup,
        supporting: tuple[_SignalContribution, ...],
    ) -> tuple[
        _SignalContribution | None,
        tuple[EvidenceSignal, ...],
        str | None,
    ]:
        by_signal: dict[EvidenceSignal, list[_SignalContribution]] = {}
        for contribution in supporting:
            by_signal.setdefault(contribution.signal, []).append(contribution)
        signal_values = tuple(sorted(by_signal, key=lambda signal: signal.value))
        if len(signal_values) == 1:
            signal = signal_values[0]
            selected = min(by_signal[signal], key=self._contribution_identity_key)
            return selected, signal_values, None
        if not group.has_recording_identity:
            return None, signal_values, "conflicting_unknown_context_signals"
        ordered = self._reliably_ordered_signals(by_signal)
        if ordered is None:
            return None, signal_values, "unresolved_lifecycle_signal_order"
        selected_signal = ordered[-1]
        selected = min(
            by_signal[selected_signal],
            key=self._contribution_identity_key,
        )
        return selected, ordered, None

    def _reliably_ordered_signals(
        self,
        by_signal: Mapping[EvidenceSignal, Sequence[_SignalContribution]],
    ) -> tuple[EvidenceSignal, ...] | None:
        for order_value in (
            self._timeline_order_value,
            self._evidence_timestamp_order_value,
            self._observation_timestamp_order_value,
        ):
            latest: dict[EvidenceSignal, float] = {}
            for signal, contributions in by_signal.items():
                values = [order_value(contribution) for contribution in contributions]
                if any(value is None for value in values):
                    latest = {}
                    break
                latest[signal] = max(value for value in values if value is not None)
            if len(latest) != len(by_signal) or len(set(latest.values())) != len(latest):
                continue
            return tuple(
                signal
                for signal, _value in sorted(latest.items(), key=lambda pair: pair[1])
            )
        return None

    def _timeline_order_value(self, contribution: _SignalContribution) -> float | None:
        timeline_range = contribution.context.timeline_range_seconds
        return timeline_range[1] if timeline_range is not None else None

    def _evidence_timestamp_order_value(
        self,
        contribution: _SignalContribution,
    ) -> float | None:
        return self._aware_timestamp(contribution.evidence_set.created_at)

    def _observation_timestamp_order_value(
        self,
        contribution: _SignalContribution,
    ) -> float | None:
        value = contribution.evidence_item.metadata.get("observation_observed_at")
        return self._metadata_timestamp(value)

    def _validate_current_state(
        self,
        current_state: OperationalState | None,
    ) -> _CurrentStateValidation:
        if current_state is None:
            return _CurrentStateValidation(
                status="absent_assumed_inactive",
                effective_value=OperationalStateValue.INACTIVE,
                context=None,
                error=None,
            )
        if current_state.kind is not OperationalStateKind.RECORDING_STATE:
            return _CurrentStateValidation(
                status="invalid_kind",
                effective_value=None,
                context=None,
                error="Current Operational State is not a recording state.",
            )
        if current_state.subject.subject_type not in _SUPPORTED_SUBJECT_TYPES:
            return _CurrentStateValidation(
                status="invalid_subject_type",
                effective_value=None,
                context=None,
                error="Current recording state uses an unsupported recording subject type.",
            )
        if current_state.status is not OperationalStateStatus.CURRENT:
            return _CurrentStateValidation(
                status="invalid_status",
                effective_value=None,
                context=None,
                error="Current recording state does not have current status.",
            )
        if current_state.value not in _SUPPORTED_RECORDING_VALUES:
            return _CurrentStateValidation(
                status="unsupported_value",
                effective_value=None,
                context=None,
                error="Current recording state value is outside the supported lifecycle.",
            )

        recording_block_id = current_state.recording_block_id
        media_artifact_id: str | None = None
        if current_state.subject.subject_type is OperationalStateSubjectType.RECORDING_BLOCK:
            subject_block = self._entity_id(current_state.subject.subject_identifier)
            if subject_block is None:
                return _CurrentStateValidation(
                    status="invalid_recording_block_subject_identifier",
                    effective_value=None,
                    context=None,
                    error="Current recording-block subject identifier is not a valid EntityId.",
                )
            if recording_block_id is not None and recording_block_id != subject_block:
                return _CurrentStateValidation(
                    status="inconsistent_recording_block_subject",
                    effective_value=None,
                    context=None,
                    error="Current recording state recording block conflicts with its subject.",
                )
            recording_block_id = subject_block
        elif current_state.subject.subject_type is OperationalStateSubjectType.MEDIA_ARTIFACT:
            media_artifact_id = current_state.subject.subject_identifier

        return _CurrentStateValidation(
            status="valid",
            effective_value=current_state.value,
            context=RecordingTransitionContext(
                recording_block_id=recording_block_id,
                stage_id=current_state.stage_id,
                media_artifact_id=media_artifact_id,
                metadata={"source": "current_operational_state"},
            ),
            error=None,
        )

    def _state_context_error(
        self,
        current_context: RecordingTransitionContext | None,
        evidence_context: RecordingTransitionContext,
    ) -> tuple[TransitionPolicyResult, str] | None:
        if current_context is None or not current_context.has_recording_identity:
            return None
        if not evidence_context.has_recording_identity:
            return (
                TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                "Recording Evidence lacks the context required to match the current state.",
            )
        if (
            current_context.recording_block_id is not None
            and evidence_context.recording_block_id is not None
            and current_context.recording_block_id != evidence_context.recording_block_id
        ):
            return (
                TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                "Recording Evidence belongs to a different recording block than the current state.",
            )
        if (
            current_context.stage_id is not None
            and evidence_context.stage_id is not None
            and current_context.stage_id != evidence_context.stage_id
        ):
            return (
                TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                "Recording Evidence belongs to a different stage than the current state.",
            )
        if (
            current_context.media_artifact_id is not None
            and evidence_context.media_artifact_id is not None
            and current_context.media_artifact_id != evidence_context.media_artifact_id
        ):
            return (
                TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                "Recording Evidence belongs to a different media artifact than the current state.",
            )
        return None

    def _extract_context(self, evidence_set: EvidenceSet) -> RecordingTransitionContext:
        metadata = evidence_set.metadata
        return RecordingTransitionContext(
            recording_block_id=evidence_set.recording_block_id
            or self._metadata_entity(metadata, "recording_block_id"),
            stage_id=self._context_entity(evidence_set, "stage_id"),
            correlation_id=evidence_set.correlation_id,
            media_artifact_id=self._context_text(
                evidence_set,
                ("media_artifact_id", "artifact_id"),
            ),
            source_evidence_set_id=evidence_set.id,
            timeline_range_seconds=self._context_timeline_range(evidence_set),
            organizational_at=evidence_set.created_at,
            metadata={
                "recording_block_source": (
                    "first_class" if evidence_set.recording_block_id is not None else "metadata"
                ),
                "stage_source": "metadata",
                "correlation_source": "first_class_traceability_only",
                "media_artifact_source": "metadata",
                "timeline_source": "metadata",
            },
        )

    def _context_entity(self, evidence_set: EvidenceSet, key: str) -> EntityId | None:
        direct = self._metadata_entity(evidence_set.metadata, key)
        if direct is not None:
            return direct
        values = {
            value
            for source in (*evidence_set.signals, *evidence_set.items)
            if (value := self._metadata_entity(source.metadata, key)) is not None
        }
        return next(iter(values)) if len(values) == 1 else None

    def _context_text(
        self,
        evidence_set: EvidenceSet,
        keys: tuple[str, ...],
    ) -> str | None:
        for key in keys:
            value = evidence_set.metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
        values = {
            value
            for source in (*evidence_set.signals, *evidence_set.items)
            for key in keys
            if isinstance(value := source.metadata.get(key), str) and value.strip()
        }
        return next(iter(values)) if len(values) == 1 else None

    def _context_timeline_range(
        self,
        evidence_set: EvidenceSet,
    ) -> tuple[float, float] | None:
        sources = (evidence_set.metadata,) + tuple(
            item.metadata for item in evidence_set.items
        )
        for source in sources:
            location = source.get("observation_location")
            start = self._number(
                source.get(
                    "timeline_range_start_seconds",
                    self._mapping_value(location, "timeline_range_start_seconds"),
                )
            )
            end = self._number(
                source.get(
                    "timeline_range_end_seconds",
                    self._mapping_value(location, "timeline_range_end_seconds"),
                )
            )
            point = self._number(
                source.get(
                    "timeline_offset_seconds",
                    self._mapping_value(location, "timeline_offset_seconds"),
                )
            )
            if start is not None and end is not None and end >= start:
                return (start, end)
            if point is not None:
                return (point, point)
        return None

    def _combined_context(self, group: _ContextGroup) -> RecordingTransitionContext:
        contexts = group.contexts
        block_ids = {
            context.recording_block_id
            for context in contexts
            if context.recording_block_id
        }
        stage_ids = {context.stage_id for context in contexts if context.stage_id}
        artifact_ids = {
            context.media_artifact_id
            for context in contexts
            if context.media_artifact_id is not None
        }
        correlation_ids = {
            context.correlation_id for context in contexts if context.correlation_id is not None
        }
        return RecordingTransitionContext(
            recording_block_id=next(iter(block_ids)) if len(block_ids) == 1 else None,
            stage_id=next(iter(stage_ids)) if len(stage_ids) == 1 else None,
            correlation_id=(
                next(iter(correlation_ids)) if len(correlation_ids) == 1 else None
            ),
            media_artifact_id=(
                next(iter(artifact_ids)) if len(artifact_ids) == 1 else None
            ),
            metadata={
                "source_evidence_set_ids": tuple(
                    entry.evidence_set.id.to_json() for entry in group.entries
                ),
            },
        )

    def _result(
        self,
        *,
        current_state: OperationalState | None,
        validation: _CurrentStateValidation,
        proposed_state: OperationalStateValue | None,
        outcome: TransitionPolicyResult,
        rationale: str,
        selected_group: _ContextGroup | None,
        conflicting_groups: tuple[_ContextGroup, ...],
        selected_contributions: tuple[_SignalContribution, ...],
        blocking_contributions: tuple[_SignalContribution, ...],
        ordered_signals: tuple[EvidenceSignal, ...],
        applied_rule: RecordingTransitionRule | None,
        ambiguity_reasons: tuple[str, ...],
        ignored_ids: tuple[EntityId, ...],
        unsupported_ids: tuple[EntityId, ...],
        duplicate_ids: tuple[EntityId, ...],
        all_contexts: tuple[RecordingTransitionContext, ...],
        evaluated_at: datetime,
    ) -> RecordingTransitionResult:
        selected_context = (
            self._combined_context(selected_group) if selected_group is not None else None
        )
        conflicting_contexts = tuple(
            self._combined_context(group) for group in conflicting_groups
        )
        all_contributions = tuple(
            contribution
            for group in (
                ((selected_group,) if selected_group is not None else ())
                + conflicting_groups
            )
            for contribution in group.contributions
        )
        qualifying_ids = tuple(
            dict.fromkeys(
                context.source_evidence_set_id
                for context in all_contexts
                if context.source_evidence_set_id is not None
            )
        )
        conflicting_ids = tuple(
            dict.fromkeys(
                entry.evidence_set.id
                for group in conflicting_groups
                for entry in group.entries
            )
        )
        profile = RecordingTransitionEvidenceProfile(
            qualifying_evidence_set_ids=qualifying_ids,
            conflicting_evidence_set_ids=conflicting_ids,
            ignored_evidence_set_ids=ignored_ids,
            unsupported_evidence_set_ids=unsupported_ids,
            duplicate_evidence_set_ids=duplicate_ids,
            contributing_evidence_item_ids=tuple(
                dict.fromkeys(
                    contribution.evidence_item.id for contribution in all_contributions
                )
            ),
            contributing_observation_ids=tuple(
                dict.fromkeys(
                    contribution.evidence_item.observation_id
                    for contribution in all_contributions
                )
            ),
            contributing_signals=tuple(
                dict.fromkeys(contribution.signal for contribution in all_contributions)
            ),
            contexts=all_contexts,
            selected_context=selected_context,
            conflicting_contexts=conflicting_contexts,
            ordered_lifecycle_signals=ordered_signals,
            current_state_validation=validation.status,
            metadata={
                "legacy_marker_used": any(
                    contribution.is_legacy_marker for contribution in all_contributions
                ),
                "correlation_used_as_recording_identity": False,
                "state_mutated": False,
                "evaluation_persisted": False,
                **self._lineage_metadata(all_contributions),
            },
        )
        supporting_ids = tuple(
            dict.fromkeys(
                contribution.evidence_set.id for contribution in selected_contributions
            )
        )
        blocking_ids = tuple(
            dict.fromkeys(
                contribution.evidence_set.id for contribution in blocking_contributions
            )
        )
        evaluation = TransitionEvaluation(
            id=EntityId.new(),
            evaluated_state_kind=self.evaluated_state_kind,
            current_state=current_state,
            proposed_state=proposed_state,
            outcome=outcome,
            supporting_evidence_ids=supporting_ids,
            blocking_evidence_ids=blocking_ids,
            rationale=TransitionReason(
                rationale,
                metadata={
                    "applied_rule_id": applied_rule.id.to_json() if applied_rule else None,
                    "ambiguity_reasons": ambiguity_reasons,
                },
            ),
            evaluated_at=evaluated_at,
            metadata={
                "policy_id": self.id.to_json(),
                "policy_kind": "recording_transition_policy",
                "current_state_id": current_state.id.to_json() if current_state else None,
                "current_state_kind": current_state.kind.value if current_state else None,
                "current_state_subject_type": (
                    current_state.subject.subject_type.value if current_state else None
                ),
                "current_state_subject_identifier": (
                    current_state.subject.subject_identifier if current_state else None
                ),
                "current_state_value": current_state.value.value if current_state else None,
                "effective_current_state_value": (
                    validation.effective_value.value
                    if validation.effective_value is not None
                    else None
                ),
                "missing_current_state_assumed_inactive": current_state is None,
                "current_state_validation": validation.status,
                "examined_evidence_ids": tuple(
                    context.source_evidence_set_id.to_json()
                    for context in all_contexts
                    if context.source_evidence_set_id is not None
                ),
                "ignored_evidence_ids": tuple(item.to_json() for item in ignored_ids),
                "unsupported_evidence_ids": tuple(item.to_json() for item in unsupported_ids),
                "duplicate_evidence_ids": tuple(item.to_json() for item in duplicate_ids),
                "conflicting_evidence_ids": tuple(
                    item.to_json() for item in conflicting_ids
                ),
                "examined_signal_values": tuple(
                    signal.value for signal in profile.contributing_signals
                ),
                "contributing_evidence_item_ids": tuple(
                    item.to_json() for item in profile.contributing_evidence_item_ids
                ),
                "contributing_observation_ids": tuple(
                    item.to_json() for item in profile.contributing_observation_ids
                ),
                "source_production_event_ids": profile.metadata.get(
                    "source_production_event_ids",
                    (),
                ),
                "source_production_event_types": profile.metadata.get(
                    "source_production_event_types",
                    (),
                ),
                "source_interpreter_ids": profile.metadata.get(
                    "source_interpreter_ids",
                    (),
                ),
                "source_interpretation_rule_ids": profile.metadata.get(
                    "source_interpretation_rule_ids",
                    (),
                ),
                "selected_context": self._context_metadata(selected_context),
                "conflicting_contexts": tuple(
                    self._context_metadata(context) for context in conflicting_contexts
                ),
                "ordered_lifecycle_signals": tuple(
                    signal.value for signal in ordered_signals
                ),
                "applied_rule_id": applied_rule.id.to_json() if applied_rule else None,
                "legacy_marker_used": profile.metadata["legacy_marker_used"],
                "transition_executed": False,
            },
        )
        return RecordingTransitionResult(
            evaluation=evaluation,
            applied_rule_id=applied_rule.id if applied_rule else None,
            evidence_profile=profile,
            ambiguity_reasons=ambiguity_reasons,
            metadata={
                "policy_id": self.id.to_json(),
                "state_mutated": False,
                "evaluation_persisted": False,
            },
        )

    def _lineage_metadata(
        self,
        contributions: tuple[_SignalContribution, ...],
    ) -> Mapping[str, Any]:
        singular_to_plural = {
            "source_production_event_id": "source_production_event_ids",
            "source_production_event_type": "source_production_event_types",
            "observation_interpreter_id": "source_interpreter_ids",
            "interpretation_rule_id": "source_interpretation_rule_ids",
        }
        output: dict[str, tuple[str, ...]] = {}
        for singular, plural in singular_to_plural.items():
            values: list[str] = []
            for contribution in contributions:
                item_value = contribution.evidence_item.metadata.get(singular)
                if isinstance(item_value, str) and item_value and item_value not in values:
                    values.append(item_value)
                set_values = contribution.evidence_set.metadata.get(plural, ())
                if isinstance(set_values, Sequence) and not isinstance(set_values, str):
                    for value in cast(Sequence[object], set_values):
                        if isinstance(value, str) and value and value not in values:
                            values.append(value)
            output[plural] = tuple(values)
        return output

    def _rule_and_mapping(
        self,
        signal: EvidenceSignal,
    ) -> tuple[RecordingTransitionRule | None, RecordingTransitionMapping | None]:
        mapping = mapping_for_recording_signal(signal)
        rule = self._rule_for_signal(signal)
        if mapping is None or rule is None or rule.proposed_state is not mapping.proposed_state:
            return None, None
        return rule, mapping

    def _rule_for_signal(
        self,
        signal: EvidenceSignal,
    ) -> RecordingTransitionRule | None:
        for rule in self.rules:
            if rule.evidence_signal is signal:
                return rule
        return None

    def _evidence_order_key(
        self,
        evidence_set: EvidenceSet,
        context: RecordingTransitionContext,
        input_index: int,
    ) -> tuple[int, float, int, float, str, int]:
        timeline_end = (
            context.timeline_range_seconds[1]
            if context.timeline_range_seconds is not None
            else 0.0
        )
        evidence_timestamp = self._aware_timestamp(evidence_set.created_at)
        return (
            0 if context.timeline_range_seconds is not None else 1,
            timeline_end,
            0 if evidence_timestamp is not None else 1,
            evidence_timestamp if evidence_timestamp is not None else 0.0,
            evidence_set.id.to_json(),
            input_index,
        )

    def _unique_contributions(
        self,
        contributions: tuple[_SignalContribution, ...],
    ) -> tuple[_SignalContribution, ...]:
        by_key: dict[tuple[str, str, str], _SignalContribution] = {}
        for contribution in contributions:
            by_key.setdefault(contribution.key, contribution)
        return tuple(
            by_key[key]
            for key in sorted(by_key)
        )

    def _contribution_identity_key(
        self,
        contribution: _SignalContribution,
    ) -> tuple[str, str, str]:
        return contribution.key

    def _metadata_entity(self, metadata: Mapping[str, Any], key: str) -> EntityId | None:
        value = metadata.get(key)
        if isinstance(value, EntityId):
            return value
        if isinstance(value, str):
            return self._entity_id(value)
        return None

    def _entity_id(self, value: str) -> EntityId | None:
        try:
            return EntityId.parse(value)
        except ValueError:
            return None

    def _number(self, value: object) -> float | None:
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        number = float(value)
        return number if isfinite(number) else None

    def _mapping_value(self, value: object, key: str) -> object | None:
        if not isinstance(value, Mapping):
            return None
        mapping = cast(Mapping[object, object], value)
        return mapping.get(key)

    def _metadata_timestamp(self, value: object) -> float | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return self._aware_timestamp(parsed)

    def _aware_timestamp(self, value: datetime) -> float | None:
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.timestamp()

    def _context_metadata(
        self,
        context: RecordingTransitionContext | None,
    ) -> Mapping[str, Any] | None:
        if context is None:
            return None
        return {
            "recording_block_id": (
                context.recording_block_id.to_json()
                if context.recording_block_id is not None
                else None
            ),
            "stage_id": context.stage_id.to_json() if context.stage_id is not None else None,
            "correlation_id": (
                context.correlation_id.to_json()
                if context.correlation_id is not None
                else None
            ),
            "media_artifact_id": context.media_artifact_id,
            "source_evidence_set_id": (
                context.source_evidence_set_id.to_json()
                if context.source_evidence_set_id is not None
                else None
            ),
            "timeline_range_seconds": context.timeline_range_seconds,
            "organizational_at": (
                context.organizational_at.isoformat()
                if context.organizational_at is not None
                else None
            ),
        }
