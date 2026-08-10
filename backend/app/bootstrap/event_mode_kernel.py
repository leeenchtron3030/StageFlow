from __future__ import annotations

import os
from dataclasses import dataclass, field

import psycopg

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import EventOperationalStatus
from app.contexts.production.event_mode_kernel.repository import (
    EventModeKernelRepository,
    KernelStorageUnavailableError,
)
from app.contexts.production.event_mode_kernel.service import StableAssetIngressPublisher
from app.contexts.production.runtime import StageFlowRuntime
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    load_kernel_deployment_configuration,
)
from app.infrastructure.postgres import (
    PostgresEventModeKernelRepository,
    PostgresIngressRepository,
)
from app.shared.ids import EntityId
from app.shared.time import Clock, SystemClock

from .media_cycle import BoundedMediaCycle, MediaCycleResult
from .runtime_factory import build_stageflow_runtime


@dataclass(slots=True)
class KernelComponents:
    configuration: EffectiveKernelConfiguration
    repository: EventModeKernelRepository
    kernel: DurableEventModeKernel
    runtime: StageFlowRuntime | None = None
    media_cycle: BoundedMediaCycle | None = None
    source_availability: dict[str, bool] = field(
        default_factory=lambda: dict[str, bool]()
    )
    startup_error: str | None = None
    postgresql_recovery_required: bool = False

    @property
    def event_key(self) -> str:
        return self.configuration.deployment.event.key

    def explicit_bootstrap(
        self,
        *,
        operation_id: EntityId,
        actor_id: EntityId,
    ) -> EventOperationalStatus:
        event_definition = self.configuration.deployment.event
        result = self.kernel.bootstrap(
            EventStageBootstrapRequest(
                operation_id=operation_id,
                event_key=event_definition.key,
                event_name=event_definition.name,
                stages=tuple(
                    StageBootstrapDefinition(
                        key=stage.key,
                        name=stage.name,
                        source_bindings={source.key: source.path for source in stage.sources},
                        external_references=stage.external_references,
                    )
                    for stage in event_definition.stages
                ),
                actor_id=actor_id,
                requested_at=self.kernel.clock.now(),
                external_references=event_definition.external_references,
            )
        )
        if result.event is None:
            raise RuntimeError(result.reason or "event_stage_bootstrap_failed")
        self.runtime = build_stageflow_runtime(
            self.configuration,
            stages=tuple(result.stages),
            clock=self.kernel.clock,
        )
        self.compose_media_cycle()
        self.reconcile_startup(result.event.id)
        return self.repository.operational_status(
            result.event.id,
            source_availability=self.source_availability,
        )

    def reconcile_startup(self, event_id: EntityId) -> EventOperationalStatus:
        self.run_media_cycle(event_id=event_id, scope="startup")
        return self.repository.operational_status(
            event_id,
            source_availability=self.source_availability,
        )

    def compose_media_cycle(self) -> None:
        if self.runtime is None:
            raise RuntimeError("runtime_not_composed")
        self.media_cycle = BoundedMediaCycle(
            configuration=self.configuration,
            runtime=self.runtime,
            kernel=self.kernel,
            source_availability=self.source_availability,
        )

    def run_media_cycle(self, *, event_id: EntityId, scope: str = "scheduled") -> MediaCycleResult:
        if self.media_cycle is None:
            self.compose_media_cycle()
        assert self.media_cycle is not None
        try:
            result = self.media_cycle.run(event_id=event_id, scope=scope)
        except KernelStorageUnavailableError:
            self.postgresql_recovery_required = True
            raise
        if not result.source_failures:
            self.postgresql_recovery_required = False
        return result

    def reconcile_postgresql_recovery(self) -> EventOperationalStatus | None:
        event = self.repository.get_event_by_key(self.event_key)
        if event is None:
            return None
        self.run_media_cycle(event_id=event.id, scope="postgresql_recovery")
        return self.status()

    def status(self) -> EventOperationalStatus | None:
        try:
            event = self.repository.get_event_by_key(self.event_key)
            if event is None:
                return None
            return self.repository.operational_status(
                event.id,
                recovery_required=self.postgresql_recovery_required,
                source_availability=self.source_availability,
            )
        except KernelStorageUnavailableError:
            self.postgresql_recovery_required = True
            raise


def verify_kernel_schema(dsn: str) -> None:
    try:
        with psycopg.connect(dsn) as connection:
            row = connection.execute(
                """
                SELECT count(*) FROM stageflow.schema_migration
                WHERE version IN (
                    '0001_ingress', '0002_event_mode_kernel',
                    '0003_kernel_projections',
                    '0004_kernel_review_corrections',
                    '0005_kernel_follow_up_closure'
                )
                """
            ).fetchone()
            if row is None or row[0] != 5:
                raise RuntimeError("kernel_schema_migration_required")
    except psycopg.OperationalError as exc:
        raise RuntimeError("postgresql_unavailable") from exc


def build_kernel_components(
    configuration: EffectiveKernelConfiguration,
    *,
    clock: Clock | None = None,
) -> KernelComponents:
    repository = PostgresEventModeKernelRepository(configuration.postgres_dsn)
    ingress = PostgresIngressRepository(configuration.postgres_dsn)
    kernel = DurableEventModeKernel(
        repository=repository,
        clock=clock or SystemClock(),
        asset_ingress_publisher=StableAssetIngressPublisher(ingress),
    )
    return KernelComponents(
        configuration=configuration,
        repository=repository,
        kernel=kernel,
    )


def load_kernel_components_from_environment(
    *,
    environment: dict[str, str] | None = None,
    clock: Clock | None = None,
) -> KernelComponents | None:
    env = dict(os.environ) if environment is None else environment
    path = env.get("STAGEFLOW_KERNEL_CONFIG_PATH")
    if path is None:
        return None
    configuration = load_kernel_deployment_configuration(path, environment=env)
    verify_kernel_schema(configuration.postgres_dsn)
    components = build_kernel_components(configuration, clock=clock)
    event = components.repository.get_event_by_key(components.event_key)
    if event is not None:
        components.runtime = build_stageflow_runtime(
            configuration,
            stages=components.repository.list_stages(event.id),
            clock=components.kernel.clock,
        )
        components.compose_media_cycle()
        components.reconcile_startup(event.id)
    return components


__all__ = [
    "KernelComponents",
    "build_kernel_components",
    "load_kernel_components_from_environment",
    "verify_kernel_schema",
]
