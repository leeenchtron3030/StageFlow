from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceBuilderContextKey:
    """Stable generic grouping key supplied by a concrete Evidence Builder."""

    components: Sequence[tuple[str, str | None]]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata, compare=False, hash=False)

    def __post_init__(self) -> None:
        normalized_components: list[tuple[str, str | None]] = []
        for label, value in self.components:
            if not label.strip():
                raise ValueError("EvidenceBuilderContextKey labels must be non-empty.")
            normalized_components.append((label, value))
        object.__setattr__(self, "components", tuple(normalized_components))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def from_components(
        cls,
        **components: str | None,
    ) -> EvidenceBuilderContextKey:
        return cls(components=tuple(components.items()))

    def as_dict(self) -> Mapping[str, str | None]:
        return MappingProxyType(dict(self.components))
