"""Human command and fenced render worker orchestration."""
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Literal, Protocol

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
    RENDER_PRESETS,
    RenderActor,
    RenderAdjustments,
    RenderedOutput,
    RenderError,
    RenderPlan,
    RenderProfile,
    RenderReason,
    RenderRequest,
    effective_profile,
    normalize_adjustments,
    render_preset,
)
from .settings import EventRenderSetting


class RenderResultCommitAmbiguousError(WorkExecutionStorageUnavailableError):
    """The result transaction may have committed; retain its published files."""


class RenderRepository(Protocol):
    def request(self, pending: PendingOperation[RenderOperationInput]) -> DurableOperation[
        RenderOperationInput
    ]: ...

    def request_at_setting(
        self, event_id: EntityId, command_id: EntityId,
        build: Callable[[EventRenderSetting | None], PendingOperation[RenderOperationInput]],
    ) -> DurableOperation[RenderOperationInput]: ...

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
        self, assembly_revision_id: EntityId, profile: RenderProfile | None,
        actor: RenderActor, command_id: EntityId,
        expected_setting_version: int | None | Literal["unspecified"] = "unspecified",
        *, requested_profile_id: str | None = None, requested_profile_version: str | None = None,
    ) -> DurableOperation[RenderOperationInput]:
        request = RenderRequest(assembly_revision_id, profile, actor, command_id,
                                expected_setting_version, requested_profile_id,
                                requested_profile_version)
        now = self.clock.now()
        event_id = self.repository.event_for_revision(assembly_revision_id)

        def build(setting: EventRenderSetting | None) -> PendingOperation[RenderOperationInput]:
            preset = RENDER_PRESETS[0] if setting is None else render_preset(
                setting.profile_id, setting.profile_version)
            adjustments = normalize_adjustments(preset, RenderAdjustments() if setting is None
                                                else setting.adjustments)
            version = None if setting is None else setting.version
            effective = effective_profile(preset, adjustments)
            named_profile = profile
            if (request.requested_profile_id is not None
                    or request.requested_profile_version is not None):
                standard_id = RENDER_PRESETS[0].profile.id
                # Keep explicit historical Standard requests refused, including the
                # legacy version-only form when the resolved preset is Standard.
                if request.requested_profile_version in {"1", "2"} and (
                    request.requested_profile_id == standard_id
                    or (request.requested_profile_id is None and effective.id == standard_id)
                ):
                    raise RenderError(RenderReason.PROFILE_UNSUPPORTED)
                if (request.requested_profile_id is not None
                        and request.requested_profile_id not in {
                            p.profile.id for p in RENDER_PRESETS}):
                    raise RenderError(RenderReason.PROFILE_UNSUPPORTED)
                if ((request.requested_profile_id is not None
                     and request.requested_profile_id != effective.id)
                        or (request.requested_profile_version is not None
                            and request.requested_profile_version != effective.version)):
                    raise RenderError(RenderReason.SETTING_CHANGED)
                named_profile = preset.profile
            if (request.expected_setting_version != "unspecified"
                    and request.expected_setting_version != version):
                raise RenderError(RenderReason.SETTING_CHANGED)
            if named_profile is not None and (
                (named_profile.id, named_profile.version) != (effective.id, effective.version)
                or (request.expected_setting_version == "unspecified"
                    and named_profile != effective)
            ):
                raise RenderError(RenderReason.SETTING_CHANGED)
            envelope = EnqueueRenderOperation(
                command_id, "render:" + command_id.value, self.deployment_id, event_id,
                RenderOperationInput(assembly_revision_id, effective.id, effective.version,
                    command_id.value.replace("-", ""), adjustments.video_bit_rate,
                    adjustments.audio_bit_rate, version),
                0, now, 3, timedelta(seconds=30), False, now,
            )
            # Time is receipt time, not caller intent. Preserve the unadjusted v3 digest.
            document: dict[str, object] = {
                "kind": "render_request", "revision": request.assembly_revision_id.value,
                "profile": effective.id, "version": effective.version,
                "actor": actor.id.value, "authority": actor.authority_kind,
            }
            if adjustments != RenderAdjustments():
                document.update(video_bit_rate=effective.bit_rate,
                                audio_bit_rate=effective.audio_bit_rate)
            return PendingOperation(envelope, human_command_digest(document),
                                    render_work_key(envelope))

        return self.repository.request_at_setting(event_id, command_id, build)


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
            value = active.operation.input
            try:
                profile = effective_profile(render_preset(value.execution_profile_id,
                                                          value.execution_profile_version),
                    RenderAdjustments(value.video_bit_rate, value.audio_bit_rate))
            except RenderError:
                raise RenderError(RenderReason.PROFILE_UNSUPPORTED) from None
            plan = self.repository.load_plan(value.assembly_revision_id, profile)
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
