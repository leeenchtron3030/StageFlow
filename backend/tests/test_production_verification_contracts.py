from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.contexts.production.verification import (
    VerificationAction,
    VerificationActor,
    VerificationActorType,
    VerificationAdjustment,
    VerificationAdjustmentType,
    VerificationDecision,
    VerificationNote,
    VerificationNoteVisibility,
    VerificationReason,
    VerificationSummary,
)
from app.shared.ids import CorrelationId, EntityId


def _actor() -> VerificationActor:
    return VerificationActor(
        actor_id=EntityId.new(),
        actor_type=VerificationActorType.HUMAN,
        display_name="Reviewer",
        role_label="operator",
    )


def _decision(
    finding_id: EntityId,
    action: VerificationAction,
    decided_at: datetime,
) -> VerificationDecision:
    return VerificationDecision(
        id=EntityId.new(),
        finding_id=finding_id,
        action=action,
        reason=VerificationReason.OTHER,
        actor=_actor(),
        correlation_id=CorrelationId.new(),
        decided_at=decided_at,
    )


def _position(recording_block_id: EntityId, seconds: int) -> TimelinePosition:
    return TimelinePosition(
        recording_block_id=recording_block_id,
        offset=timedelta(seconds=seconds),
    )


def test_verification_decision_creation() -> None:
    finding_id = EntityId.new()
    decided_at = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    decision = VerificationDecision(
        id=EntityId.new(),
        finding_id=finding_id,
        action=VerificationAction.ACCEPT,
        reason=VerificationReason.OPERATOR_CONFIRMATION,
        actor=_actor(),
        correlation_id=CorrelationId.new(),
        decided_at=decided_at,
        note=VerificationNote("Looks correct.", VerificationNoteVisibility.REVIEWER),
        metadata={"source": "manual"},
    )

    assert decision.finding_id == finding_id
    assert decision.action is VerificationAction.ACCEPT
    assert decision.reason is VerificationReason.OPERATOR_CONFIRMATION
    assert decision.decided_at == decided_at
    assert decision.note is not None
    assert dict(decision.metadata) == {"source": "manual"}


def test_verification_decision_references_finding_id_only() -> None:
    field_names = {field.name for field in fields(VerificationDecision)}

    assert "finding_id" in field_names
    assert "finding" not in field_names


def test_verification_action_allowed_values() -> None:
    assert {action.value for action in VerificationAction} == {
        "accept",
        "reject",
        "adjust",
        "merge",
        "split",
        "defer",
        "escalate",
        "annotate",
        "supersede",
    }


def test_verification_action_does_not_include_verified() -> None:
    assert "verified" not in {action.value for action in VerificationAction}


def test_verification_reason_allowed_values() -> None:
    assert {reason.value for reason in VerificationReason} == {
        "operator_confirmation",
        "schedule_alignment",
        "editorial_review",
        "technical_review",
        "insufficient_evidence",
        "duplicate_finding",
        "manual_adjustment",
        "conflicting_evidence",
        "quality_issue",
        "other",
    }


def test_verification_actor_creation() -> None:
    actor_id = EntityId.new()
    actor = VerificationActor(
        actor_id=actor_id,
        actor_type=VerificationActorType.APPROVED_SYSTEM,
        display_name="Boundary assistant",
        role_label="system",
    )

    assert actor.actor_id == actor_id
    assert actor.actor_type is VerificationActorType.APPROVED_SYSTEM
    assert actor.display_name == "Boundary assistant"
    assert actor.role_label == "system"


def test_verification_adjustment_for_timeline_position() -> None:
    recording_block_id = EntityId.new()
    position = _position(recording_block_id, 120)
    adjustment = VerificationAdjustment(
        adjustment_type=VerificationAdjustmentType.ADJUST_START,
        adjusted_position=position,
        rationale="Start appears slightly later.",
    )

    assert adjustment.adjustment_type is VerificationAdjustmentType.ADJUST_START
    assert adjustment.adjusted_position == position
    assert adjustment.adjusted_range is None


def test_verification_adjustment_for_timeline_range() -> None:
    recording_block_id = EntityId.new()
    time_range = TimelineRange(
        start=_position(recording_block_id, 120),
        end=_position(recording_block_id, 180),
    )
    adjustment = VerificationAdjustment(
        adjustment_type=VerificationAdjustmentType.ADJUST_RANGE,
        adjusted_range=time_range,
    )

    assert adjustment.adjustment_type is VerificationAdjustmentType.ADJUST_RANGE
    assert adjustment.adjusted_range == time_range
    assert adjustment.adjusted_position is None


