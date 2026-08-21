from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict

from app.api.v1.response_models import (
    ImmutableJsonMapping,
    ProgramChangeResponse,
    program_change_responses,
)
from app.bootstrap.event_mode_kernel import KernelComponents, KernelStartupProgress
from app.contexts.editorial import (
    EditorialMomentStorageUnavailableError,
    EditorialSessionCandidateProjection,
)
from app.contexts.events import (
    ProgramExpectation,
    ProgramExpectationReconciliation,
)
from app.contexts.production.event_mode_kernel.contracts import (
    EventOperationalStatus,
    SessionOperationalProjection,
)
from app.contexts.production.event_mode_kernel.repository import (
    KernelStorageUnavailableError,
)
from app.demo.autonomous import (
    AutonomousEventNodeCoordinator,
    AutonomousEventNodeStatus,
)

router = APIRouter(prefix="/kernel", tags=["kernel"])


class AssemblingSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    activity_state: str
    package_state: str
    package_revision: int
    revision: int
    authoritative_start: datetime
    authoritative_end: datetime | None
    program_expectation_id: str | None
    program_expectation_title: str | None
    program_expectation_revision: int | None
    program_expectation_planned_start: datetime | None
    program_expectation_planned_end: datetime | None
    completion_decision_id: str | None
    completion_actor_id: str | None
    completion_decided_at: datetime | None
    editorial_candidate_count: int | None
    editorial_latest_candidate_activity_at: datetime | None
    editorial_generation_state: str
    editorial_location_conflict_count: int | None


class StageStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage_id: str
    key: str
    name: str
    source_available: bool | None
    session_id: str | None
    assembling_session_ids: tuple[str, ...]
    assembling_sessions: tuple[AssemblingSessionResponse, ...]
    assembling_sessions_truncated: bool
    recent_sessions: tuple[AssemblingSessionResponse, ...]
    recent_sessions_truncated: bool
    session_limit: int
    session_activity_state: str | None
    session_package_state: str | None
    session_package_revision: int | None
    session_revision: int | None
    session_authoritative_start: datetime | None
    session_authoritative_end: datetime | None
    last_media_arrived_at: datetime | None
    discovered: int
    stabilizing: int
    ready: int
    registered: int
    associated: int
    unresolved: int
    conflicting: int
    attention_codes: tuple[str, ...]


class MediaStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    proposed_asset_id: str
    asset_id: str | None
    stage_id: str
    source_binding_key: str
    registration_state: str
    discovered_at: datetime
    last_observed_at: datetime
    association_status: str | None
    association_authority: str | None
    session_id: str | None
    epistemic_kinds: tuple[str, ...]
    media_started_at: datetime | None
    media_ended_at: datetime | None
    diagnostic_codes: tuple[str, ...]
    association_reason_codes: tuple[str, ...]
    association_evidence_ids: tuple[str, ...]
    association_policy_id: str | None
    association_policy_version: str | None
    association_input_references: tuple[ImmutableJsonMapping, ...]
    association_actor_id: str | None
    association_decided_at: datetime | None


class BoundaryProposalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposal_id: str
    session_id: str
    boundary_kind: str
    boundary_at: datetime
    epistemic_kind: str
    proposer_id: str
    evidence_ids: tuple[str, ...]
    policy_id: str
    policy_version: str
    model_id: str | None
    model_version: str | None
    reason: str
    proposed_at: datetime


class ProgramExpectationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    expectation_id: str
    key: str
    stage_id: str | None
    title: str
    speakers: tuple[str, ...]
    planned_start: datetime | None
    planned_end: datetime | None
    revision: int
    recorded_at: datetime
    provider: str | None
    external_event_id: str | None
    external_session_id: str | None
    external_room_id: str | None
    lifecycle_state: str
    synchronization_scope: str | None
    last_observed_at: datetime
    lifecycle_changed_at: datetime
    evidence_kind: str = "external"



class ProgramSynchronizationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    synchronized_at: datetime
    observed: int
    added: int
    changed: int
    unchanged: int
    withdrawn: int
    restored: int
    current_expectation_count: int
    changes: tuple[ProgramChangeResponse, ...]
    changes_truncated: bool

class AutomationStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    state: str
    owner: bool
    media_reconciliation_interval_seconds: float
    program_refresh_interval_seconds: float
    media_cycle_count: int
    media_last_attempt_at: datetime | None
    media_last_success_at: datetime | None
    media_last_failure_code: str | None
    media_candidates_seen: int
    media_assets_registered: int
    transcription_operations_enqueued: int
    transcription_enqueue_failures: int
    program_refresh_count: int
    program_last_attempt_at: datetime | None
    program_last_success_at: datetime | None
    program_last_failure_code: str | None

class KernelStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    configured: bool
    configuration_supplied: bool
    configuration_valid: bool | None
    runtime_composed: bool
    runtime_profile: str | None
    deployment_id: str | None = None
    node_id: str | None = None
    automation: AutomationStatusResponse | None = None
    event_id: str | None
    event_key: str | None
    event_name: str | None
    database_available: bool
    ready: bool
    recovering: bool
    reconciliation_status: str | None
    reconciliation_started_at: datetime | None
    reconciliation_completed_at: datetime | None
    stages: tuple[StageStatusResponse, ...]
    program_expectations: tuple[ProgramExpectationResponse, ...] = ()
    program_synchronization: ProgramSynchronizationResponse | None = None
    recent_media: tuple[MediaStatusResponse, ...] = ()
    boundary_proposals: tuple[BoundaryProposalResponse, ...] = ()
    attention_codes: tuple[str, ...]
    startup_error: str | None = None


def _fallback_response(
    *,
    configured: bool,
    configuration_supplied: bool,
    configuration_valid: bool | None,
    runtime_composed: bool,
    runtime_profile: str | None,
    event_key: str | None,
    event_name: str | None,
    database_available: bool,
    attention_code: str,
    startup_error: str | None = None,
) -> KernelStatusResponse:
    return KernelStatusResponse(
        configured=configured,
        configuration_supplied=configuration_supplied,
        configuration_valid=configuration_valid,
        runtime_composed=runtime_composed,
        runtime_profile=runtime_profile,
        event_id=None,
        event_key=event_key,
        event_name=event_name,
        database_available=database_available,
        ready=False,
        recovering=False,
        reconciliation_status=None,
        reconciliation_started_at=None,
        reconciliation_completed_at=None,
        stages=(),
        attention_codes=(attention_code,),
        startup_error=startup_error,
    )



