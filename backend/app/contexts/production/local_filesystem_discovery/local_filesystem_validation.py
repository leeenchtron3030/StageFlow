from __future__ import annotations

from collections.abc import Mapping, Sequence
from os import path
from pathlib import PurePath
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from app.contexts.production.runtime.runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_limitations,
    require_aware,
    require_non_empty,
)

_GLOB_CHARACTERS = frozenset("*?[]{}")
_CREDENTIAL_MARKERS = (
    "access_token=",
    "api_key=",
    "authorization=",
    "credential=",
    "password=",
    "secret=",
    "token=",
)


def validate_absolute_target_location(value: str, field_name: str) -> str:
    normalized = require_non_empty(value, field_name)
    if "\x00" in normalized:
        raise ValueError(f"{field_name} must not contain a null byte.")
    parsed = urlsplit(normalized)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} must not embed credentials.")
    lowered = normalized.casefold()
    if any(marker in lowered for marker in _CREDENTIAL_MARKERS):
        raise ValueError(f"{field_name} must not embed credential material.")
    if not path.isabs(normalized):
        raise ValueError(f"{field_name} must be absolute.")
    if ".." in PurePath(normalized).parts:
        raise ValueError(f"{field_name} must not contain parent traversal.")
    if any(character in normalized for character in _GLOB_CHARACTERS):
        raise ValueError(f"{field_name} must not contain glob or wildcard syntax.")
    return path.normpath(normalized)


def normalize_extension(value: str, field_name: str) -> str:
    normalized = require_non_empty(value, field_name)
    if "/" in normalized or "\\" in normalized or "\x00" in normalized:
        raise ValueError(f"{field_name} must be a filename extension or suffix.")
    return normalized if normalized.startswith(".") else f".{normalized}"


def normalize_extensions(
    values: Sequence[str],
    field_name: str,
    *,
    casefold: bool,
) -> tuple[str, ...]:
    normalized = {
        normalize_extension(value, field_name).casefold()
        if casefold
        else normalize_extension(value, field_name)
        for value in values
    }
    return tuple(sorted(normalized))


def normalize_hint_mapping[T](
    values: Mapping[str, T],
    field_name: str,
    *,
    casefold: bool,
) -> Mapping[str, T]:
    normalized: dict[str, T] = {}
    for extension, hint in values.items():
        key = normalize_extension(extension, field_name)
        normalized[key.casefold() if casefold else key] = hint
    return MappingProxyType(dict(sorted(normalized.items())))


def freeze_discovery_metadata(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    return freeze_runtime_metadata(value, field_name)


__all__ = [
    "freeze_discovery_metadata",
    "normalize_extension",
    "normalize_extensions",
    "normalize_hint_mapping",
    "normalize_limitations",
    "require_aware",
    "require_non_empty",
    "validate_absolute_target_location",
]
