from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class OperatorAdapterKind(StrEnum):
    DESKTOP_OPERATOR = "desktop_operator"
    MOBILE_OPERATOR = "mobile_operator"
    CONTROL_SURFACE = "control_surface"
    MANUAL_ENTRY = "manual_entry"
    SIMULATED_SOURCE = "simulated_source"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperatorAdapterIdentity:
    """Generic identity information for an operator source adapter."""

    adapter_name: str
    adapter_kind: OperatorAdapterKind
    stage_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("OperatorAdapterIdentity adapter_name must not be empty.")
        if self.stage_label is not None and not self.stage_label.strip():
            raise ValueError("OperatorAdapterIdentity stage_label must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
