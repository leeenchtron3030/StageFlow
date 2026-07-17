from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, cast

from app.contexts.production.runtime.runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_limitations,
    normalize_strings,
    require_aware,
    require_non_empty,
    require_opaque_reference,
)
from app.shared.ids import EntityId


def require_positive(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def require_non_negative(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must not be negative.")


def require_enum[TEnum: Enum](
    value: object,
    enum_type: type[TEnum],
    field_name: str,
) -> TEnum:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field_name} must use an approved {enum_type.__name__} value.")
    return value


def require_bool(value: object, field_name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{field_name} must be boolean.")


def normalize_ids(values: Sequence[EntityId]) -> tuple[EntityId, ...]:
    return tuple(sorted(set(values), key=lambda value: value.value))


def freeze_metadata(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    return freeze_runtime_metadata(value, field_name)


def canonical_value(value: object) -> str:
    if is_dataclass(value) and not isinstance(value, type):
        return (
            type(value).__name__
            + "("
            + ",".join(
                f"{item.name}={canonical_value(getattr(value, item.name))}"
                for item in fields(value)
            )
            + ")"
        )
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value)
        return (
            "{"
            + ",".join(
                f"{key!r}:{canonical_value(item)}"
                for key, item in sorted(items.items(), key=lambda pair: repr(pair[0]))
            )
            + "}"
        )
    if isinstance(value, (tuple, list, set, frozenset)):
        items = cast(Sequence[object], value)
        return "[" + ",".join(sorted(canonical_value(item) for item in items)) + "]"
    if isinstance(value, Enum):
        return f"{type(value).__name__}:{value.value}"
    if isinstance(value, datetime):
        return f"datetime:{value.isoformat()}"
    if isinstance(value, EntityId):
        return f"EntityId:{value.value}"
    return f"{type(value).__name__}:{value!r}"


__all__ = [
    "canonical_value",
    "freeze_metadata",
    "normalize_ids",
    "normalize_limitations",
    "normalize_strings",
    "require_aware",
    "require_bool",
    "require_enum",
    "require_non_empty",
    "require_non_negative",
    "require_opaque_reference",
    "require_positive",
]
