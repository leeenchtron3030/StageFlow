from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class SessionWindowProductLineage:
    """ID-only traceability from the product to verified reasoning."""

    originating_finding_ids: Sequence[EntityId]
    originating_verification_decision_ids: Sequence[EntityId]
    originating_operational_product_id: EntityId
    source_label: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "originating_finding_ids", tuple(self.originating_finding_ids))
        object.__setattr__(
            self,
            "originating_verification_decision_ids",
            tuple(self.originating_verification_decision_ids),
        )

        if not self.originating_finding_ids and not self.originating_verification_decision_ids:
            raise ValueError(
                "SessionWindowProductLineage requires at least one Finding ID or "
                "Verification Decision ID reference."
            )