def _response(
    status: EventOperationalStatus,
    *,
    configuration_supplied: bool,
    configuration_valid: bool | None,
    runtime_composed: bool,
    runtime_profile: str,
    deployment_id: str,
    node_id: str,
    program_expectations: tuple[ProgramExpectation, ...],
    program_reconciliation: ProgramExpectationReconciliation | None,
    editorial_projections: tuple[EditorialSessionCandidateProjection, ...],
    automation: AutonomousEventNodeStatus | None,
) -> KernelStatusResponse:
    reconciliation = status.latest_reconciliation
    editorial_by_session = {
        item.session_id: item for item in editorial_projections
    }

    def session_response(
        item: SessionOperationalProjection,
    ) -> AssemblingSessionResponse:
        editorial = editorial_by_session.get(item.session_id)
        return AssemblingSessionResponse(
            session_id=item.session_id.value,
            activity_state=item.activity_state.value,
            package_state=item.package_state.value,
            package_revision=item.package_revision,
            revision=item.revision,
            authoritative_start=item.authoritative_start,
            authoritative_end=item.authoritative_end,
            program_expectation_id=(
                None
                if item.program_expectation_id is None
                else item.program_expectation_id.value
            ),
            program_expectation_title=item.program_expectation_title,
            program_expectation_revision=item.program_expectation_revision,
            program_expectation_planned_start=(
                item.program_expectation_planned_start
            ),
            program_expectation_planned_end=item.program_expectation_planned_end,
            completion_decision_id=(
                None
                if item.completion_decision_id is None
                else item.completion_decision_id.value
            ),
            completion_actor_id=(
                None
                if item.completion_actor_id is None
                else item.completion_actor_id.value
            ),
            completion_decided_at=item.completion_decided_at,
            editorial_candidate_count=(
                None if editorial is None else editorial.candidate_count
            ),
            editorial_latest_candidate_activity_at=(
                None
                if editorial is None
                else editorial.latest_candidate_activity_at
            ),
            editorial_generation_state=(
                "unknown"
                if editorial is None
                else editorial.generation_state.value
            ),
            editorial_location_conflict_count=(
                None if editorial is None else editorial.location_conflict_count
            ),
        )

    return KernelStatusResponse(
        configured=True,
        configuration_supplied=configuration_supplied,
        configuration_valid=configuration_valid,
        runtime_composed=runtime_composed,
        runtime_profile=runtime_profile,
        deployment_id=deployment_id,
        node_id=node_id,
        automation=(
            None
            if automation is None
            else AutomationStatusResponse.model_validate(
                {
                    field: getattr(automation, field)
                    for field in automation.__dataclass_fields__
                }
            )
        ),
        event_id=status.event_id.value,
        event_key=status.event_key,
        event_name=status.event_name,
        database_available=status.database_available,
        ready=status.ready,
        recovering=status.recovering,
        reconciliation_status=(
            None if reconciliation is None else reconciliation.status.value
        ),
        reconciliation_started_at=(
            None if reconciliation is None else reconciliation.started_at
        ),
        reconciliation_completed_at=(
            None if reconciliation is None else reconciliation.completed_at
        ),
        program_expectations=tuple(
            ProgramExpectationResponse(
                expectation_id=item.id.value,
                key=item.key,
                stage_id=None if item.stage_id is None else item.stage_id.value,
                title=item.title,
                speakers=tuple(item.speakers),
                planned_start=item.planned_start,
                planned_end=item.planned_end,
                revision=item.revision,
                recorded_at=item.recorded_at,
                provider=item.external_references.get("provider"),
                external_event_id=item.external_references.get("devcon_event_id"),
                external_session_id=item.external_references.get("devcon_session_id"),
                external_room_id=item.external_references.get("devcon_room_id"),
                lifecycle_state=item.lifecycle_state.value,
                synchronization_scope=item.synchronization_scope,
                last_observed_at=item.last_observed_at or item.recorded_at,
                lifecycle_changed_at=item.lifecycle_changed_at or item.recorded_at,
            )
            for item in program_expectations
        ),
        program_synchronization=(
            None
            if program_reconciliation is None
            else ProgramSynchronizationResponse(
                provider=program_reconciliation.provider,
                synchronized_at=program_reconciliation.synchronized_at,
                observed=program_reconciliation.observed,
                added=program_reconciliation.added,
                changed=program_reconciliation.changed,
                unchanged=program_reconciliation.unchanged,
                withdrawn=program_reconciliation.withdrawn,
                restored=program_reconciliation.restored,
                current_expectation_count=len(program_reconciliation.expectations),
                changes=program_change_responses(program_reconciliation.changes),
                changes_truncated=program_reconciliation.changes_truncated,
            )
        ),
        stages=tuple(
            StageStatusResponse(
                stage_id=stage.stage_id.value,
                key=stage.stage_key,
                name=stage.stage_name,
                source_available=stage.source_available,
                session_id=(
                    None
                    if stage.active_or_assembling_session_id is None
                    else stage.active_or_assembling_session_id.value
                ),
                assembling_session_ids=tuple(
                    value.value for value in stage.assembling_session_ids
                ),
                assembling_sessions=tuple(
                    session_response(item)
                    for item in stage.assembling_sessions
                ),
                assembling_sessions_truncated=stage.assembling_sessions_truncated,
                recent_sessions=tuple(
                    session_response(item) for item in stage.recent_sessions
                ),
                recent_sessions_truncated=stage.recent_sessions_truncated,
                session_limit=stage.session_limit,
                session_activity_state=(
                    None
                    if stage.session_activity_state is None
                    else stage.session_activity_state.value
                ),
                session_package_state=(
                    None
                    if stage.session_package_state is None
                    else stage.session_package_state.value
                ),
                session_package_revision=stage.session_package_revision,
                session_revision=stage.session_revision,
                session_authoritative_start=stage.session_authoritative_start,
                session_authoritative_end=stage.session_authoritative_end,
                last_media_arrived_at=stage.last_media_arrived_at,
                discovered=stage.discovered_media,
                stabilizing=stage.stabilizing_media,
                ready=stage.ready_media,
                registered=stage.registered_media,
                associated=stage.associated_media,
                unresolved=stage.unresolved_media,
                conflicting=stage.conflicting_media,
                attention_codes=tuple(stage.attention_codes),
            )
            for stage in status.stages
        ),
        recent_media=tuple(
            MediaStatusResponse(
                candidate_id=item.candidate_id.value,
                proposed_asset_id=item.proposed_asset_id.value,
                asset_id=None if item.asset_id is None else item.asset_id.value,
                stage_id=item.stage_id.value,
                source_binding_key=item.source_binding_key,
                registration_state=item.registration_state.value,
                discovered_at=item.discovered_at,
                last_observed_at=item.last_observed_at,
                association_status=(
                    None
                    if item.association_status is None
                    else item.association_status.value
                ),
                association_authority=(
                    None
                    if item.association_authority is None
                    else item.association_authority.value
                ),
                session_id=None if item.session_id is None else item.session_id.value,
                epistemic_kinds=tuple(value.value for value in item.epistemic_kinds),
                media_started_at=item.media_started_at,
                media_ended_at=item.media_ended_at,
                diagnostic_codes=tuple(item.diagnostic_codes),
                association_reason_codes=tuple(item.association_reason_codes),
                association_evidence_ids=tuple(
                    value.value for value in item.association_evidence_ids
                ),
                association_policy_id=item.association_policy_id,
                association_policy_version=item.association_policy_version,
                association_input_references=tuple(
                    {
                        "record_type": value.record_type,
                        "record_id": value.record_id,
                        "revision": value.revision,
                    }
                    for value in item.association_input_references
                ),
                association_actor_id=(
                    None
                    if item.association_actor_id is None
                    else item.association_actor_id.value
                ),
                association_decided_at=item.association_decided_at,
            )
            for item in status.recent_media
        ),
        boundary_proposals=tuple(
            BoundaryProposalResponse(
                proposal_id=item.id.value,
                session_id=item.session_id.value,
                boundary_kind=item.boundary_kind,
                boundary_at=item.boundary_at,
                epistemic_kind=item.epistemic_kind.value,
                proposer_id=item.proposer_id.value,
                evidence_ids=tuple(value.value for value in item.evidence_ids),
                policy_id=item.policy_id,
                policy_version=item.policy_version,
                model_id=item.model_id,
                model_version=item.model_version,
                reason=item.reason,
                proposed_at=item.proposed_at,
            )
            for item in status.boundary_proposals
        ),
        attention_codes=tuple(status.attention_codes),
    )