def test_verification_adjustment_for_merge_target_ids() -> None:
    target_ids = [EntityId.new(), EntityId.new()]
    adjustment = VerificationAdjustment(
        adjustment_type=VerificationAdjustmentType.MERGE_FINDINGS,
        target_finding_ids=target_ids,
    )

    assert adjustment.target_finding_ids == tuple(target_ids)


def test_verification_note_creation() -> None:
    note = VerificationNote("Needs a closer look.", VerificationNoteVisibility.INTERNAL)

    assert note.text == "Needs a closer look."
    assert note.visibility is VerificationNoteVisibility.INTERNAL
    with pytest.raises(ValueError, match="must not be empty"):
        VerificationNote("")


def test_verification_summary_counts_decisions() -> None:
    finding_id = EntityId.new()
    decisions = [
        _decision(finding_id, VerificationAction.ACCEPT, datetime(2026, 7, 6, 12, 0, tzinfo=UTC)),
        _decision(finding_id, VerificationAction.ANNOTATE, datetime(2026, 7, 6, 12, 5, tzinfo=UTC)),
        _decision(
            EntityId.new(),
            VerificationAction.REJECT,
            datetime(2026, 7, 6, 12, 6, tzinfo=UTC),
        ),
    ]

    summary = VerificationSummary.from_decisions(finding_id, decisions)

    assert summary.decision_count == 2
    assert summary.count_by_action[VerificationAction.ACCEPT] == 1
    assert summary.count_by_action[VerificationAction.ANNOTATE] == 1
    assert summary.latest_action is VerificationAction.ANNOTATE


def test_verification_summary_detects_decision_categories() -> None:
    finding_id = EntityId.new()
    decisions = [
        _decision(finding_id, VerificationAction.ACCEPT, datetime(2026, 7, 6, 12, 0, tzinfo=UTC)),
        _decision(finding_id, VerificationAction.REJECT, datetime(2026, 7, 6, 12, 1, tzinfo=UTC)),
        _decision(finding_id, VerificationAction.ADJUST, datetime(2026, 7, 6, 12, 2, tzinfo=UTC)),
        _decision(finding_id, VerificationAction.ESCALATE, datetime(2026, 7, 6, 12, 3, tzinfo=UTC)),
    ]

    summary = VerificationSummary.from_decisions(finding_id, decisions)

    assert summary.has_accept_decision
    assert summary.has_reject_decision
    assert summary.has_adjustment_decision
    assert summary.has_escalation_decision
    assert summary.latest_decided_at == datetime(2026, 7, 6, 12, 3, tzinfo=UTC)


def test_verification_summary_does_not_produce_final_outcome() -> None:
    summary_fields = {field.name for field in fields(VerificationSummary)}
    forbidden_outcome_field = "_".join(("final", "outcome"))
    forbidden_status_field = "status"

    assert forbidden_outcome_field not in summary_fields
    assert forbidden_status_field not in summary_fields


def test_no_finding_mutation_behavior_exists() -> None:
    decision_fields = {field.name for field in fields(VerificationDecision)}
    adjustment_fields = {field.name for field in fields(VerificationAdjustment)}
    forbidden_terms = {
        "_".join(("finding", "status")),
        "".join(("mut", "ate")),
        "_".join(("update", "finding")),
        "apply",
    }

    assert not any(
        term in field_name
        for field_name in decision_fields | adjustment_fields
        for term in forbidden_terms
    )


def test_no_operational_product_creation_exists() -> None:
    field_names = {field.name for field in fields(VerificationDecision)} | {
        field.name for field in fields(VerificationAdjustment)
    }
    forbidden_terms = {
        "_".join(("session", "window")),
        "clip",
        "alert",
        "incident",
        "package",
        "task",
        "product",
    }

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_provider_specific_names_appear() -> None:
    enum_values = (
        {action.value for action in VerificationAction}
        | {reason.value for reason in VerificationReason}
        | {actor_type.value for actor_type in VerificationActorType}
        | {visibility.value for visibility in VerificationNoteVisibility}
    )
    forbidden_terms = {
        "provider",
        "vendor",
        "tool",
        "brand",
        "conference",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
