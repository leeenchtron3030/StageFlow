from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .evidence_context_source import EvidenceContextSource


class EvidenceContextConflictResolution(StrEnum):
    FIRST_CLASS_VALUE_RETAINED = "first_class_value_retained"
    EVIDENCE_ISOLATED = "evidence_isolated"
    INPUT_IGNORED = "input_ignored"
    BUILD_REJECTED = "build_rejected"
    COMPOSITION_REJECTED = "composition_rejected"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceContextConflict:
    """One deterministic, descriptive conflict between context authorities."""

    field_name: str
    authoritative_value: Sequence[str]
    conflicting_value: Sequence[str]
    authoritative_source: EvidenceContextSource
    conflicting_source: EvidenceContextSource
    contributing_reference_ids: Sequence[EntityId] = field(default_factory=tuple)
    resolution: EvidenceContextConflictResolution = EvidenceContextConflictResolution.UNKNOWN
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise ValueError("EvidenceContextConflict field_name must not be blank.")
        object.__setattr__(
            self,
            "authoritative_value",
            tuple(sorted(dict.fromkeys(self.authoritative_value))),
        )
        object.__setattr__(
            self,
            "conflicting_value",
            tuple(sorted(dict.fromkeys(self.conflicting_value))),
        )
        object.__setattr__(
            self,
            "contributing_reference_ids",
            tuple(
                sorted(
                    dict.fromkeys(self.contributing_reference_ids),
                    key=lambda item: item.to_json(),
                )
            ),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
