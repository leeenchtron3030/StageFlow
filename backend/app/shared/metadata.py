from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID

from app.shared.ids import CorrelationId, EntityId


def freeze_metadata(metadata: Mapping[Any, Any]) -> Mapping[str, Any]:
    """Return a recursively immutable snapshot of supplementary metadata."""

    return _freeze_mapping(metadata, "metadata", set())


def _freeze_mapping(
    metadata: Mapping[Any, Any],
    field_name: str,
    active_containers: set[int],
) -> Mapping[str, Any]:
    marker = id(metadata)
    if marker in active_containers:
        raise ValueError(f"{field_name} must not contain reference cycles.")
    active_containers.add(marker)
    frozen: dict[str, Any] = {}
    try:
        for key, value in metadata.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} keys must be strings.")
            frozen[key] = _freeze_value(
                value,
                f"{field_name}.{key}",
                active_containers,
            )
        return MappingProxyType(frozen)
    finally:
        active_containers.remove(marker)


def _freeze_value(
    value: Any,
    field_name: str,
    active_containers: set[int],
) -> Any:
    if isinstance(value, Enum):
        _validate_stageflow_enum(value, field_name, active_containers)
        return value
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{field_name} must contain only finite numbers.")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} datetime values must be timezone-aware.")
        return value
    if isinstance(value, timedelta | UUID | EntityId | CorrelationId):
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(
            cast(Mapping[Any, Any], value),
            field_name,
            active_containers,
        )
    if isinstance(value, list | tuple):
        sequence = cast(Sequence[Any], value)
        marker = id(sequence)
        if marker in active_containers:
            raise ValueError(f"{field_name} must not contain reference cycles.")
        active_containers.add(marker)
        try:
            return tuple(
                _freeze_value(
                    item,
                    f"{field_name}[{index}]",
                    active_containers,
                )
                for index, item in enumerate(sequence)
            )
        finally:
            active_containers.remove(marker)
    if isinstance(value, set | frozenset):
        items = cast(Set[Any], value)
        return frozenset(
            _freeze_value(item, field_name, active_containers) for item in items
        )
    if is_dataclass(value) and not isinstance(value, type):
        return _validate_frozen_stageflow_value(
            value,
            field_name,
            active_containers,
        )
    raise ValueError(f"{field_name} contains an unsupported mutable or active value.")


def _validate_frozen_stageflow_value(
    value: Any,
    field_name: str,
    active_containers: set[int],
) -> Any:
    value_object = cast(object, value)
    value_type: type[object] = type(value_object)
    parameters = getattr(value_type, "__dataclass_params__", None)
    if (
        parameters is None
        or not parameters.frozen
        or not value_type.__module__.startswith("app.")
    ):
        raise ValueError(
            f"{field_name} must use a frozen StageFlow value contract."
        )
    marker = id(value_object)
    if marker in active_containers:
        raise ValueError(f"{field_name} must not contain reference cycles.")
    active_containers.add(marker)
    try:
        for item in fields(cast(Any, value_object)):
            nested = getattr(value_object, item.name)
            if isinstance(nested, Mapping) and not isinstance(nested, MappingProxyType):
                raise ValueError(
                    f"{field_name}.{item.name} contains a mutable nested mapping."
                )
            if isinstance(nested, list | set):
                raise ValueError(
                    f"{field_name}.{item.name} contains a mutable nested collection."
                )
            _validate_existing_value(
                nested,
                f"{field_name}.{item.name}",
                active_containers,
            )
        return value
    finally:
        active_containers.remove(marker)


def _validate_existing_value(
    value: Any,
    field_name: str,
    active_containers: set[int],
) -> None:
    if isinstance(value, Enum):
        _validate_stageflow_enum(value, field_name, active_containers)
        return
    if value is None or isinstance(
        value,
        str | int | bool | timedelta | UUID | EntityId | CorrelationId,
    ):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{field_name} must contain only finite numbers.")
        return
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} datetime values must be timezone-aware.")
        return
    if isinstance(value, MappingProxyType):
        marker = id(cast(object, value))
        if marker in active_containers:
            raise ValueError(f"{field_name} must not contain reference cycles.")
        active_containers.add(marker)
        try:
            for key, nested in cast(Mapping[Any, Any], value).items():
                if not isinstance(key, str):
                    raise ValueError(f"{field_name} keys must be strings.")
                _validate_existing_value(
                    nested,
                    f"{field_name}.{key}",
                    active_containers,
                )
            return
        finally:
            active_containers.remove(marker)
    if isinstance(value, tuple | frozenset):
        items = cast(tuple[Any, ...] | frozenset[Any], value)
        for index, nested in enumerate(items):
            _validate_existing_value(
                nested,
                f"{field_name}[{index}]",
                active_containers,
            )
        return
    if is_dataclass(value) and not isinstance(value, type):
        _validate_frozen_stageflow_value(value, field_name, active_containers)
        return
    raise ValueError(f"{field_name} contains a mutable or unsupported nested value.")


def _validate_stageflow_enum(
    value: Enum,
    field_name: str,
    active_containers: set[int],
) -> None:
    if not type(value).__module__.startswith("app."):
        raise ValueError(f"{field_name} must use a StageFlow enum value.")
    _validate_existing_value(
        value.value,
        f"{field_name}.value",
        active_containers,
    )


__all__ = ["freeze_metadata"]
