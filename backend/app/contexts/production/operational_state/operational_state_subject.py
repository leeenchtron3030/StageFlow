from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.metadata import freeze_metadata


class OperationalStateSubjectType(StrEnum):
    STAGEFLOW = "stageflow"
    RECORDING_BLOCK = "recording_block"
    MEDIA_ARTIFACT = "media_artifact"
    TRANSCRIPT_STREAM = "transcript_stream"
    STAGE = "stage"
    SCHEDULED_ACTIVITY = "scheduled_activity"
    SESSION_CANDIDATE = "session_candidate"
    SESSION_PRODUCT = "session_product"
    EDITORIAL_CANDIDATE = "editorial_candidate"
    PACKAGE_CANDIDATE = "package_candidate"
    EXTERNAL_ENVIRONMENT = "external_environment"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateSubject:
    """Lightweight reference to what an OperationalState applies to."""

    subject_type: OperationalStateSubjectType
    subject_identifier: str
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.subject_identifier.strip():
            raise ValueError("OperationalStateSubject requires a subject identifier.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
