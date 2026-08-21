from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from threading import RLock
from types import MappingProxyType
from uuid import UUID, uuid5

from app.contexts.production.asset_readiness import (
    AssetFinalizationObservation,
    AssetReadAccessObservation,
    AssetReadinessObservation,
    AssetReadinessObservationBundle,
    AssetResourcePresenceObservation,
    AssetResourceSnapshot,
    AssetWriteStateObservation,
)
from app.contexts.production.runtime import (
    RuntimeCapabilityKind,
    RuntimeCapabilitySupportStatus,
    RuntimeCollectionPlan,
    RuntimeCollectionTarget,
    RuntimeConfiguration,
    RuntimeConfigurationValidity,
    RuntimeObservationCapability,
    RuntimeObservationType,
    RuntimeProfile,
    RuntimeReadinessPolicySelection,
    StageFlowRuntime,
    validate_runtime,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeSnapshot,
)
from app.shared.ids import EntityId

from .media_collection_contracts import (
    DiscoveredMediaCandidate,
    MediaCandidateConflict,
    MediaCandidateDiscoveryRequest,
    MediaCandidateDiscoveryResult,
    MediaCandidateRecord,
    MediaCollectionCoordinatorSnapshot,
    MediaCollectionCycleRequest,
    MediaCollectionCycleResult,
    MediaCollectionCycleSummary,
    MediaCollectionQueryResult,
    MediaObservationCollectionRequest,
    MediaObservationCollectionResult,
)
from .media_collection_dependencies import MediaCollectionDependencies
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
from .media_collection_validation import canonical_value

_logger = logging.getLogger(__name__)

_ID_NAMESPACE = UUID("62a92419-4fb3-5af8-aed5-ddc946e17a72")
_OBSERVATION_ORDER = {
    RuntimeObservationType.RESOURCE_PRESENCE: 0,
    RuntimeObservationType.RESOURCE_SNAPSHOT: 1,
    RuntimeObservationType.FINALIZATION: 2,
    RuntimeObservationType.WRITE_STATE: 3,
    RuntimeObservationType.READ_ACCESS: 4,
}
_OBSERVATION_CLASSES: Mapping[RuntimeObservationType, type[object]] = {
    RuntimeObservationType.RESOURCE_PRESENCE: AssetResourcePresenceObservation,
    RuntimeObservationType.RESOURCE_SNAPSHOT: AssetResourceSnapshot,
    RuntimeObservationType.FINALIZATION: AssetFinalizationObservation,
    RuntimeObservationType.WRITE_STATE: AssetWriteStateObservation,
    RuntimeObservationType.READ_ACCESS: AssetReadAccessObservation,
}


def _mapping[T](value: Mapping[str, T]) -> Mapping[str, T]:
    return MappingProxyType(dict(value))


def _derived_id(*parts: object) -> EntityId:
    return EntityId(str(uuid5(_ID_NAMESPACE, ":".join(str(part) for part in parts))))


@dataclass(frozen=True, slots=True)
class _PlanContext:
    plan: RuntimeCollectionPlan
    selection: RuntimeReadinessPolicySelection
    discovery_capability_id: EntityId
    observation_capabilities: tuple[RuntimeObservationCapability, ...]
    required_observation_capability_ids: frozenset[EntityId]


@dataclass(frozen=True, slots=True)
class _ActiveReservation:
    request: MediaCollectionCycleRequest
    fingerprint: str
    previous_snapshot: MediaCollectionCoordinatorSnapshot


@dataclass(frozen=True, slots=True)
class _OperationRecord:
    fingerprint: str
    result: MediaCollectionCycleResult


@dataclass(frozen=True, slots=True)
class _CoordinatorState:
    snapshot: MediaCollectionCoordinatorSnapshot
    candidate_records: Mapping[str, MediaCandidateRecord]
    proposed_asset_index: Mapping[str, str]
    resource_index: Mapping[str, str]
    observation_bundles: Mapping[str, AssetReadinessObservationBundle]
    conflicts: Mapping[str, MediaCandidateConflict]
    completed_cycle_results: Mapping[str, _OperationRecord]
    operation_fingerprints: Mapping[str, str]
    cycle_history: tuple[MediaCollectionCycleResult, ...]
    active_cycle_reservation: _ActiveReservation | None


@dataclass(slots=True)
class _CandidateCycleFacts:
    attempted: int = 0
    valid_or_empty: int = 0
    retained: int = 0
    deferred: bool = False
    blocked: bool = False
    failed: bool = False


@dataclass(slots=True)
class _CycleWork:
    records: dict[str, MediaCandidateRecord]
    proposed_index: dict[str, str]
    resource_index: dict[str, str]
    bundles: dict[str, AssetReadinessObservationBundle]
    conflicts: dict[str, MediaCandidateConflict]
    discovery_results: list[MediaCandidateDiscoveryResult]
    observation_results: list[MediaObservationCollectionResult]
    affected: set[EntityId]
    new: set[EntityId]
    known: set[EntityId]
    conflicted: set[EntityId]
    deferred: set[EntityId]
    reasons: list[MediaCollectionCycleReasonCode]
    candidate_facts: dict[str, _CandidateCycleFacts]
    explicit_times: list[datetime]
    considered: int = 0
    observation_calls: int = 0
    retained_observations: int = 0
    candidate_budget_exhausted: bool = False
    observation_budget_exhausted: bool = False
    interrupted: bool = False
    partial: bool = False


