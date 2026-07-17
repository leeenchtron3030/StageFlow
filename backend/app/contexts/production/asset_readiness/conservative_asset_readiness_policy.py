from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletion,
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetReadiness,
    CompletedMediaAssetReadinessStatus,
)
from app.shared.ids import EntityId

from .asset_finalization_observation import AssetFinalizationObservation
from .asset_read_access_observation import (
    AssetReadAccessObservation,
    AssetReadAccessStatus,
)
from .asset_readiness_evaluation import AssetReadinessEvaluation
from .asset_readiness_evaluation_request import AssetReadinessEvaluationRequest
from .asset_readiness_observation_bundle import AssetReadinessObservationBundle
from .asset_readiness_outcome import AssetReadinessOutcome
from .asset_readiness_policy import AssetReadinessPolicy
from .asset_readiness_policy_parameters import AssetReadinessPolicyParameters
from .asset_readiness_reason import AssetReadinessReason, AssetReadinessReasonCode
from .asset_readiness_validation import normalize_entity_ids, normalize_limitations
from .asset_resource_presence_observation import (
    AssetResourcePresenceObservation,
    AssetResourcePresenceStatus,
)
from .asset_resource_snapshot import AssetResourceSnapshot
from .asset_stability_window import AssetStabilityWindow, find_stability_window
from .asset_write_state_observation import (
    AssetWriteStateObservation,
    AssetWriteStateStatus,
)
from .media_asset_candidate import MediaAssetCandidate


@dataclass(frozen=True, slots=True)
class _RouteEvaluation:
    reasons: tuple[AssetReadinessReason, ...]
    supporting_ids: tuple[EntityId, ...]
    limitations: tuple[str, ...]
    qualified: bool


