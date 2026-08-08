from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.operational_product.operational_product_origin import (
    OperationalProductOrigin,
)
from app.contexts.production.operational_product.operational_product_reference import (
    OperationalProductReference,
)
from app.contexts.production.operational_product.operational_product_status import (
    OperationalProductStatus,
)
from app.contexts.production.operational_product.operational_product_type import (
    OperationalProductType,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_LINEAGE_OPTIONAL_ORIGINS = {
    OperationalProductOrigin.HUMAN_CREATED,
    OperationalProductOrigin.SYSTEM_CREATED,
    OperationalProductOrigin.IMPORTED,
}


@dataclass(frozen=True, slots=True)
class OperationalProduct:
    """Generic downstream output of verified reasoning."""

    id: EntityId
    product_type: OperationalProductType
    status: OperationalProductStatus
    origin: OperationalProductOrigin
    originating_finding_ids: Sequence[EntityId]
    originating_verification_decision_ids: Sequence[EntityId]
    correlation_id: CorrelationId
    created_at: datetime
    references: Sequence[OperationalProductReference] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    notes: str | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.created_at, "OperationalProduct.created_at")
        object.__setattr__(self, "originating_finding_ids", tuple(self.originating_finding_ids))
        object.__setattr__(
            self,
            "originating_verification_decision_ids",
            tuple(self.originating_verification_decision_ids),
        )
        object.__setattr__(self, "references", tuple(self.references))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

        has_lineage = bool(
            self.originating_finding_ids or self.originating_verification_decision_ids
        )
        if self.origin not in _LINEAGE_OPTIONAL_ORIGINS and not has_lineage:
            raise ValueError(
                "OperationalProduct requires Finding or Verification Decision lineage "
                "for this origin."
            )