class MediaCandidateCollectionCoordinator:
    """Synchronous, bounded orchestration over supplied candidate/observation ports."""

    def __init__(
        self,
        *,
        coordinator_id: EntityId,
        runtime: StageFlowRuntime,
        dependencies: MediaCollectionDependencies,
        allow_development_profile: bool = False,
    ) -> None:
        self._coordinator_id = coordinator_id
        self._runtime = runtime
        self._dependencies = dependencies
        self._allow_development_profile = allow_development_profile
        self._lock = RLock()
        snapshot = MediaCollectionCoordinatorSnapshot(
            coordinator_id=coordinator_id,
            runtime_id=runtime.identity.runtime_id,
            configuration_id=runtime.configuration.id,
            coordinator_revision=0,
            active_cycle_id=None,
            candidate_count=0,
            conflict_count=0,
            cumulative_observation_count=0,
            completed_cycle_count=0,
            latest_cycle_id=None,
            latest_cycle_outcome=None,
        )
        self._state = _CoordinatorState(
            snapshot=snapshot,
            candidate_records=_mapping({}),
            proposed_asset_index=_mapping({}),
            resource_index=_mapping({}),
            observation_bundles=_mapping({}),
            conflicts=_mapping({}),
            completed_cycle_results=_mapping({}),
            operation_fingerprints=_mapping({}),
            cycle_history=(),
            active_cycle_reservation=None,
        )

    @property
    def runtime(self) -> StageFlowRuntime:
        return self._runtime

    @property
    def execution_configuration(self) -> RuntimeConfiguration:
        return self._runtime.configuration

    @property
    def snapshot(self) -> MediaCollectionCoordinatorSnapshot:
        with self._lock:
            return self._state.snapshot

    def run_cycle(self, request: MediaCollectionCycleRequest) -> MediaCollectionCycleResult:
        fingerprint = canonical_value(request)
        with self._lock:
            immediate = self._initial_rejection(request, fingerprint)
            if immediate is not None:
                return immediate
            context, outcome, reasons = self._validate_plan(request)
            if context is None:
                return self._rejection(request, outcome, reasons)

        initial_snapshot = self._read_agent_snapshot(request)
        if initial_snapshot is None:
            return self._rejection(
                request,
                MediaCollectionCycleOutcome.INVALID_DEPENDENCY,
                (MediaCollectionCycleReasonCode.REQUIRED_PORT_MISSING,),
            )
        permitted, permission_reasons = self._permission(initial_snapshot, request)
        if not permitted:
            return self._rejection(
                request,
                self._identity_or_permission_outcome(initial_snapshot),
                permission_reasons,
                starting_agent_snapshot=initial_snapshot,
                final_agent_snapshot=initial_snapshot,
            )

        with self._lock:
            immediate = self._initial_rejection(request, fingerprint)
            if immediate is not None:
                return immediate
            previous = self._state.snapshot
            active_snapshot = replace(previous, active_cycle_id=request.cycle_id)
            reservation = _ActiveReservation(request, fingerprint, previous)
            self._state = replace(
                self._state,
                snapshot=active_snapshot,
                active_cycle_reservation=reservation,
            )

        try:
            return self._execute_reserved_cycle(
                request,
                context,
                reservation,
                initial_snapshot,
            )
        except Exception as error:
            _logger.error(
                "media_collection_cycle_failed cycle_id=%s exception_type=%s",
                request.cycle_id.value,
                type(error).__name__,
            )
            return self._commit_unexpected_failure(
                request,
                reservation,
                initial_snapshot,
            )

    def get_candidate(self, candidate_id: EntityId) -> MediaCollectionQueryResult:
        with self._lock:
            candidate = self._state.candidate_records.get(candidate_id.value)
        return MediaCollectionQueryResult(
            outcome=(
                MediaCollectionQueryOutcome.FOUND
                if candidate is not None
                else MediaCollectionQueryOutcome.NOT_FOUND
            ),
            candidate=candidate,
            reason=None if candidate is not None else "candidate_not_found",
        )

    def get_observation_bundle(
        self,
        candidate_id: EntityId,
    ) -> MediaCollectionQueryResult:
        with self._lock:
            bundle = self._state.observation_bundles.get(candidate_id.value)
        return MediaCollectionQueryResult(
            outcome=(
                MediaCollectionQueryOutcome.FOUND
                if bundle is not None
                else MediaCollectionQueryOutcome.NOT_FOUND
            ),
            observation_bundle=bundle,
            reason=None if bundle is not None else "observation_bundle_not_found",
        )

    def get_conflict(self, conflict_id: EntityId) -> MediaCollectionQueryResult:
        with self._lock:
            conflict = self._state.conflicts.get(conflict_id.value)
        return MediaCollectionQueryResult(
            outcome=(
                MediaCollectionQueryOutcome.FOUND
                if conflict is not None
                else MediaCollectionQueryOutcome.NOT_FOUND
            ),
            conflict=conflict,
            reason=None if conflict is not None else "conflict_not_found",
        )

    def list_candidates(self) -> MediaCollectionQueryResult:
        with self._lock:
            candidates = tuple(self._state.candidate_records.values())
        return MediaCollectionQueryResult(
            outcome=MediaCollectionQueryOutcome.FOUND,
            candidates=candidates,
        )

    def list_conflicts(self) -> MediaCollectionQueryResult:
        with self._lock:
            conflicts = tuple(self._state.conflicts.values())
        return MediaCollectionQueryResult(
            outcome=MediaCollectionQueryOutcome.FOUND,
            conflicts=conflicts,
        )

    def list_cycle_history(self) -> MediaCollectionQueryResult:
        with self._lock:
            history = self._state.cycle_history
        return MediaCollectionQueryResult(
            outcome=MediaCollectionQueryOutcome.FOUND,
            cycle_history=history,
        )

    def get_cycle_result(self, operation_id: EntityId) -> MediaCollectionQueryResult:
        with self._lock:
            record = self._state.completed_cycle_results.get(operation_id.value)
        return MediaCollectionQueryResult(
            outcome=(
                MediaCollectionQueryOutcome.FOUND
                if record is not None
                else MediaCollectionQueryOutcome.NOT_FOUND
            ),
            cycle_result=None if record is None else record.result,
            reason=None if record is not None else "cycle_result_not_found",
        )

    def summarize_cycle(
        self, operation_id: EntityId
    ) -> MediaCollectionQueryResult | MediaCollectionCycleSummary:
        query = self.get_cycle_result(operation_id)
        if query.cycle_result is None:
            return query
        plan = next(
            plan
            for plan in self._runtime.configuration.collection_plans
            if plan.id == query.cycle_result.collection_plan_id
        )
        return MediaCollectionCycleSummary.from_result(
            query.cycle_result,
            target_count=len(plan.targets),
        )

    def _initial_rejection(
        self,
        request: MediaCollectionCycleRequest,
        fingerprint: str,
    ) -> MediaCollectionCycleResult | None:
        completed = self._state.completed_cycle_results.get(request.operation_id.value)
        if completed is not None:
            if completed.fingerprint != fingerprint:
                return self._rejection(
                    request,
                    MediaCollectionCycleOutcome.OPERATION_CONFLICT,
                    (MediaCollectionCycleReasonCode.OPERATION_IDENTITY_CONFLICT,),
                )
            return replace(
                completed.result,
                outcome=MediaCollectionCycleOutcome.ALREADY_APPLIED,
                reasons=normalize_cycle_reasons(
                    (*completed.result.reasons, MediaCollectionCycleReasonCode.OPERATION_REPLAY)
                ),
            )
        active = self._state.active_cycle_reservation
        if active is not None:
            if active.request.operation_id == request.operation_id:
                if active.fingerprint != fingerprint:
                    return self._rejection(
                        request,
                        MediaCollectionCycleOutcome.OPERATION_CONFLICT,
                        (MediaCollectionCycleReasonCode.OPERATION_IDENTITY_CONFLICT,),
                    )
            return self._rejection(
                request,
                MediaCollectionCycleOutcome.CYCLE_IN_PROGRESS,
                (MediaCollectionCycleReasonCode.CYCLE_ALREADY_ACTIVE,),
            )
        prior_fingerprint = self._state.operation_fingerprints.get(request.operation_id.value)
        if prior_fingerprint is not None and prior_fingerprint != fingerprint:
            return self._rejection(
                request,
                MediaCollectionCycleOutcome.OPERATION_CONFLICT,
                (MediaCollectionCycleReasonCode.OPERATION_IDENTITY_CONFLICT,),
            )
        if request.expected_coordinator_revision != self._state.snapshot.coordinator_revision:
            return self._rejection(
                request,
                MediaCollectionCycleOutcome.STALE_REVISION,
                (MediaCollectionCycleReasonCode.STALE_COORDINATOR_REVISION,),
            )
        return None

    def _validate_plan(
        self,
        request: MediaCollectionCycleRequest,
    ) -> tuple[
        _PlanContext | None,
        MediaCollectionCycleOutcome,
        tuple[MediaCollectionCycleReasonCode, ...],
    ]:
        runtime = self._runtime
        configuration = runtime.configuration
        if request.runtime_id != runtime.identity.runtime_id:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_RUNTIME,
                (MediaCollectionCycleReasonCode.RUNTIME_ID_MISMATCH,),
            )
        if request.configuration_id != configuration.id:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_CONFIGURATION,
                (MediaCollectionCycleReasonCode.CONFIGURATION_ID_MISMATCH,),
            )
        if runtime.profile not in (RuntimeProfile.AGENT, RuntimeProfile.DEVELOPMENT):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_RUNTIME,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        if runtime.profile is RuntimeProfile.DEVELOPMENT and not self._allow_development_profile:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_RUNTIME,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        validation = validate_runtime(runtime)
        if validation.outcome not in (
            RuntimeConfigurationValidity.VALID,
            RuntimeConfigurationValidity.VALID_WITH_LIMITATIONS,
        ):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_CONFIGURATION,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        if (
            runtime.capability_set != configuration.capability_set
            or runtime.resource_policy != configuration.resource_policy
            or runtime.event_mode != configuration.event_mode
            or runtime.collection_plans != configuration.collection_plans
            or runtime.readiness_policy_selections != configuration.readiness_policy_selections
            or runtime.asset_assembly_plans != configuration.asset_assembly_plans
        ):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_CONFIGURATION,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        plan = next(
            (
                plan
                for plan in configuration.collection_plans
                if plan.id == request.collection_plan_id
            ),
            None,
        )
        if plan is None:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_PLAN_MISSING,),
            )
        if not plan.enabled:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_PLAN_DISABLED,),
            )
        selection = next(
            (
                value
                for value in configuration.readiness_policy_selections
                if value.id == plan.readiness_policy_selection_id
            ),
            None,
        )
        if selection is None:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.READINESS_SELECTION_MISMATCH,),
            )
        discovery_capability = next(
            (
                capability
                for capability in configuration.capability_set.capabilities
                if capability.kind is RuntimeCapabilityKind.CANDIDATE_DISCOVERY
                and capability.support_status
                in (
                    RuntimeCapabilitySupportStatus.SUPPORTED,
                    RuntimeCapabilitySupportStatus.DEGRADED,
                )
            ),
            None,
        )
        if discovery_capability is None:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.CAPABILITY_MISSING,),
            )
        observation_by_id = {
            capability.id: capability
            for capability in configuration.capability_set.observation_capabilities
        }
        selected: list[RuntimeObservationCapability] = []
        for capability_id in plan.observation_capability_ids:
            capability = observation_by_id.get(capability_id)
            if capability is None:
                return (
                    None,
                    MediaCollectionCycleOutcome.INVALID_PLAN,
                    (MediaCollectionCycleReasonCode.CAPABILITY_MISSING,),
                )
            selected.append(capability)
        target_types = {
            item for target in plan.targets for item in target.enabled_observation_types
        }
        if any(capability.observation_type not in target_types for capability in selected):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_TARGET_INVALID,),
            )
        source_ids = {source.id for source in configuration.capability_set.source_capabilities}
        if any(target.source_capability_id not in source_ids for target in plan.targets):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_TARGET_INVALID,),
            )
        if (
            plan.resource_policy_id != configuration.resource_policy.id
            or plan.event_mode_id != configuration.event_mode.id
        ):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.EVENT_MODE_INCOMPATIBLE,),
            )
        required_ids = frozenset(
            capability.id
            for capability in selected
            if capability.runtime_capability_id in selection.required_capability_ids
        )
        missing = self._missing_ports(selected)
        if missing:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_DEPENDENCY,
                (MediaCollectionCycleReasonCode.REQUIRED_PORT_MISSING,),
            )
        return (
            _PlanContext(
                plan=plan,
                selection=selection,
                discovery_capability_id=discovery_capability.id,
                observation_capabilities=tuple(
                    sorted(
                        selected,
                        key=lambda value: (
                            value.id not in required_ids,
                            _OBSERVATION_ORDER[value.observation_type],
                            value.id.value,
                        ),
                    )
                ),
                required_observation_capability_ids=required_ids,
            ),
            MediaCollectionCycleOutcome.COMPLETED,
            (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_PASSED,),
        )

    def _missing_ports(
        self,
        capabilities: Sequence[RuntimeObservationCapability],
    ) -> tuple[str, ...]:
        missing: list[str] = []
        if self._dependencies.agent_execution_state_port is None:
            missing.append("agent_execution_state_port")
        if self._dependencies.media_candidate_discovery_port is None:
            missing.append("media_candidate_discovery_port")
        for capability in capabilities:
            if self._observation_port(capability.observation_type) is None:
                missing.append(capability.observation_type.value)
        return tuple(sorted(set(missing)))

    def _read_agent_snapshot(
        self,
        request: MediaCollectionCycleRequest,
    ) -> AgentRuntimeSnapshot | None:
        port = self._dependencies.agent_execution_state_port
        if port is None:
            return None
        try:
            return port.get_current_snapshot(request.runtime_id)
        except Exception as error:
            _logger.error(
                (
                    "media_collection_agent_snapshot_failed cycle_id=%s "
                    "runtime_id=%s exception_type=%s"
                ),
                request.cycle_id.value,
                request.runtime_id.value,
                type(error).__name__,
            )
            return None

    def _permission(
        self,
        snapshot: AgentRuntimeSnapshot,
        request: MediaCollectionCycleRequest,
    ) -> tuple[bool, tuple[MediaCollectionCycleReasonCode, ...]]:
        if snapshot.runtime_id != request.runtime_id:
            return False, (MediaCollectionCycleReasonCode.RUNTIME_ID_MISMATCH,)
        if snapshot.configuration_id != request.configuration_id:
            return False, (MediaCollectionCycleReasonCode.CONFIGURATION_ID_MISMATCH,)
        if snapshot.deployment_profile != self._runtime.profile:
            return False, (MediaCollectionCycleReasonCode.RUNTIME_ID_MISMATCH,)
        if snapshot.cancellation is not None:
            return False, (MediaCollectionCycleReasonCode.AGENT_CANCELLED,)
        if snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING:
            if snapshot.execution_permission is AgentRuntimeExecutionPermission.NORMAL:
                return True, (MediaCollectionCycleReasonCode.AGENT_RUNNING_NORMAL,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.YIELDING:
            if snapshot.execution_permission is AgentRuntimeExecutionPermission.REDUCED:
                if request.permit_reduced_execution:
                    return True, (MediaCollectionCycleReasonCode.AGENT_YIELDING_REDUCED,)
                return False, (MediaCollectionCycleReasonCode.AGENT_PERMISSION_ABSENT,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPING:
            return False, (MediaCollectionCycleReasonCode.AGENT_STOPPING,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED:
            return False, (MediaCollectionCycleReasonCode.AGENT_STOPPED,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.FAILED:
            return False, (MediaCollectionCycleReasonCode.AGENT_FAILED,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.DISABLED:
            return False, (MediaCollectionCycleReasonCode.AGENT_DISABLED,)
        if snapshot.execution_permission is AgentRuntimeExecutionPermission.ESSENTIAL_ONLY:
            return False, (MediaCollectionCycleReasonCode.ESSENTIAL_ONLY_UNDEFINED,)
        return False, (MediaCollectionCycleReasonCode.AGENT_PERMISSION_ABSENT,)

    def _identity_or_permission_outcome(
        self,
        snapshot: AgentRuntimeSnapshot,
    ) -> MediaCollectionCycleOutcome:
        if (
            snapshot.runtime_id != self._runtime.identity.runtime_id
            or snapshot.configuration_id != self._runtime.configuration.id
            or snapshot.deployment_profile != self._runtime.profile
        ):
            return MediaCollectionCycleOutcome.INVALID_RUNTIME
        return MediaCollectionCycleOutcome.PERMISSION_DENIED

    def _rejection(
        self,
        request: MediaCollectionCycleRequest,
        outcome: MediaCollectionCycleOutcome,
        reasons: Sequence[MediaCollectionCycleReasonCode],
        *,
        starting_agent_snapshot: AgentRuntimeSnapshot | None = None,
        final_agent_snapshot: AgentRuntimeSnapshot | None = None,
    ) -> MediaCollectionCycleResult:
        snapshot = self._state.snapshot
        return MediaCollectionCycleResult(
            cycle_id=request.cycle_id,
            operation_id=request.operation_id,
            runtime_id=request.runtime_id,
            configuration_id=request.configuration_id,
            collection_plan_id=request.collection_plan_id,
            outcome=outcome,
            reasons=reasons,
            previous_coordinator_snapshot=snapshot,
            current_coordinator_snapshot=snapshot,
            starting_agent_snapshot=starting_agent_snapshot,
            final_agent_snapshot=final_agent_snapshot,
            discovery_results=(),
            candidate_results=(),
            observation_collection_results=(),
            affected_candidate_ids=(),
            newly_discovered_candidate_ids=(),
            already_known_candidate_ids=(),
            conflicted_candidate_ids=(),
            deferred_candidate_ids=(),
            total_candidates_considered=0,
            total_observation_calls_attempted=0,
            total_observations_retained=0,
            remaining_candidate_budget=request.maximum_total_candidates,
            remaining_observation_call_budget=(request.maximum_total_observation_port_calls),
            started_at=request.requested_at,
            completed_at=request.requested_at,
        )

    def _execute_reserved_cycle(
        self,
        request: MediaCollectionCycleRequest,
        context: _PlanContext,
        reservation: _ActiveReservation,
        initial_snapshot: AgentRuntimeSnapshot,
    ) -> MediaCollectionCycleResult:
        with self._lock:
            state = self._state
            work = _CycleWork(
                records=dict(state.candidate_records),
                proposed_index=dict(state.proposed_asset_index),
                resource_index=dict(state.resource_index),
                bundles=dict(state.observation_bundles),
                conflicts=dict(state.conflicts),
                discovery_results=[],
                observation_results=[],
                affected=set(),
                new=set(),
                known=set(),
                conflicted=set(),
                deferred=set(),
                reasons=[
                    MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_PASSED,
                    *self._permission(initial_snapshot, request)[1],
                ],
                candidate_facts={},
                explicit_times=[request.requested_at],
            )

        current_snapshot = initial_snapshot
        discovered: list[DiscoveredMediaCandidate] = []
        for target in context.plan.targets:
            if work.considered >= request.maximum_total_candidates:
                work.candidate_budget_exhausted = True
                work.reasons.append(MediaCollectionCycleReasonCode.CANDIDATE_LIMIT_REACHED)
                break
            checkpoint, permitted = self._checkpoint(request)
            if not permitted:
                current_snapshot = checkpoint or current_snapshot
                work.interrupted = True
                work.reasons.extend(self._interruption_reasons(checkpoint, request))
                break
            assert checkpoint is not None
            current_snapshot = checkpoint
            remaining = request.maximum_total_candidates - work.considered
            discovery_request = MediaCandidateDiscoveryRequest(
                discovery_request_id=_derived_id(
                    self._coordinator_id.value,
                    request.cycle_id.value,
                    "discovery-request",
                    target.id.value,
                ),
                collection_cycle_id=request.cycle_id,
                runtime_id=request.runtime_id,
                configuration_id=request.configuration_id,
                collection_plan_id=context.plan.id,
                collection_target_id=target.id,
                source_capability_id=target.source_capability_id,
                discovery_capability_id=context.discovery_capability_id,
                maximum_candidate_count=remaining,
                requested_at=request.requested_at,
                execution_permission=current_snapshot.execution_permission,
                event_mode_id=context.plan.event_mode_id,
                resource_policy_id=context.plan.resource_policy_id,
                target_reference=target.opaque_location_reference,
            )
            result = self._invoke_discovery(discovery_request)
            normalized, valid_discoveries = self._normalize_discovery_result(
                discovery_request,
                result,
                target,
            )
            if normalized.started_at is not None:
                work.explicit_times.append(normalized.started_at)
            if normalized.completed_at is not None:
                work.explicit_times.append(normalized.completed_at)
            work.explicit_times.extend(item.discovered_at for item in valid_discoveries)
            work.discovery_results.append(normalized)
            self._retain_discovery_result_conflicts(work, normalized, target)
            if len(valid_discoveries) > remaining:
                valid_discoveries = valid_discoveries[:remaining]
                work.candidate_budget_exhausted = True
                work.partial = True
                work.reasons.extend(
                    (
                        MediaCollectionCycleReasonCode.DISCOVERY_RESULT_EXCEEDED_LIMIT,
                        MediaCollectionCycleReasonCode.CANDIDATE_LIMIT_REACHED,
                    )
                )
            discovered.extend(valid_discoveries)
            work.considered += len(valid_discoveries)
            self._record_discovery_outcome(work, normalized)

            checkpoint, permitted = self._checkpoint(request)
            if not permitted:
                current_snapshot = checkpoint or current_snapshot
                work.interrupted = True
                work.reasons.extend(self._interruption_reasons(checkpoint, request))
                break
            assert checkpoint is not None
            current_snapshot = checkpoint

        ordered_discoveries = tuple(
            sorted(
                discovered,
                key=lambda value: (
                    value.collection_target_id.value,
                    value.candidate.id.value,
                    value.candidate.proposed_asset_id.value,
                    value.candidate.primary_resource.id.value,
                ),
            )
        )
        for item in ordered_discoveries:
            self._merge_discovery(work, item, request)

        cycle_candidate_ids = tuple(
            sorted(
                work.affected - work.conflicted,
                key=lambda value: (
                    str(work.records[value.value].metadata.get("collection_target_id", "")),
                    value.value,
                    work.records[value.value].candidate.proposed_asset_id.value,
                    work.records[value.value].candidate.primary_resource.id.value,
                ),
            )
        )
        if work.interrupted:
            work.deferred.update(cycle_candidate_ids)
            for candidate_id in cycle_candidate_ids:
                work.candidate_facts[candidate_id.value].deferred = True
        if not work.interrupted:
            current_snapshot = self._collect_observations(
                request,
                context,
                work,
                cycle_candidate_ids,
                current_snapshot,
            )

        final_snapshot, final_permitted = self._checkpoint(request)
        if not final_permitted:
            work.interrupted = True
            work.reasons.extend(self._interruption_reasons(final_snapshot, request))
            final_snapshot = final_snapshot or current_snapshot
        assert final_snapshot is not None
        self._finalize_candidate_records(work, context, request)
        return self._commit_work(
            request,
            reservation,
            initial_snapshot,
            final_snapshot,
            work,
        )

    def _checkpoint(
        self,
        request: MediaCollectionCycleRequest,
    ) -> tuple[AgentRuntimeSnapshot | None, bool]:
        snapshot = self._read_agent_snapshot(request)
        if snapshot is None:
            return None, False
        permitted, _ = self._permission(snapshot, request)
        return snapshot, permitted

    def _interruption_reasons(
        self,
        snapshot: AgentRuntimeSnapshot | None,
        request: MediaCollectionCycleRequest,
    ) -> tuple[MediaCollectionCycleReasonCode, ...]:
        permission_reasons = () if snapshot is None else self._permission(snapshot, request)[1]
        return (
            *permission_reasons,
            MediaCollectionCycleReasonCode.AGENT_LIFECYCLE_CHANGED,
            MediaCollectionCycleReasonCode.CYCLE_INTERRUPTED,
        )

    def _invoke_discovery(
        self,
        request: MediaCandidateDiscoveryRequest,
    ) -> MediaCandidateDiscoveryResult:
        port = self._dependencies.media_candidate_discovery_port
        if port is None:
            return MediaCandidateDiscoveryResult(
                discovery_request_id=request.discovery_request_id,
                cycle_id=request.collection_cycle_id,
                port_id=_derived_id("missing-discovery-port"),
                outcome=MediaCandidateDiscoveryOutcome.FAILED,
                reasons=("required discovery port is absent",),
                started_at=request.requested_at,
                completed_at=request.requested_at,
            )
        try:
            return self._require_discovery_result(port.discover(request))
        except Exception as error:
            _logger.error(
                "media_collection_discovery_failed request_id=%s cycle_id=%s exception_type=%s",
                request.discovery_request_id.value,
                request.collection_cycle_id.value,
                type(error).__name__,
            )
            return MediaCandidateDiscoveryResult(
                discovery_request_id=request.discovery_request_id,
                cycle_id=request.collection_cycle_id,
                port_id=_derived_id("failed-discovery-port"),
                outcome=MediaCandidateDiscoveryOutcome.FAILED,
                reasons=(f"discovery_port_exception:{type(error).__name__}",),
                started_at=request.requested_at,
                completed_at=request.requested_at,
            )

    def _require_discovery_result(
        self,
        result: object,
    ) -> MediaCandidateDiscoveryResult:
        if not isinstance(result, MediaCandidateDiscoveryResult):
            raise TypeError("Discovery port returned an unsupported result type.")
        return result

    def _normalize_discovery_result(
        self,
        request: MediaCandidateDiscoveryRequest,
        result: MediaCandidateDiscoveryResult,
        target: RuntimeCollectionTarget,
    ) -> tuple[MediaCandidateDiscoveryResult, list[DiscoveredMediaCandidate]]:
        conflicting_discovery_ids = result.conflicting_discovery_ids
        valid = (
            result.discovery_request_id == request.discovery_request_id
            and result.cycle_id == request.collection_cycle_id
            and not result.conflicting_discovery_ids
        )
        candidates: list[DiscoveredMediaCandidate] = []
        for discovered in result.discovered_candidates:
            candidate = discovered.candidate
            resource = candidate.primary_resource
            wrapper_valid = (
                discovered.discovery_request_id == request.discovery_request_id
                and discovered.cycle_id == request.collection_cycle_id
                and discovered.collection_plan_id == request.collection_plan_id
                and discovered.collection_target_id == request.collection_target_id
                and discovered.discovery_port_id == result.port_id
            )
            candidate_valid = (
                candidate.source_runtime_id == request.runtime_id
                and candidate.runtime_profile.value == self._runtime.profile.value
                and (
                    candidate.source_host_id is None
                    or candidate.source_host_id == target.source_host_id
                )
                and (
                    resource.source_host_id is None
                    or resource.source_host_id == target.source_host_id
                )
                and (
                    target.source_volume_id is None
                    or resource.source_volume_id is None
                    or resource.source_volume_id == target.source_volume_id
                )
                and (
                    candidate.context.stage_id is None
                    or target.configured_stage_id is None
                    or candidate.context.stage_id == target.configured_stage_id
                )
                and (
                    candidate.context.recording_block_id is None
                    or target.configured_recording_block_id is None
                    or candidate.context.recording_block_id == target.configured_recording_block_id
                )
            )
            if wrapper_valid and candidate_valid:
                candidates.append(discovered)
            else:
                valid = False
        count_exceeded = len(candidates) > request.maximum_candidate_count
        if count_exceeded:
            valid = False
        if result.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED and not candidates:
            valid = False
        if result.outcome is MediaCandidateDiscoveryOutcome.NO_CANDIDATES and candidates:
            valid = False
        if not valid:
            result = replace(
                result,
                outcome=MediaCandidateDiscoveryOutcome.INVALID_RESULT,
                reasons=(*result.reasons, "discovery result violated request identity or limit"),
                limitations=(
                    *result.limitations,
                    *(("candidate_limit_exceeded",) if count_exceeded else ()),
                ),
            )
            object.__setattr__(
                result,
                "conflicting_discovery_ids",
                conflicting_discovery_ids,
            )
        return result, candidates

    def _retain_discovery_result_conflicts(
        self,
        work: _CycleWork,
        result: MediaCandidateDiscoveryResult,
        target: RuntimeCollectionTarget,
    ) -> None:
        conflicting_discovery_ids = set(result.conflicting_discovery_ids)
        for discovered in result.discovered_candidates:
            candidate = discovered.candidate
            code: MediaCandidateConflictCode | None = None
            if discovered.discovery_id in conflicting_discovery_ids:
                code = MediaCandidateConflictCode.DUPLICATE_DISCOVERY_ID
            elif candidate.source_runtime_id != self._runtime.identity.runtime_id:
                code = MediaCandidateConflictCode.RUNTIME_IDENTITY_MISMATCH
            elif discovered.collection_target_id != target.id:
                code = MediaCandidateConflictCode.COLLECTION_TARGET_MISMATCH
            elif (
                candidate.source_host_id is not None
                and candidate.source_host_id != target.source_host_id
            ):
                code = MediaCandidateConflictCode.SOURCE_HOST_CONTRADICTION
            elif (
                target.source_volume_id is not None
                and candidate.primary_resource.source_volume_id is not None
                and candidate.primary_resource.source_volume_id != target.source_volume_id
            ):
                code = MediaCandidateConflictCode.SOURCE_VOLUME_CONTRADICTION
            if code is None:
                continue
            conflict = self._make_conflict(
                code,
                (candidate.id,),
                (candidate.proposed_asset_id,),
                (candidate.primary_resource.id,),
                (discovered.discovery_id,),
                (),
                discovered.discovered_at,
            )
            work.conflicts.setdefault(conflict.id.value, conflict)
            work.partial = True
            if code is MediaCandidateConflictCode.DUPLICATE_DISCOVERY_ID:
                work.reasons.append(MediaCollectionCycleReasonCode.CANDIDATE_ID_CONFLICT)
            elif code is MediaCandidateConflictCode.RUNTIME_IDENTITY_MISMATCH:
                work.reasons.append(MediaCollectionCycleReasonCode.RUNTIME_IDENTITY_CONFLICT)
            else:
                work.reasons.append(MediaCollectionCycleReasonCode.TARGET_IDENTITY_CONFLICT)

    def _record_discovery_outcome(
        self,
        work: _CycleWork,
        result: MediaCandidateDiscoveryResult,
    ) -> None:
        outcome_reason = {
            MediaCandidateDiscoveryOutcome.DISCOVERED: (
                MediaCollectionCycleReasonCode.CANDIDATES_DISCOVERED
            ),
            MediaCandidateDiscoveryOutcome.NO_CANDIDATES: (
                MediaCollectionCycleReasonCode.NO_CANDIDATES_DISCOVERED
            ),
            MediaCandidateDiscoveryOutcome.PARTIAL: (
                MediaCollectionCycleReasonCode.DISCOVERY_PARTIAL
            ),
            MediaCandidateDiscoveryOutcome.DEFERRED: (
                MediaCollectionCycleReasonCode.DISCOVERY_DEFERRED
            ),
            MediaCandidateDiscoveryOutcome.BLOCKED: (
                MediaCollectionCycleReasonCode.DISCOVERY_BLOCKED
            ),
            MediaCandidateDiscoveryOutcome.FAILED: (
                MediaCollectionCycleReasonCode.DISCOVERY_FAILED
            ),
            MediaCandidateDiscoveryOutcome.INVALID_RESULT: (
                MediaCollectionCycleReasonCode.INVALID_DISCOVERY_RESULT
            ),
            MediaCandidateDiscoveryOutcome.UNSUPPORTED: (
                MediaCollectionCycleReasonCode.CAPABILITY_UNSUPPORTED
            ),
            MediaCandidateDiscoveryOutcome.UNKNOWN: (
                MediaCollectionCycleReasonCode.UNKNOWN_COLLECTION_FAILURE
            ),
        }
        work.reasons.append(outcome_reason[result.outcome])
        if result.outcome not in (
            MediaCandidateDiscoveryOutcome.DISCOVERED,
            MediaCandidateDiscoveryOutcome.NO_CANDIDATES,
        ):
            work.partial = True

    def _merge_discovery(
        self,
        work: _CycleWork,
        discovered: DiscoveredMediaCandidate,
        request: MediaCollectionCycleRequest,
    ) -> None:
        candidate = discovered.candidate
        key = candidate.id.value
        existing = work.records.get(key)
        if existing is not None:
            if existing.candidate != candidate:
                conflict = self._make_conflict(
                    MediaCandidateConflictCode.CANDIDATE_ID_REUSED,
                    (existing.candidate.id, candidate.id),
                    (existing.candidate.proposed_asset_id, candidate.proposed_asset_id),
                    (
                        existing.candidate.primary_resource.id,
                        candidate.primary_resource.id,
                    ),
                    (discovered.discovery_id,),
                    (),
                    discovered.discovered_at,
                )
                self._retain_conflict(work, conflict, (existing.candidate.id,))
                work.reasons.append(MediaCollectionCycleReasonCode.CANDIDATE_ID_CONFLICT)
                return
            target_value = existing.metadata.get("collection_target_id")
            if target_value not in (None, discovered.collection_target_id.value):
                conflict = self._make_conflict(
                    MediaCandidateConflictCode.COLLECTION_TARGET_MISMATCH,
                    (candidate.id,),
                    (candidate.proposed_asset_id,),
                    (candidate.primary_resource.id,),
                    (discovered.discovery_id,),
                    (),
                    discovered.discovered_at,
                )
                self._retain_conflict(work, conflict, (candidate.id,))
                work.reasons.append(MediaCollectionCycleReasonCode.TARGET_IDENTITY_CONFLICT)
                return
            work.records[key] = replace(
                existing,
                discovery_ids=(*existing.discovery_ids, discovered.discovery_id),
                last_discovered_at=max(
                    existing.last_discovered_at,
                    discovered.discovered_at,
                ),
                discovery_count=len(
                    {
                        *(value.value for value in existing.discovery_ids),
                        discovered.discovery_id.value,
                    }
                ),
                latest_cycle_id=request.cycle_id,
                candidate_revision=existing.candidate_revision + 1,
            )
            work.known.add(candidate.id)
            work.affected.add(candidate.id)
            work.reasons.append(MediaCollectionCycleReasonCode.CANDIDATE_ALREADY_KNOWN)
            work.candidate_facts.setdefault(key, _CandidateCycleFacts())
            return

        conflicting_candidates: set[EntityId] = set()
        proposed_owner = work.proposed_index.get(candidate.proposed_asset_id.value)
        if proposed_owner is not None and proposed_owner != key:
            owner = work.records[proposed_owner].candidate
            if owner.primary_resource.id != candidate.primary_resource.id:
                conflicting_candidates.update((owner.id, candidate.id))
                conflict = self._make_conflict(
                    MediaCandidateConflictCode.PROPOSED_ASSET_ID_REUSED,
                    (owner.id, candidate.id),
                    (candidate.proposed_asset_id,),
                    (owner.primary_resource.id, candidate.primary_resource.id),
                    (discovered.discovery_id,),
                    (),
                    discovered.discovered_at,
                )
                self._retain_conflict(work, conflict, (owner.id,))
                work.reasons.append(MediaCollectionCycleReasonCode.PROPOSED_ASSET_ID_CONFLICT)
        resource_owner = work.resource_index.get(candidate.primary_resource.id.value)
        if resource_owner is not None and resource_owner != key:
            owner = work.records[resource_owner].candidate
            conflicting_candidates.update((owner.id, candidate.id))
            conflict = self._make_conflict(
                MediaCandidateConflictCode.RESOURCE_ID_REUSED,
                (owner.id, candidate.id),
                (owner.proposed_asset_id, candidate.proposed_asset_id),
                (candidate.primary_resource.id,),
                (discovered.discovery_id,),
                (),
                discovered.discovered_at,
            )
            self._retain_conflict(work, conflict, (owner.id,))
            work.reasons.append(MediaCollectionCycleReasonCode.RESOURCE_ID_CONFLICT)

        related_conflicts = tuple(
            conflict.id
            for conflict in work.conflicts.values()
            if candidate.id in conflict.candidate_ids
        )
        work.records[key] = MediaCandidateRecord(
            candidate=candidate,
            first_discovery_id=discovered.discovery_id,
            discovery_ids=(discovered.discovery_id,),
            first_discovered_at=discovered.discovered_at,
            last_discovered_at=discovered.discovered_at,
            discovery_count=1,
            collection_status=(
                MediaCandidateCollectionStatus.CONFLICTED
                if conflicting_candidates or related_conflicts
                else MediaCandidateCollectionStatus.DISCOVERED
            ),
            cumulative_observation_bundle_id=None,
            cumulative_observation_ids=(),
            missing_required_observation_types=(),
            unavailable_capability_ids=(),
            blocked_capability_ids=(),
            failed_capability_ids=(),
            conflict_ids=related_conflicts,
            latest_cycle_id=request.cycle_id,
            candidate_revision=1,
            limitations=discovered.source_limitations,
            metadata={"collection_target_id": discovered.collection_target_id.value},
        )
        if not conflicting_candidates and not related_conflicts:
            work.proposed_index[candidate.proposed_asset_id.value] = key
            work.resource_index[candidate.primary_resource.id.value] = key
        else:
            work.conflicted.add(candidate.id)
            for value in conflicting_candidates:
                work.conflicted.add(value)
        work.new.add(candidate.id)
        work.affected.add(candidate.id)
        work.candidate_facts[key] = _CandidateCycleFacts()

    def _make_conflict(
        self,
        code: MediaCandidateConflictCode,
        candidate_ids: Sequence[EntityId],
        proposed_asset_ids: Sequence[EntityId],
        resource_ids: Sequence[EntityId],
        discovery_ids: Sequence[EntityId],
        observation_ids: Sequence[EntityId],
        detected_at: datetime,
    ) -> MediaCandidateConflict:
        identity = ":".join(
            sorted(
                value.value
                for value in (
                    *candidate_ids,
                    *proposed_asset_ids,
                    *resource_ids,
                    *discovery_ids,
                    *observation_ids,
                )
            )
        )
        return MediaCandidateConflict(
            id=_derived_id(self._coordinator_id.value, "conflict", code.value, identity),
            candidate_ids=candidate_ids,
            proposed_asset_ids=proposed_asset_ids,
            resource_ids=resource_ids,
            conflict_code=code,
            discovery_ids=discovery_ids,
            observation_ids=observation_ids,
            detected_at=detected_at,
        )

    def _retain_conflict(
        self,
        work: _CycleWork,
        conflict: MediaCandidateConflict,
        existing_candidate_ids: Sequence[EntityId],
    ) -> None:
        work.conflicts.setdefault(conflict.id.value, conflict)
        for candidate_id in existing_candidate_ids:
            record = work.records.get(candidate_id.value)
            if record is not None:
                work.records[candidate_id.value] = replace(
                    record,
                    collection_status=MediaCandidateCollectionStatus.CONFLICTED,
                    conflict_ids=(*record.conflict_ids, conflict.id),
                    candidate_revision=record.candidate_revision + 1,
                )
            work.conflicted.add(candidate_id)
            work.affected.add(candidate_id)
        work.partial = True

    def _collect_observations(
        self,
        request: MediaCollectionCycleRequest,
        context: _PlanContext,
        work: _CycleWork,
        candidate_ids: Sequence[EntityId],
        current_snapshot: AgentRuntimeSnapshot,
    ) -> AgentRuntimeSnapshot:
        required = tuple(
            capability
            for capability in context.observation_capabilities
            if capability.id in context.required_observation_capability_ids
        )
        optional = tuple(
            capability
            for capability in context.observation_capabilities
            if capability.id not in context.required_observation_capability_ids
        )
        for required_phase, capabilities in ((True, required), (False, optional)):
            for candidate_id in candidate_ids:
                if candidate_id in work.conflicted:
                    continue
                record = work.records[candidate_id.value]
                target_id = record.metadata.get("collection_target_id")
                target = next(
                    (value for value in context.plan.targets if value.id.value == target_id),
                    None,
                )
                if target is None:
                    work.partial = True
                    work.conflicted.add(candidate_id)
                    continue
                selected = tuple(
                    capability
                    for capability in capabilities
                    if capability.observation_type in target.enabled_observation_types
                )
                if not selected:
                    continue
                checkpoint, permitted = self._checkpoint(request)
                if not permitted:
                    current_snapshot = checkpoint or current_snapshot
                    work.interrupted = True
                    work.deferred.update(candidate_ids)
                    for deferred_id in candidate_ids:
                        work.candidate_facts[deferred_id.value].deferred = True
                    work.reasons.extend(self._interruption_reasons(checkpoint, request))
                    return current_snapshot
                assert checkpoint is not None
                if (
                    current_snapshot.execution_permission is AgentRuntimeExecutionPermission.NORMAL
                    and checkpoint.execution_permission is AgentRuntimeExecutionPermission.REDUCED
                ):
                    work.reasons.append(MediaCollectionCycleReasonCode.AGENT_LIFECYCLE_CHANGED)
                current_snapshot = checkpoint
                for capability in selected:
                    if (
                        not required_phase
                        and current_snapshot.execution_permission
                        is AgentRuntimeExecutionPermission.REDUCED
                    ):
                        result = self._deferred_observation_result(
                            request,
                            record,
                            capability,
                            "optional collection skipped under reduced permission",
                        )
                        work.observation_results.append(result)
                        work.deferred.add(candidate_id)
                        work.candidate_facts[candidate_id.value].deferred = True
                        work.reasons.extend(
                            (
                                MediaCollectionCycleReasonCode.OPTIONAL_SKIPPED_REDUCED,
                                MediaCollectionCycleReasonCode.OBSERVATION_DEFERRED,
                            )
                        )
                        work.partial = True
                        continue
                    if work.observation_calls >= request.maximum_total_observation_port_calls:
                        work.observation_budget_exhausted = True
                        work.deferred.update(candidate_ids)
                        for deferred_id in candidate_ids:
                            work.candidate_facts[deferred_id.value].deferred = True
                        work.reasons.append(
                            MediaCollectionCycleReasonCode.OBSERVATION_CALL_LIMIT_REACHED
                        )
                        return current_snapshot
                    checkpoint, permitted = self._checkpoint(request)
                    if not permitted:
                        current_snapshot = checkpoint or current_snapshot
                        work.interrupted = True
                        work.deferred.update(candidate_ids)
                        for deferred_id in candidate_ids:
                            work.candidate_facts[deferred_id.value].deferred = True
                        work.reasons.extend(self._interruption_reasons(checkpoint, request))
                        return current_snapshot
                    assert checkpoint is not None
                    if (
                        current_snapshot.execution_permission
                        is AgentRuntimeExecutionPermission.NORMAL
                        and checkpoint.execution_permission
                        is AgentRuntimeExecutionPermission.REDUCED
                    ):
                        work.reasons.append(MediaCollectionCycleReasonCode.AGENT_LIFECYCLE_CHANGED)
                    current_snapshot = checkpoint
                    if (
                        not required_phase
                        and current_snapshot.execution_permission
                        is AgentRuntimeExecutionPermission.REDUCED
                    ):
                        result = self._deferred_observation_result(
                            request,
                            record,
                            capability,
                            "optional collection skipped under reduced permission",
                        )
                        work.observation_results.append(result)
                        work.deferred.add(candidate_id)
                        work.candidate_facts[candidate_id.value].deferred = True
                        work.reasons.extend(
                            (
                                MediaCollectionCycleReasonCode.OPTIONAL_SKIPPED_REDUCED,
                                MediaCollectionCycleReasonCode.OBSERVATION_DEFERRED,
                            )
                        )
                        work.partial = True
                        continue
                    observation_request = MediaObservationCollectionRequest(
                        collection_request_id=_derived_id(
                            self._coordinator_id.value,
                            request.cycle_id.value,
                            "observation-request",
                            candidate_id.value,
                            capability.id.value,
                        ),
                        collection_cycle_id=request.cycle_id,
                        runtime_id=request.runtime_id,
                        configuration_id=request.configuration_id,
                        collection_plan_id=context.plan.id,
                        collection_target_id=target.id,
                        candidate_id=candidate_id,
                        resource_id=record.candidate.primary_resource.id,
                        observation_capability_id=capability.id,
                        observation_type=capability.observation_type,
                        collection_mode=capability.collection_mode,
                        requested_at=request.requested_at,
                        execution_permission=current_snapshot.execution_permission,
                        required=required_phase,
                        source_capability_ids=(target.source_capability_id,),
                    )
                    result = self._invoke_observation(observation_request)
                    work.observation_calls += 1
                    work.candidate_facts[candidate_id.value].attempted += 1
                    normalized, observations = self._normalize_observation_result(
                        observation_request,
                        result,
                    )
                    if normalized.outcome not in (
                        MediaObservationCollectionOutcome.COLLECTED,
                        MediaObservationCollectionOutcome.NO_OBSERVATION,
                    ):
                        conflicts = normalized.conflicting_observation_ids
                        normalized = replace(
                            normalized,
                            reasons=(
                                *normalized.reasons,
                                (
                                    "required observation unavailable"
                                    if required_phase
                                    else "optional observation unavailable"
                                ),
                            ),
                        )
                        object.__setattr__(
                            normalized,
                            "conflicting_observation_ids",
                            conflicts,
                        )
                    work.observation_results.append(normalized)
                    if normalized.started_at is not None:
                        work.explicit_times.append(normalized.started_at)
                    if normalized.completed_at is not None:
                        work.explicit_times.append(normalized.completed_at)
                    work.explicit_times.extend(value.observed_at for value in observations)
                    self._merge_observation_result(
                        work,
                        record.candidate.id,
                        capability,
                        required_phase,
                        normalized,
                        observations,
                        request,
                    )
                    record = work.records[candidate_id.value]
                    if candidate_id in work.conflicted:
                        break
        return current_snapshot

    def _deferred_observation_result(
        self,
        request: MediaCollectionCycleRequest,
        record: MediaCandidateRecord,
        capability: RuntimeObservationCapability,
        reason: str,
    ) -> MediaObservationCollectionResult:
        return MediaObservationCollectionResult(
            collection_request_id=_derived_id(
                self._coordinator_id.value,
                request.cycle_id.value,
                "deferred-observation",
                record.candidate.id.value,
                capability.id.value,
            ),
            cycle_id=request.cycle_id,
            candidate_id=record.candidate.id,
            resource_id=record.candidate.primary_resource.id,
            observation_type=capability.observation_type,
            port_id=capability.collector_or_adapter_id,
            outcome=MediaObservationCollectionOutcome.DEFERRED,
            reasons=(reason,),
            started_at=request.requested_at,
            completed_at=request.requested_at,
        )

    def _observation_port(self, observation_type: RuntimeObservationType) -> object | None:
        if observation_type is RuntimeObservationType.RESOURCE_SNAPSHOT:
            return self._dependencies.resource_snapshot_collection_port
        if observation_type is RuntimeObservationType.FINALIZATION:
            return self._dependencies.finalization_observation_collection_port
        if observation_type is RuntimeObservationType.WRITE_STATE:
            return self._dependencies.write_state_observation_collection_port
        if observation_type is RuntimeObservationType.READ_ACCESS:
            return self._dependencies.read_access_observation_collection_port
        if observation_type is RuntimeObservationType.RESOURCE_PRESENCE:
            return self._dependencies.resource_presence_observation_collection_port
        return None

    def _invoke_observation(
        self,
        request: MediaObservationCollectionRequest,
    ) -> MediaObservationCollectionResult:
        port = self._observation_port(request.observation_type)
        try:
            if request.observation_type is RuntimeObservationType.RESOURCE_SNAPSHOT:
                collector = self._dependencies.resource_snapshot_collection_port
                if collector is None:
                    raise RuntimeError("Resource snapshot port is absent.")
                result: object = collector.collect_resource_snapshot(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.FINALIZATION:
                collector = self._dependencies.finalization_observation_collection_port
                if collector is None:
                    raise RuntimeError("Finalization port is absent.")
                result = collector.collect_finalization_observation(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.WRITE_STATE:
                collector = self._dependencies.write_state_observation_collection_port
                if collector is None:
                    raise RuntimeError("Write-state port is absent.")
                result = collector.collect_write_state_observation(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.READ_ACCESS:
                collector = self._dependencies.read_access_observation_collection_port
                if collector is None:
                    raise RuntimeError("Read-access port is absent.")
                result = collector.collect_read_access_observation(request)
                return self._require_observation_result(result)
            if request.observation_type is RuntimeObservationType.RESOURCE_PRESENCE:
                collector = self._dependencies.resource_presence_observation_collection_port
                if collector is None:
                    raise RuntimeError("Resource-presence port is absent.")
                result = collector.collect_resource_presence_observation(request)
                return self._require_observation_result(result)
            raise ValueError("Unsupported observation type.")
        except Exception as error:
            _logger.error(
                (
                    "media_collection_observation_failed candidate_id=%s "
                    "resource_id=%s observation_type=%s exception_type=%s"
                ),
                request.candidate_id.value,
                request.resource_id.value,
                request.observation_type.value,
                type(error).__name__,
            )
            return MediaObservationCollectionResult(
                collection_request_id=request.collection_request_id,
                cycle_id=request.collection_cycle_id,
                candidate_id=request.candidate_id,
                resource_id=request.resource_id,
                observation_type=request.observation_type,
                port_id=(
                    _derived_id("missing-observation-port", request.observation_type.value)
                    if port is None
                    else request.observation_capability_id
                ),
                outcome=MediaObservationCollectionOutcome.FAILED,
                reasons=(f"observation_port_exception:{type(error).__name__}",),
                started_at=request.requested_at,
                completed_at=request.requested_at,
            )

    def _require_observation_result(
        self,
        result: object,
    ) -> MediaObservationCollectionResult:
        if not isinstance(result, MediaObservationCollectionResult):
            raise TypeError("Observation port returned an unsupported result type.")
        return result

    def _normalize_observation_result(
        self,
        request: MediaObservationCollectionRequest,
        result: MediaObservationCollectionResult,
    ) -> tuple[MediaObservationCollectionResult, tuple[AssetReadinessObservation, ...]]:
        conflicting_observation_ids = result.conflicting_observation_ids
        valid = (
            result.collection_request_id == request.collection_request_id
            and result.cycle_id == request.collection_cycle_id
            and result.candidate_id == request.candidate_id
            and result.resource_id == request.resource_id
            and result.observation_type is request.observation_type
        )
        expected_class = _OBSERVATION_CLASSES[request.observation_type]
        observations: list[AssetReadinessObservation] = []
        conflicting_values = set(result.conflicting_observation_ids)
        for observation in result.observations:
            observation_valid = (
                isinstance(observation, expected_class)
                and observation.candidate_id == request.candidate_id
                and observation.resource_id == request.resource_id
                and (
                    observation.source_runtime_id is None
                    or observation.source_runtime_id == request.runtime_id
                )
            )
            if not observation_valid:
                valid = False
            elif observation.id not in conflicting_values:
                observations.append(observation)
        if conflicting_values:
            valid = False
        if result.outcome is MediaObservationCollectionOutcome.COLLECTED and not observations:
            valid = False
        if result.outcome is MediaObservationCollectionOutcome.NO_OBSERVATION and observations:
            valid = False
        if not valid:
            result = replace(
                result,
                outcome=MediaObservationCollectionOutcome.INVALID_RESULT,
                reasons=(*result.reasons, "observation result violated request identity"),
            )
            object.__setattr__(
                result,
                "conflicting_observation_ids",
                conflicting_observation_ids,
            )
        return result, tuple(observations)

    def _merge_observation_result(
        self,
        work: _CycleWork,
        candidate_id: EntityId,
        capability: RuntimeObservationCapability,
        required: bool,
        result: MediaObservationCollectionResult,
        observations: Sequence[AssetReadinessObservation],
        request: MediaCollectionCycleRequest,
    ) -> None:
        record = work.records[candidate_id.value]
        facts = work.candidate_facts[candidate_id.value]
        outcome_reason = {
            MediaObservationCollectionOutcome.COLLECTED: (
                MediaCollectionCycleReasonCode.OBSERVATION_COLLECTED
            ),
            MediaObservationCollectionOutcome.NO_OBSERVATION: (
                MediaCollectionCycleReasonCode.NO_OBSERVATION_SUPPLIED
            ),
            MediaObservationCollectionOutcome.UNSUPPORTED: (
                MediaCollectionCycleReasonCode.OBSERVATION_UNSUPPORTED
            ),
            MediaObservationCollectionOutcome.DEFERRED: (
                MediaCollectionCycleReasonCode.OBSERVATION_DEFERRED
            ),
            MediaObservationCollectionOutcome.BLOCKED: (
                MediaCollectionCycleReasonCode.OBSERVATION_BLOCKED
            ),
            MediaObservationCollectionOutcome.FAILED: (
                MediaCollectionCycleReasonCode.OBSERVATION_FAILED
            ),
            MediaObservationCollectionOutcome.INVALID_RESULT: (
                MediaCollectionCycleReasonCode.INVALID_OBSERVATION_RESULT
            ),
            MediaObservationCollectionOutcome.UNKNOWN: (
                MediaCollectionCycleReasonCode.UNKNOWN_COLLECTION_FAILURE
            ),
        }
        work.reasons.append(outcome_reason[result.outcome])
        if result.outcome in (
            MediaObservationCollectionOutcome.COLLECTED,
            MediaObservationCollectionOutcome.NO_OBSERVATION,
        ):
            facts.valid_or_empty += 1
        else:
            work.partial = True
            work.reasons.append(
                MediaCollectionCycleReasonCode.REQUIRED_OBSERVATION_UNAVAILABLE
                if required
                else MediaCollectionCycleReasonCode.OPTIONAL_OBSERVATION_UNAVAILABLE
            )
        unavailable = list(record.unavailable_capability_ids)
        blocked = list(record.blocked_capability_ids)
        failed = list(record.failed_capability_ids)
        if result.outcome in (
            MediaObservationCollectionOutcome.UNSUPPORTED,
            MediaObservationCollectionOutcome.DEFERRED,
            MediaObservationCollectionOutcome.UNKNOWN,
        ):
            unavailable.append(capability.id)
            facts.deferred = True
        elif result.outcome is MediaObservationCollectionOutcome.BLOCKED:
            blocked.append(capability.id)
            facts.blocked = True
        elif result.outcome in (
            MediaObservationCollectionOutcome.FAILED,
            MediaObservationCollectionOutcome.INVALID_RESULT,
        ):
            failed.append(capability.id)
            facts.failed = True

        if (
            result.candidate_id != candidate_id
            or result.resource_id != record.candidate.primary_resource.id
        ):
            code = (
                MediaCandidateConflictCode.OBSERVATION_CANDIDATE_MISMATCH
                if result.candidate_id != candidate_id
                else MediaCandidateConflictCode.OBSERVATION_RESOURCE_MISMATCH
            )
            conflict = self._make_conflict(
                code,
                (candidate_id, result.candidate_id),
                (record.candidate.proposed_asset_id,),
                (record.candidate.primary_resource.id, result.resource_id),
                (),
                tuple(value.id for value in result.observations),
                result.completed_at or request.requested_at,
            )
            self._retain_conflict(work, conflict, (candidate_id,))
            work.reasons.append(MediaCollectionCycleReasonCode.OBSERVATION_IDENTITY_CONFLICT)
            observations = ()

        old_bundle = work.bundles.get(candidate_id.value)
        old_observations = () if old_bundle is None else old_bundle.all_observations
        by_id = {value.id.value: value for value in old_observations}
        retained = list(old_observations)
        for observation in observations:
            existing = by_id.get(observation.id.value)
            if existing is None:
                retained.append(observation)
                by_id[observation.id.value] = observation
                facts.retained += 1
                work.retained_observations += 1
            elif existing != observation:
                conflict = self._make_conflict(
                    MediaCandidateConflictCode.DUPLICATE_OBSERVATION_ID,
                    (candidate_id,),
                    (record.candidate.proposed_asset_id,),
                    (record.candidate.primary_resource.id,),
                    (),
                    (observation.id,),
                    observation.observed_at,
                )
                self._retain_conflict(work, conflict, (candidate_id,))
                work.reasons.append(MediaCollectionCycleReasonCode.OBSERVATION_IDENTITY_CONFLICT)
        if result.conflicting_observation_ids:
            conflict = self._make_conflict(
                MediaCandidateConflictCode.DUPLICATE_OBSERVATION_ID,
                (candidate_id,),
                (record.candidate.proposed_asset_id,),
                (record.candidate.primary_resource.id,),
                (),
                result.conflicting_observation_ids,
                result.completed_at or request.requested_at,
            )
            self._retain_conflict(work, conflict, (candidate_id,))
            work.reasons.append(MediaCollectionCycleReasonCode.OBSERVATION_IDENTITY_CONFLICT)

        if candidate_id not in work.conflicted and retained:
            created_at = max(
                request.requested_at,
                *(value.observed_at for value in retained),
                *((old_bundle.created_at,) if old_bundle is not None else ()),
                *((result.completed_at,) if result.completed_at is not None else ()),
            )
            bundle = self._build_bundle(record, retained, created_at)
            work.bundles[candidate_id.value] = bundle
            bundle_id: EntityId | None = bundle.id
            observation_ids: Sequence[EntityId] = bundle.observation_ids
        else:
            bundle_id = None if old_bundle is None else old_bundle.id
            observation_ids = () if old_bundle is None else old_bundle.observation_ids
        current_record = work.records[candidate_id.value]
        work.records[candidate_id.value] = replace(
            current_record,
            cumulative_observation_bundle_id=bundle_id,
            cumulative_observation_ids=observation_ids,
            unavailable_capability_ids=unavailable,
            blocked_capability_ids=blocked,
            failed_capability_ids=failed,
            limitations=(*current_record.limitations, *result.limitations),
        )

    def _build_bundle(
        self,
        record: MediaCandidateRecord,
        observations: Sequence[AssetReadinessObservation],
        created_at: datetime,
    ) -> AssetReadinessObservationBundle:
        return AssetReadinessObservationBundle(
            id=_derived_id(
                self._coordinator_id.value,
                "observation-bundle",
                record.candidate.id.value,
            ),
            candidate_id=record.candidate.id,
            resource_id=record.candidate.primary_resource.id,
            created_at=created_at,
            resource_snapshots=tuple(
                value for value in observations if isinstance(value, AssetResourceSnapshot)
            ),
            finalization_observations=tuple(
                value for value in observations if isinstance(value, AssetFinalizationObservation)
            ),
            write_state_observations=tuple(
                value for value in observations if isinstance(value, AssetWriteStateObservation)
            ),
            read_access_observations=tuple(
                value for value in observations if isinstance(value, AssetReadAccessObservation)
            ),
            presence_observations=tuple(
                value
                for value in observations
                if isinstance(value, AssetResourcePresenceObservation)
            ),
        )

    def _finalize_candidate_records(
        self,
        work: _CycleWork,
        context: _PlanContext,
        request: MediaCollectionCycleRequest,
    ) -> None:
        all_required_types = {
            capability.observation_type
            for capability in context.observation_capabilities
            if capability.id in context.required_observation_capability_ids
        }
        for candidate_id in tuple(work.affected):
            record = work.records[candidate_id.value]
            target_id = record.metadata.get("collection_target_id")
            enabled_types = next(
                (
                    set(target.enabled_observation_types)
                    for target in context.plan.targets
                    if target.id.value == target_id
                ),
                set[RuntimeObservationType](),
            )
            required_types = all_required_types & enabled_types
            bundle = work.bundles.get(candidate_id.value)
            supplied_types: set[RuntimeObservationType] = set()
            if bundle is not None:
                supplied_types.update(
                    self._observation_type(value) for value in bundle.all_observations
                )
            facts = work.candidate_facts.get(candidate_id.value, _CandidateCycleFacts())
            if candidate_id in work.conflicted or record.conflict_ids:
                status = MediaCandidateCollectionStatus.CONFLICTED
            elif facts.attempted == 0:
                status = (
                    MediaCandidateCollectionStatus.DEFERRED
                    if facts.deferred or candidate_id in work.deferred
                    else MediaCandidateCollectionStatus.DISCOVERED
                )
            elif facts.blocked and facts.valid_or_empty == 0:
                status = MediaCandidateCollectionStatus.BLOCKED
            elif facts.failed or facts.deferred or facts.blocked:
                status = MediaCandidateCollectionStatus.PARTIALLY_OBSERVED
            else:
                status = MediaCandidateCollectionStatus.OBSERVATIONS_AVAILABLE
            work.records[candidate_id.value] = replace(
                record,
                collection_status=status,
                missing_required_observation_types=tuple(
                    sorted(required_types - supplied_types, key=lambda value: value.value)
                ),
                latest_cycle_id=request.cycle_id,
            )

    def _observation_type(
        self,
        observation: AssetReadinessObservation,
    ) -> RuntimeObservationType:
        if isinstance(observation, AssetResourcePresenceObservation):
            return RuntimeObservationType.RESOURCE_PRESENCE
        if isinstance(observation, AssetResourceSnapshot):
            return RuntimeObservationType.RESOURCE_SNAPSHOT
        if isinstance(observation, AssetFinalizationObservation):
            return RuntimeObservationType.FINALIZATION
        if isinstance(observation, AssetWriteStateObservation):
            return RuntimeObservationType.WRITE_STATE
        return RuntimeObservationType.READ_ACCESS

    def _commit_work(
        self,
        request: MediaCollectionCycleRequest,
        reservation: _ActiveReservation,
        initial_snapshot: AgentRuntimeSnapshot,
        final_snapshot: AgentRuntimeSnapshot,
        work: _CycleWork,
    ) -> MediaCollectionCycleResult:
        if work.interrupted:
            outcome = MediaCollectionCycleOutcome.INTERRUPTED
        elif work.candidate_budget_exhausted or work.observation_budget_exhausted:
            outcome = MediaCollectionCycleOutcome.BUDGET_EXHAUSTED
        elif not work.affected:
            if work.discovery_results and all(
                result.outcome is MediaCandidateDiscoveryOutcome.NO_CANDIDATES
                for result in work.discovery_results
            ):
                outcome = MediaCollectionCycleOutcome.NO_CANDIDATES
            elif any(
                result.outcome
                in (
                    MediaCandidateDiscoveryOutcome.FAILED,
                    MediaCandidateDiscoveryOutcome.INVALID_RESULT,
                )
                for result in work.discovery_results
            ):
                outcome = MediaCollectionCycleOutcome.DISCOVERY_FAILED
            else:
                outcome = MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
        elif work.partial or work.conflicted:
            outcome = MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
        else:
            outcome = MediaCollectionCycleOutcome.COMPLETED
        if outcome is MediaCollectionCycleOutcome.COMPLETED:
            work.reasons.append(MediaCollectionCycleReasonCode.CYCLE_COMPLETED)
        elif outcome in (
            MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS,
            MediaCollectionCycleOutcome.BUDGET_EXHAUSTED,
            MediaCollectionCycleOutcome.DISCOVERY_FAILED,
        ):
            work.reasons.append(MediaCollectionCycleReasonCode.CYCLE_COMPLETED_PARTIALLY)
        work.reasons.extend(
            (
                MediaCollectionCycleReasonCode.NO_READINESS_EVALUATION,
                MediaCollectionCycleReasonCode.NO_ASSET_ASSEMBLY,
            )
        )
        completed_at = max(work.explicit_times)
        with self._lock:
            if self._state.active_cycle_reservation != reservation:
                raise RuntimeError("Media collection reservation changed before commit.")
            previous = reservation.previous_snapshot
            current = MediaCollectionCoordinatorSnapshot(
                coordinator_id=self._coordinator_id,
                runtime_id=self._runtime.identity.runtime_id,
                configuration_id=self._runtime.configuration.id,
                coordinator_revision=previous.coordinator_revision + 1,
                active_cycle_id=None,
                candidate_count=len(work.records),
                conflict_count=len(work.conflicts),
                cumulative_observation_count=sum(
                    len(bundle.all_observations) for bundle in work.bundles.values()
                ),
                completed_cycle_count=previous.completed_cycle_count + 1,
                latest_cycle_id=request.cycle_id,
                latest_cycle_outcome=outcome,
            )
            result = MediaCollectionCycleResult(
                cycle_id=request.cycle_id,
                operation_id=request.operation_id,
                runtime_id=request.runtime_id,
                configuration_id=request.configuration_id,
                collection_plan_id=request.collection_plan_id,
                outcome=outcome,
                reasons=work.reasons,
                previous_coordinator_snapshot=previous,
                current_coordinator_snapshot=current,
                starting_agent_snapshot=initial_snapshot,
                final_agent_snapshot=final_snapshot,
                discovery_results=work.discovery_results,
                candidate_results=tuple(
                    work.records[value.value]
                    for value in sorted(work.affected, key=lambda item: item.value)
                ),
                observation_collection_results=work.observation_results,
                affected_candidate_ids=tuple(work.affected),
                newly_discovered_candidate_ids=tuple(work.new),
                already_known_candidate_ids=tuple(work.known),
                conflicted_candidate_ids=tuple(work.conflicted),
                deferred_candidate_ids=tuple(work.deferred),
                total_candidates_considered=work.considered,
                total_observation_calls_attempted=work.observation_calls,
                total_observations_retained=work.retained_observations,
                remaining_candidate_budget=(request.maximum_total_candidates - work.considered),
                remaining_observation_call_budget=(
                    request.maximum_total_observation_port_calls - work.observation_calls
                ),
                started_at=request.requested_at,
                completed_at=completed_at,
            )
            completed = dict(self._state.completed_cycle_results)
            completed[request.operation_id.value] = _OperationRecord(
                reservation.fingerprint,
                result,
            )
            fingerprints = dict(self._state.operation_fingerprints)
            fingerprints[request.operation_id.value] = reservation.fingerprint
            self._state = _CoordinatorState(
                snapshot=current,
                candidate_records=_mapping(work.records),
                proposed_asset_index=_mapping(work.proposed_index),
                resource_index=_mapping(work.resource_index),
                observation_bundles=_mapping(work.bundles),
                conflicts=_mapping(work.conflicts),
                completed_cycle_results=_mapping(completed),
                operation_fingerprints=_mapping(fingerprints),
                cycle_history=(*self._state.cycle_history, result),
                active_cycle_reservation=None,
            )
        return result

    def _commit_unexpected_failure(
        self,
        request: MediaCollectionCycleRequest,
        reservation: _ActiveReservation,
        initial_snapshot: AgentRuntimeSnapshot,
    ) -> MediaCollectionCycleResult:
        with self._lock:
            if self._state.active_cycle_reservation != reservation:
                return self._rejection(
                    request,
                    MediaCollectionCycleOutcome.FAILED,
                    (MediaCollectionCycleReasonCode.UNKNOWN_COLLECTION_FAILURE,),
                    starting_agent_snapshot=initial_snapshot,
                    final_agent_snapshot=initial_snapshot,
                )
            previous = reservation.previous_snapshot
            current = replace(
                previous,
                coordinator_revision=previous.coordinator_revision + 1,
                active_cycle_id=None,
                completed_cycle_count=previous.completed_cycle_count + 1,
                latest_cycle_id=request.cycle_id,
                latest_cycle_outcome=MediaCollectionCycleOutcome.FAILED,
            )
            result = MediaCollectionCycleResult(
                cycle_id=request.cycle_id,
                operation_id=request.operation_id,
                runtime_id=request.runtime_id,
                configuration_id=request.configuration_id,
                collection_plan_id=request.collection_plan_id,
                outcome=MediaCollectionCycleOutcome.FAILED,
                reasons=(MediaCollectionCycleReasonCode.UNKNOWN_COLLECTION_FAILURE,),
                previous_coordinator_snapshot=previous,
                current_coordinator_snapshot=current,
                starting_agent_snapshot=initial_snapshot,
                final_agent_snapshot=initial_snapshot,
                discovery_results=(),
                candidate_results=(),
                observation_collection_results=(),
                affected_candidate_ids=(),
                newly_discovered_candidate_ids=(),
                already_known_candidate_ids=(),
                conflicted_candidate_ids=(),
                deferred_candidate_ids=(),
                total_candidates_considered=0,
                total_observation_calls_attempted=0,
                total_observations_retained=0,
                remaining_candidate_budget=request.maximum_total_candidates,
                remaining_observation_call_budget=(request.maximum_total_observation_port_calls),
                started_at=request.requested_at,
                completed_at=request.requested_at,
            )
            completed = dict(self._state.completed_cycle_results)
            completed[request.operation_id.value] = _OperationRecord(
                reservation.fingerprint,
                result,
            )
            fingerprints = dict(self._state.operation_fingerprints)
            fingerprints[request.operation_id.value] = reservation.fingerprint
            self._state = replace(
                self._state,
                snapshot=current,
                completed_cycle_results=_mapping(completed),
                operation_fingerprints=_mapping(fingerprints),
                cycle_history=(*self._state.cycle_history, result),
                active_cycle_reservation=None,
            )
            return result


__all__ = ["MediaCandidateCollectionCoordinator"]
