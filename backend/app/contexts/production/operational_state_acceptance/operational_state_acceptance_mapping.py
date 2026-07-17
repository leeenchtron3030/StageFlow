from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from app.contexts.production.evidence import EvidenceSignal
from app.contexts.production.operational_state import (
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.contexts.production.recording_transition_policy.recording_transition_policy import (
    recording_transition_rule_id,
)
from app.contexts.production.session_transition_policy import SESSION_TRANSITION_RULES
from app.shared.ids import EntityId

from .operational_state_acceptance_rule import OperationalStateAcceptanceRule

RECORDING_TRANSITION_POLICY_KIND = "recording_transition_policy"
SESSION_TRANSITION_POLICY_KIND = "session_transition_policy"

_REQUIRED_LINEAGE_FIELDS = (
    "policy_id",
    "applied_rule_id",
    "supporting_evidence_set_ids",
    "contributing_evidence_item_ids",
    "contributing_observation_ids",
    "contributing_production_event_ids",
)


def _stable_id(name: str) -> EntityId:
    return EntityId.parse(str(uuid5(NAMESPACE_URL, f"stageflow:state-acceptance:{name}")))


def _rule(
    *,
    policy_kind: str,
    transition_rule_id: EntityId,
    state_kind: OperationalStateKind,
    current: OperationalStateValue,
    proposed: OperationalStateValue,
    subjects: tuple[OperationalStateSubjectType, ...],
    family: OperationalStateFamily,
) -> OperationalStateAcceptanceRule:
    return OperationalStateAcceptanceRule(
        id=_stable_id(
            f"{policy_kind}:{transition_rule_id.to_json()}:{current.value}:{proposed.value}"
        ),
        supported_policy_kind=policy_kind,
        supported_transition_rule_id=transition_rule_id,
        state_kind=state_kind,
        effective_current_value=current,
        proposed_value=proposed,
        required_subject_types=subjects,
        required_state_family=family,
        current_state_required=current is not OperationalStateValue.INACTIVE,
        supersession_expected=current is not OperationalStateValue.INACTIVE,
        required_lineage_fields=_REQUIRED_LINEAGE_FIELDS,
        rationale=(
            f"{policy_kind} rule permits {state_kind.value} "
            f"{current.value} to {proposed.value} acceptance."
        ),
    )


_RECORDING_SUBJECTS = (
    OperationalStateSubjectType.RECORDING_BLOCK,
    OperationalStateSubjectType.MEDIA_ARTIFACT,
    OperationalStateSubjectType.STAGEFLOW,
)
_SESSION_SUBJECTS = (
    OperationalStateSubjectType.SESSION_CANDIDATE,
    OperationalStateSubjectType.RECORDING_BLOCK,
)

_RECORDING_ACCEPTANCE_SPECS = (
    (
        EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        OperationalStateValue.INACTIVE,
        OperationalStateValue.ACTIVE,
    ),
    (
        EvidenceSignal.RECORDING_PAUSE_INDICATED,
        OperationalStateValue.ACTIVE,
        OperationalStateValue.PAUSED,
    ),
    (
        EvidenceSignal.RECORDING_CONTINUITY_RESTORED,
        OperationalStateValue.PAUSED,
        OperationalStateValue.ACTIVE,
    ),
    (
        EvidenceSignal.RECORDING_END_INDICATED,
        OperationalStateValue.ACTIVE,
        OperationalStateValue.STOPPED,
    ),
    (
        EvidenceSignal.RECORDING_END_INDICATED,
        OperationalStateValue.PAUSED,
        OperationalStateValue.STOPPED,
    ),
)

RECORDING_ACCEPTANCE_RULES = tuple(
    _rule(
        policy_kind=RECORDING_TRANSITION_POLICY_KIND,
        transition_rule_id=recording_transition_rule_id(signal),
        state_kind=OperationalStateKind.RECORDING_STATE,
        current=current,
        proposed=proposed,
        subjects=_RECORDING_SUBJECTS,
        family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
    )
    for signal, current, proposed in _RECORDING_ACCEPTANCE_SPECS
)

SESSION_ACCEPTANCE_RULES = tuple(
    _rule(
        policy_kind=SESSION_TRANSITION_POLICY_KIND,
        transition_rule_id=rule.id,
        state_kind=OperationalStateKind.SESSION_STATE,
        current=rule.current_state_value,
        proposed=rule.proposed_state_value,
        subjects=_SESSION_SUBJECTS,
        family=OperationalStateFamily.EVIDENCE_DERIVED,
    )
    for rule in SESSION_TRANSITION_RULES
    if rule.current_state_value is not rule.proposed_state_value
)

OPERATIONAL_STATE_ACCEPTANCE_RULES = (
    *RECORDING_ACCEPTANCE_RULES,
    *SESSION_ACCEPTANCE_RULES,
)

_FAMILY_BY_KIND = {
    OperationalStateKind.RECORDING_STATE: OperationalStateFamily.DIRECTLY_OBSERVABLE,
    OperationalStateKind.SESSION_STATE: OperationalStateFamily.EVIDENCE_DERIVED,
}
_POLICY_BY_KIND = {
    OperationalStateKind.RECORDING_STATE: RECORDING_TRANSITION_POLICY_KIND,
    OperationalStateKind.SESSION_STATE: SESSION_TRANSITION_POLICY_KIND,
}
_SUBJECTS_BY_KIND = {
    OperationalStateKind.RECORDING_STATE: _RECORDING_SUBJECTS,
    OperationalStateKind.SESSION_STATE: _SESSION_SUBJECTS,
}


def acceptance_rule_for(
    *,
    policy_kind: str,
    transition_rule_id: EntityId,
    state_kind: OperationalStateKind,
    effective_current_value: OperationalStateValue,
    proposed_value: OperationalStateValue,
) -> OperationalStateAcceptanceRule | None:
    for rule in OPERATIONAL_STATE_ACCEPTANCE_RULES:
        if (
            rule.supported_policy_kind == policy_kind
            and rule.supported_transition_rule_id == transition_rule_id
            and rule.state_kind is state_kind
            and rule.effective_current_value is effective_current_value
            and rule.proposed_value is proposed_value
        ):
            return rule
    return None


def state_family_for_kind(
    state_kind: OperationalStateKind,
) -> OperationalStateFamily | None:
    return _FAMILY_BY_KIND.get(state_kind)


def policy_kind_for_state_kind(state_kind: OperationalStateKind) -> str | None:
    return _POLICY_BY_KIND.get(state_kind)


def subject_types_for_kind(
    state_kind: OperationalStateKind,
) -> tuple[OperationalStateSubjectType, ...]:
    return _SUBJECTS_BY_KIND.get(state_kind, ())


def lifecycle_is_supported(
    state_kind: OperationalStateKind,
    current: OperationalStateValue,
    proposed: OperationalStateValue,
) -> bool:
    return any(
        rule.state_kind is state_kind
        and rule.effective_current_value is current
        and rule.proposed_value is proposed
        for rule in OPERATIONAL_STATE_ACCEPTANCE_RULES
    )
