from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .asset_readiness_validation import (
    freeze_readiness_metadata,
    normalize_entity_ids,
    require_non_empty,
)


class AssetReadinessReasonCode(StrEnum):
    EXPLICIT_RECORDER_FINALIZATION_OBSERVED = (
        "explicit_recorder_finalization_observed"
    )
    CLOSED_SEGMENT_NOTIFICATION_OBSERVED = "closed_segment_notification_observed"
    ATOMIC_RENAME_OBSERVED = "atomic_rename_observed"
    COMPLETION_MARKER_OBSERVED = "completion_marker_observed"
    MANUAL_DECLARATION_OBSERVED = "manual_declaration_observed"
    STABLE_INTERVAL_SATISFIED = "stable_interval_satisfied"
    RESOURCE_PRESENT_AFTER_FINALIZATION = "resource_present_after_finalization"
    INACTIVE_WRITE_STATE_OBSERVED = "inactive_write_state_observed"
    READ_ACCESS_CONFIRMED = "read_access_confirmed"
    RESOURCE_IDENTITY_CONSISTENT = "resource_identity_consistent"
    NO_CONTRADICTORY_LATER_SNAPSHOT = "no_contradictory_later_snapshot"
    ACTIVE_WRITE_OBSERVED = "active_write_observed"
    RESOURCE_CONTINUED_GROWING = "resource_continued_growing"
    MODIFICATION_TIMESTAMP_CHANGED = "modification_timestamp_changed"
    RESOURCE_MISSING = "resource_missing"
    RESOURCE_REPLACED = "resource_replaced"
    READ_ACCESS_FAILED = "read_access_failed"
    FINALIZATION_CONTRADICTED = "finalization_contradicted"
    RESOURCE_IDENTITY_CHANGED = "resource_identity_changed"
    OBSERVATION_TIMESTAMP_CONFLICT = "observation_timestamp_conflict"
    NO_COMPLETION_BASIS = "no_completion_basis"
    INSUFFICIENT_SNAPSHOTS = "insufficient_snapshots"
    STABLE_INTERVAL_TOO_SHORT = "stable_interval_too_short"
    READ_ACCESS_NOT_ASSESSED = "read_access_not_assessed"
    WRITE_STATE_UNKNOWN = "write_state_unknown"
    RESOURCE_PRESENCE_NOT_CONFIRMED = "resource_presence_not_confirmed"
    FINALIZATION_METHOD_UNKNOWN = "finalization_method_unknown"
    REQUIRED_POST_FINALIZATION_OBSERVATION_MISSING = (
        "required_post_finalization_observation_missing"
    )
    CANDIDATE_ID_MISMATCH = "candidate_id_mismatch"
    RESOURCE_ID_MISMATCH = "resource_id_mismatch"
    SOURCE_RUNTIME_MISMATCH = "source_runtime_mismatch"
    POLICY_ID_MISMATCH = "policy_id_mismatch"
    POLICY_VERSION_MISMATCH = "policy_version_mismatch"
    DUPLICATE_OBSERVATION_ID = "duplicate_observation_id"
    TIMEZONE_NAIVE_TIMESTAMP = "timezone_naive_timestamp"
    UNSUPPORTED_COMPLETION_METHOD = "unsupported_completion_method"
    UNSUPPORTED_SOURCE_CAPABILITY = "unsupported_source_capability"
    UNKNOWN_FAILURE = "unknown_failure"