@dataclass(frozen=True, slots=True)
class ConservativeAssetReadinessPolicy(AssetReadinessPolicy):
    """One conservative proof policy over supplied immutable resource facts."""

    policy_id: EntityId
    parameters: AssetReadinessPolicyParameters

    def evaluate(
        self,
        candidate: MediaAssetCandidate,
        observations: AssetReadinessObservationBundle,
        request: AssetReadinessEvaluationRequest,
    ) -> AssetReadinessEvaluation:
        invalid_reasons = self._invalid_request_reasons(candidate, observations, request)
        if invalid_reasons:
            return self._non_safe_result(
                candidate,
                observations,
                request,
                AssetReadinessOutcome.INVALID_REQUEST,
                invalid_reasons,
            )

        conflict_reasons = self._conflict_reasons(candidate, observations)
        if conflict_reasons:
            return self._non_safe_result(
                candidate,
                observations,
                request,
                AssetReadinessOutcome.CONFLICTING_OBSERVATION,
                conflict_reasons,
            )

        if self._is_unsupported(observations):
            return self._non_safe_result(
                candidate,
                observations,
                request,
                AssetReadinessOutcome.UNSUPPORTED_SOURCE,
                self._unsupported_reasons(observations),
            )

        stability_window = find_stability_window(
            observations.resource_snapshots,
            self.parameters.minimum_stable_interval,
        )
        strong_finalization = self._latest_strong_finalization(observations)
        blocking_basis = (
            strong_finalization.observed_at
            if strong_finalization is not None
            else stability_window.ended_at
            if stability_window is not None
            else None
        )
        blocking_reasons = self._blocking_reasons(
            observations,
            basis_time=blocking_basis,
        )
        if blocking_reasons:
            return self._non_safe_result(
                candidate,
                observations,
                request,
                AssetReadinessOutcome.NOT_SAFE_TO_READ,
                blocking_reasons,
            )

        if strong_finalization is not None:
            route = self._strong_route(observations, strong_finalization)
            if route.qualified:
                return self._safe_result(
                    candidate,
                    request,
                    route,
                    strong_finalization.completion_method,
                    strong_finalization.observed_at,
                    strong_finalization.declaring_entity_id,
                    strong_finalization.completion_marker_resource_id,
                    stability_window=None,
                )
            return self._non_safe_result(
                candidate,
                observations,
                request,
                AssetReadinessOutcome.INSUFFICIENT_OBSERVATION,
                route.reasons,
                stability_window=stability_window,
                additional_limitations=route.limitations,
            )

        manual = self._latest_manual_finalization(observations)
        if manual is not None and stability_window is not None:
            route = self._stability_route(
                observations,
                stability_window,
                require_read_access=True,
                require_inactive_write=True,
                basis_time=max(manual.observed_at, stability_window.ended_at),
            )
            manual_reason = _reason(
                AssetReadinessReasonCode.MANUAL_DECLARATION_OBSERVED,
                "Manual finalization declaration was retained with technical safeguards.",
                (manual.id,),
            )
            route = _RouteEvaluation(
                reasons=(manual_reason, *route.reasons),
                supporting_ids=normalize_entity_ids(
                    (manual.id, *route.supporting_ids),
                    "manual route supporting IDs",
                ),
                limitations=route.limitations,
                qualified=route.qualified,
            )
            if route.qualified:
                return self._safe_result(
                    candidate,
                    request,
                    route,
                    CompletedMediaAssetCompletionMethod.MANUAL_DECLARATION,
                    manual.observed_at,
                    manual.declaring_entity_id,
                    manual.completion_marker_resource_id,
                    stability_window=stability_window,
                )

        if stability_window is not None:
            route = self._stability_route(
                observations,
                stability_window,
                require_read_access=self.parameters.require_read_access_for_stability,
                require_inactive_write=self.parameters.require_inactive_write_when_available,
                basis_time=stability_window.ended_at,
            )
            if route.qualified:
                return self._safe_result(
                    candidate,
                    request,
                    route,
                    CompletedMediaAssetCompletionMethod.STABLE_FILE_OBSERVATION,
                    stability_window.ended_at,
                    candidate.source_runtime_id,
                    None,
                    stability_window=stability_window,
                )
            return self._non_safe_result(
                candidate,
                observations,
                request,
                AssetReadinessOutcome.INSUFFICIENT_OBSERVATION,
                route.reasons,
                stability_window=stability_window,
                additional_limitations=route.limitations,
            )

        return self._non_safe_result(
            candidate,
            observations,
            request,
            AssetReadinessOutcome.INSUFFICIENT_OBSERVATION,
            self._insufficient_reasons(observations),
        )

    def _invalid_request_reasons(
        self,
        candidate: MediaAssetCandidate,
        observations: AssetReadinessObservationBundle,
        request: AssetReadinessEvaluationRequest,
    ) -> tuple[AssetReadinessReason, ...]:
        reasons: list[AssetReadinessReason] = []
        if request.policy_id != self.policy_id:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.POLICY_ID_MISMATCH,
                    "Evaluation request policy ID does not match this policy.",
                )
            )
        if request.policy_version != self.parameters.policy_version:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.POLICY_VERSION_MISMATCH,
                    "Evaluation request policy version does not match parameters.",
                )
            )
        if request.candidate_id != candidate.id or observations.candidate_id != candidate.id:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.CANDIDATE_ID_MISMATCH,
                    "Candidate, bundle, and request candidate IDs must match.",
                )
            )
        if (
            request.resource_id != candidate.primary_resource.id
            or observations.resource_id != candidate.primary_resource.id
        ):
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.RESOURCE_ID_MISMATCH,
                    "Candidate, bundle, and request resource IDs must match.",
                )
            )
        if candidate.first_observed_at > request.evaluated_at:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT,
                    "Candidate first observation must not follow evaluation time.",
                )
            )
        if observations.created_at > request.evaluated_at:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT,
                    "Observation bundle creation must not follow evaluation time.",
                )
            )
        future_ids = tuple(
            observation.id
            for observation in observations.all_observations
            if observation.observed_at > request.evaluated_at
        )
        if future_ids:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT,
                    "An observation occurs after the explicit evaluation time.",
                    future_ids,
                )
            )
        runtime_mismatches = tuple(
            observation.id
            for observation in observations.all_observations
            if observation.source_runtime_id is not None
            and observation.source_runtime_id != candidate.source_runtime_id
        )
        if runtime_mismatches:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.SOURCE_RUNTIME_MISMATCH,
                    "Observation source Runtime conflicts with the candidate Runtime.",
                    runtime_mismatches,
                )
            )
        return tuple(reasons)

    def _conflict_reasons(
        self,
        candidate: MediaAssetCandidate,
        observations: AssetReadinessObservationBundle,
    ) -> tuple[AssetReadinessReason, ...]:
        reasons: list[AssetReadinessReason] = []
        if observations.conflicting_observation_ids:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.DUPLICATE_OBSERVATION_ID,
                    "One observation ID describes conflicting resource facts.",
                    observations.conflicting_observation_ids,
                )
            )
        replaced = tuple(
            observation.id
            for observation in observations.presence_observations
            if observation.status is AssetResourcePresenceStatus.REPLACED
        )
        if replaced:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.RESOURCE_REPLACED,
                    "A replacement observation prevents silent candidate reuse.",
                    replaced,
                )
            )
        identity_conflicts = self._identity_conflict_ids(candidate, observations)
        if identity_conflicts:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.RESOURCE_IDENTITY_CHANGED,
                    "Supplied resource identity, host, or volume facts conflict.",
                    identity_conflicts,
                )
            )
        same_time_conflicts = self._same_time_conflict_ids(observations)
        if same_time_conflicts:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.OBSERVATION_TIMESTAMP_CONFLICT,
                    "Contradictory states were observed at the same timestamp.",
                    same_time_conflicts,
                )
            )
        finalization = self._latest_strong_finalization(observations)
        if finalization is not None:
            active_after = tuple(
                observation.id
                for observation in observations.write_state_observations
                if observation.observed_at >= finalization.observed_at
                and observation.status is AssetWriteStateStatus.ACTIVE
            )
            if active_after:
                reasons.extend(
                    (
                        _reason(
                            AssetReadinessReasonCode.FINALIZATION_CONTRADICTED,
                            "Active writing contradicts the supplied finalization basis.",
                            (finalization.id, *active_after),
                        ),
                        _reason(
                            AssetReadinessReasonCode.ACTIVE_WRITE_OBSERVED,
                            "Active writing was observed after claimed finalization.",
                            active_after,
                        ),
                    )
                )
            snapshots_before = tuple(
                snapshot
                for snapshot in observations.resource_snapshots
                if snapshot.observed_at <= finalization.observed_at
            )
            snapshots_after = tuple(
                snapshot
                for snapshot in observations.resource_snapshots
                if snapshot.observed_at > finalization.observed_at
            )
            comparison_snapshots = (
                (*(_latest_snapshot(snapshots_before),), *snapshots_after)
                if snapshots_before
                else snapshots_after
            )
            size_changed = len(
                {snapshot.size_bytes for snapshot in comparison_snapshots}
            ) > 1
            modification_times = {
                snapshot.filesystem_modified_at
                for snapshot in comparison_snapshots
                if snapshot.filesystem_modified_at is not None
            }
            modification_changed = len(modification_times) > 1
            if size_changed or modification_changed:
                snapshot_ids = tuple(snapshot.id for snapshot in comparison_snapshots)
                reasons.extend(
                    (
                        _reason(
                            AssetReadinessReasonCode.FINALIZATION_CONTRADICTED,
                            "Resource growth contradicts the supplied finalization basis.",
                            (finalization.id, *snapshot_ids),
                        ),
                        _reason(
                            AssetReadinessReasonCode.RESOURCE_CONTINUED_GROWING,
                            "Resource size changed after claimed finalization.",
                            snapshot_ids,
                        ),
                    )
                )
                if modification_changed:
                    reasons.append(
                        _reason(
                            AssetReadinessReasonCode.MODIFICATION_TIMESTAMP_CHANGED,
                            "Resource modification time changed after finalization.",
                            snapshot_ids,
                        )
                    )
        return tuple(reasons)

    def _identity_conflict_ids(
        self,
        candidate: MediaAssetCandidate,
        observations: AssetReadinessObservationBundle,
    ) -> tuple[EntityId, ...]:
        conflicts: list[EntityId] = []
        tokens = {
            snapshot.stable_resource_identity_token
            for snapshot in observations.resource_snapshots
            if snapshot.stable_resource_identity_token is not None
        } | {
            presence.observed_resource_identity_token
            for presence in observations.presence_observations
            if presence.observed_resource_identity_token is not None
        }
        if len(tokens) > 1:
            conflicts.extend(
                observation.id
                for observation in observations.all_observations
                if (
                    isinstance(observation, AssetResourceSnapshot)
                    and observation.stable_resource_identity_token is not None
                )
                or (
                    isinstance(observation, AssetResourcePresenceObservation)
                    and observation.observed_resource_identity_token is not None
                )
            )
        expected_host = candidate.source_host_id or candidate.primary_resource.source_host_id
        expected_volume = candidate.primary_resource.source_volume_id
        for snapshot in observations.resource_snapshots:
            if (
                expected_host is not None
                and snapshot.source_host_id is not None
                and snapshot.source_host_id != expected_host
            ) or (
                expected_volume is not None
                and snapshot.source_volume_id is not None
                and snapshot.source_volume_id != expected_volume
            ):
                conflicts.append(snapshot.id)
        return normalize_entity_ids(conflicts, "identity conflict IDs")

    def _same_time_conflict_ids(
        self,
        observations: AssetReadinessObservationBundle,
    ) -> tuple[EntityId, ...]:
        return normalize_entity_ids(
            (
                *_conflicting_at_same_time(
                    observations.write_state_observations,
                    observed_at=lambda observation: observation.observed_at,
                    status=lambda observation: observation.status,
                    identity=lambda observation: observation.id,
                ),
                *_conflicting_at_same_time(
                    observations.read_access_observations,
                    observed_at=lambda observation: observation.observed_at,
                    status=lambda observation: observation.status,
                    identity=lambda observation: observation.id,
                ),
                *_conflicting_at_same_time(
                    observations.presence_observations,
                    observed_at=lambda observation: observation.observed_at,
                    status=lambda observation: observation.status,
                    identity=lambda observation: observation.id,
                ),
            ),
            "same-time conflict IDs",
        )

    def _blocking_reasons(
        self,
        observations: AssetReadinessObservationBundle,
        *,
        basis_time: datetime | None,
    ) -> tuple[AssetReadinessReason, ...]:
        reasons: list[AssetReadinessReason] = []
        latest_presence = _latest_presence(observations.presence_observations)
        if (
            latest_presence is not None
            and latest_presence.status is AssetResourcePresenceStatus.MISSING
            and (basis_time is None or latest_presence.observed_at >= basis_time)
        ):
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.RESOURCE_MISSING,
                    "The latest supplied presence state reports the resource missing.",
                    (latest_presence.id,),
                )
            )
        latest_access = _latest_access(observations.read_access_observations)
        if (
            latest_access is not None
            and latest_access.status is AssetReadAccessStatus.UNREADABLE
            and (basis_time is None or latest_access.observed_at >= basis_time)
        ):
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.READ_ACCESS_FAILED,
                    "The latest supplied read-access result is unreadable.",
                    (latest_access.id,),
                )
            )
        latest_write = _latest_write(observations.write_state_observations)
        if (
            latest_write is not None
            and latest_write.status is AssetWriteStateStatus.ACTIVE
            and (basis_time is None or latest_write.observed_at >= basis_time)
        ):
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.ACTIVE_WRITE_OBSERVED,
                    "The latest supplied write state is active.",
                    (latest_write.id,),
                )
            )
        snapshots = tuple(
            sorted(
                (
                    snapshot
                    for snapshot in observations.resource_snapshots
                    if basis_time is None or snapshot.observed_at >= basis_time
                ),
                key=lambda snapshot: (snapshot.observed_at, snapshot.id.value),
            )
        )
        if len(snapshots) >= 2:
            previous, latest = snapshots[-2:]
            if previous.size_bytes != latest.size_bytes:
                reasons.append(
                    _reason(
                        AssetReadinessReasonCode.RESOURCE_CONTINUED_GROWING,
                        "The latest resource snapshots have different sizes.",
                        (previous.id, latest.id),
                    )
                )
            elif (
                previous.filesystem_modified_at is not None
                and latest.filesystem_modified_at is not None
                and previous.filesystem_modified_at != latest.filesystem_modified_at
            ):
                reasons.append(
                    _reason(
                        AssetReadinessReasonCode.MODIFICATION_TIMESTAMP_CHANGED,
                        "The latest stable-size snapshots changed modification time.",
                        (previous.id, latest.id),
                    )
                )
        return tuple(reasons)

    def _strong_route(
        self,
        observations: AssetReadinessObservationBundle,
        finalization: AssetFinalizationObservation,
    ) -> _RouteEvaluation:
        reasons = [
            _reason_for_finalization(finalization),
            _reason(
                AssetReadinessReasonCode.RESOURCE_IDENTITY_CONSISTENT,
                "No supplied observation changes the resource identity.",
                (finalization.id,),
            ),
            _reason(
                AssetReadinessReasonCode.NO_CONTRADICTORY_LATER_SNAPSHOT,
                "No later supplied snapshot contradicts finalization.",
                tuple(
                    snapshot.id
                    for snapshot in observations.resource_snapshots
                    if snapshot.observed_at >= finalization.observed_at
                ),
            ),
        ]
        supporting_ids: list[EntityId] = [finalization.id]
        limitations: list[str] = list(finalization.limitations)
        qualified = True
        presence = _latest_presence_after(
            observations.presence_observations,
            finalization.observed_at,
        )
        if self.parameters.require_post_finalization_presence and (
            presence is None or presence.status is not AssetResourcePresenceStatus.PRESENT
        ):
            reasons.extend(
                (
                    _reason(
                        AssetReadinessReasonCode.RESOURCE_PRESENCE_NOT_CONFIRMED,
                        "Post-finalization resource presence was not confirmed.",
                    ),
                    _reason(
                        AssetReadinessReasonCode.REQUIRED_POST_FINALIZATION_OBSERVATION_MISSING,
                        "Required post-finalization presence observation is missing.",
                    ),
                )
            )
            qualified = False
        elif presence is not None and presence.status is AssetResourcePresenceStatus.PRESENT:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.RESOURCE_PRESENT_AFTER_FINALIZATION,
                    "Resource presence was confirmed after finalization.",
                    (presence.id,),
                )
            )
            supporting_ids.append(presence.id)
            limitations.extend(presence.limitations)
        write = _latest_write_after(
            observations.write_state_observations,
            finalization.observed_at,
        )
        if write is not None and write.status is AssetWriteStateStatus.INACTIVE:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.INACTIVE_WRITE_STATE_OBSERVED,
                    "Inactive write state was observed after finalization.",
                    (write.id,),
                )
            )
            supporting_ids.append(write.id)
            limitations.extend(write.limitations)
        else:
            limitations.append("write-state inspection unavailable")
        access = _latest_access_after(
            observations.read_access_observations,
            finalization.observed_at,
        )
        if access is not None and access.status is AssetReadAccessStatus.READABLE:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.READ_ACCESS_CONFIRMED,
                    "Non-destructive read access was confirmed after finalization.",
                    (access.id,),
                )
            )
            supporting_ids.append(access.id)
            limitations.extend(access.limitations)
        else:
            limitations.append("read access not independently assessed")
        return _RouteEvaluation(
            reasons=tuple(reasons),
            supporting_ids=normalize_entity_ids(supporting_ids, "strong route supporting IDs"),
            limitations=normalize_limitations(limitations, "strong route limitations"),
            qualified=qualified,
        )

    def _stability_route(
        self,
        observations: AssetReadinessObservationBundle,
        window: AssetStabilityWindow,
        *,
        require_read_access: bool,
        require_inactive_write: bool,
        basis_time: datetime,
    ) -> _RouteEvaluation:
        reasons = [
            _reason(
                AssetReadinessReasonCode.STABLE_INTERVAL_SATISFIED,
                "Resource snapshots satisfy the configured stable interval.",
                window.snapshot_ids,
            ),
            _reason(
                AssetReadinessReasonCode.RESOURCE_IDENTITY_CONSISTENT,
                "Stable-window snapshots preserve one resource identity.",
                window.snapshot_ids,
            ),
            _reason(
                AssetReadinessReasonCode.NO_CONTRADICTORY_LATER_SNAPSHOT,
                "No later supplied snapshot contradicts the selected stability window.",
                (window.last_snapshot_id,),
            ),
        ]
        supporting_ids: list[EntityId] = list(window.snapshot_ids)
        limitations: list[str] = list(window.limitations)
        qualified = True
        presence = _latest_presence_after(observations.presence_observations, basis_time)
        if presence is None or presence.status is not AssetResourcePresenceStatus.PRESENT:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.RESOURCE_PRESENCE_NOT_CONFIRMED,
                    "Resource presence was not confirmed at or after the stable interval.",
                )
            )
            qualified = False
        else:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.RESOURCE_PRESENT_AFTER_FINALIZATION,
                    "Resource remained present after the stability basis.",
                    (presence.id,),
                )
            )
            supporting_ids.append(presence.id)
            limitations.extend(presence.limitations)
        write = _latest_write_after(observations.write_state_observations, basis_time)
        if write is not None and write.status is AssetWriteStateStatus.INACTIVE:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.INACTIVE_WRITE_STATE_OBSERVED,
                    "Inactive write state was observed after the stability basis.",
                    (write.id,),
                )
            )
            supporting_ids.append(write.id)
            limitations.extend(write.limitations)
        elif require_inactive_write:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.WRITE_STATE_UNKNOWN,
                    "Inactive write state is required but was not supplied.",
                )
            )
            limitations.append("write-state inspection unavailable")
            qualified = False
        else:
            limitations.append("write state not independently assessed")
        access = _latest_access_after(observations.read_access_observations, basis_time)
        if access is not None and access.status is AssetReadAccessStatus.READABLE:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.READ_ACCESS_CONFIRMED,
                    "Non-destructive read access was confirmed after the stability basis.",
                    (access.id,),
                )
            )
            supporting_ids.append(access.id)
            limitations.extend(access.limitations)
        elif require_read_access:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.READ_ACCESS_NOT_ASSESSED,
                    "Required non-destructive read access was not confirmed.",
                )
            )
            limitations.append("read access not independently assessed")
            qualified = False
        else:
            limitations.append("read access not independently assessed")
        return _RouteEvaluation(
            reasons=tuple(reasons),
            supporting_ids=normalize_entity_ids(
                supporting_ids,
                "stability route supporting IDs",
            ),
            limitations=normalize_limitations(limitations, "stability route limitations"),
            qualified=qualified,
        )

    def _insufficient_reasons(
        self,
        observations: AssetReadinessObservationBundle,
    ) -> tuple[AssetReadinessReason, ...]:
        reasons: list[AssetReadinessReason] = []
        snapshots = observations.resource_snapshots
        if not observations.all_observations:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.NO_COMPLETION_BASIS,
                    "No supplied observation establishes a completion basis.",
                )
            )
        elif len(snapshots) < 2:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.INSUFFICIENT_SNAPSHOTS,
                    "At least two compatible snapshots are required for stability.",
                    tuple(snapshot.id for snapshot in snapshots),
                )
            )
        elif _has_equal_snapshot_pair(snapshots):
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.STABLE_INTERVAL_TOO_SHORT,
                    "Compatible snapshots do not span the configured stable interval.",
                    tuple(snapshot.id for snapshot in snapshots),
                )
            )
        if any(
            observation.completion_method is CompletedMediaAssetCompletionMethod.UNKNOWN
            for observation in observations.finalization_observations
        ):
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.FINALIZATION_METHOD_UNKNOWN,
                    "Unknown finalization method cannot establish completion.",
                    tuple(
                        observation.id
                        for observation in observations.finalization_observations
                        if observation.completion_method
                        is CompletedMediaAssetCompletionMethod.UNKNOWN
                    ),
                )
            )
        if not reasons:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.NO_COMPLETION_BASIS,
                    "Supplied observations do not establish a supported completion basis.",
                )
            )
        return tuple(reasons)

    def _is_unsupported(self, observations: AssetReadinessObservationBundle) -> bool:
        if not observations.all_observations:
            return False
        if observations.resource_snapshots:
            return False
        if self._latest_supported_finalization(observations) is not None:
            return False
        if any(
            observation.status
            in (
                AssetWriteStateStatus.ACTIVE,
                AssetReadAccessStatus.UNREADABLE,
                AssetResourcePresenceStatus.MISSING,
                AssetResourcePresenceStatus.REPLACED,
            )
            for observation in observations.all_observations
            if isinstance(
                observation,
                AssetWriteStateObservation
                | AssetReadAccessObservation
                | AssetResourcePresenceObservation,
            )
        ):
            return False
        return True

    def _unsupported_reasons(
        self,
        observations: AssetReadinessObservationBundle,
    ) -> tuple[AssetReadinessReason, ...]:
        reasons: list[AssetReadinessReason] = []
        unknown = tuple(
            observation.id
            for observation in observations.finalization_observations
            if observation.completion_method is CompletedMediaAssetCompletionMethod.UNKNOWN
        )
        unsupported = tuple(
            observation.id
            for observation in observations.finalization_observations
            if observation.completion_method
            is CompletedMediaAssetCompletionMethod.OTHER_SUPPORTED_METHOD
        )
        if unknown:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.FINALIZATION_METHOD_UNKNOWN,
                    "Unknown finalization semantics cannot establish completion.",
                    unknown,
                )
            )
        if unsupported:
            reasons.append(
                _reason(
                    AssetReadinessReasonCode.UNSUPPORTED_COMPLETION_METHOD,
                    "The supplied finalization method is not accepted by this policy.",
                    unsupported,
                )
            )
        reasons.append(
            _reason(
                AssetReadinessReasonCode.UNSUPPORTED_SOURCE_CAPABILITY,
                "Supplied capabilities establish no supported completion route.",
                observations.observation_ids,
            )
        )
        return tuple(reasons)

    def _latest_strong_finalization(
        self,
        observations: AssetReadinessObservationBundle,
    ) -> AssetFinalizationObservation | None:
        supported = tuple(
            observation
            for observation in observations.finalization_observations
            if observation.completion_method
            in self.parameters.accepted_strong_finalization_methods
        )
        return _latest_finalization(supported)

    @staticmethod
    def _latest_manual_finalization(
        observations: AssetReadinessObservationBundle,
    ) -> AssetFinalizationObservation | None:
        manual = tuple(
            observation
            for observation in observations.finalization_observations
            if observation.completion_method
            is CompletedMediaAssetCompletionMethod.MANUAL_DECLARATION
        )
        return _latest_finalization(manual)

    def _latest_supported_finalization(
        self,
        observations: AssetReadinessObservationBundle,
    ) -> AssetFinalizationObservation | None:
        supported = tuple(
            observation
            for observation in observations.finalization_observations
            if observation.completion_method
            in (
                *self.parameters.accepted_strong_finalization_methods,
                CompletedMediaAssetCompletionMethod.MANUAL_DECLARATION,
            )
        )
        return _latest_finalization(supported)

    def _safe_result(
        self,
        candidate: MediaAssetCandidate,
        request: AssetReadinessEvaluationRequest,
        route: _RouteEvaluation,
        method: CompletedMediaAssetCompletionMethod,
        finalized_at: datetime,
        declaring_id: EntityId,
        marker_id: EntityId | None,
        *,
        stability_window: AssetStabilityWindow | None,
    ) -> AssetReadinessEvaluation:
        completion = CompletedMediaAssetCompletion(
            id=request.completion_declaration_id,
            method=method,
            is_finalized=True,
            finalized_at=finalized_at,
            declaring_runtime_or_adapter_id=declaring_id,
            source_reference_ids=route.supporting_ids,
            completion_marker_reference_id=marker_id,
            limitations=route.limitations,
            metadata={
                "asset_readiness_policy_id": self.policy_id.value,
                "asset_readiness_policy_version": self.parameters.policy_version,
            },
        )
        readiness = CompletedMediaAssetReadiness(
            id=request.readiness_declaration_id,
            status=CompletedMediaAssetReadinessStatus.SAFE_TO_READ,
            assessed_at=request.evaluated_at,
            assessment_method_identifiers=(
                "conservative_asset_readiness_policy",
                self.parameters.policy_version,
            ),
            supporting_check_ids=route.supporting_ids,
            limitations=route.limitations,
            metadata={"asset_readiness_policy_id": self.policy_id.value},
        )
        return AssetReadinessEvaluation(
            evaluation_id=request.evaluation_id,
            policy_id=self.policy_id,
            policy_version=self.parameters.policy_version,
            candidate_id=candidate.id,
            proposed_asset_id=candidate.proposed_asset_id,
            resource_id=candidate.primary_resource.id,
            outcome=AssetReadinessOutcome.SAFE_TO_READ,
            reasons=route.reasons,
            evaluated_at=request.evaluated_at,
            policy_parameters=self.parameters,
            supporting_observation_ids=route.supporting_ids,
            selected_completion_method=method,
            stability_window=stability_window,
            completion_declaration=completion,
            readiness_declaration=readiness,
            limitations=route.limitations,
            metadata={"route": method.value},
        )

    def _non_safe_result(
        self,
        candidate: MediaAssetCandidate,
        observations: AssetReadinessObservationBundle,
        request: AssetReadinessEvaluationRequest,
        outcome: AssetReadinessOutcome,
        reasons: Sequence[AssetReadinessReason],
        *,
        stability_window: AssetStabilityWindow | None = None,
        additional_limitations: Sequence[str] = (),
    ) -> AssetReadinessEvaluation:
        reason_ids = tuple(
            observation_id
            for reason in reasons
            for observation_id in reason.observation_ids
        )
        limitations = normalize_limitations(
            (
                *(
                    limitation
                    for observation in observations.all_observations
                    for limitation in observation.limitations
                ),
                *additional_limitations,
            ),
            "non-safe evaluation limitations",
        )
        readiness = None
        if outcome in (
            AssetReadinessOutcome.NOT_SAFE_TO_READ,
            AssetReadinessOutcome.INSUFFICIENT_OBSERVATION,
            AssetReadinessOutcome.UNSUPPORTED_SOURCE,
        ):
            status = (
                CompletedMediaAssetReadinessStatus.NOT_SAFE_TO_READ
                if outcome is AssetReadinessOutcome.NOT_SAFE_TO_READ
                else CompletedMediaAssetReadinessStatus.UNKNOWN
            )
            readiness = CompletedMediaAssetReadiness(
                id=request.readiness_declaration_id,
                status=status,
                assessed_at=request.evaluated_at,
                assessment_method_identifiers=(
                    "conservative_asset_readiness_policy",
                    self.parameters.policy_version,
                ),
                supporting_check_ids=reason_ids,
                limitations=limitations,
                metadata={"asset_readiness_policy_id": self.policy_id.value},
            )
        blocking_ids = reason_ids if outcome in (
            AssetReadinessOutcome.NOT_SAFE_TO_READ,
            AssetReadinessOutcome.CONFLICTING_OBSERVATION,
        ) else ()
        return AssetReadinessEvaluation(
            evaluation_id=request.evaluation_id,
            policy_id=self.policy_id,
            policy_version=self.parameters.policy_version,
            candidate_id=candidate.id,
            proposed_asset_id=candidate.proposed_asset_id,
            resource_id=candidate.primary_resource.id,
            outcome=outcome,
            reasons=reasons,
            evaluated_at=request.evaluated_at,
            policy_parameters=self.parameters,
            blocking_observation_ids=blocking_ids,
            stability_window=stability_window,
            readiness_declaration=readiness,
            limitations=limitations,
        )


