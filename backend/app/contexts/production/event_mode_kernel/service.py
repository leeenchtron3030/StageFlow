from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol

from app.contexts.events import (
    EventStageBootstrapRequest,
    EventStageBootstrapResult,
    ProgramExpectation,
)
from app.contexts.production.asset_readiness import (
    AssetReadinessEvaluation,
    AssetReadinessOutcome,
)
from app.contexts.production.completed_media_asset import CompletedMediaAsset
from app.contexts.production.ingress import (
    IngressRegistrationRequest,
    IngressRegistrationStatus,
    IngressRepository,
    StableSourceIdentity,
)
from app.contexts.production.media_collection import MediaCandidateDiscoveryResult
from app.contexts.production.production_event import (
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.time import Clock

from .contracts import (
    AssociationAuthority,
    AssociationInputReference,
    AssociationStatus,
    CompletionDecision,
    EpistemicKind,
    MediaAssociation,
    MediaCandidate,
    MediaRegistrationState,
    ReconciliationRun,
    ReconciliationStatus,
    RegisteredMediaAsset,
    ResourceObservation,
    Session,
    SessionActivityState,
    SessionBoundaryProposal,
    SessionPackageState,
    StartSessionRequest,
)
from .repository import (
    EventModeKernelRepository,
    KernelConflictError,
    KernelNotFoundError,
    KernelStorageUnavailableError,
)


class AssetIngressPublisher(Protocol):
    def publish(self, asset: RegisteredMediaAsset, *, received_at: datetime) -> EntityId: ...


_ASSOCIATION_POLICY_ID = "stageflow.kernel.media-association"
_ASSOCIATION_POLICY_VERSION = "1.1.0"


def _command_digest(kind: str, values: Mapping[str, object]) -> str:
    normalized = {
        key: (
            value.astimezone(UTC).isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, EntityId)
            else value
        )
        for key, value in values.items()
    }
    document = json.dumps(
        {"kind": kind, **normalized}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


class StableAssetIngressPublisher:
    def __init__(self, repository: IngressRepository) -> None:
        self._repository = repository

    def publish(self, asset: RegisteredMediaAsset, *, received_at: datetime) -> EntityId:
        occurred_at = asset.media_ended_at or asset.registered_at
        result = self._repository.register(
            IngressRegistrationRequest(
                source_identity=StableSourceIdentity(
                    namespace="stageflow.completed_media_asset",
                    identifier=asset.id.value,
                ),
                event_type=ProductionEventType.MEDIA_FILE_FINALIZED,
                event_source=ProductionEventSource.INTERNAL_SYSTEM,
                payload=ProductionEventPayload(
                    {
                        "asset_id": asset.id.value,
                        "manifest_id": asset.manifest_id.value,
                        "candidate_id": asset.candidate_id.value,
                        "stage_id": asset.stage_id.value,
                        "registration_status": "registered",
                    }
                ),
                correlation_id=CorrelationId(asset.id.value),
                occurred_at=occurred_at,
                received_at=max(received_at, occurred_at),
                source_event_key=f"completed-media-asset:{asset.id.value}",
                authoritative_source_facts={
                    "asset_id": asset.id,
                    "manifest_id": asset.manifest_id,
                    "candidate_id": asset.candidate_id,
                    "stage_id": asset.stage_id,
                },
            )
        )
        if result.status is IngressRegistrationStatus.STORAGE_UNAVAILABLE:
            raise KernelStorageUnavailableError("asset_ingress_storage_unavailable")
        if result.status is IngressRegistrationStatus.CONFLICT:
            raise KernelConflictError("asset_ingress_identity_conflict")
        if result.record is None:
            raise KernelStorageUnavailableError("asset_ingress_record_missing")
        return result.record.production_event_id


class DurableEventModeKernel:
    def __init__(
        self,
        *,
        repository: EventModeKernelRepository,
        clock: Clock,
        asset_ingress_publisher: AssetIngressPublisher | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.asset_ingress_publisher = asset_ingress_publisher

    def bootstrap(self, request: EventStageBootstrapRequest) -> EventStageBootstrapResult:
        return self.repository.bootstrap(request)

    def record_program_expectation(
        self,
        *,
        event_id: EntityId,
        key: str,
        title: str,
        speakers: Sequence[str] = (),
        stage_id: EntityId | None = None,
        planned_start: datetime | None = None,
        planned_end: datetime | None = None,
        external_references: Mapping[str, str] | None = None,
    ) -> ProgramExpectation:
        if stage_id is not None and all(
            stage.id != stage_id for stage in self.repository.list_stages(event_id)
        ):
            raise KernelConflictError("program_expectation_stage_event_mismatch")
        return self.repository.put_program_expectation(
            ProgramExpectation(
                id=EntityId.new(),
                event_id=event_id,
                key=key,
                stage_id=stage_id,
                title=title,
                speakers=speakers,
                planned_start=planned_start,
                planned_end=planned_end,
                external_references=external_references or {},
                revision=1,
                recorded_at=self.clock.now(),
            )
        )

    def start_session(self, request: StartSessionRequest) -> Session:
        return self.repository.start_session(request)

    def correct_session_boundary(
        self,
        *,
        operation_id: EntityId,
        session_id: EntityId,
        boundary_kind: str,
        boundary_at: datetime,
        actor_id: EntityId,
        reason: str,
    ) -> Session:
        request_digest = _command_digest(
            "session_boundary_correction",
            {
                "session_id": session_id,
                "boundary_kind": boundary_kind,
                "boundary_at": boundary_at,
                "actor_id": actor_id,
                "reason": reason.strip(),
            },
        )
        session, _ = self.repository.correct_boundary(
            session_id=session_id,
            boundary_kind=boundary_kind,
            boundary_at=boundary_at,
            actor_id=actor_id,
            reason=reason,
            decided_at=self.clock.now(),
            operation_id=operation_id,
            request_digest=request_digest,
        )
        return session

    def propose_session_boundary(
        self,
        *,
        session_id: EntityId,
        boundary_kind: str,
        boundary_at: datetime,
        epistemic_kind: EpistemicKind,
        proposer_id: EntityId,
        evidence_ids: Sequence[EntityId],
        policy_id: str,
        policy_version: str,
        reason: str,
        model_id: str | None = None,
        model_version: str | None = None,
    ) -> SessionBoundaryProposal:
        return self.repository.put_boundary_proposal(
            SessionBoundaryProposal(
                id=EntityId.new(),
                session_id=session_id,
                boundary_kind=boundary_kind,
                boundary_at=boundary_at,
                epistemic_kind=epistemic_kind,
                proposer_id=proposer_id,
                evidence_ids=evidence_ids,
                policy_id=policy_id,
                policy_version=policy_version,
                reason=reason,
                proposed_at=self.clock.now(),
                model_id=model_id,
                model_version=model_version,
            )
        )

    def register_candidate(self, candidate: MediaCandidate) -> MediaCandidate:
        return self.repository.register_candidate(candidate)

    def retain_discovery_results(
        self,
        *,
        results: Sequence[MediaCandidateDiscoveryResult],
        source_bindings_by_target_id: Mapping[EntityId, str],
    ) -> tuple[MediaCandidate, ...]:
        retained: list[MediaCandidate] = []
        for result in results:
            for discovered in result.discovered_candidates:
                source_binding = source_bindings_by_target_id.get(
                    discovered.collection_target_id
                )
                if source_binding is None:
                    raise KernelConflictError("discovery_target_binding_missing")
                stage_id = discovered.candidate.context.stage_id
                if stage_id is None:
                    raise KernelConflictError("discovered_candidate_stage_missing")
                retained.append(
                    self.repository.register_candidate(
                        MediaCandidate(
                            id=discovered.candidate.id,
                            proposed_asset_id=discovered.candidate.proposed_asset_id,
                            stage_id=stage_id,
                            source_binding_key=source_binding,
                            source_reference=(
                                discovered.candidate.primary_resource.source_location.location_value
                            ),
                            discovered_at=discovered.discovered_at,
                            last_observed_at=discovered.discovered_at,
                            state=MediaRegistrationState.DISCOVERED,
                            revision=1,
                        )
                    )
                )
        return tuple(retained)

    def record_resource_observation(
        self,
        *,
        candidate_id: EntityId,
        observation_kind: str,
        observed_at: datetime,
        facts: Mapping[str, object],
    ) -> ResourceObservation:
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            raise KernelNotFoundError("candidate_not_found")
        observation = ResourceObservation(
            id=EntityId.new(),
            candidate_id=candidate_id,
            observation_kind=observation_kind,
            epistemic_kind=EpistemicKind.OBSERVED,
            observed_at=observed_at,
            recorded_at=self.clock.now(),
            facts=facts,
        )
        self.repository.record_observation(observation)
        if candidate.state is not MediaRegistrationState.REGISTERED:
            self.repository.mark_candidate_state(
                candidate_id, MediaRegistrationState.STABILIZING.value, observed_at
            )
        return observation

    def record_readiness(
        self,
        *,
        candidate_id: EntityId,
        ready: bool,
        evaluated_at: datetime,
        policy_id: str,
        evidence_ids: Sequence[EntityId],
    ) -> ResourceObservation:
        observation = ResourceObservation(
            id=EntityId.new(),
            candidate_id=candidate_id,
            observation_kind="asset_readiness_evaluation",
            epistemic_kind=EpistemicKind.DERIVED,
            observed_at=evaluated_at,
            recorded_at=self.clock.now(),
            facts={
                "ready": ready,
                "policy_id": policy_id,
                "evidence_ids": tuple(value.value for value in evidence_ids),
            },
        )
        self.repository.record_observation(observation)
        self.repository.mark_candidate_state(
            candidate_id,
            (
                MediaRegistrationState.READY.value
                if ready
                else MediaRegistrationState.STABILIZING.value
            ),
            evaluated_at,
        )
        return observation

    def record_readiness_evaluation(
        self, evaluation: AssetReadinessEvaluation
    ) -> ResourceObservation:
        return self.record_readiness(
            candidate_id=evaluation.candidate_id,
            ready=evaluation.outcome is AssetReadinessOutcome.SAFE_TO_READ,
            evaluated_at=evaluation.evaluated_at,
            policy_id=f"{evaluation.policy_id.value}:{evaluation.policy_version}",
            evidence_ids=evaluation.supporting_observation_ids,
        )

    def register_completed_media_asset(
        self,
        asset: CompletedMediaAsset,
        *,
        candidate_id: EntityId,
        source_binding_key: str,
        contradictory_session_ids: Sequence[EntityId] = (),
    ) -> tuple[RegisteredMediaAsset, MediaAssociation, EntityId | None]:
        stage_id = asset.context.stage_id
        if stage_id is None:
            raise KernelConflictError("completed_asset_stage_context_missing")
        return self.register_completed_asset(
            RegisteredMediaAsset(
                id=asset.id,
                candidate_id=candidate_id,
                manifest_id=asset.manifest.id,
                stage_id=stage_id,
                source_binding_key=source_binding_key,
                registered_at=asset.manifested_at,
                media_started_at=asset.recorded_start_at,
                media_ended_at=asset.recorded_end_at,
            ),
            contradictory_session_ids=contradictory_session_ids,
        )

    def register_completed_asset(
        self,
        asset: RegisteredMediaAsset,
        *,
        contradictory_session_ids: Sequence[EntityId] = (),
    ) -> tuple[RegisteredMediaAsset, MediaAssociation, EntityId | None]:
        candidate = self.repository.get_candidate(asset.candidate_id)
        if candidate is None:
            raise KernelNotFoundError("candidate_not_found")
        if candidate.state is not MediaRegistrationState.READY:
            existing_asset = self.repository.get_asset(asset.id)
            if existing_asset is None:
                raise KernelConflictError("candidate_not_ready")
        registered = self.repository.register_asset(asset)
        production_event_id = (
            None
            if self.asset_ingress_publisher is None
            else self.asset_ingress_publisher.publish(registered, received_at=self.clock.now())
        )
        existing_association = self.repository.get_association(registered.id)
        if existing_association is not None:
            return registered, existing_association, production_event_id
        association = self._automatic_association(
            registered,
            contradictory_session_ids=tuple(contradictory_session_ids),
        )
        return registered, association, production_event_id

    def _automatic_association(
        self,
        asset: RegisteredMediaAsset,
        *,
        contradictory_session_ids: tuple[EntityId, ...],
    ) -> MediaAssociation:
        sessions = self.repository.list_sessions_for_stage(asset.stage_id)
        eligible = [session for session in sessions if self._temporally_eligible(asset, session)]
        contradicted = set(contradictory_session_ids)
        safe = [session for session in eligible if session.id not in contradicted]
        if contradicted and any(session.id in contradicted for session in eligible):
            status = AssociationStatus.CONFLICT
            selected = None
            reasons = ("material_contradictory_evidence",)
        elif len(safe) == 1:
            status = AssociationStatus.ASSOCIATED
            selected = safe[0]
            reasons = ("structural_stage_match", "single_temporally_compatible_session")
        else:
            status = AssociationStatus.UNRESOLVED
            selected = None
            reasons = (
                "multiple_eligible_sessions"
                if len(safe) > 1
                else "no_safely_eligible_session",
            )
        current = self.repository.get_association(asset.id)
        candidate = self.repository.get_candidate(asset.candidate_id)
        if candidate is None:
            raise KernelNotFoundError("candidate_not_found")
        input_references = [
            AssociationInputReference("registered_media_asset", asset.id.value),
            AssociationInputReference(
                "media_candidate", candidate.id.value, candidate.revision
            ),
            AssociationInputReference(
                "stage_source_binding", asset.source_binding_key
            ),
        ]
        input_references.extend(
            AssociationInputReference("session", session.id.value, session.revision)
            for session in sessions
        )
        input_references.extend(
            AssociationInputReference("contradictory_session", value.value)
            for value in contradictory_session_ids
        )
        association = MediaAssociation(
            asset_id=asset.id,
            status=status,
            session_id=None if selected is None else selected.id,
            authority=AssociationAuthority.DETERMINISTIC,
            reason_codes=reasons,
            evidence_ids=(),
            revision=1 if current is None else current.revision + 1,
            decided_at=self.clock.now(),
            policy_id=_ASSOCIATION_POLICY_ID,
            policy_version=_ASSOCIATION_POLICY_VERSION,
            input_references=input_references,
        )
        return self.repository.put_association(association)

    def _temporally_eligible(self, asset: RegisteredMediaAsset, session: Session) -> bool:
        if asset.media_started_at is None and asset.media_ended_at is None:
            return (
                session.activity_state is SessionActivityState.PRESENTATION_ACTIVE
                or (
                    session.activity_state is SessionActivityState.PRESENTATION_ENDED
                    and session.package_state is SessionPackageState.ASSEMBLING
                )
            )
        if session.activity_state is SessionActivityState.PRESENTATION_ACTIVE:
            if asset.media_ended_at is None:
                assert asset.media_started_at is not None
                return asset.media_started_at >= session.authoritative_start
            return asset.media_ended_at >= session.authoritative_start
        session_end = session.authoritative_end
        if session_end is None:
            return False
        media_start = asset.media_started_at or asset.media_ended_at
        media_end = asset.media_ended_at or asset.media_started_at
        assert media_start is not None and media_end is not None
        return (
            media_end >= session.authoritative_start
            and media_start <= session_end
        )

    def assign_asset(
        self,
        *,
        operation_id: EntityId,
        asset_id: EntityId,
        session_id: EntityId,
        actor_id: EntityId,
        reason: str,
    ) -> MediaAssociation:
        asset = self.repository.get_asset(asset_id)
        session = self.repository.get_session(session_id)
        if asset is None:
            raise KernelNotFoundError("asset_not_found")
        if session is None:
            raise KernelNotFoundError("session_not_found")
        current = self.repository.get_association(asset_id)
        input_references = (
            AssociationInputReference("registered_media_asset", asset.id.value),
            AssociationInputReference("session", session.id.value, session.revision),
            AssociationInputReference("stage_source_binding", asset.source_binding_key),
        )
        if asset.stage_id != session.stage_id:
            association = MediaAssociation(
                asset_id=asset_id,
                status=AssociationStatus.CONFLICT,
                session_id=None,
                authority=AssociationAuthority.HUMAN,
                reason_codes=("authoritative_stage_conflict", reason),
                evidence_ids=(),
                revision=1 if current is None else current.revision + 1,
                decided_at=self.clock.now(),
                actor_id=actor_id,
                operation_id=operation_id,
                input_references=input_references,
            )
        else:
            association = MediaAssociation(
                asset_id=asset_id,
                status=AssociationStatus.ASSOCIATED,
                session_id=session_id,
                authority=AssociationAuthority.HUMAN,
                reason_codes=("human_assignment", reason),
                evidence_ids=(),
                revision=1 if current is None else current.revision + 1,
                decided_at=self.clock.now(),
                actor_id=actor_id,
                operation_id=operation_id,
                input_references=input_references,
            )
        return self.repository.put_association(
            association,
            request_digest=_command_digest(
                "media_assignment",
                {
                    "asset_id": asset_id,
                    "session_id": session_id,
                    "actor_id": actor_id,
                    "reason": reason.strip(),
                },
            ),
        )

    def mark_package_ready(self, session_id: EntityId) -> Session:
        return self.repository.set_package_state(
            session_id, SessionPackageState.READY_FOR_REVIEW.value, self.clock.now()
        )

    def complete_package(
        self,
        *,
        operation_id: EntityId,
        session_id: EntityId,
        actor_id: EntityId,
        approved: bool,
        reason: str,
    ) -> Session:
        session = self.repository.get_session(session_id)
        if session is None:
            raise KernelNotFoundError("session_not_found")
        return self.repository.complete_session(
            CompletionDecision(
                id=EntityId.new(),
                session_id=session_id,
                package_revision=session.package_revision,
                actor_id=actor_id,
                approved=approved,
                reason=reason,
                decided_at=self.clock.now(),
                operation_id=operation_id,
            ),
            request_digest=_command_digest(
                "package_completion",
                {
                    "session_id": session_id,
                    "actor_id": actor_id,
                    "approved": approved,
                    "reason": reason.strip(),
                },
            ),
        )

    def begin_reconciliation(self, *, event_id: EntityId, scope: str) -> ReconciliationRun:
        return self.repository.put_reconciliation(
            ReconciliationRun(
                id=EntityId.new(),
                event_id=event_id,
                status=ReconciliationStatus.RUNNING,
                scope=scope,
                started_at=self.clock.now(),
                completed_at=None,
                candidates_seen=0,
                assets_registered=0,
            )
        )

    def finish_reconciliation(
        self,
        run: ReconciliationRun,
        *,
        candidates_seen: int,
        assets_registered: int,
        failure_code: str | None = None,
    ) -> ReconciliationRun:
        completed = replace(
            run,
            status=(
                ReconciliationStatus.FAILED
                if failure_code is not None
                else ReconciliationStatus.COMPLETED
            ),
            completed_at=self.clock.now(),
            candidates_seen=candidates_seen,
            assets_registered=assets_registered,
            failure_code=failure_code,
        )
        return self.repository.put_reconciliation(completed)


__all__ = [
    "AssetIngressPublisher",
    "DurableEventModeKernel",
    "StableAssetIngressPublisher",
]
