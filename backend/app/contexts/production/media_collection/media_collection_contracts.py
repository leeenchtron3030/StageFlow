from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.asset_readiness import (
    AssetReadinessObservation,
    AssetReadinessObservationBundle,
    MediaAssetCandidate,
)
from app.contexts.production.runtime import (
    RuntimeCollectionMode,
    RuntimeObservationType,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeSnapshot,
)
from app.shared.ids import EntityId

from .media_collection_lifecycle import (
    MediaCandidateCollectionStatus,
    MediaCandidateConflictCode,
    MediaCandidateDiscoveryOutcome,
    MediaCollectionCycleOutcome,
    MediaCollectionCycleReasonCode,
    MediaCollectionQueryOutcome,
    MediaObservationCollectionOutcome,
    normalize_cycle_reasons,
)
from .media_collection_validation import (
    canonical_value,
    freeze_metadata,
    normalize_ids,
    normalize_limitations,
    normalize_strings,
    require_aware,
    require_bool,
    require_enum,
    require_non_negative,
    require_opaque_reference,
    require_positive,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class MediaCandidateDiscoveryRequest:
    discovery_request_id: EntityId
    collection_cycle_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    collection_plan_id: EntityId
    collection_target_id: EntityId
    source_capability_id: EntityId
    discovery_capability_id: EntityId
    maximum_candidate_count: int
    requested_at: datetime
    execution_permission: AgentRuntimeExecutionPermission
    event_mode_id: EntityId
    resource_policy_id: EntityId
    target_reference: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_positive(self.maximum_candidate_count, "maximum_candidate_count")
        require_aware(self.requested_at, "MediaCandidateDiscoveryRequest.requested_at")
        require_enum(
            self.execution_permission,
            AgentRuntimeExecutionPermission,
            "MediaCandidateDiscoveryRequest.execution_permission",
        )
        object.__setattr__(
            self,
            "target_reference",
            require_opaque_reference(
                self.target_reference,
                "MediaCandidateDiscoveryRequest.target_reference",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaCandidateDiscoveryRequest.metadata"),
        )


@dataclass(frozen=True, slots=True)
class DiscoveredMediaCandidate:
    discovery_id: EntityId
    discovery_request_id: EntityId
    cycle_id: EntityId
    collection_plan_id: EntityId
    collection_target_id: EntityId
    discovery_port_id: EntityId
    candidate: MediaAssetCandidate
    discovered_at: datetime
    source_limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.discovered_at, "DiscoveredMediaCandidate.discovered_at")
        object.__setattr__(
            self,
            "source_limitations",
            normalize_limitations(self.source_limitations, "source_limitations"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "DiscoveredMediaCandidate.metadata"),
        )


def _discovered_candidate_order_key(
    value: DiscoveredMediaCandidate,
) -> tuple[str, ...]:
    resource = value.candidate.primary_resource
    location = resource.source_location.location_value
    return (
        value.collection_target_id.value,
        location.casefold(),
        location,
        resource.original_filename.casefold(),
        resource.original_filename,
        value.candidate.id.value,
        value.candidate.proposed_asset_id.value,
        resource.id.value,
    )


@dataclass(frozen=True, slots=True)
class MediaCandidateDiscoveryResult:
    discovery_request_id: EntityId
    cycle_id: EntityId
    port_id: EntityId
    outcome: MediaCandidateDiscoveryOutcome
    discovered_candidates: Sequence[DiscoveredMediaCandidate] = field(default_factory=tuple)
    reasons: Sequence[str] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    conflicting_discovery_ids: tuple[EntityId, ...] = field(init=False, default_factory=tuple)

    def __post_init__(self) -> None:
        require_enum(
            self.outcome,
            MediaCandidateDiscoveryOutcome,
            "MediaCandidateDiscoveryResult.outcome",
        )
        if self.started_at is not None:
            require_aware(self.started_at, "MediaCandidateDiscoveryResult.started_at")
        if self.completed_at is not None:
            require_aware(self.completed_at, "MediaCandidateDiscoveryResult.completed_at")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("Discovery completion cannot precede discovery start.")
        grouped: dict[str, list[DiscoveredMediaCandidate]] = {}
        for discovered in self.discovered_candidates:
            grouped.setdefault(discovered.discovery_id.value, []).append(discovered)
        normalized: list[DiscoveredMediaCandidate] = []
        conflicts: list[EntityId] = []
        for discovery_id in sorted(grouped):
            choices = sorted(grouped[discovery_id], key=canonical_value)
            if len({canonical_value(choice) for choice in choices}) > 1:
                conflicts.append(choices[0].discovery_id)
            normalized.append(choices[0])
        object.__setattr__(
            self,
            "discovered_candidates",
            tuple(
                sorted(
                    normalized,
                    key=_discovered_candidate_order_key,
                )
            ),
        )
        object.__setattr__(self, "conflicting_discovery_ids", normalize_ids(conflicts))
        object.__setattr__(self, "reasons", normalize_strings(self.reasons, "reasons"))
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(self.limitations, "limitations"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaCandidateDiscoveryResult.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaObservationCollectionRequest:
    collection_request_id: EntityId
    collection_cycle_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    collection_plan_id: EntityId
    collection_target_id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    observation_capability_id: EntityId
    observation_type: RuntimeObservationType
    collection_mode: RuntimeCollectionMode
    requested_at: datetime
    execution_permission: AgentRuntimeExecutionPermission
    required: bool
    source_capability_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.requested_at, "MediaObservationCollectionRequest.requested_at")
        require_enum(
            self.observation_type,
            RuntimeObservationType,
            "MediaObservationCollectionRequest.observation_type",
        )
        require_enum(
            self.collection_mode,
            RuntimeCollectionMode,
            "MediaObservationCollectionRequest.collection_mode",
        )
        require_enum(
            self.execution_permission,
            AgentRuntimeExecutionPermission,
            "MediaObservationCollectionRequest.execution_permission",
        )
        object.__setattr__(self, "source_capability_ids", normalize_ids(self.source_capability_ids))
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaObservationCollectionRequest.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaObservationCollectionResult:
    collection_request_id: EntityId
    cycle_id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    observation_type: RuntimeObservationType
    port_id: EntityId
    outcome: MediaObservationCollectionOutcome
    observations: Sequence[AssetReadinessObservation] = field(default_factory=tuple)
    reasons: Sequence[str] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    conflicting_observation_ids: tuple[EntityId, ...] = field(init=False, default_factory=tuple)

    def __post_init__(self) -> None:
        require_enum(
            self.observation_type,
            RuntimeObservationType,
            "MediaObservationCollectionResult.observation_type",
        )
        require_enum(
            self.outcome,
            MediaObservationCollectionOutcome,
            "MediaObservationCollectionResult.outcome",
        )
        if self.started_at is not None:
            require_aware(self.started_at, "MediaObservationCollectionResult.started_at")
        if self.completed_at is not None:
            require_aware(self.completed_at, "MediaObservationCollectionResult.completed_at")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("Observation completion cannot precede start.")
        grouped: dict[str, list[AssetReadinessObservation]] = {}
        for observation in self.observations:
            grouped.setdefault(observation.id.value, []).append(observation)
        normalized: list[AssetReadinessObservation] = []
        conflicts: list[EntityId] = []
        for observation_id in sorted(grouped):
            choices = sorted(grouped[observation_id], key=canonical_value)
            if len({canonical_value(choice) for choice in choices}) > 1:
                conflicts.append(choices[0].id)
            normalized.append(choices[0])
        object.__setattr__(
            self,
            "observations",
            tuple(sorted(normalized, key=lambda value: (value.observed_at, value.id.value))),
        )
        object.__setattr__(self, "conflicting_observation_ids", normalize_ids(conflicts))
        object.__setattr__(self, "reasons", normalize_strings(self.reasons, "reasons"))
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(self.limitations, "limitations"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaObservationCollectionResult.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaCollectionCycleRequest:
    cycle_id: EntityId
    operation_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    collection_plan_id: EntityId
    expected_coordinator_revision: int
    requested_at: datetime
    maximum_total_candidates: int
    maximum_total_observation_port_calls: int
    permit_reduced_execution: bool
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_non_negative(self.expected_coordinator_revision, "expected_coordinator_revision")
        require_positive(self.maximum_total_candidates, "maximum_total_candidates")
        require_positive(
            self.maximum_total_observation_port_calls,
            "maximum_total_observation_port_calls",
        )
        require_aware(self.requested_at, "MediaCollectionCycleRequest.requested_at")
        require_bool(self.permit_reduced_execution, "permit_reduced_execution")
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaCollectionCycleRequest.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaCandidateConflict:
    id: EntityId
    candidate_ids: Sequence[EntityId]
    proposed_asset_ids: Sequence[EntityId]
    resource_ids: Sequence[EntityId]
    conflict_code: MediaCandidateConflictCode
    discovery_ids: Sequence[EntityId]
    observation_ids: Sequence[EntityId]
    detected_at: datetime
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.detected_at, "MediaCandidateConflict.detected_at")
        require_enum(
            self.conflict_code,
            MediaCandidateConflictCode,
            "MediaCandidateConflict.conflict_code",
        )
        for name in (
            "candidate_ids",
            "proposed_asset_ids",
            "resource_ids",
            "discovery_ids",
            "observation_ids",
        ):
            object.__setattr__(self, name, normalize_ids(getattr(self, name)))
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(self.limitations, "limitations"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaCandidateConflict.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaCandidateRecord:
    candidate: MediaAssetCandidate
    first_discovery_id: EntityId
    discovery_ids: Sequence[EntityId]
    first_discovered_at: datetime
    last_discovered_at: datetime
    discovery_count: int
    collection_status: MediaCandidateCollectionStatus
    cumulative_observation_bundle_id: EntityId | None
    cumulative_observation_ids: Sequence[EntityId]
    missing_required_observation_types: Sequence[RuntimeObservationType]
    unavailable_capability_ids: Sequence[EntityId]
    blocked_capability_ids: Sequence[EntityId]
    failed_capability_ids: Sequence[EntityId]
    conflict_ids: Sequence[EntityId]
    latest_cycle_id: EntityId
    candidate_revision: int
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.first_discovered_at, "MediaCandidateRecord.first_discovered_at")
        require_aware(self.last_discovered_at, "MediaCandidateRecord.last_discovered_at")
        if self.last_discovered_at < self.first_discovered_at:
            raise ValueError("Last discovery cannot precede first discovery.")
        require_positive(self.discovery_count, "discovery_count")
        require_positive(self.candidate_revision, "candidate_revision")
        require_enum(
            self.collection_status,
            MediaCandidateCollectionStatus,
            "MediaCandidateRecord.collection_status",
        )
        for value in self.missing_required_observation_types:
            require_enum(
                value,
                RuntimeObservationType,
                "MediaCandidateRecord.missing_required_observation_types",
            )
        for name in (
            "discovery_ids",
            "cumulative_observation_ids",
            "unavailable_capability_ids",
            "blocked_capability_ids",
            "failed_capability_ids",
            "conflict_ids",
        ):
            object.__setattr__(self, name, normalize_ids(getattr(self, name)))
        object.__setattr__(
            self,
            "missing_required_observation_types",
            tuple(
                sorted(set(self.missing_required_observation_types), key=lambda value: value.value)
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(self.limitations, "limitations"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaCandidateRecord.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaCollectionCoordinatorSnapshot:
    coordinator_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    coordinator_revision: int
    active_cycle_id: EntityId | None
    candidate_count: int
    conflict_count: int
    cumulative_observation_count: int
    completed_cycle_count: int
    latest_cycle_id: EntityId | None
    latest_cycle_outcome: MediaCollectionCycleOutcome | None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for value, name in (
            (self.coordinator_revision, "coordinator_revision"),
            (self.candidate_count, "candidate_count"),
            (self.conflict_count, "conflict_count"),
            (self.cumulative_observation_count, "cumulative_observation_count"),
            (self.completed_cycle_count, "completed_cycle_count"),
        ):
            require_non_negative(value, name)
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaCollectionCoordinatorSnapshot.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaCollectionCycleResult:
    cycle_id: EntityId
    operation_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    collection_plan_id: EntityId
    outcome: MediaCollectionCycleOutcome
    reasons: Sequence[MediaCollectionCycleReasonCode]
    previous_coordinator_snapshot: MediaCollectionCoordinatorSnapshot
    current_coordinator_snapshot: MediaCollectionCoordinatorSnapshot
    starting_agent_snapshot: AgentRuntimeSnapshot | None
    final_agent_snapshot: AgentRuntimeSnapshot | None
    discovery_results: Sequence[MediaCandidateDiscoveryResult]
    candidate_results: Sequence[MediaCandidateRecord]
    observation_collection_results: Sequence[MediaObservationCollectionResult]
    affected_candidate_ids: Sequence[EntityId]
    newly_discovered_candidate_ids: Sequence[EntityId]
    already_known_candidate_ids: Sequence[EntityId]
    conflicted_candidate_ids: Sequence[EntityId]
    deferred_candidate_ids: Sequence[EntityId]
    total_candidates_considered: int
    total_observation_calls_attempted: int
    total_observations_retained: int
    remaining_candidate_budget: int
    remaining_observation_call_budget: int
    started_at: datetime
    completed_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.started_at, "MediaCollectionCycleResult.started_at")
        require_aware(self.completed_at, "MediaCollectionCycleResult.completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("Cycle completion cannot precede cycle start.")
        require_enum(
            self.outcome,
            MediaCollectionCycleOutcome,
            "MediaCollectionCycleResult.outcome",
        )
        object.__setattr__(self, "reasons", normalize_cycle_reasons(self.reasons))
        object.__setattr__(self, "discovery_results", tuple(self.discovery_results))
        object.__setattr__(
            self,
            "candidate_results",
            tuple(sorted(self.candidate_results, key=lambda value: value.candidate.id.value)),
        )
        object.__setattr__(
            self,
            "observation_collection_results",
            tuple(self.observation_collection_results),
        )
        for name in (
            "affected_candidate_ids",
            "newly_discovered_candidate_ids",
            "already_known_candidate_ids",
            "conflicted_candidate_ids",
            "deferred_candidate_ids",
        ):
            object.__setattr__(self, name, normalize_ids(getattr(self, name)))
        for value, name in (
            (self.total_candidates_considered, "total_candidates_considered"),
            (self.total_observation_calls_attempted, "total_observation_calls_attempted"),
            (self.total_observations_retained, "total_observations_retained"),
            (self.remaining_candidate_budget, "remaining_candidate_budget"),
            (self.remaining_observation_call_budget, "remaining_observation_call_budget"),
        ):
            require_non_negative(value, name)
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "MediaCollectionCycleResult.metadata"),
        )


@dataclass(frozen=True, slots=True)
class MediaCollectionCycleSummary:
    cycle_id: EntityId
    runtime_id: EntityId
    collection_plan_id: EntityId
    outcome: MediaCollectionCycleOutcome
    starting_execution_permission: AgentRuntimeExecutionPermission | None
    final_execution_permission: AgentRuntimeExecutionPermission | None
    target_count: int
    candidates_discovered: int
    candidates_already_known: int
    candidates_conflicted: int
    candidates_deferred: int
    observation_calls_attempted: int
    observations_retained: int
    required_capability_failures: int
    optional_capability_limitations: int
    candidate_budget_remaining: int
    observation_budget_remaining: int
    interruption_reason: str | None
    started_at: datetime
    completed_at: datetime
    warning_codes: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_aware(self.started_at, "MediaCollectionCycleSummary.started_at")
        require_aware(self.completed_at, "MediaCollectionCycleSummary.completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("Cycle summary completion cannot precede cycle start.")
        require_enum(
            self.outcome,
            MediaCollectionCycleOutcome,
            "MediaCollectionCycleSummary.outcome",
        )
        for value, name in (
            (self.target_count, "target_count"),
            (self.candidates_discovered, "candidates_discovered"),
            (self.candidates_already_known, "candidates_already_known"),
            (self.candidates_conflicted, "candidates_conflicted"),
            (self.candidates_deferred, "candidates_deferred"),
            (self.observation_calls_attempted, "observation_calls_attempted"),
            (self.observations_retained, "observations_retained"),
            (self.required_capability_failures, "required_capability_failures"),
            (self.optional_capability_limitations, "optional_capability_limitations"),
            (self.candidate_budget_remaining, "candidate_budget_remaining"),
            (self.observation_budget_remaining, "observation_budget_remaining"),
        ):
            require_non_negative(value, name)
        object.__setattr__(
            self,
            "warning_codes",
            normalize_strings(self.warning_codes, "warning_codes"),
        )

    @classmethod
    def from_result(
        cls,
        result: MediaCollectionCycleResult,
        *,
        target_count: int,
    ) -> MediaCollectionCycleSummary:
        required_failures = sum(
            1
            for item in result.observation_collection_results
            if item.outcome
            not in (
                MediaObservationCollectionOutcome.COLLECTED,
                MediaObservationCollectionOutcome.NO_OBSERVATION,
            )
            and any("required" in reason for reason in item.reasons)
        )
        optional_limitations = sum(
            1
            for item in result.observation_collection_results
            if any("optional" in reason for reason in item.reasons)
        )
        interruption_codes = (
            MediaCollectionCycleReasonCode.AGENT_CANCELLED,
            MediaCollectionCycleReasonCode.AGENT_STOPPING,
            MediaCollectionCycleReasonCode.AGENT_STOPPED,
            MediaCollectionCycleReasonCode.AGENT_FAILED,
            MediaCollectionCycleReasonCode.AGENT_DISABLED,
            MediaCollectionCycleReasonCode.AGENT_PERMISSION_ABSENT,
            MediaCollectionCycleReasonCode.AGENT_LIFECYCLE_CHANGED,
        )
        interruption = (
            next(
                (reason.value for reason in interruption_codes if reason in result.reasons),
                None,
            )
            if result.outcome is MediaCollectionCycleOutcome.INTERRUPTED
            else None
        )
        return cls(
            cycle_id=result.cycle_id,
            runtime_id=result.runtime_id,
            collection_plan_id=result.collection_plan_id,
            outcome=result.outcome,
            starting_execution_permission=(
                None
                if result.starting_agent_snapshot is None
                else result.starting_agent_snapshot.execution_permission
            ),
            final_execution_permission=(
                None
                if result.final_agent_snapshot is None
                else result.final_agent_snapshot.execution_permission
            ),
            target_count=target_count,
            candidates_discovered=len(result.newly_discovered_candidate_ids),
            candidates_already_known=len(result.already_known_candidate_ids),
            candidates_conflicted=len(result.conflicted_candidate_ids),
            candidates_deferred=len(result.deferred_candidate_ids),
            observation_calls_attempted=result.total_observation_calls_attempted,
            observations_retained=result.total_observations_retained,
            required_capability_failures=required_failures,
            optional_capability_limitations=optional_limitations,
            candidate_budget_remaining=result.remaining_candidate_budget,
            observation_budget_remaining=result.remaining_observation_call_budget,
            interruption_reason=interruption,
            started_at=result.started_at,
            completed_at=result.completed_at,
            warning_codes=tuple(reason.value for reason in result.reasons),
        )


@dataclass(frozen=True, slots=True)
class MediaCollectionQueryResult:
    outcome: MediaCollectionQueryOutcome
    candidate: MediaCandidateRecord | None = None
    observation_bundle: AssetReadinessObservationBundle | None = None
    conflict: MediaCandidateConflict | None = None
    cycle_result: MediaCollectionCycleResult | None = None
    candidates: Sequence[MediaCandidateRecord] = field(default_factory=tuple)
    conflicts: Sequence[MediaCandidateConflict] = field(default_factory=tuple)
    cycle_history: Sequence[MediaCollectionCycleResult] = field(default_factory=tuple)
    reason: str | None = None

    def __post_init__(self) -> None:
        require_enum(
            self.outcome,
            MediaCollectionQueryOutcome,
            "MediaCollectionQueryResult.outcome",
        )
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(self.candidates, key=lambda value: value.candidate.id.value)),
        )
        object.__setattr__(
            self,
            "conflicts",
            tuple(sorted(self.conflicts, key=lambda value: value.id.value)),
        )
        object.__setattr__(self, "cycle_history", tuple(self.cycle_history))


__all__ = [
    "DiscoveredMediaCandidate",
    "MediaCandidateConflict",
    "MediaCandidateDiscoveryRequest",
    "MediaCandidateDiscoveryResult",
    "MediaCandidateRecord",
    "MediaCollectionCoordinatorSnapshot",
    "MediaCollectionCycleRequest",
    "MediaCollectionCycleResult",
    "MediaCollectionCycleSummary",
    "MediaCollectionQueryResult",
    "MediaObservationCollectionRequest",
    "MediaObservationCollectionResult",
]