@router.get("/status", response_model=KernelStatusResponse)
def kernel_status(request: Request, response: Response) -> KernelStatusResponse:
    components = getattr(request.app.state, "kernel", None)
    startup_error = getattr(request.app.state, "kernel_startup_error", None)
    startup_progress = getattr(request.app.state, "kernel_startup_progress", None)
    if not isinstance(startup_progress, KernelStartupProgress):
        startup_progress = KernelStartupProgress()
    configuration_supplied = startup_progress.configuration_supplied
    configuration_valid = startup_progress.configuration_valid
    database_available = startup_progress.database_available is True
    runtime_composed = startup_progress.runtime_composed
    if isinstance(components, KernelComponents):
        configuration_supplied = True
        configuration_valid = True
        database_available = True
        runtime_composed = components.runtime is not None
    if not isinstance(components, KernelComponents):
        return _fallback_response(
            configured=configuration_valid is True,
            configuration_supplied=configuration_supplied,
            configuration_valid=configuration_valid,
            runtime_composed=runtime_composed,
            runtime_profile=None,
            event_key=None,
            event_name=None,
            database_available=database_available,
            attention_code=(
                "kernel_startup_failed" if startup_error else "kernel_not_configured"
            ),
            startup_error=startup_error,
        )
    try:
        status = components.status()
    except KernelStorageUnavailableError as exc:
        response.status_code = 503
        return _fallback_response(
            configured=True,
            configuration_supplied=configuration_supplied,
            configuration_valid=configuration_valid,
            runtime_composed=runtime_composed,
            runtime_profile=components.configuration.deployment.runtime_profile.value,
            event_key=components.event_key,
            event_name=components.configuration.deployment.event.name,
            database_available=False,
            attention_code="postgresql_unavailable",
            startup_error=str(exc),
        )
    if status is None:
        return _fallback_response(
            configured=True,
            configuration_supplied=configuration_supplied,
            configuration_valid=configuration_valid,
            runtime_composed=runtime_composed,
            runtime_profile=components.configuration.deployment.runtime_profile.value,
            event_key=components.event_key,
            event_name=components.configuration.deployment.event.name,
            database_available=True,
            attention_code="explicit_event_stage_bootstrap_required",
        )
    session_ids = tuple(
        dict.fromkeys(
            item.session_id
            for stage in status.stages
            for item in (*stage.assembling_sessions, *stage.recent_sessions)
        )
    )
    coordinator = getattr(request.app.state, "autonomous_event_node", None)
    automation = (
        coordinator.status()
        if isinstance(coordinator, AutonomousEventNodeCoordinator)
        else None
    )
    try:
        editorial_projections = (
            ()
            if components.editorial_moments is None
            else components.editorial_moments.projections_for_sessions(session_ids)
        )
        return _response(
            status,
            configuration_supplied=configuration_supplied,
            configuration_valid=configuration_valid,
            runtime_composed=runtime_composed,
            runtime_profile=components.configuration.deployment.runtime_profile.value,
            deployment_id=components.configuration.deployment.deployment_id,
            node_id=components.configuration.deployment.node_id,
            program_expectations=components.repository.list_program_expectations(
                status.event_id
            ),
            program_reconciliation=(
                None
                if len(status.stages) != 1
                else components.repository.get_latest_program_reconciliation(
                    status.event_id, status.stages[0].stage_id
                )
            ),
            editorial_projections=editorial_projections,
            automation=automation,
        )
    except (KernelStorageUnavailableError, EditorialMomentStorageUnavailableError) as exc:
        response.status_code = 503
        return _fallback_response(
            configured=True,
            configuration_supplied=configuration_supplied,
            configuration_valid=configuration_valid,
            runtime_composed=runtime_composed,
            runtime_profile=components.configuration.deployment.runtime_profile.value,
            event_key=components.event_key,
            event_name=components.configuration.deployment.event.name,
            database_available=False,
            attention_code="postgresql_unavailable",
            startup_error=str(exc),
        )


__all__ = [
    "AutomationStatusResponse",
    "BoundaryProposalResponse",
    "AssemblingSessionResponse",
    "KernelStatusResponse",
    "MediaStatusResponse",
    "ProgramExpectationResponse",
    "StageStatusResponse",
    "router",
]
