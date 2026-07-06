from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.contexts.production.evidence.evidence_purpose import EvidencePurpose
from app.contexts.production.evidence.evidence_set import EvidenceSet
from app.contexts.production.evidence.evidence_strength import EvidenceStrength
from app.shared.ids import EntityId

_STRENGTH_ORDER = (
    EvidenceStrength.STRONG,
    EvidenceStrength.MODERATE,
    EvidenceStrength.WEAK,
    EvidenceStrength.UNKNOWN,
    EvidenceStrength.CONTRADICTORY,
)


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    """A lightweight summary of an evidence set."""

    evidence_set_id: EntityId
    purpose: EvidencePurpose
    total_item_count: int
    count_by_strength: MappingProxyType[EvidenceStrength, int]

    @classmethod
    def from_evidence_set(cls, evidence_set: EvidenceSet) -> EvidenceSummary:
        counts = {strength: 0 for strength in EvidenceStrength}
        for item in evidence_set.items:
            counts[item.strength] += 1

        return cls(
            evidence_set_id=evidence_set.id,
            purpose=evidence_set.purpose,
            total_item_count=len(evidence_set.items),
            count_by_strength=MappingProxyType(counts),
        )

    @property
    def contradictory_count(self) -> int:
        return self.count_by_strength[EvidenceStrength.CONTRADICTORY]

    @property
    def strongest_strength(self) -> EvidenceStrength | None:
        for strength in _STRENGTH_ORDER:
            if self.count_by_strength[strength] > 0:
                return strength
        return None
