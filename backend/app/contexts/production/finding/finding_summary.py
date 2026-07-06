from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.finding.finding import Finding
from app.contexts.production.finding.finding_confidence import FindingConfidence
from app.contexts.production.finding.finding_origin import FindingOrigin
from app.contexts.production.finding.finding_type import FindingType
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class FindingSummary:
    """A lightweight finding representation for future review surfaces."""

    finding_id: EntityId
    finding_type: FindingType
    confidence: FindingConfidence
    origin: FindingOrigin
    timeline_location_summary: str
    supporting_hypothesis_count: int
    contradicting_hypothesis_count: int

    @classmethod
    def from_finding(cls, finding: Finding) -> FindingSummary:
        return cls(
            finding_id=finding.id,
            finding_type=finding.finding_type,
            confidence=finding.confidence,
            origin=finding.origin,
            timeline_location_summary=finding.location.summary(),
            supporting_hypothesis_count=finding.support.supporting_count,
            contradicting_hypothesis_count=finding.support.contradicting_count,
        )
