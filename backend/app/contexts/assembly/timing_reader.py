"""Assembly-owned read port for advisory ordering inputs, never timing authority."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.contexts.production.media_timing_evidence.contracts import (
    RecorderProfileQualificationStatus,
)
from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

from .session_contracts import positive


@dataclass(frozen=True, slots=True)
class AssemblyTimingEvidence:
    asset_id: EntityId
    evidence_id: EntityId
    revision: int
    qualification: RecorderProfileQualificationStatus
    candidate_started_at: datetime

    def __post_init__(self) -> None:
        positive(self.revision, "evidence revision")
        require_aware_datetime(self.candidate_started_at, "candidate_started_at")
        object.__setattr__(self, "qualification",
                           RecorderProfileQualificationStatus(self.qualification))


class AssemblyTimingReader(Protocol):
    def read(self, asset_ids: tuple[EntityId, ...]) -> tuple[AssemblyTimingEvidence, ...]:
        """At most one result per asset: exactly one matching derivation in active MTE."""
        ...
