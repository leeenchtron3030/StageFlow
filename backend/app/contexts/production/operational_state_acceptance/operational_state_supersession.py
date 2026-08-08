from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.operational_state import OperationalStateStatus
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateSupersession:
    """Describes intended supersession without mutating or persisting state."""

    predecessor_state_id: EntityId
    successor_state_id: EntityId
    transition_evaluation_id: EntityId
    accepted_at: datetime
    predecessor_status_before_acceptance: OperationalStateStatus
    successor_status: OperationalStateStatus
    reason: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.accepted_at, "OperationalStateSupersession.accepted_at")
        if not self.reason.strip():
            raise ValueError("OperationalStateSupersession reason must not be empty.")
        if self.predecessor_state_id == self.successor_state_id:
            raise ValueError("OperationalStateSupersession requires distinct state IDs.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
