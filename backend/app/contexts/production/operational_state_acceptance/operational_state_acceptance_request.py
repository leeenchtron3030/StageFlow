from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.operational_state import OperationalState, OperationalStateSubject
from app.contexts.production.transition_policy import TransitionEvaluation

from .operational_state_acceptance_context import OperationalStateAcceptanceContext
from .operational_state_acceptance_history import OperationalStateAcceptanceHistory
from .operational_state_acceptance_lineage import OperationalStateAcceptanceLineage


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceRequest:
    """One immutable request to accept one TransitionEvaluation."""

    evaluation: TransitionEvaluation
    lineage: OperationalStateAcceptanceLineage
    current_state: OperationalState | None
    target_subject: OperationalStateSubject
    history: OperationalStateAcceptanceHistory
    accepted_at: datetime
    context: OperationalStateAcceptanceContext = field(
        default_factory=OperationalStateAcceptanceContext.unknown
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