def _reason(
    code: AssetReadinessReasonCode,
    message: str,
    observation_ids: Sequence[EntityId] = (),
) -> AssetReadinessReason:
    return AssetReadinessReason(
        code=code,
        message=message,
        observation_ids=observation_ids,
    )


def _reason_for_finalization(
    observation: AssetFinalizationObservation,
) -> AssetReadinessReason:
    mapping = {
        CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION: (
            AssetReadinessReasonCode.EXPLICIT_RECORDER_FINALIZATION_OBSERVED,
            "Explicit recorder finalization was supplied.",
        ),
        CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION: (
            AssetReadinessReasonCode.CLOSED_SEGMENT_NOTIFICATION_OBSERVED,
            "Closed-segment notification was supplied.",
        ),
        CompletedMediaAssetCompletionMethod.ATOMIC_RENAME_OBSERVED: (
            AssetReadinessReasonCode.ATOMIC_RENAME_OBSERVED,
            "Atomic rename into finalized resource identity was supplied.",
        ),
        CompletedMediaAssetCompletionMethod.SIDECAR_COMPLETION_MARKER: (
            AssetReadinessReasonCode.COMPLETION_MARKER_OBSERVED,
            "Completion sidecar or marker was supplied.",
        ),
    }
    code, message = mapping[observation.completion_method]
    return _reason(code, message, (observation.id,))


