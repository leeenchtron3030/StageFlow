from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

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


def normalize_limitations(
    limitations: Sequence[str],
    field_name: str,
) -> tuple[str, ...]:
    return normalize_strings(limitations, field_name)


def freeze_readiness_metadata(
    metadata: Mapping[Any, Any],
    field_name: str,
) -> Mapping[str, Any]:
    return freeze_metadata(metadata, field_name)


def validate_observation_identity(
    *,
    observed_at: datetime,
    limitations: Sequence[str],
    metadata: Mapping[Any, Any],
    field_name: str,
) -> tuple[tuple[str, ...], Mapping[str, Any]]:
    require_aware(observed_at, f"{field_name}.observed_at")
    return (
        normalize_limitations(limitations, f"{field_name}.limitations"),
        freeze_readiness_metadata(metadata, f"{field_name}.metadata"),
    )


def identity_values(values: Sequence[EntityId]) -> tuple[str, ...]:
    return tuple(value.value for value in normalize_entity_ids(values, "identity values"))


__all__ = [
    "freeze_readiness_metadata",
    "identity_values",
    "normalize_entity_ids",
    "normalize_limitations",
    "normalize_strings",
    "require_aware",
    "require_non_empty",
    "require_optional_aware",
    "require_optional_non_empty",
    "validate_observation_identity",
]