_REASON_ORDER = {
    code: index
    for index, code in enumerate(
        (
            AssetReadinessReasonCode.CANDIDATE_ID_MISMATCH,
            AssetReadinessReasonCode.RESOURCE_ID_MISMATCH,
            AssetReadinessReasonCode.SOURCE_RUNTIME_MISMATCH,
            AssetReadinessReasonCode.POLICY_ID_MISMATCH,
            AssetReadinessReasonCode.POLICY_VERSION_MISMATCH,
            AssetReadinessReasonCode.TIMEZONE_NAIVE_TIMESTAMP,
            AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT,
            AssetReadinessReasonCode.DUPLICATE_OBSERVATION_ID,
            AssetReadinessReasonCode.RESOURCE_IDENTITY_CHANGED,
            AssetReadinessReasonCode.RESOURCE_REPLACED,
            AssetReadinessReasonCode.FINALIZATION_CONTRADICTED,
            AssetReadinessReasonCode.UNSUPPORTED_COMPLETION_METHOD,
            AssetReadinessReasonCode.UNSUPPORTED_SOURCE_CAPABILITY,
            AssetReadinessReasonCode.ACTIVE_WRITE_OBSERVED,
            AssetReadinessReasonCode.RESOURCE_CONTINUED_GROWING,
            AssetReadinessReasonCode.MODIFICATION_TIMESTAMP_CHANGED,
            AssetReadinessReasonCode.RESOURCE_MISSING,
            AssetReadinessReasonCode.READ_ACCESS_FAILED,
            AssetReadinessReasonCode.EXPLICIT_RECORDER_FINALIZATION_OBSERVED,
            AssetReadinessReasonCode.CLOSED_SEGMENT_NOTIFICATION_OBSERVED,
            AssetReadinessReasonCode.ATOMIC_RENAME_OBSERVED,
            AssetReadinessReasonCode.COMPLETION_MARKER_OBSERVED,
            AssetReadinessReasonCode.MANUAL_DECLARATION_OBSERVED,
            AssetReadinessReasonCode.STABLE_INTERVAL_SATISFIED,
            AssetReadinessReasonCode.RESOURCE_PRESENT_AFTER_FINALIZATION,
            AssetReadinessReasonCode.INACTIVE_WRITE_STATE_OBSERVED,
            AssetReadinessReasonCode.READ_ACCESS_CONFIRMED,
            AssetReadinessReasonCode.RESOURCE_IDENTITY_CONSISTENT,
            AssetReadinessReasonCode.NO_CONTRADICTORY_LATER_SNAPSHOT,
            AssetReadinessReasonCode.NO_COMPLETION_BASIS,
            AssetReadinessReasonCode.INSUFFICIENT_SNAPSHOTS,
            AssetReadinessReasonCode.STABLE_INTERVAL_TOO_SHORT,
            AssetReadinessReasonCode.READ_ACCESS_NOT_ASSESSED,
            AssetReadinessReasonCode.WRITE_STATE_UNKNOWN,
            AssetReadinessReasonCode.RESOURCE_PRESENCE_NOT_CONFIRMED,
            AssetReadinessReasonCode.FINALIZATION_METHOD_UNKNOWN,
            AssetReadinessReasonCode.REQUIRED_POST_FINALIZATION_OBSERVATION_MISSING,
            AssetReadinessReasonCode.UNKNOWN_FAILURE,
        )
    )
}

SUPPORTING_REASON_CODES = frozenset(
    {
        AssetReadinessReasonCode.EXPLICIT_RECORDER_FINALIZATION_OBSERVED,
        AssetReadinessReasonCode.CLOSED_SEGMENT_NOTIFICATION_OBSERVED,
        AssetReadinessReasonCode.ATOMIC_RENAME_OBSERVED,
        AssetReadinessReasonCode.COMPLETION_MARKER_OBSERVED,
        AssetReadinessReasonCode.MANUAL_DECLARATION_OBSERVED,
        AssetReadinessReasonCode.STABLE_INTERVAL_SATISFIED,
        AssetReadinessReasonCode.RESOURCE_PRESENT_AFTER_FINALIZATION,
        AssetReadinessReasonCode.INACTIVE_WRITE_STATE_OBSERVED,
        AssetReadinessReasonCode.READ_ACCESS_CONFIRMED,
        AssetReadinessReasonCode.RESOURCE_IDENTITY_CONSISTENT,
        AssetReadinessReasonCode.NO_CONTRADICTORY_LATER_SNAPSHOT,
    }
)

BLOCKING_REASON_CODES = frozenset(
    {
        AssetReadinessReasonCode.ACTIVE_WRITE_OBSERVED,
        AssetReadinessReasonCode.RESOURCE_CONTINUED_GROWING,
        AssetReadinessReasonCode.MODIFICATION_TIMESTAMP_CHANGED,
        AssetReadinessReasonCode.RESOURCE_MISSING,
        AssetReadinessReasonCode.RESOURCE_REPLACED,
        AssetReadinessReasonCode.READ_ACCESS_FAILED,
        AssetReadinessReasonCode.FINALIZATION_CONTRADICTED,
        AssetReadinessReasonCode.RESOURCE_IDENTITY_CHANGED,
        AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT,
    }
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AssetReadinessReason:
    code: AssetReadinessReasonCode
    message: str
    observation_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "message",
            require_non_empty(self.message, "AssetReadinessReason.message"),
        )
        object.__setattr__(
            self,
            "observation_ids",
            normalize_entity_ids(
                self.observation_ids,
                "AssetReadinessReason.observation_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(self.metadata, "AssetReadinessReason.metadata"),
        )


def normalize_readiness_reasons(
    reasons: Sequence[AssetReadinessReason],
) -> tuple[AssetReadinessReason, ...]:
    by_key: dict[tuple[int, str, str, tuple[str, ...]], AssetReadinessReason] = {}
    for reason in reasons:
        key = (
            _REASON_ORDER[reason.code],
            reason.code.value,
            reason.message,
            tuple(observation_id.value for observation_id in reason.observation_ids),
        )
        by_key[key] = reason
    return tuple(by_key[key] for key in sorted(by_key))