def _latest_finalization(
    observations: Sequence[AssetFinalizationObservation],
) -> AssetFinalizationObservation | None:
    return max(
        observations,
        key=lambda observation: (
            observation.observed_at,
            observation.completion_method.value,
            observation.id.value,
        ),
        default=None,
    )


def _latest_write(
    observations: Sequence[AssetWriteStateObservation],
) -> AssetWriteStateObservation | None:
    return max(observations, key=lambda item: (item.observed_at, item.id.value), default=None)


def _latest_access(
    observations: Sequence[AssetReadAccessObservation],
) -> AssetReadAccessObservation | None:
    return max(observations, key=lambda item: (item.observed_at, item.id.value), default=None)


def _latest_presence(
    observations: Sequence[AssetResourcePresenceObservation],
) -> AssetResourcePresenceObservation | None:
    return max(observations, key=lambda item: (item.observed_at, item.id.value), default=None)


def _latest_snapshot(
    observations: Sequence[AssetResourceSnapshot],
) -> AssetResourceSnapshot:
    return max(observations, key=lambda item: (item.observed_at, item.id.value))


def _latest_write_after(
    observations: Sequence[AssetWriteStateObservation],
    basis_time: datetime,
) -> AssetWriteStateObservation | None:
    return _latest_write(tuple(item for item in observations if item.observed_at >= basis_time))


