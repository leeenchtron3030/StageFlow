from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceRole, EvidenceSignal, EvidenceStrength
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceBuilderSemanticRule:
    """Generic rule mechanics for one normalized semantic value."""

    id: EntityId
    normalized_semantic_value: str
    target_signal: EvidenceSignal
    evidence_role: EvidenceRole = EvidenceRole.SUPPORTS
    evidence_strength: EvidenceStrength = EvidenceStrength.STRONG
    rationale_template: str = "{semantic_value} indicates {evidence_signal}."
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.normalized_semantic_value.strip():
            raise ValueError("EvidenceBuilderSemanticRule semantic value is required.")
        if self.target_signal is EvidenceSignal.UNKNOWN:
            raise ValueError("EvidenceBuilderSemanticRule must not target unknown Signal.")
        if not self.rationale_template.strip():
            raise ValueError("EvidenceBuilderSemanticRule rationale template is required.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def rationale(self) -> str:
        return self.rationale_template.format(
            semantic_value=self.normalized_semantic_value,
            evidence_signal=self.target_signal.value,
        )
