from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TransitionReason:
    """Concise explanation for a transition policy evaluation result."""

    message: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("TransitionReason message must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
