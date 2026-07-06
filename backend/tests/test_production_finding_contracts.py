from dataclasses import fields
from datetime import timedelta

import pytest

from app.contexts.production.finding import (
    Finding,
    FindingConfidence,
    FindingLocation,
    FindingOrigin,
    FindingSummary,
    FindingSupport,
    FindingType,
)
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId


def _position(recording_block_id: EntityId, seconds: int) -> TimelinePosition:
    return TimelinePosition(
        recording_block_id=recording_block_id,
        offset=timedelta(seconds=seconds),
    )


def _support() -> FindingSupport:
    return FindingSupport(supporting_hypothesis_ids=[EntityId.new()])


def test_finding_creation() -> None:
    recording_block_id = EntityId.new()
    finding = Finding(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        finding_type=FindingType.POSSIBLE_SESSION_BOUNDARY,
        confidence=FindingConfidence(0.74),
        origin=FindingOrigin.MULTI_SOURCE_REASONING,
        location=FindingLocation.at_point(_position(recording_block_id, 272)),
        support=_support(),
        correlation_id=CorrelationId.new(),
        notes="Worth human attention.",
        metadata={"summary": "possible boundary"},
    )

    assert finding.recording_block_id == recording_block_id
    assert finding.finding_type is FindingType.POSSIBLE_SESSION_BOUNDARY
    assert finding.confidence.value == 0.74
    assert finding.origin is FindingOrigin.MULTI_SOURCE_REASONING
    assert finding.support.supporting_count == 1
    assert dict(finding.metadata) == {"summary": "possible boundary"}


def test_finding_confidence_validation() -> None:
    assert FindingConfidence(0.0).value == 0.0
    assert FindingConfidence(1.0).value == 1.0
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        FindingConfidence(-0.01)
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        FindingConfidence(1.01)


def test_finding_type_values() -> None:
    assert {finding_type.value for finding_type in FindingType} == {
        "possible_session_boundary",
        "editorial_moment",
        "technical_incident",
        "schedule_conflict",
        "metadata_event",
        "alert_condition",
        "unknown",
    }


def test_finding_origin_values() -> None:
    assert {origin.value for origin in FindingOrigin} == {
        "human_review",
        "schedule_reasoning",
        "transcript_reasoning",
        "graphics_reasoning",
        "audio_reasoning",
        "multi_source_reasoning",
        "unknown",
    }


def test_finding_location_using_timeline_position() -> None:
    recording_block_id = EntityId.new()
    location = FindingLocation.at_point(_position(recording_block_id, 15))

    assert location.is_point
    assert not location.is_range
    assert location.recording_block_id == recording_block_id
    assert location.summary() == "point:15.000s"


def test_finding_location_using_timeline_range() -> None:
    recording_block_id = EntityId.new()
    location = FindingLocation.over_range(
        TimelineRange(
            start=_position(recording_block_id, 15),
            end=_position(recording_block_id, 45),
        )
    )

    assert location.is_range
    assert not location.is_point
    assert location.recording_block_id == recording_block_id
    assert location.summary() == "range:15.000s-45.000s"


def test_finding_location_requires_exactly_one_shape() -> None:
    recording_block_id = EntityId.new()
    with pytest.raises(ValueError, match="exactly one"):
        FindingLocation()
    with pytest.raises(ValueError, match="exactly one"):
        FindingLocation(
            point=_position(recording_block_id, 15),
            range=TimelineRange(
                start=_position(recording_block_id, 15),
                end=_position(recording_block_id, 45),
            ),
        )


def test_finding_support_references_hypothesis_ids() -> None:
    supporting_id = EntityId.new()
    contradicting_id = EntityId.new()
    neutral_id = EntityId.new()
    support = FindingSupport(
        supporting_hypothesis_ids=[supporting_id],
        contradicting_hypothesis_ids=[contradicting_id],
        neutral_hypothesis_ids=[neutral_id],
    )

    assert support.supporting_hypothesis_ids == (supporting_id,)
    assert support.contradicting_hypothesis_ids == (contradicting_id,)
    assert support.neutral_hypothesis_ids == (neutral_id,)
    assert support.supporting_count == 1
    assert support.contradicting_count == 1
    assert support.total_count == 3
    assert "hypotheses" not in {field.name for field in fields(FindingSupport)}


def test_finding_rejects_location_from_different_recording_block() -> None:
    with pytest.raises(ValueError, match="recording_block_id"):
        Finding(
            id=EntityId.new(),
            recording_block_id=EntityId.new(),
            finding_type=FindingType.UNKNOWN,
            confidence=FindingConfidence(0.1),
            origin=FindingOrigin.UNKNOWN,
            location=FindingLocation.at_point(_position(EntityId.new(), 15)),
            support=_support(),
            correlation_id=CorrelationId.new(),
        )


def test_finding_requires_hypothesis_support() -> None:
    recording_block_id = EntityId.new()
    with pytest.raises(ValueError, match="Hypothesis ID reference"):
        Finding(
            id=EntityId.new(),
            recording_block_id=recording_block_id,
            finding_type=FindingType.UNKNOWN,
            confidence=FindingConfidence(0.0),
            origin=FindingOrigin.UNKNOWN,
            location=FindingLocation.at_point(_position(recording_block_id, 15)),
            support=FindingSupport(),
            correlation_id=CorrelationId.new(),
        )


def test_finding_summary_generation() -> None:
    recording_block_id = EntityId.new()
    finding = Finding(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        finding_type=FindingType.TECHNICAL_INCIDENT,
        confidence=FindingConfidence(0.8),
        origin=FindingOrigin.AUDIO_REASONING,
        location=FindingLocation.at_point(_position(recording_block_id, 90)),
        support=FindingSupport(
            supporting_hypothesis_ids=[EntityId.new(), EntityId.new()],
            contradicting_hypothesis_ids=[EntityId.new()],
        ),
        correlation_id=CorrelationId.new(),
    )

    summary = FindingSummary.from_finding(finding)

    assert summary.finding_id == finding.id
    assert summary.finding_type is FindingType.TECHNICAL_INCIDENT
    assert summary.confidence == finding.confidence
    assert summary.origin is FindingOrigin.AUDIO_REASONING
    assert summary.timeline_location_summary == "point:90.000s"
    assert summary.supporting_hypothesis_count == 2
    assert summary.contradicting_hypothesis_count == 1


def test_provider_agnostic_naming() -> None:
    enum_values = {finding_type.value for finding_type in FindingType} | {
        origin.value for origin in FindingOrigin
    }
    field_names = {field.name for field in fields(Finding)} | {
        field.name for field in fields(FindingSupport)
    }
    forbidden_terms = {
        "provider",
        "vendor",
        "tool",
        "brand",
        "conference",
    }

    assert not any(term in value for value in enum_values | field_names for term in forbidden_terms)


def test_no_verification_or_workflow_behavior_present() -> None:
    field_names = {field.name for field in fields(Finding)} | {
        field.name for field in fields(FindingSummary)
    }
    forbidden_terms = {
        "verification",
        "workflow",
        "_".join(("review", "state")),
        "reviewer",
        "_".join(("session", "window")),
        "clip",
        "package",
    }

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)
