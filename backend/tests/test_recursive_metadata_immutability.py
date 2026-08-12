from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, cast

import pytest

from app.contexts.production.interpreter import InterpreterContext
from app.contexts.production.observation import ObservationContext
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.recording_adapter import (
    RecordingSessionEvent,
    RecordingSessionEventKind,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


class _ExternalMutableEnum(Enum):
    VALUE = []


class _MetadataContract(Protocol):
    @property
    def metadata(self) -> Mapping[str, Any]: ...


type _MetadataConstructor = Callable[[dict[str, Any]], _MetadataContract]


def _event(metadata: dict[str, Any]) -> ProductionEvent:
    return ProductionEvent(
        id=EntityId.new(),
        event_type=ProductionEventType.RECORDING_BLOCK_STARTED,
        source=ProductionEventSource.RECORDING_SYSTEM,
        payload=ProductionEventPayload({}),
        correlation_id=CorrelationId.new(),
        occurred_at=NOW,
        received_at=NOW,
        metadata=metadata,
    )


def _observation_context(metadata: dict[str, Any]) -> ObservationContext:
    return ObservationContext(metadata=metadata)


def _interpreter_context(metadata: dict[str, Any]) -> InterpreterContext:
    return InterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=NOW,
        metadata=metadata,
    )


_METADATA_CONSTRUCTORS: tuple[_MetadataConstructor, ...] = (
    _event,
    _observation_context,
    _interpreter_context,
)


@pytest.mark.parametrize(
    "construct",
    _METADATA_CONSTRUCTORS,
)
def test_legacy_contract_boundaries_recursively_snapshot_metadata(
    construct: _MetadataConstructor,
) -> None:
    caller_items = ["before"]
    caller_mapping: dict[str, Any] = {"items": caller_items}
    caller_set = {"one"}
    value = construct(
        {
            "nested": caller_mapping,
            "labels": caller_set,
            "id": EntityId.new(),
            "observed_at": NOW,
        }
    )

    caller_items.append("after")
    caller_mapping["extra"] = True
    caller_set.add("two")

    nested = cast(Mapping[str, Any], value.metadata["nested"])
    assert isinstance(nested, MappingProxyType)
    assert nested["items"] == ("before",)
    assert "extra" not in nested
    assert value.metadata["labels"] == frozenset({"one"})


def test_frozen_stageflow_values_remain_compatible_metadata_values() -> None:
    adapter_event = RecordingSessionEvent(
        recording_system_identifier="recorder-a",
        event_kind=RecordingSessionEventKind.RECORDING_STARTED,
        occurred_at=NOW,
        metadata={"nested": {"labels": ["main"]}},
    )

    event = _event({"adapter_event": adapter_event})

    assert event.metadata["adapter_event"] is adapter_event


@pytest.mark.parametrize(
    "unsupported",
    [
        object(),
        datetime(2026, 8, 7, 12, 0),
        float("nan"),
        float("inf"),
        _ExternalMutableEnum.VALUE,
    ],
)
def test_unsupported_or_ambiguous_metadata_values_fail_closed(
    unsupported: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="unsupported|timezone-aware|finite numbers|StageFlow enum",
    ):
        freeze_metadata({"value": unsupported})


def test_metadata_keys_must_be_strings() -> None:
    with pytest.raises(ValueError, match="keys must be strings"):
        freeze_metadata(cast(Any, {1: "invalid"}))


def test_metadata_reference_cycles_fail_closed() -> None:
    cyclic: dict[str, Any] = {}
    cyclic["self"] = cyclic

    with pytest.raises(ValueError, match="reference cycles"):
        freeze_metadata(cyclic)
