from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from inspect import Parameter, signature
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import app
from app.contexts.production.dispatcher import DispatchContext
from app.contexts.production.evidence import EvidenceSet
from app.contexts.production.evidence_builder import EvidenceBuilderContext
from app.contexts.production.finding import Finding
from app.contexts.production.hypothesis import Hypothesis
from app.contexts.production.interpreter import InterpreterContext
from app.contexts.production.observation import Observation
from app.contexts.production.observation_interpreter import ObservationInterpreterContext
from app.contexts.production.operational_product import OperationalProduct
from app.contexts.production.operational_state import OperationalState
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.session_window_product import SessionWindowProduct
from app.contexts.production.timeline import RecordingBlock, SessionWindow
from app.contexts.production.transition_policy import TransitionEvaluation
from app.contexts.production.verification import VerificationDecision
from app.shared.domain_events import DomainEvent
from app.shared.ids import CorrelationId, EntityId
from app.shared.time import (
    FixedClock,
    TimeRange,
    normalize_utc_datetime,
    parse_aware_datetime,
    require_aware_datetime,
)


@pytest.mark.parametrize(
    ("contract", "field_names"),
    (
        (DomainEvent, ("occurred_at",)),
        (DispatchContext, ("timestamp",)),
        (EvidenceSet, ("created_at",)),
        (EvidenceBuilderContext, ("current_timestamp",)),
        (Finding, ("created_at",)),
        (Hypothesis, ("created_at",)),
        (InterpreterContext, ("current_timestamp",)),
        (Observation, ("observed_at",)),
        (ObservationInterpreterContext, ("current_timestamp",)),
        (OperationalProduct, ("created_at",)),
        (OperationalState, ("observed_or_derived_at",)),
        (ProductionEvent, ("occurred_at", "received_at")),
        (RecordingBlock, ("created_at",)),
        (SessionWindow, ("created_at", "updated_at")),
        (SessionWindowProduct, ("created_at",)),
        (TransitionEvaluation, ("evaluated_at",)),
        (VerificationDecision, ("decided_at",)),
    ),
)
def test_authoritative_contract_timestamps_have_no_implicit_default(
    contract: type[object], field_names: tuple[str, ...]
) -> None:
    parameters = signature(contract).parameters

    assert all(parameters[name].default is Parameter.empty for name in field_names)


def test_production_event_rejects_naive_occurrence_and_receipt_times() -> None:
    aware = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="occurred_at must be timezone-aware"):
        ProductionEvent(
            id=EntityId.new(),
            event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
            source=ProductionEventSource.INTERNAL_SYSTEM,
            payload=ProductionEventPayload(),
            correlation_id=CorrelationId.new(),
            occurred_at=aware.replace(tzinfo=None),
            received_at=aware,
        )
    with pytest.raises(ValueError, match="received_at must be timezone-aware"):
        ProductionEvent(
            id=EntityId.new(),
            event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
            source=ProductionEventSource.INTERNAL_SYSTEM,
            payload=ProductionEventPayload(),
            correlation_id=CorrelationId.new(),
            occurred_at=aware,
            received_at=aware.replace(tzinfo=None),
        )


def test_non_utc_offsets_remain_valid_and_compare_as_instants() -> None:
    offset = timezone(timedelta(hours=-7))
    occurred = datetime(2026, 8, 8, 5, 0, tzinfo=offset)
    received = datetime(2026, 8, 8, 12, 0, 1, tzinfo=UTC)

    event = ProductionEvent(
        id=EntityId.new(),
        event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
        source=ProductionEventSource.INTERNAL_SYSTEM,
        payload=ProductionEventPayload(),
        correlation_id=CorrelationId.new(),
        occurred_at=occurred,
        received_at=received,
    )

    assert event.occurred_at.utcoffset() == timedelta(hours=-7)
    assert event.received_at - event.occurred_at == timedelta(seconds=1)


def test_dst_fold_instants_normalize_without_losing_their_distinction() -> None:
    event_zone = ZoneInfo("America/Los_Angeles")
    first = datetime(2026, 11, 1, 1, 30, tzinfo=event_zone, fold=0)
    second = datetime(2026, 11, 1, 1, 30, tzinfo=event_zone, fold=1)

    first_utc = normalize_utc_datetime(first, "first")
    second_utc = normalize_utc_datetime(second, "second")

    assert second_utc - first_utc == timedelta(hours=1)
    assert first_utc.tzinfo is UTC
    assert second_utc.tzinfo is UTC


def test_time_values_and_fixed_clock_reject_naive_inputs() -> None:
    naive = datetime(2026, 8, 8, 12, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        require_aware_datetime(naive, "boundary")
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeRange(naive, naive + timedelta(seconds=1))


def test_legacy_metadata_parsers_fail_closed_for_naive_values() -> None:
    assert parse_aware_datetime("2026-08-08T12:00:00") is None
    assert parse_aware_datetime(datetime(2026, 8, 8, 12, 0)) is None
    assert parse_aware_datetime("2026-08-08T12:00:00+02:00") is not None


def test_system_clock_is_the_only_production_wall_clock_reader() -> None:
    app_root = Path(app.__file__).parent
    readers: list[str] = []
    silent_utc_attachment: list[str] = []
    for path in app_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "datetime.now(" in source:
            readers.append(path.relative_to(app_root).as_posix())
        if "replace(tzinfo=UTC)" in source:
            silent_utc_attachment.append(path.relative_to(app_root).as_posix())

    assert readers == ["shared/time/clock.py"]
    assert silent_utc_attachment == []
