from __future__ import annotations

from dataclasses import dataclass

from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class EvidenceBuilderSummary:
    """Lightweight diagnostics for an Observation Evidence Builder."""

    builder_id: EntityId
    builder_name: str
    rule_count: int
    operational_concern_count: int
    declared_signal_count: int

    @classmethod
    def from_builder(cls, builder: ObservationEvidenceBuilder) -> EvidenceBuilderSummary:
        concerns = {rule.concern for rule in builder.rules}
        signals = {rule.evidence_signal for rule in builder.rules}
        return cls(
            builder_id=builder.id,
            builder_name=builder.name,
            rule_count=len(builder.rules),
            operational_concern_count=len(concerns),
            declared_signal_count=len(signals),
        )


from app.contexts.production.evidence_builder.observation_evidence_builder import (  # noqa: E402
    ObservationEvidenceBuilder,
)
