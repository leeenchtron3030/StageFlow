from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.verification.verification_action import VerificationAction
from app.contexts.production.verification.verification_actor import VerificationActor
from app.contexts.production.verification.verification_adjustment import VerificationAdjustment
from app.contexts.production.verification.verification_note import VerificationNote
from app.contexts.production.verification.verification_reason import VerificationReason
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    """One immutable judgment record about a finding."""

    id: EntityId
    finding_id: EntityId
    action: VerificationAction
    reason: VerificationReason
    actor: VerificationActor
    correlation_id: CorrelationId
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    adjustment: VerificationAdjustment | None = None
    note: VerificationNote | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
