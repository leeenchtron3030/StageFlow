from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum


class MediaCandidateDiscoveryOutcome(StrEnum):
    DISCOVERED = "discovered"
    NO_CANDIDATES = "no_candidates"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    FAILED = "failed"
    INVALID_RESULT = "invalid_result"
    UNKNOWN = "unknown"


class MediaObservationCollectionOutcome(StrEnum):
    COLLECTED = "collected"
    NO_OBSERVATION = "no_observation"
    UNSUPPORTED = "unsupported"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    FAILED = "failed"
    INVALID_RESULT = "invalid_result"
    UNKNOWN = "unknown"


class MediaCandidateCollectionStatus(StrEnum):
    DISCOVERED = "discovered"
    OBSERVATIONS_AVAILABLE = "observations_available"
    PARTIALLY_OBSERVED = "partially_observed"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    CONFLICTED = "conflicted"


class MediaCollectionCycleOutcome(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_PARTIAL_RESULTS = "completed_with_partial_results"
    NO_CANDIDATES = "no_candidates"
    INTERRUPTED = "interrupted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PERMISSION_DENIED = "permission_denied"
    CYCLE_IN_PROGRESS = "cycle_in_progress"
    ALREADY_APPLIED = "already_applied"
    STALE_REVISION = "stale_revision"
    OPERATION_CONFLICT = "operation_conflict"
    INVALID_RUNTIME = "invalid_runtime"
    INVALID_CONFIGURATION = "invalid_configuration"
    INVALID_PLAN = "invalid_plan"
    INVALID_DEPENDENCY = "invalid_dependency"
    DISCOVERY_FAILED = "discovery_failed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class MediaCollectionQueryOutcome(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    INVALID_QUERY = "invalid_query"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


class MediaCandidateConflictCode(StrEnum):
    CANDIDATE_ID_REUSED = "candidate_id_reused_with_different_facts"
    PROPOSED_ASSET_ID_REUSED = "proposed_asset_id_reused_incompatibly"
    RESOURCE_ID_REUSED = "resource_id_reused_incompatibly"
    RUNTIME_IDENTITY_MISMATCH = "runtime_identity_mismatch"
    COLLECTION_TARGET_MISMATCH = "collection_target_mismatch"
    DUPLICATE_DISCOVERY_ID = "duplicate_discovery_id_with_different_content"
    DUPLICATE_OBSERVATION_ID = "duplicate_observation_id_with_different_content"
    OBSERVATION_CANDIDATE_MISMATCH = "observation_candidate_mismatch"
    OBSERVATION_RESOURCE_MISMATCH = "observation_resource_mismatch"
    SOURCE_HOST_CONTRADICTION = "source_host_contradiction"
    SOURCE_VOLUME_CONTRADICTION = "source_volume_contradiction"
    UNKNOWN = "unknown_conflict"


class MediaCollectionCycleReasonCode(StrEnum):
    AGENT_RUNNING_NORMAL = "agent_running_with_normal_permission"
    AGENT_YIELDING_REDUCED = "agent_yielding_with_reduced_permission"
    AGENT_PERMISSION_ABSENT = "agent_permission_absent"
    ESSENTIAL_ONLY_UNDEFINED = "essential_only_collection_undefined"
    AGENT_CANCELLED = "agent_cancelled"
    AGENT_STOPPING = "agent_stopping"
    AGENT_STOPPED = "agent_stopped"
    AGENT_FAILED = "agent_failed"
    AGENT_DISABLED = "agent_disabled"
    AGENT_LIFECYCLE_CHANGED = "agent_lifecycle_changed_during_cycle"
    OPTIONAL_SKIPPED_REDUCED = "optional_collection_skipped_under_reduced_permission"
    RUNTIME_VALIDATION_PASSED = "runtime_validation_passed"
    RUNTIME_VALIDATION_FAILED = "runtime_validation_failed"
    RUNTIME_ID_MISMATCH = "runtime_id_mismatch"
    CONFIGURATION_ID_MISMATCH = "configuration_id_mismatch"
    COLLECTION_PLAN_MISSING = "collection_plan_missing"
    COLLECTION_PLAN_DISABLED = "collection_plan_disabled"
    COLLECTION_TARGET_INVALID = "collection_target_invalid"
    CAPABILITY_MISSING = "capability_missing"
    CAPABILITY_UNSUPPORTED = "capability_unsupported"
    READINESS_SELECTION_MISMATCH = "readiness_selection_mismatch"
    REQUIRED_PORT_MISSING = "required_port_missing"
    EVENT_MODE_INCOMPATIBLE = "event_mode_incompatibility"
    CANDIDATES_DISCOVERED = "candidates_discovered"
    NO_CANDIDATES_DISCOVERED = "no_candidates_discovered"
    DISCOVERY_PARTIAL = "discovery_partial"
    DISCOVERY_DEFERRED = "discovery_deferred"
    DISCOVERY_BLOCKED = "discovery_blocked"
    DISCOVERY_FAILED = "discovery_failed"
    DISCOVERY_RESULT_EXCEEDED_LIMIT = "discovery_result_exceeded_limit"
    INVALID_DISCOVERY_RESULT = "invalid_discovery_result"
    CANDIDATE_ALREADY_KNOWN = "candidate_already_known"
    CANDIDATE_ID_CONFLICT = "candidate_id_conflict"
    PROPOSED_ASSET_ID_CONFLICT = "proposed_asset_id_conflict"
    RESOURCE_ID_CONFLICT = "resource_id_conflict"
    RUNTIME_IDENTITY_CONFLICT = "runtime_identity_conflict"
    TARGET_IDENTITY_CONFLICT = "target_identity_conflict"
    OBSERVATION_COLLECTED = "observation_collected"
    NO_OBSERVATION_SUPPLIED = "no_observation_supplied"
    OBSERVATION_UNSUPPORTED = "observation_unsupported"
    OBSERVATION_DEFERRED = "observation_deferred"
    OBSERVATION_BLOCKED = "observation_blocked"
    OBSERVATION_FAILED = "observation_failed"
    INVALID_OBSERVATION_RESULT = "invalid_observation_result"
    OBSERVATION_IDENTITY_CONFLICT = "observation_identity_conflict"
    REQUIRED_OBSERVATION_UNAVAILABLE = "required_observation_unavailable"
    OPTIONAL_OBSERVATION_UNAVAILABLE = "optional_observation_unavailable"
    CANDIDATE_LIMIT_REACHED = "candidate_limit_reached"
    OBSERVATION_CALL_LIMIT_REACHED = "observation_call_limit_reached"
    CYCLE_INTERRUPTED = "cycle_interrupted"
    CYCLE_COMPLETED = "cycle_completed"
    CYCLE_COMPLETED_PARTIALLY = "cycle_completed_partially"
    NO_READINESS_EVALUATION = "no_readiness_evaluation_performed"
    NO_ASSET_ASSEMBLY = "no_asset_assembly_performed"
    STALE_COORDINATOR_REVISION = "stale_coordinator_revision"
    OPERATION_REPLAY = "operation_replay"
    OPERATION_IDENTITY_CONFLICT = "operation_identity_conflict"
    CYCLE_ALREADY_ACTIVE = "cycle_already_active"
    UNKNOWN_COLLECTION_FAILURE = "unknown_collection_failure"


_REASON_ORDER = {value: index for index, value in enumerate(MediaCollectionCycleReasonCode)}


def normalize_cycle_reasons(
    values: Sequence[MediaCollectionCycleReasonCode],
) -> tuple[MediaCollectionCycleReasonCode, ...]:
    return tuple(sorted(set(values), key=_REASON_ORDER.__getitem__))


__all__ = [
    "MediaCandidateCollectionStatus",
    "MediaCandidateConflictCode",
    "MediaCandidateDiscoveryOutcome",
    "MediaCollectionCycleOutcome",
    "MediaCollectionCycleReasonCode",
    "MediaCollectionQueryOutcome",
    "MediaObservationCollectionOutcome",
    "normalize_cycle_reasons",
]
