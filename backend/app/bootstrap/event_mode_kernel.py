from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import EventOperationalStatus
from app.contexts.production.event_mode_kernel.repository import EventModeKernelRepository
from app.contexts.production.event_mode_kernel.service import StableAssetIngressPublisher
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


@dataclass(slots=True)
class KernelComponents:
    configuration: EffectiveKernelConfiguration
    repository: EventModeKernelRepository
    kernel: DurableEventModeKernel
    source_availability: dict[str, bool] = field(
        default_factory=lambda: dict[str, bool]()
    )
    startup_error: str | None = None

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
        self.reconcile_startup(result.event.id)
        return self.repository.operational_status(
            result.event.id,
            source_availability=self.source_availability,
        )

    def reconcile_startup(self, event_id: EntityId) -> EventOperationalStatus:
        run = self.kernel.begin_reconciliation(event_id=event_id, scope="startup")
        self.source_availability = {
            key: Path(path).exists() for key, path in self.configuration.sources.items()
        }
        unavailable = sorted(
            key for key, available in self.source_availability.items() if not available
        )
        self.kernel.finish_reconciliation(
            run,
            candidates_seen=0,
            assets_registered=0,
            failure_code=(
                None
                if not unavailable
                else f"configured_sources_unavailable:{','.join(unavailable)}"
            ),
        )
        return self.repository.operational_status(
            event_id,
            source_availability=self.source_availability,
        )

    def status(self) -> EventOperationalStatus | None:
        event = self.repository.get_event_by_key(self.event_key)
        if event is None:
            return None
        return self.repository.operational_status(
            event.id,
            source_availability=self.source_availability,
        )


def verify_kernel_schema(dsn: str) -> None:
    try:
        with psycopg.connect(dsn) as connection:
            row = connection.execute(
                """
                SELECT count(*) FROM stageflow.schema_migration
                WHERE version IN ('0001_ingress', '0002_event_mode_kernel')
                """
            ).fetchone()
            if row is None or row[0] != 2:
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
        components.reconcile_startup(event.id)
    return components


__all__ = [
    "KernelComponents",
    "build_kernel_components",
    "load_kernel_components_from_environment",
    "verify_kernel_schema",
]
