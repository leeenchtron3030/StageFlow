from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


class ProductionEventReferenceType(StrEnum):
    RECORDING_BLOCK = "recording_block"
    STAGE = "stage"
    TIMELINE_POSITION = "timeline_position"
    TIMELINE_RANGE = "timeline_range"
    MEDIA_FILE = "media_file"
    SCHEDULE_ARTIFACT = "schedule_artifact"
    EXTERNAL_OBJECT = "external_object"
    OPERATOR = "operator"
    SYSTEM = "system"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ProductionEventReference:
    """Lightweight ID or external string reference connected to an event."""

    reference_type: ProductionEventReferenceType
    referenced_id: EntityId | None = None
    external_reference: str | None = None
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

        has_referenced_id = self.referenced_id is not None
        has_external_reference = self.external_reference is not None
        if has_referenced_id == has_external_reference:
            raise ValueError(
                "ProductionEventReference requires exactly one of referenced_id "
                "or external_reference."
            )
        if self.external_reference is not None and not self.external_reference.strip():
            raise ValueError("ProductionEventReference external_reference must not be empty.")
