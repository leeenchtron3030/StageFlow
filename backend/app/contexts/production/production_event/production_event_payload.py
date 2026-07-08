from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, cast


def _empty_payload() -> Mapping[str, Any]:
    return {}


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("ProductionEventPayload float values must be finite.")
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        value_mapping = cast(Mapping[Any, Any], value)
        return MappingProxyType(
            {
                _validated_key(key): _freeze_json_value(nested_value)
                for key, nested_value in value_mapping.items()
            }
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        value_sequence = cast(Sequence[Any], value)
        return tuple(_freeze_json_value(item) for item in value_sequence)
    raise ValueError("ProductionEventPayload values must be JSON-compatible.")


def _validated_key(key: Any) -> str:
    if not isinstance(key, str):
        raise ValueError("ProductionEventPayload keys must be strings.")
    return key


@dataclass(frozen=True, slots=True)
class ProductionEventPayload:
    """Source data carried by a production event without assigning domain meaning."""

    data: Mapping[str, Any] = field(default_factory=_empty_payload)

    def __post_init__(self) -> None:
        frozen_data = {
            _validated_key(key): _freeze_json_value(value)
            for key, value in self.data.items()
        }
        object.__setattr__(self, "data", MappingProxyType(frozen_data))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def key_count(self) -> int:
        return len(self.data)