def _latest_access_after(
    observations: Sequence[AssetReadAccessObservation],
    basis_time: datetime,
) -> AssetReadAccessObservation | None:
    return _latest_access(tuple(item for item in observations if item.observed_at >= basis_time))


def _latest_presence_after(
    observations: Sequence[AssetResourcePresenceObservation],
    basis_time: datetime,
) -> AssetResourcePresenceObservation | None:
    return _latest_presence(tuple(item for item in observations if item.observed_at >= basis_time))


def _has_equal_snapshot_pair(snapshots: Sequence[AssetResourceSnapshot]) -> bool:
    ordered = tuple(sorted(snapshots, key=lambda item: (item.observed_at, item.id.value)))
    return any(
        first.size_bytes == second.size_bytes
        and (
            first.filesystem_modified_at is None
            or second.filesystem_modified_at is None
            or first.filesystem_modified_at == second.filesystem_modified_at
        )
        and (
            first.stable_resource_identity_token is None
            or second.stable_resource_identity_token is None
            or first.stable_resource_identity_token
            == second.stable_resource_identity_token
        )
        for first, second in zip(ordered, ordered[1:], strict=False)
    )


def _conflicting_at_same_time[T, S: Hashable](
    observations: Sequence[T],
    *,
    observed_at: Callable[[T], datetime],
    status: Callable[[T], S],
    identity: Callable[[T], EntityId],
) -> tuple[EntityId, ...]:
    by_time: dict[datetime, list[T]] = {}
    for observation in observations:
        by_time.setdefault(observed_at(observation), []).append(observation)
    return tuple(
        identity(observation)
        for same_time in by_time.values()
        if len({status(observation) for observation in same_time}) > 1
        for observation in same_time
    )
