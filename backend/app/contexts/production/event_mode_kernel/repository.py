from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import datetime
from threading import RLock

from app.contexts.events import (
    BusinessEvent,
    EventStageBootstrapRequest,
    EventStageBootstrapResult,
    ProgramExpectation,
    Stage,
)
from app.shared.ids import EntityId

from .contracts import (
    AssociationStatus,
    BoundaryDecision,
    CompletionDecision,
    EpistemicKind,
    EventOperationalStatus,
    MediaAssociation,
    MediaCandidate,
    MediaOperationalProjection,
    MediaRegistrationState,
    ReconciliationRun,
    ReconciliationStatus,
    RegisteredMediaAsset,
    ResourceObservation,
    Session,
    SessionBoundaryProposal,
    SessionOperationalProjection,
    StartSessionRequest,
)


class KernelConflictError(RuntimeError):
    pass


class KernelNotFoundError(LookupError):
    pass


class KernelStorageUnavailableError(RuntimeError):
    pass


class EventModeKernelRepository(ABC):
    @abstractmethod
    def bootstrap(self, request: EventStageBootstrapRequest) -> EventStageBootstrapResult: ...

    @abstractmethod
    def get_event_by_key(self, event_key: str) -> BusinessEvent | None: ...

    @abstractmethod
    def get_stage_by_key(self, event_id: EntityId, stage_key: str) -> Stage | None: ...

    @abstractmethod
    def list_stages(self, event_id: EntityId) -> tuple[Stage, ...]: ...

    @abstractmethod
    def put_program_expectation(self, expectation: ProgramExpectation) -> ProgramExpectation: ...

    @abstractmethod
    def get_program_expectation(self, expectation_id: EntityId) -> ProgramExpectation | None: ...

    @abstractmethod
    def start_session(self, request: StartSessionRequest) -> Session: ...

    @abstractmethod
    def get_session(self, session_id: EntityId) -> Session | None: ...

    @abstractmethod
    def list_sessions_for_stage(self, stage_id: EntityId) -> tuple[Session, ...]: ...

    @abstractmethod
    def correct_boundary(
        self,
        *,
        session_id: EntityId,
        boundary_kind: str,
        boundary_at: datetime,
        actor_id: EntityId,
        reason: str,
        decided_at: datetime,
    ) -> tuple[Session, BoundaryDecision]: ...

    @abstractmethod
    def put_boundary_proposal(
        self, proposal: SessionBoundaryProposal
    ) -> SessionBoundaryProposal: ...

    @abstractmethod
    def list_boundary_proposals(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[SessionBoundaryProposal, ...]: ...

    @abstractmethod
    def register_candidate(self, candidate: MediaCandidate) -> MediaCandidate: ...

    @abstractmethod
    def get_candidate(self, candidate_id: EntityId) -> MediaCandidate | None: ...

    @abstractmethod
    def record_observation(self, observation: ResourceObservation) -> ResourceObservation: ...

    @abstractmethod
    def list_observations(self, candidate_id: EntityId) -> tuple[ResourceObservation, ...]: ...

    @abstractmethod
    def mark_candidate_state(
        self, candidate_id: EntityId, state: str, at: datetime
    ) -> MediaCandidate: ...

    @abstractmethod
    def register_asset(self, asset: RegisteredMediaAsset) -> RegisteredMediaAsset: ...

    @abstractmethod
    def get_asset(self, asset_id: EntityId) -> RegisteredMediaAsset | None: ...

    @abstractmethod
    def put_association(self, association: MediaAssociation) -> MediaAssociation: ...

    @abstractmethod
    def get_association(self, asset_id: EntityId) -> MediaAssociation | None: ...

    @abstractmethod
    def set_package_state(self, session_id: EntityId, state: str, at: datetime) -> Session: ...

    @abstractmethod
    def complete_session(self, decision: CompletionDecision) -> Session: ...

    @abstractmethod
    def put_reconciliation(self, run: ReconciliationRun) -> ReconciliationRun: ...

    @abstractmethod
    def get_latest_reconciliation(self, event_id: EntityId) -> ReconciliationRun | None: ...

    @abstractmethod
    def list_recent_media(
        self, event_id: EntityId, *, limit: int = 100
    ) -> tuple[MediaOperationalProjection, ...]: ...

    @abstractmethod
    def operational_status(
        self,
        event_id: EntityId,
        *,
        database_available: bool = True,
        source_availability: dict[str, bool] | None = None,
    ) -> EventOperationalStatus: ...


class InMemoryEventModeKernelRepository(EventModeKernelRepository):
    """Process-local test double. Never use as event authority."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._events: dict[EntityId, BusinessEvent] = {}
        self._event_keys: dict[str, EntityId] = {}
        self._stages: dict[EntityId, Stage] = {}
        self._stage_keys: dict[tuple[EntityId, str], EntityId] = {}
        self._expectations: dict[EntityId, ProgramExpectation] = {}
        self._expectation_keys: dict[tuple[EntityId, str], EntityId] = {}
        self._sessions: dict[EntityId, Session] = {}
        self._start_operations: dict[EntityId, tuple[StartSessionRequest, EntityId]] = {}
        self._bootstrap_operations: dict[EntityId, EventStageBootstrapResult] = {}
        self._boundaries: list[BoundaryDecision] = []
        self._boundary_proposals: dict[EntityId, SessionBoundaryProposal] = {}
        self._candidates: dict[EntityId, MediaCandidate] = {}
        self._observations: dict[EntityId, ResourceObservation] = {}
        self._assets: dict[EntityId, RegisteredMediaAsset] = {}
        self._associations: dict[EntityId, MediaAssociation] = {}
        self._association_history: list[MediaAssociation] = []
        self._completion_history: list[CompletionDecision] = []
        self._reconciliations: dict[EntityId, ReconciliationRun] = {}
        self._reconciliation_order: list[EntityId] = []

    def bootstrap(self, request: EventStageBootstrapRequest) -> EventStageBootstrapResult:
        from app.contexts.events import BootstrapStatus

        with self._lock:
            replay = self._bootstrap_operations.get(request.operation_id)
            if replay is not None:
                return replay
            event_id = self._event_keys.get(request.event_key)
            created = event_id is None
            changed = False
            if event_id is None:
                event_id = EntityId.new()
                event = BusinessEvent(
                    id=event_id,
                    key=request.event_key,
                    name=request.event_name,
                    external_references=request.external_references,
                    revision=1,
                    created_at=request.requested_at,
                    updated_at=request.requested_at,
                )
                self._events[event_id] = event
                self._event_keys[event.key] = event_id
            else:
                event = self._events[event_id]
                if event.name != request.event_name or dict(event.external_references) != dict(
                    request.external_references
                ):
                    event = replace(
                        event,
                        name=request.event_name,
                        external_references=request.external_references,
                        revision=event.revision + 1,
                        updated_at=request.requested_at,
                    )
                    self._events[event_id] = event
                    changed = True

            requested_stage_keys = {definition.key for definition in request.stages}
            existing_stage_keys = {
                key for (owner_id, key) in self._stage_keys if owner_id == event_id
            }
            if existing_stage_keys - requested_stage_keys:
                result = EventStageBootstrapResult(
                    status=BootstrapStatus.CONFLICT,
                    event=event,
                    stages=self.list_stages(event_id),
                    reason="stage_removal_not_permitted",
                )
                self._bootstrap_operations[request.operation_id] = result
                return result

            existing_source_owners = {
                source_key: stage.id
                for stage in self.list_stages(event_id)
                for source_key in stage.source_bindings
            }
            for definition in request.stages:
                stage_id = self._stage_keys.get((event_id, definition.key))
                for source_key in definition.source_bindings:
                    owner = existing_source_owners.get(source_key)
                    if owner is not None and owner != stage_id:
                        result = EventStageBootstrapResult(
                            status=BootstrapStatus.CONFLICT,
                            event=event,
                            stages=self.list_stages(event_id),
                            reason="source_binding_stage_conflict",
                        )
                        self._bootstrap_operations[request.operation_id] = result
                        return result

            for definition in request.stages:
                stage_id = self._stage_keys.get((event_id, definition.key))
                if stage_id is None:
                    stage = Stage(
                        id=EntityId.new(),
                        event_id=event_id,
                        key=definition.key,
                        name=definition.name,
                        source_bindings=definition.source_bindings,
                        external_references=definition.external_references,
                        revision=1,
                        created_at=request.requested_at,
                        updated_at=request.requested_at,
                    )
                    self._stages[stage.id] = stage
                    self._stage_keys[(event_id, stage.key)] = stage.id
                    changed = changed or not created
                else:
                    stage = self._stages[stage_id]
                    if (
                        stage.name != definition.name
                        or dict(stage.source_bindings) != dict(definition.source_bindings)
                        or dict(stage.external_references)
                        != dict(definition.external_references)
                    ):
                        self._stages[stage_id] = replace(
                            stage,
                            name=definition.name,
                            source_bindings=definition.source_bindings,
                            external_references=definition.external_references,
                            revision=stage.revision + 1,
                            updated_at=request.requested_at,
                        )
                        changed = True
            status = (
                BootstrapStatus.CREATED
                if created
                else BootstrapStatus.UPDATED
                if changed
                else BootstrapStatus.RESOLVED
            )
            result = EventStageBootstrapResult(
                status=status,
                event=self._events[event_id],
                stages=self.list_stages(event_id),
            )
            self._bootstrap_operations[request.operation_id] = result
            return result

    def get_event_by_key(self, event_key: str) -> BusinessEvent | None:
        with self._lock:
            event_id = self._event_keys.get(event_key)
            return None if event_id is None else self._events[event_id]

    def get_stage_by_key(self, event_id: EntityId, stage_key: str) -> Stage | None:
        with self._lock:
            stage_id = self._stage_keys.get((event_id, stage_key))
            return None if stage_id is None else self._stages[stage_id]

    def list_stages(self, event_id: EntityId) -> tuple[Stage, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (stage for stage in self._stages.values() if stage.event_id == event_id),
                    key=lambda value: value.key,
                )
            )

    def put_program_expectation(self, expectation: ProgramExpectation) -> ProgramExpectation:
        with self._lock:
            key = (expectation.event_id, expectation.key)
            existing_id = self._expectation_keys.get(key)
            if existing_id is None:
                self._expectations[expectation.id] = expectation
                self._expectation_keys[key] = expectation.id
                return expectation
            existing = self._expectations[existing_id]
            if expectation.id != existing.id:
                expectation = replace(expectation, id=existing.id)
            expectation = replace(expectation, revision=existing.revision + 1)
            self._expectations[existing.id] = expectation
            return expectation

    def get_program_expectation(self, expectation_id: EntityId) -> ProgramExpectation | None:
        with self._lock:
            return self._expectations.get(expectation_id)

    def start_session(self, request: StartSessionRequest) -> Session:
        from .contracts import SessionActivityState, SessionPackageState

        with self._lock:
            replay = self._start_operations.get(request.operation_id)
            if replay is not None:
                prior_request, session_id = replay
                if prior_request != request:
                    raise KernelConflictError("operation_id_conflict")
                return self._sessions[session_id]
            stage = self._stages.get(request.stage_id)
            if stage is None or stage.event_id != request.event_id:
                raise KernelConflictError("stage_event_mismatch")
            if request.program_expectation_id is not None:
                expectation = self._expectations.get(request.program_expectation_id)
                if expectation is None or expectation.event_id != request.event_id:
                    raise KernelConflictError("program_expectation_event_mismatch")
            if any(
                session.stage_id == request.stage_id
                and session.activity_state is SessionActivityState.PRESENTATION_ACTIVE
                for session in self._sessions.values()
            ):
                raise KernelConflictError("stage_already_has_active_session")
            session = Session(
                id=EntityId.new(),
                event_id=request.event_id,
                stage_id=request.stage_id,
                program_expectation_id=request.program_expectation_id,
                title=request.title,
                activity_state=SessionActivityState.PRESENTATION_ACTIVE,
                package_state=SessionPackageState.ASSEMBLING,
                authoritative_start=request.authoritative_start,
                authoritative_end=None,
                package_revision=1,
                revision=1,
                created_by=request.actor_id,
                created_at=request.requested_at,
                updated_at=request.requested_at,
            )
            self._sessions[session.id] = session
            self._boundaries.append(
                BoundaryDecision(
                    id=EntityId.new(),
                    session_id=session.id,
                    boundary_kind="start",
                    boundary_at=request.authoritative_start,
                    authority=EpistemicKind.DECLARED,
                    actor_id=request.actor_id,
                    reason="human_session_start",
                    decided_at=request.requested_at,
                    resulting_session_revision=1,
                )
            )
            self._start_operations[request.operation_id] = (request, session.id)
            return session

    def get_session(self, session_id: EntityId) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions_for_stage(self, stage_id: EntityId) -> tuple[Session, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        session
                        for session in self._sessions.values()
                        if session.stage_id == stage_id
                    ),
                    key=lambda value: (value.authoritative_start, value.id.value),
                )
            )

    def correct_boundary(
        self,
        *,
        session_id: EntityId,
        boundary_kind: str,
        boundary_at: datetime,
        actor_id: EntityId,
        reason: str,
        decided_at: datetime,
    ) -> tuple[Session, BoundaryDecision]:
        from .contracts import EpistemicKind, SessionActivityState, SessionPackageState

        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KernelNotFoundError("session_not_found")
            start = boundary_at if boundary_kind == "start" else session.authoritative_start
            end = boundary_at if boundary_kind == "end" else session.authoritative_end
            if end is not None and end < start:
                raise KernelConflictError("session_boundary_order_conflict")
            package_revision = session.package_revision
            package_state = session.package_state
            if package_state is SessionPackageState.COMPLETE:
                package_revision += 1
                package_state = SessionPackageState.CORRECTION_REQUIRED
            activity_state = session.activity_state
            if boundary_kind == "end":
                activity_state = SessionActivityState.PRESENTATION_ENDED
            updated = replace(
                session,
                authoritative_start=start,
                authoritative_end=end,
                activity_state=activity_state,
                package_state=package_state,
                package_revision=package_revision,
                revision=session.revision + 1,
                updated_at=decided_at,
            )
            decision = BoundaryDecision(
                id=EntityId.new(),
                session_id=session_id,
                boundary_kind=boundary_kind,
                boundary_at=boundary_at,
                authority=EpistemicKind.DECLARED,
                actor_id=actor_id,
                reason=reason,
                decided_at=decided_at,
                resulting_session_revision=updated.revision,
            )
            self._sessions[session_id] = updated
            self._boundaries.append(decision)
            return updated, decision

    def put_boundary_proposal(
        self, proposal: SessionBoundaryProposal
    ) -> SessionBoundaryProposal:
        with self._lock:
            if proposal.session_id not in self._sessions:
                raise KernelNotFoundError("session_not_found")
            existing = self._boundary_proposals.get(proposal.id)
            if existing is not None and existing != proposal:
                raise KernelConflictError("boundary_proposal_identity_conflict")
            self._boundary_proposals[proposal.id] = proposal
            return proposal

    def list_boundary_proposals(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[SessionBoundaryProposal, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self._lock:
            return tuple(
                sorted(
                    (
                        item
                        for item in self._boundary_proposals.values()
                        if item.session_id == session_id
                    ),
                    key=lambda value: (value.proposed_at, value.id.value),
                    reverse=True,
                )[:limit]
            )

    def register_candidate(self, candidate: MediaCandidate) -> MediaCandidate:
        with self._lock:
            stage = self._stages.get(candidate.stage_id)
            if stage is None:
                raise KernelNotFoundError("stage_not_found")
            if candidate.source_binding_key not in stage.source_bindings:
                raise KernelConflictError("candidate_source_stage_conflict")
            existing = self._candidates.get(candidate.id)
            if existing is None:
                self._candidates[candidate.id] = candidate
                return candidate
            immutable_existing = (
                existing.proposed_asset_id,
                existing.stage_id,
                existing.source_binding_key,
                existing.source_reference,
            )
            immutable_candidate = (
                candidate.proposed_asset_id,
                candidate.stage_id,
                candidate.source_binding_key,
                candidate.source_reference,
            )
            if immutable_existing != immutable_candidate:
                raise KernelConflictError("candidate_identity_conflict")
            if (
                candidate.last_observed_at <= existing.last_observed_at
                and candidate.state is existing.state
            ):
                return existing
            updated = replace(
                existing,
                last_observed_at=max(existing.last_observed_at, candidate.last_observed_at),
                revision=existing.revision + 1,
            )
            self._candidates[candidate.id] = updated
            return updated

    def get_candidate(self, candidate_id: EntityId) -> MediaCandidate | None:
        with self._lock:
            return self._candidates.get(candidate_id)

    def record_observation(self, observation: ResourceObservation) -> ResourceObservation:
        with self._lock:
            existing = self._observations.get(observation.id)
            if existing is not None and existing != observation:
                raise KernelConflictError("observation_identity_conflict")
            if existing is not None:
                return existing
            if observation.candidate_id not in self._candidates:
                raise KernelNotFoundError("candidate_not_found")
            self._observations[observation.id] = observation
            candidate = self._candidates[observation.candidate_id]
            self._candidates[observation.candidate_id] = replace(
                candidate,
                last_observed_at=max(candidate.last_observed_at, observation.observed_at),
                revision=candidate.revision + 1,
            )
            return observation

    def list_observations(self, candidate_id: EntityId) -> tuple[ResourceObservation, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        observation
                        for observation in self._observations.values()
                        if observation.candidate_id == candidate_id
                    ),
                    key=lambda value: (value.observed_at, value.id.value),
                )
            )

    def mark_candidate_state(
        self, candidate_id: EntityId, state: str, at: datetime
    ) -> MediaCandidate:
        from .contracts import MediaRegistrationState

        with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                raise KernelNotFoundError("candidate_not_found")
            updated = replace(
                candidate,
                state=MediaRegistrationState(state),
                last_observed_at=max(candidate.last_observed_at, at),
                revision=candidate.revision + 1,
            )
            self._candidates[candidate_id] = updated
            return updated

    def register_asset(self, asset: RegisteredMediaAsset) -> RegisteredMediaAsset:
        from .contracts import MediaRegistrationState

        with self._lock:
            existing = self._assets.get(asset.id)
            if existing is not None:
                if existing != asset:
                    raise KernelConflictError("asset_identity_conflict")
                return existing
            candidate = self._candidates.get(asset.candidate_id)
            if candidate is None:
                raise KernelNotFoundError("candidate_not_found")
            if candidate.stage_id != asset.stage_id:
                raise KernelConflictError("asset_candidate_stage_conflict")
            if candidate.source_binding_key != asset.source_binding_key:
                raise KernelConflictError("asset_candidate_source_conflict")
            self._assets[asset.id] = asset
            self._candidates[candidate.id] = replace(
                candidate,
                state=MediaRegistrationState.REGISTERED,
                last_observed_at=max(candidate.last_observed_at, asset.registered_at),
                revision=candidate.revision + 1,
            )
            return asset

    def get_asset(self, asset_id: EntityId) -> RegisteredMediaAsset | None:
        with self._lock:
            return self._assets.get(asset_id)

    def put_association(self, association: MediaAssociation) -> MediaAssociation:
        from .contracts import AssociationStatus, SessionPackageState

        with self._lock:
            if association.asset_id not in self._assets:
                raise KernelNotFoundError("asset_not_found")
            current = self._associations.get(association.asset_id)
            expected_revision = 1 if current is None else current.revision + 1
            if association.revision != expected_revision:
                raise KernelConflictError("association_revision_conflict")
            if association.status is AssociationStatus.ASSOCIATED:
                assert association.session_id is not None
                session = self._sessions.get(association.session_id)
                asset = self._assets[association.asset_id]
                if session is None:
                    raise KernelNotFoundError("session_not_found")
                if session.stage_id != asset.stage_id:
                    raise KernelConflictError("association_stage_conflict")
                if session.package_state is SessionPackageState.COMPLETE:
                    self._sessions[session.id] = replace(
                        session,
                        package_state=SessionPackageState.CORRECTION_REQUIRED,
                        package_revision=session.package_revision + 1,
                        revision=session.revision + 1,
                        updated_at=association.decided_at,
                    )
            self._associations[association.asset_id] = association
            self._association_history.append(association)
            return association

    def get_association(self, asset_id: EntityId) -> MediaAssociation | None:
        with self._lock:
            return self._associations.get(asset_id)

    def set_package_state(self, session_id: EntityId, state: str, at: datetime) -> Session:
        from .contracts import SessionPackageState

        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KernelNotFoundError("session_not_found")
            target = SessionPackageState(state)
            if target is SessionPackageState.COMPLETE:
                raise KernelConflictError("completion_requires_human_decision")
            updated = replace(
                session,
                package_state=target,
                revision=session.revision + 1,
                updated_at=at,
            )
            self._sessions[session_id] = updated
            return updated

    def complete_session(self, decision: CompletionDecision) -> Session:
        from .contracts import SessionPackageState

        with self._lock:
            session = self._sessions.get(decision.session_id)
            if session is None:
                raise KernelNotFoundError("session_not_found")
            if decision.package_revision != session.package_revision:
                raise KernelConflictError("package_revision_conflict")
            if session.package_state not in {
                SessionPackageState.READY_FOR_REVIEW,
                SessionPackageState.IN_REVIEW,
            }:
                raise KernelConflictError("package_not_ready_for_completion")
            target = (
                SessionPackageState.COMPLETE
                if decision.approved
                else SessionPackageState.CORRECTION_REQUIRED
            )
            updated = replace(
                session,
                package_state=target,
                revision=session.revision + 1,
                updated_at=decision.decided_at,
            )
            self._sessions[session.id] = updated
            self._completion_history.append(decision)
            return updated

    def put_reconciliation(self, run: ReconciliationRun) -> ReconciliationRun:
        with self._lock:
            existing = self._reconciliations.get(run.id)
            if existing is not None and (
                existing.event_id != run.event_id
                or existing.scope != run.scope
                or existing.started_at != run.started_at
            ):
                raise KernelConflictError("reconciliation_identity_conflict")
            if (
                existing is not None
                and existing.status is not ReconciliationStatus.RUNNING
                and existing != run
            ):
                raise KernelConflictError("reconciliation_already_finished")
            self._reconciliations[run.id] = run
            if existing is None:
                self._reconciliation_order.append(run.id)
            return run

    def get_latest_reconciliation(self, event_id: EntityId) -> ReconciliationRun | None:
        with self._lock:
            for run_id in reversed(self._reconciliation_order):
                run = self._reconciliations[run_id]
                if run.event_id == event_id:
                    return run
            return None

    def list_recent_media(
        self, event_id: EntityId, *, limit: int = 100
    ) -> tuple[MediaOperationalProjection, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self._lock:
            stage_ids = {stage.id for stage in self._stages.values() if stage.event_id == event_id}
            projections: list[MediaOperationalProjection] = []
            for candidate in self._candidates.values():
                if candidate.stage_id not in stage_ids:
                    continue
                asset = next(
                    (
                        value
                        for value in self._assets.values()
                        if value.candidate_id == candidate.id
                    ),
                    None,
                )
                association = None if asset is None else self._associations.get(asset.id)
                epistemic = {
                    observation.epistemic_kind
                    for observation in self._observations.values()
                    if observation.candidate_id == candidate.id
                }
                diagnostic_codes: list[str] = []
                if candidate.state is MediaRegistrationState.DISCOVERED:
                    diagnostic_codes.append("not_observed")
                elif candidate.state is MediaRegistrationState.STABILIZING:
                    diagnostic_codes.append("readiness_pending")
                if (
                    association is not None
                    and association.status is not AssociationStatus.ASSOCIATED
                ):
                    diagnostic_codes.append(f"association_{association.status.value}")
                projections.append(
                    MediaOperationalProjection(
                        candidate_id=candidate.id,
                        proposed_asset_id=candidate.proposed_asset_id,
                        asset_id=None if asset is None else asset.id,
                        stage_id=candidate.stage_id,
                        source_binding_key=candidate.source_binding_key,
                        registration_state=candidate.state,
                        discovered_at=candidate.discovered_at,
                        last_observed_at=candidate.last_observed_at,
                        association_status=(
                            None if association is None else association.status
                        ),
                        association_authority=(
                            None if association is None else association.authority
                        ),
                        session_id=None if association is None else association.session_id,
                        epistemic_kinds=tuple(
                            sorted(epistemic, key=lambda value: value.value)
                        ),
                        media_started_at=None if asset is None else asset.media_started_at,
                        media_ended_at=None if asset is None else asset.media_ended_at,
                        diagnostic_codes=diagnostic_codes,
                    )
                )
            return tuple(
                sorted(
                    projections,
                    key=lambda value: (value.last_observed_at, value.candidate_id.value),
                    reverse=True,
                )[:limit]
            )

    def operational_status(
        self,
        event_id: EntityId,
        *,
        database_available: bool = True,
        source_availability: dict[str, bool] | None = None,
    ) -> EventOperationalStatus:
        from .contracts import (
            AssociationStatus,
            EventOperationalStatus,
            MediaRegistrationState,
            ReconciliationStatus,
            SessionActivityState,
            SessionPackageState,
            StageOperationalStatus,
        )

        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                raise KernelNotFoundError("event_not_found")
            availability = source_availability or {}
            stages: list[StageOperationalStatus] = []
            attention: list[str] = []
            for stage in self.list_stages(event_id):
                candidates = [
                    item for item in self._candidates.values() if item.stage_id == stage.id
                ]
                assets = [item for item in self._assets.values() if item.stage_id == stage.id]
                associations = [
                    self._associations[item.id]
                    for item in assets
                    if item.id in self._associations
                ]
                sessions = self.list_sessions_for_stage(stage.id)
                assembling_session_ids = tuple(
                    item.id
                    for item in sessions
                    if item.package_state
                    in {
                        SessionPackageState.ASSEMBLING,
                        SessionPackageState.CORRECTION_REQUIRED,
                    }
                )
                assembling_sessions = tuple(
                    SessionOperationalProjection(
                        session_id=item.id,
                        activity_state=item.activity_state,
                        package_state=item.package_state,
                        package_revision=item.package_revision,
                        revision=item.revision,
                        authoritative_start=item.authoritative_start,
                        authoritative_end=item.authoritative_end,
                    )
                    for item in sessions
                    if item.id in assembling_session_ids
                )
                current = next(
                    (
                        item
                        for item in reversed(sessions)
                        if item.activity_state is SessionActivityState.PRESENTATION_ACTIVE
                        or item.package_state
                        in {
                            SessionPackageState.ASSEMBLING,
                            SessionPackageState.CORRECTION_REQUIRED,
                            SessionPackageState.READY_FOR_REVIEW,
                            SessionPackageState.IN_REVIEW,
                        }
                    ),
                    None,
                )
                source_values = [availability.get(key) for key in stage.source_bindings]
                known_values = [value for value in source_values if value is not None]
                source_available = all(known_values) if known_values else None
                unresolved = sum(
                    item.status is AssociationStatus.UNRESOLVED for item in associations
                )
                conflicts = sum(
                    item.status is AssociationStatus.CONFLICT for item in associations
                )
                stage_attention: list[str] = []
                if unresolved:
                    stage_attention.append("unresolved_media")
                if conflicts:
                    stage_attention.append("association_conflict")
                if source_available is False:
                    stage_attention.append("source_unavailable")
                attention.extend(
                    f"stage:{stage.key}:{code}" for code in stage_attention
                )
                stages.append(
                    StageOperationalStatus(
                        stage_id=stage.id,
                        stage_key=stage.key,
                        stage_name=stage.name,
                        source_available=source_available,
                        active_or_assembling_session_id=None if current is None else current.id,
                        assembling_session_ids=assembling_session_ids,
                        assembling_sessions=assembling_sessions,
                        session_activity_state=(
                            None if current is None else current.activity_state
                        ),
                        session_package_state=(
                            None if current is None else current.package_state
                        ),
                        session_package_revision=(
                            None if current is None else current.package_revision
                        ),
                        session_revision=None if current is None else current.revision,
                        session_authoritative_start=(
                            None if current is None else current.authoritative_start
                        ),
                        session_authoritative_end=(
                            None if current is None else current.authoritative_end
                        ),
                        last_media_arrived_at=(
                            max((item.last_observed_at for item in candidates), default=None)
                        ),
                        discovered_media=sum(
                            item.state is MediaRegistrationState.DISCOVERED for item in candidates
                        ),
                        stabilizing_media=sum(
                            item.state is MediaRegistrationState.STABILIZING for item in candidates
                        ),
                        ready_media=sum(
                            item.state is MediaRegistrationState.READY for item in candidates
                        ),
                        registered_media=len(assets),
                        associated_media=sum(
                            item.status is AssociationStatus.ASSOCIATED for item in associations
                        ),
                        unresolved_media=unresolved,
                        conflicting_media=conflicts,
                        attention_codes=stage_attention,
                    )
                )
            latest = self.get_latest_reconciliation(event_id)
            recovering = latest is not None and latest.status is ReconciliationStatus.RUNNING
            ready = (
                database_available
                and not recovering
                and latest is not None
                and latest.status is ReconciliationStatus.COMPLETED
            )
            if not database_available:
                attention.append("postgresql_unavailable")
            if recovering:
                attention.append("startup_reconciliation_running")
            if latest is not None and latest.status is ReconciliationStatus.FAILED:
                attention.append("startup_reconciliation_failed")
            return EventOperationalStatus(
                event_id=event.id,
                event_key=event.key,
                event_name=event.name,
                database_available=database_available,
                ready=ready,
                recovering=recovering,
                stages=stages,
                attention_codes=attention,
                latest_reconciliation=latest,
                recent_media=self.list_recent_media(event_id),
                boundary_proposals=tuple(
                    proposal
                    for session in (
                        session
                        for stage in self.list_stages(event_id)
                        for session in self.list_sessions_for_stage(stage.id)
                    )
                    for proposal in self.list_boundary_proposals(session.id)
                )[:100],
            )


__all__ = [
    "EventModeKernelRepository",
    "InMemoryEventModeKernelRepository",
    "KernelConflictError",
    "KernelNotFoundError",
    "KernelStorageUnavailableError",
]
