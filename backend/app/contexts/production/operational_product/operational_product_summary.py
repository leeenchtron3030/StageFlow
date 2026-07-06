from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.contexts.production.operational_product.operational_product import OperationalProduct
from app.contexts.production.operational_product.operational_product_origin import (
    OperationalProductOrigin,
)
from app.contexts.production.operational_product.operational_product_status import (
    OperationalProductStatus,
)
from app.contexts.production.operational_product.operational_product_type import (
    OperationalProductType,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class OperationalProductSummary:
    """Lightweight operational product representation for future surfaces."""

    operational_product_id: EntityId
    product_type: OperationalProductType
    status: OperationalProductStatus
    origin: OperationalProductOrigin
    originating_finding_count: int
    originating_verification_decision_count: int
    reference_count: int
    created_at: datetime

    @classmethod
    def from_operational_product(
        cls,
        product: OperationalProduct,
    ) -> OperationalProductSummary:
        return cls(
            operational_product_id=product.id,
            product_type=product.product_type,
            status=product.status,
            origin=product.origin,
            originating_finding_count=len(product.originating_finding_ids),
            originating_verification_decision_count=len(
                product.originating_verification_decision_ids
            ),
            reference_count=len(product.references),
            created_at=product.created_at,
        )
