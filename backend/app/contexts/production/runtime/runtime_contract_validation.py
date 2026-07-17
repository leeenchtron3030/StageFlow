from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

from app.contexts.production.completed_media_asset.completed_media_asset_validation import (
    freeze_metadata,
    normalize_entity_ids,
    normalize_strings,
    require_aware,
    require_non_empty,
    require_optional_aware,
    require_optional_non_empty,
)
from app.shared.ids import EntityId


def freeze_runtime_metadata(
    metadata: Mapping[Any, Any],
    field_name: str,
) -> Mapping[str, Any]:
    return freeze_metadata(metadata, field_name)


def normalize_limitations(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    return normalize_strings(values, field_name)


def normalize_enum_values[T: Enum](
    values: Sequence[T],
) -> tuple[T, ...]:
    return tuple(sorted(set(values), key=lambda value: str(value.value)))


def require_optional_non_negative_int(value: int | None, field_name: str) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{field_name} must not be negative.")


def require_optional_positive_int(value: int | None, field_name: str) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def require_optional_percentage(value: float | None, field_name: str) -> None:
    if value is not None and not 0 <= value <= 100:
        raise ValueError(f"{field_name} must be between 0 and 100 inclusive.")


def require_optional_non_negative_duration(
    value: timedelta | None,
    field_name: str,
) -> None:
    if value is not None and value < timedelta(0):
        raise ValueError(f"{field_name} must not be negative.")


def require_optional_positive_duration(
    value: timedelta | None,
    field_name: str,
) -> None:
    if value is not None and value <= timedelta(0):
        raise ValueError(f"{field_name} must be positive.")


def require_opaque_reference(value: str, field_name: str) -> str:
    normalized = require_non_empty(value, field_name)
    if "\x00" in normalized:
        raise ValueError(f"{field_name} must not contain a null byte.")
    parsed = urlsplit(normalized)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} must not embed credentials.")
    lowered = normalized.casefold()
    if any(
        marker in lowered
        for marker in ("access_token=", "api_key=", "password=", "secret=")
    ):
        raise ValueError(f"{field_name} must not embed credential material.")
    return normalized


__all__ = [
    "EntityId",
    "freeze_runtime_metadata",
    "normalize_entity_ids",
    "normalize_enum_values",
    "normalize_limitations",
    "normalize_strings",
    "require_aware",
    "require_non_empty",
    "require_opaque_reference",
    "require_optional_aware",
    "require_optional_non_empty",
    "require_optional_non_negative_duration",
    "require_optional_non_negative_int",
    "require_optional_percentage",
    "require_optional_positive_duration",
    "require_optional_positive_int",
]
