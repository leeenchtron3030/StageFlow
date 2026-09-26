"""Human command and fenced render worker orchestration."""
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Protocol

from app.contexts.work_execution import (
    ClaimRequest,
    DurableOperation,
    EnqueueRenderOperation,
    OperationClaim,
    OperationFailure,
    PendingOperation,
    RenderOperationInput,
    WorkerHealth,
    WorkerPressure,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.contexts.work_execution.application import render_work_key
from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    RenderActor,
    RenderedOutput,
    RenderError,
    RenderPlan,
    RenderProfile,
    RenderReason,
    RenderRequest,
)


class RenderResultCommitAmbiguousError(WorkExecutionStorageUnavailableError):
    """The result transaction may have committed; retain its published files."""


class RenderRepository(Protocol):
    def request(self, pending: PendingOperation[RenderOperationInput]) -> DurableOperation[
        RenderOperationInput
    ]: ...

    def event_for_revision(self, revision_id: EntityId) -> EntityId: ...

    def load_plan(self, revision_id: EntityId, profile: RenderProfile) -> RenderPlan: ...

    def apply_render_result(
        self, claim: OperationClaim[RenderOperationInput], output: RenderedOutput,
    ) -> RenderedOutput: ...


@dataclass(slots=True)
class RenderingService:
    repository: RenderRepository
    clock: Clock
    deployment_id: str

    def request_render(
        self, assembly_revision_id: EntityId, profile: RenderProfile,
        actor: RenderActor, command_id: EntityId,
    ) -> DurableOperation[RenderOperationInput]:
        request = RenderRequest(assembly_revision_id, profile, actor, command_id)
        now = self.clock.now()
        envelope = EnqueueRenderOperation(
            command_id, "render:" + command_id.value, self.deployment_id,
            self.repository.event_for_revision(assembly_revision_id),
            RenderOperationInput(assembly_revision_id, profile.id, profile.version,
                                 command_id.value.replace("-", "")),
            0, now, 3, timedelta(seconds=30), False, now,
        )
        # Time is receipt time, not caller intent. Actor is part of exact command replay.
        digest = human_command_digest({
            "kind": "render_request", "revision": request.assembly_revision_id.value,
            "profile": profile.id, "version": profile.version,
            "actor": actor.id.value, "authority": actor.authority_kind,
        })
        return self.repository.request(PendingOperation(
            envelope, digest, render_work_key(envelope),
        ))


class RenderExecutionPort(Protocol):
    def discard_unregistered(self, output: RenderedOutput) -> None: ...

    def execute(
        self, claim: OperationClaim[RenderOperationInput], plan: RenderPlan,
        heartbeat: Callable[[], None],
    ) -> RenderedOutput: ...


@dataclass(slots=True)
class RenderWorker:
    work: WorkExecutionRepository[RenderOperationInput]
    repository: RenderRepository
    execution: RenderExecutionPort
    profile: RenderProfile

    def run_once(self, request: ClaimRequest) -> DurableOperation[RenderOperationInput] | None:
        claim = self.work.claim_next(replace(request, operation_kind="render"))
        if claim is None:
            return None
        active = self.work.mark_running(claim)

        def heartbeat() -> None:
            nonlocal active
            active = self.work.renew(active, lease_duration=request.lease_duration)
            self.work.record_presence(
                request.worker_id, ttl=timedelta(seconds=30), maximum_concurrency=1,
                health=WorkerHealth.AVAILABLE, pressure=WorkerPressure.NORMAL,
            )

        try:
            plan = self.repository.load_plan(active.operation.input.assembly_revision_id,
                                             self.profile)
            output = self.execution.execute(active, plan, heartbeat)
            try:
                self.repository.apply_render_result(active, output)
            except RenderResultCommitAmbiguousError:
                raise
            except Exception:
                self.execution.discard_unregistered(output)
                raise
        except Exception as exc:
            # Fencing is still authoritative: record_failure may itself refuse a lost lease.
            error = exc if isinstance(exc, RenderError) else RenderError(RenderReason.INTERNAL)
            return self.work.record_failure(active, OperationFailure(
                error.code.value, error.retryable, error.code.value,
            ))
        return self.work.get_operation(active.operation.id)
