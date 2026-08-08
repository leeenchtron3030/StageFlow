from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


class OperationalProductReferenceType(StrEnum):
    FINDING = "finding"
    VERIFICATION_DECISION = "verification_decision"
    RECORDING_BLOCK = "recording_block"
    TIMELINE_RANGE = "timeline_range"
    SESSION = "session"
    CLIP = "clip"
    PACKAGE = "package"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalProductReference:
    """Loose ID reference from an operational product to another object."""

    reference_type: OperationalProductReferenceType
    referenced_id: EntityId
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
