from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, cast

from app.contexts.production.runtime.runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_limitations,
    normalize_strings,
    require_aware,
    require_non_empty,
)
from app.shared.ids import EntityId


def require_non_negative_revision(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must not be negative.")


def normalize_ordered_entity_ids(
    values: Sequence[EntityId],
    field_name: str,
) -> tuple[EntityId, ...]:
    normalized = tuple(values)
    if len({value.value for value in normalized}) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate IDs.")
    return normalized


def canonical_value(value: Any) -> str:
    if is_dataclass(value) and not isinstance(value, type):
        rendered = ",".join(
            f"{item.name}={canonical_value(getattr(value, item.name))}" for item in fields(value)
        )
        return f"{type(value).__qualname__}({rendered})"
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        rendered = ",".join(
            f"{canonical_value(key)}:{canonical_value(item)}"
            for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0]))
        )
        return "{" + rendered + "}"
    if isinstance(value, tuple | list):
        sequence = cast(Sequence[Any], value)
        return "[" + ",".join(canonical_value(item) for item in sequence) + "]"
    if isinstance(value, Enum):
        return f"{type(value).__qualname__}:{value.value}"
    if isinstance(value, EntityId):
        return f"EntityId:{value.value}"
    if isinstance(value, datetime):
        return f"datetime:{value.isoformat()}"
    return f"{type(value).__qualname__}:{value!r}"


__all__ = [
    "canonical_value",
    "freeze_runtime_metadata",
    "normalize_entity_ids",
    "normalize_limitations",
    "normalize_ordered_entity_ids",
    "normalize_strings",
    "require_aware",
    "require_non_empty",
    "require_non_negative_revision",
]
