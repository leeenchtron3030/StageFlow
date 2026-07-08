from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ScheduledActivityIdentity:
    """Descriptive identity for planned activity information."""

    activity_title: str
    subtitle: str | None = None
    external_identifier: str | None = None
    organizer_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.activity_title.strip():
            raise ValueError("ScheduledActivityIdentity activity_title must not be empty.")
        if self.external_identifier is not None and not self.external_identifier.strip():
            raise ValueError(
                "ScheduledActivityIdentity external_identifier must not be empty."
            )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
