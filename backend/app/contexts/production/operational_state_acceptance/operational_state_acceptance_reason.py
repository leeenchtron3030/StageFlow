from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.shared.ids import EntityId


class OperationalStateAcceptanceReasonCode(StrEnum):
    EVALUATION_OUTCOME_NOT_SUPPORTED = "evaluation_outcome_not_supported"
    MISSING_PROPOSED_STATE = "missing_proposed_state"
    UNSUPPORTED_STATE_KIND = "unsupported_state_kind"
    INVALID_POLICY_IDENTITY = "invalid_policy_identity"
    INVALID_RULE_IDENTITY = "invalid_rule_identity"
    MISSING_SUPPORTING_EVIDENCE = "missing_supporting_evidence"
    MISSING_OBSERVATION_LINEAGE = "missing_observation_lineage"
    MISSING_EVENT_LINEAGE = "missing_event_lineage"
    EVALUATION_CURRENT_STATE_MISMATCH = "evaluation_current_state_mismatch"
    INVALID_CURRENT_STATE_KIND = "invalid_current_state_kind"
    INVALID_CURRENT_STATE_STATUS = "invalid_current_state_status"
    INVALID_CURRENT_STATE_VALUE = "invalid_current_state_value"
    INVALID_CURRENT_STATE_SUBJECT = "invalid_current_state_subject"
    INVALID_TARGET_SUBJECT = "invalid_target_subject"
    SUBJECT_MISMATCH = "subject_mismatch"
    CONTEXT_MISMATCH = "context_mismatch"
    INVALID_LIFECYCLE_TRANSITION = "invalid_lifecycle_transition"
    EVALUATION_ALREADY_ACCEPTED = "evaluation_already_accepted"
    SUCCESSOR_CREATED = "successor_created"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceReason:
    """One descriptive acceptance decision reason."""

    code: OperationalStateAcceptanceReasonCode
    message: str
    evaluation_id: EntityId
    current_state_id: EntityId | None = None
    subject_identifier: str | None = None
    related_lineage_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("OperationalStateAcceptanceReason message must not be empty.")
        if self.subject_identifier is not None and not self.subject_identifier.strip():
            raise ValueError(
                "OperationalStateAcceptanceReason subject_identifier must not be empty."
            )
        object.__setattr__(
            self,
            "related_lineage_ids",
            tuple(dict.fromkeys(self.related_lineage_ids)),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
