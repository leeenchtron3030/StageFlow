from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
)
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateKind,
    OperationalStateValue,
)
from app.contexts.production.recording_transition_policy.recording_transition_mapping import (
    RECORDING_TRANSITION_MAPPINGS,
    mapping_for_recording_marker,
    mapping_for_recording_signal,
)
from app.contexts.production.recording_transition_policy.recording_transition_rule import (
    RecordingTransitionRule,
)
from app.contexts.production.transition_policy import (
    TransitionEvaluation,
    TransitionPolicyResult,
    TransitionReason,
)
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def default_recording_transition_rules() -> tuple[RecordingTransitionRule, ...]:
    return tuple(
        RecordingTransitionRule(
            id=EntityId.new(),
            evidence_signal=mapping.evidence_signal,
            proposed_state=mapping.proposed_state,
            legacy_evidence_marker=mapping.legacy_evidence_marker,
            description=mapping.rationale,
        )
        for mapping in RECORDING_TRANSITION_MAPPINGS
    )


@dataclass(frozen=True, slots=True)
class RecordingTransitionPolicy:
    """Deterministic policy for evaluating recording Operational State transitions."""

    id: EntityId
    name: str = "Recording Transition Policy"
    rules: Sequence[RecordingTransitionRule] = field(
        default_factory=default_recording_transition_rules
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("RecordingTransitionPolicy name must not be empty.")
        object.__setattr__(self, "rules", tuple(self.rules))
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
        recording_evidence = tuple(
            evidence_set
            for evidence_set in evidence_sets
            if evidence_set.concern is EvidenceConcern.RECORDING_COVERAGE
        )
        examined_ids = tuple(evidence_set.id.to_json() for evidence_set in recording_evidence)
        examined_signal_values = self._examined_signal_values(recording_evidence)

        if not recording_evidence:
            return self._evaluation(
                current_state=current_state,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                supporting_evidence=(),
                blocking_evidence=(),
                rationale="Recording Evidence incomplete.",
                examined_ids=examined_ids,
                examined_signal_values=examined_signal_values,
            )

        blocking_evidence = self._blocking_evidence(recording_evidence)
        if blocking_evidence:
            return self._evaluation(
                current_state=current_state,
                proposed_state=None,
                outcome=TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
                supporting_evidence=(),
                blocking_evidence=blocking_evidence,
                rationale="Recording Evidence argues against transition.",
                examined_ids=examined_ids,
                examined_signal_values=examined_signal_values,
            )

        supported = self._supported_evidence(recording_evidence)
        if not supported:
            return self._evaluation(
                current_state=current_state,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                supporting_evidence=(),
                blocking_evidence=(),
                rationale="Recording Evidence incomplete.",
                examined_ids=examined_ids,
                examined_signal_values=examined_signal_values,
            )

        proposed_state, supporting_evidence, rationale = self._proposed_state(supported)
        if proposed_state is None:
            return self._evaluation(
                current_state=current_state,
                proposed_state=None,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
                supporting_evidence=(),
                blocking_evidence=(),
                rationale="Recording Evidence missing a supported recording transition Signal.",
                examined_ids=examined_ids,
                examined_signal_values=examined_signal_values,
            )

        if current_state is not None and current_state.value is proposed_state:
            return self._evaluation(
                current_state=current_state,
                proposed_state=proposed_state,
                outcome=TransitionPolicyResult.ALREADY_CURRENT,
                supporting_evidence=supporting_evidence,
                blocking_evidence=(),
                rationale="Current recording state already matches supported Evidence.",
                examined_ids=examined_ids,
                examined_signal_values=examined_signal_values,
            )

        return self._evaluation(
            current_state=current_state,
            proposed_state=proposed_state,
            outcome=TransitionPolicyResult.TRANSITION_SUPPORTED,
            supporting_evidence=supporting_evidence,
            blocking_evidence=(),
            rationale=rationale,
            examined_ids=examined_ids,
            examined_signal_values=examined_signal_values,
        )

    def _blocking_evidence(
        self,
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[EvidenceSet, ...]:
        return tuple(
            evidence_set
            for evidence_set in evidence_sets
            if any(item.role is EvidenceRole.CONTRADICTS for item in evidence_set.items)
        )

    def _supported_evidence(
        self,
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[EvidenceSet, ...]:
        return tuple(
            evidence_set
            for evidence_set in evidence_sets
            if any(item.role is EvidenceRole.SUPPORTS for item in evidence_set.items)
        )

    def _proposed_state(
        self,
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[OperationalStateValue | None, tuple[EvidenceSet, ...], str]:
        for rule in self.rules:
            matching_evidence = tuple(
                evidence_set
                for evidence_set in evidence_sets
                if self._evidence_has_signal(evidence_set, rule.evidence_signal)
            )
            if matching_evidence:
                mapping = mapping_for_recording_signal(rule.evidence_signal)
                rationale = mapping.rationale if mapping is not None else rule.description
                return (
                    rule.proposed_state,
                    matching_evidence,
                    rationale or "Recording Evidence supports transition.",
                )

            legacy_evidence_marker = rule.legacy_evidence_marker
            if legacy_evidence_marker is None:
                continue
            legacy_matching_evidence = tuple(
                evidence_set
                for evidence_set in evidence_sets
                if not evidence_set.signals
                and evidence_set.metadata.get("recording_transition_marker")
                == legacy_evidence_marker
            )
            if legacy_matching_evidence:
                mapping = mapping_for_recording_marker(legacy_evidence_marker)
                rationale = mapping.rationale if mapping is not None else rule.description
                return (
                    rule.proposed_state,
                    legacy_matching_evidence,
                    rationale or "Recording Evidence supports transition.",
                )
        return None, (), ""

    def _evidence_has_signal(
        self,
        evidence_set: EvidenceSet,
        evidence_signal: EvidenceSignal,
    ) -> bool:
        return any(
            signal_reference.signal is evidence_signal
            for signal_reference in evidence_set.signals
        )

    def _evaluation(
        self,
        *,
        current_state: OperationalState | None,
        proposed_state: OperationalStateValue | None,
        outcome: TransitionPolicyResult,
        supporting_evidence: tuple[EvidenceSet, ...],
        blocking_evidence: tuple[EvidenceSet, ...],
        rationale: str,
        examined_ids: tuple[str, ...],
        examined_signal_values: tuple[str, ...],
    ) -> TransitionEvaluation:
        return TransitionEvaluation(
            id=EntityId.new(),
            evaluated_state_kind=self.evaluated_state_kind,
            current_state=current_state,
            proposed_state=proposed_state,
            outcome=outcome,
            supporting_evidence_ids=tuple(
                evidence_set.id for evidence_set in supporting_evidence
            ),
            blocking_evidence_ids=tuple(
                evidence_set.id for evidence_set in blocking_evidence
            ),
            rationale=TransitionReason(rationale),
            metadata={
                "policy_id": self.id.to_json(),
                "examined_evidence_ids": examined_ids,
                "examined_signal_values": examined_signal_values,
            },
        )

    def _examined_signal_values(
        self,
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[str, ...]:
        return tuple(
            signal_reference.signal.value
            for evidence_set in evidence_sets
            for signal_reference in evidence_set.signals
        )
