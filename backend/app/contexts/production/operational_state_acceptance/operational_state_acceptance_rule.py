from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.operational_state import (
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceRule:
    """Static acceptance rule for one policy rule and lifecycle transition."""

    id: EntityId
    supported_policy_kind: str
    supported_transition_rule_id: EntityId
    state_kind: OperationalStateKind
    effective_current_value: OperationalStateValue
    proposed_value: OperationalStateValue
    required_subject_types: Sequence[OperationalStateSubjectType]
    required_state_family: OperationalStateFamily
    current_state_required: bool
    supersession_expected: bool
    required_lineage_fields: Sequence[str]
    rationale: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.supported_policy_kind.strip():
            raise ValueError("Acceptance rule policy kind must not be empty.")
        if not self.required_subject_types:
            raise ValueError("Acceptance rule requires at least one subject type.")
        if not self.required_lineage_fields:
            raise ValueError("Acceptance rule requires explicit lineage fields.")
        if not self.rationale.strip():
            raise ValueError("Acceptance rule rationale must not be empty.")
        object.__setattr__(
            self,
            "required_subject_types",
            tuple(dict.fromkeys(self.required_subject_types)),
        )
        object.__setattr__(
            self,
            "required_lineage_fields",
            tuple(dict.fromkeys(self.required_lineage_fields)),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
