from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.operational_state import OperationalState, OperationalStateSubject
from app.shared.ids import EntityId

from .operational_state_acceptance_lineage import OperationalStateAcceptanceLineage
from .operational_state_acceptance_outcome import OperationalStateAcceptanceOutcome
from .operational_state_acceptance_reason import OperationalStateAcceptanceReason
from .operational_state_supersession import OperationalStateSupersession


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceResult:
    """Immutable acceptance decision with no persistence or execution behavior."""

    id: EntityId
    outcome: OperationalStateAcceptanceOutcome
    accepted_evaluation_id: EntityId
    reasons: Sequence[OperationalStateAcceptanceReason]
    current_state_id: EntityId | None
    target_subject: OperationalStateSubject
    successor_state: OperationalState | None
    supersession: OperationalStateSupersession | None
    lineage: OperationalStateAcceptanceLineage
    applied_acceptance_rule_id: EntityId | None
    accepted_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        reasons = tuple(self.reasons)
        if not reasons:
            raise ValueError("OperationalStateAcceptanceResult requires at least one reason.")
        object.__setattr__(self, "reasons", reasons)
        if self.outcome is OperationalStateAcceptanceOutcome.ACCEPTED:
            if self.accepted_evaluation_id != self.lineage.evaluation_id:
                raise ValueError("Accepted result Evaluation ID must match lineage.")
            if self.successor_state is None or self.applied_acceptance_rule_id is None:
                raise ValueError("Accepted result requires successor state and acceptance rule.")
            if self.current_state_id is not None and self.supersession is None:
                raise ValueError("Accepted result with a predecessor requires supersession.")
            if self.current_state_id is None and self.supersession is not None:
                raise ValueError("Initial accepted result must not contain supersession.")
        elif self.successor_state is not None or self.supersession is not None:
            raise ValueError("Non-accepted result must not contain successor or supersession.")

        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def is_accepted(self) -> bool:
        return self.outcome is OperationalStateAcceptanceOutcome.ACCEPTED
