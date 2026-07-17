from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from math import isfinite
from types import MappingProxyType
from typing import Any, cast

from app.shared.ids import CorrelationId, EntityId

_SENSITIVE_METADATA_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "credentials",
    "network_password",
    "password",
    "private_key",
    "secret",
    "share_password",
}


def require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def require_optional_aware(value: datetime | None, field_name: str) -> None:
    if value is not None:
        require_aware(value, field_name)


def require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def require_optional_non_empty(value: str | None, field_name: str) -> str | None:
    return None if value is None else require_non_empty(value, field_name)


def require_non_negative_duration(value: timedelta | None, field_name: str) -> None:
    if value is not None and value < timedelta(0):
        raise ValueError(f"{field_name} must not be negative.")


def require_positive_number(value: int | float | None, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{field_name} must be finite.")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def normalize_entity_ids(
    values: Sequence[EntityId],
    field_name: str,
) -> tuple[EntityId, ...]:
    by_value: dict[str, EntityId] = {}
    for value in values:
        by_value[value.value] = value
    return tuple(by_value[value] for value in sorted(by_value))


def normalize_correlation_ids(
    values: Sequence[CorrelationId],
    field_name: str,
) -> tuple[CorrelationId, ...]:
    by_value: dict[str, CorrelationId] = {}
    for value in values:
        by_value[value.value] = value
    return tuple(by_value[value] for value in sorted(by_value))


def normalize_strings(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    normalized: set[str] = set()
    for value in values:
        normalized.add(require_non_empty(value, field_name))
    return tuple(sorted(normalized))


def freeze_metadata(
    metadata: Mapping[Any, Any],
    field_name: str,
) -> Mapping[str, Any]:
    frozen: dict[str, Any] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} keys must be strings.")
        normalized_key = require_non_empty(key, f"{field_name} key")
        if normalized_key.casefold() in _SENSITIVE_METADATA_KEYS:
            raise ValueError(f"{field_name} must not contain credential material.")
        frozen[normalized_key] = _freeze_metadata_value(
            value,
            f"{field_name}.{normalized_key}",
        )
    return MappingProxyType(frozen)


def _freeze_metadata_value(value: Any, field_name: str) -> Any:
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{field_name} must contain only finite numbers.")
        return value
    if isinstance(value, Mapping):
        return freeze_metadata(cast(Mapping[Any, Any], value), field_name)
    if isinstance(value, list | tuple):
        sequence = cast(Sequence[Any], value)
        return tuple(
            _freeze_metadata_value(item, f"{field_name}[{index}]")
            for index, item in enumerate(sequence)
        )
    raise ValueError(
        f"{field_name} must contain only serialization-friendly metadata values."
    )
