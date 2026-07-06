from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.production.timeline import (
    LivestreamStatus,
    RecordingBlock,
    RecordingStatus,
    ScheduleReference,
    SessionWindow,
    SessionWindowStatus,
    TimelinePosition,
    TimelineRange,
    VerificationStatus,
)
from app.shared.ids import CorrelationId, EntityId


def test_recording_block_creation() -> None:
    block = RecordingBlock(
        id=EntityId.new(),
        stage_id=EntityId.new(),
        label="Main Stage morning recording block",
        planned_start=datetime(2026, 7, 6, 9, 0, tzinfo=UTC),
        planned_end=datetime(2026, 7, 6, 12, 0, tzinfo=UTC),
        correlation_id=CorrelationId.new(),
        recording_status=RecordingStatus.READY,
        livestream_status=LivestreamStatus.NOT_STARTED,
    )

    assert block.label == "Main Stage morning recording block"
    assert block.recording_status is RecordingStatus.READY
    assert block.livestream_status is LivestreamStatus.NOT_STARTED


def test_recording_block_status_values() -> None:
    assert {status.value for status in RecordingStatus} == {
        "planned",
        "ready",
        "recording",
        "paused",
        "completed",
        "failed",
        "archived",
    }
    assert {status.value for status in LivestreamStatus} == {
        "not_started",
        "live",
        "interrupted",
        "ended",
        "unknown",
    }


def test_timeline_position_rejects_negative_offsets() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        TimelinePosition(
            recording_block_id=EntityId.new(),
            offset=timedelta(seconds=-1),
        )


def test_timeline_position_comparison() -> None:
    recording_block_id = EntityId.new()
    first = TimelinePosition(recording_block_id, timedelta(minutes=1))
    second = TimelinePosition(recording_block_id, timedelta(minutes=2))

    assert first < second
    assert sorted([second, first]) == [first, second]


def test_timeline_range_requires_same_recording_block() -> None:
    start = TimelinePosition(EntityId.new(), timedelta(minutes=1))
    end = TimelinePosition(EntityId.new(), timedelta(minutes=2))

    with pytest.raises(ValueError, match="same RecordingBlock"):
        TimelineRange(start=start, end=end)


def test_timeline_range_rejects_end_before_start() -> None:
    recording_block_id = EntityId.new()
    start = TimelinePosition(recording_block_id, timedelta(minutes=3))
    end = TimelinePosition(recording_block_id, timedelta(minutes=2))

    with pytest.raises(ValueError, match="end must be after start"):
        TimelineRange(start=start, end=end)


def test_timeline_range_duration_calculation() -> None:
    recording_block_id = EntityId.new()
    time_range = TimelineRange(
        start=TimelinePosition(recording_block_id, timedelta(minutes=4)),
        end=TimelinePosition(recording_block_id, timedelta(minutes=9, seconds=30)),
    )

    assert time_range.recording_block_id == recording_block_id
    assert time_range.duration == timedelta(minutes=5, seconds=30)


def test_schedule_reference_uses_generic_external_identifiers() -> None:
    reference = ScheduleReference(
        external_system_id=EntityId.new(),
        external_schedule_id="external-session-123",
        external_version="revision-7",
        source_label="Published schedule",
    )

    assert reference.external_schedule_id == "external-session-123"
    assert reference.external_version == "revision-7"
    assert reference.source_label == "Published schedule"
    assert "provider_specific_id" not in {field.name for field in fields(ScheduleReference)}


def test_session_window_confidence_validation() -> None:
    recording_block_id = EntityId.new()
    timeline_range = TimelineRange(
        start=TimelinePosition(recording_block_id, timedelta(minutes=10)),
        end=TimelinePosition(recording_block_id, timedelta(minutes=20)),
    )

    with pytest.raises(ValueError, match="confidence"):
        SessionWindow(
            id=EntityId.new(),
            schedule_reference=ScheduleReference(EntityId.new(), "external-session-123"),
            recording_block_id=recording_block_id,
            timeline_range=timeline_range,
            correlation_id=CorrelationId.new(),
            confidence=1.1,
        )


def test_session_window_can_represent_proposed_and_verified_windows() -> None:
    recording_block_id = EntityId.new()
    timeline_range = TimelineRange(
        start=TimelinePosition(recording_block_id, timedelta(minutes=10)),
        end=TimelinePosition(recording_block_id, timedelta(minutes=45)),
    )
    schedule_reference = ScheduleReference(EntityId.new(), "external-session-123")

    proposed = SessionWindow(
        id=EntityId.new(),
        schedule_reference=schedule_reference,
        recording_block_id=recording_block_id,
        timeline_range=timeline_range,
        correlation_id=CorrelationId.new(),
        confidence=0.65,
    )
    verified = SessionWindow(
        id=EntityId.new(),
        schedule_reference=schedule_reference,
        recording_block_id=recording_block_id,
        timeline_range=timeline_range,
        correlation_id=CorrelationId.new(),
        window_status=SessionWindowStatus.VERIFIED,
        verification_status=VerificationStatus.HUMAN_VERIFIED,
        confidence=1.0,
    )

    assert proposed.window_status is SessionWindowStatus.PROPOSED
    assert proposed.verification_status is VerificationStatus.UNVERIFIED
    assert verified.window_status is SessionWindowStatus.VERIFIED
    assert verified.verification_status is VerificationStatus.HUMAN_VERIFIED


def test_timeline_contracts_have_no_file_or_media_chunk_assumptions() -> None:
    contract_fields = {
        field.name
        for contract in (
            RecordingBlock,
            TimelinePosition,
            TimelineRange,
            ScheduleReference,
            SessionWindow,
        )
        for field in fields(contract)
    }

    forbidden_terms = ("file", "path", "chunk", "codec", "provider_specific")

    assert not any(term in field_name for field_name in contract_fields for term in forbidden_terms)
