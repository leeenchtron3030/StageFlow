from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import psycopg

from app.contexts.editorial import EditorialMomentService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.integration.devcon import DevconProgramSync, ProgramSyncResult
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import (
    EventOperationalStatus,
    Session,
)
from app.contexts.production.event_mode_kernel.repository import (
    EventModeKernelRepository,
    KernelStorageUnavailableError,
)
from app.contexts.production.event_mode_kernel.service import StableAssetIngressPublisher
from app.contexts.production.media_timing_evidence import MediaTimingEvidenceRepository
from app.contexts.production.runtime import StageFlowRuntime
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    RuntimeProfile,
    load_kernel_deployment_configuration,
)
from app.infrastructure.devcon import DevconPublicProgramAdapter
from app.infrastructure.postgres import (
    PostgresEditorialMomentRepository,
    PostgresEventModeKernelRepository,
    PostgresIngressRepository,
    PostgresMediaTimingEvidenceRepository,
)
from app.shared.ids import EntityId
from app.shared.time import Clock, SystemClock

from .media_cycle import BoundedMediaCycle, MediaCycleResult
from .runtime_factory import build_stageflow_runtime


class KernelDatabaseUnavailableError(RuntimeError):
    """The configured PostgreSQL dependency could not be reached."""


class KernelSchemaMigrationRequiredError(RuntimeError):
    """PostgreSQL is reachable but does not have the required Kernel schema."""


@dataclass(slots=True)
class KernelStartupProgress:
    configuration_supplied: bool = False
    configuration_valid: bool | None = None
    database_available: bool | None = None
    runtime_composed: bool = False


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
    media_timing_evidence_repository: MediaTimingEvidenceRepository | None = None
    devcon_program_sync: DevconProgramSync | None = None
    editorial_moments: EditorialMomentService | None = None

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

    def sync_devcon_program(self) -> ProgramSyncResult:
        if self.devcon_program_sync is None:
            raise RuntimeError("devcon_read_not_configured")
        event = self.repository.get_event_by_key(self.event_key)
        if event is None:
            raise RuntimeError("explicit_event_stage_bootstrap_required")
        stages = self.repository.list_stages(event.id)
        if len(stages) != 1:
            raise RuntimeError("demo_single_stage_topology_invalid")
        return self.devcon_program_sync.synchronize(
            event_id=event.id,
            stage_id=stages[0].id,
        )

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
        session = self.kernel.correct_session_boundary(
            operation_id=operation_id,
            session_id=session_id,
            boundary_kind=boundary_kind,
            boundary_at=boundary_at,
            actor_id=actor_id,
            reason=reason,
        )
        if self.editorial_moments is not None:
            self.editorial_moments.revalidate_session_boundary(session.id)
        return session

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
                    '0005_kernel_follow_up_closure',
                    '0006_media_timing_evidence'
                )
                """
            ).fetchone()
            if row is None or row[0] != 6:
                raise KernelSchemaMigrationRequiredError(
                    "kernel_schema_migration_required"
                )
    except psycopg.OperationalError as exc:
        raise KernelDatabaseUnavailableError("postgresql_unavailable") from exc


def verify_transcription_schema(dsn: str) -> None:
    try:
        with psycopg.connect(dsn) as connection:
            row = connection.execute(
                """
                SELECT count(*) FROM stageflow.schema_migration
                WHERE version IN (
                    '0007_transcription_worker', '0008_demo_vertical_slice',
                    '0009_program_expectation_reconciliation'
                )
                """
            ).fetchone()
            if row is None or row[0] != 3:
                raise KernelSchemaMigrationRequiredError(
                    "transcription_schema_migration_required"
                )
    except psycopg.OperationalError as exc:
        raise KernelDatabaseUnavailableError("postgresql_unavailable") from exc


def verify_editorial_schema(dsn: str) -> None:
    try:
        with psycopg.connect(dsn) as connection:
            row = connection.execute(
                """
                SELECT count(*) FROM stageflow.schema_migration
                WHERE version IN (
                    '0008_demo_vertical_slice',
                    '0010_editorial_candidate_moment',
                    '0011_editorial_review_foundation'
                )
                """
            ).fetchone()
            if row is None or row[0] != 3:
                raise KernelSchemaMigrationRequiredError(
                    "editorial_schema_migration_required"
                )
    except psycopg.OperationalError as exc:
        raise KernelDatabaseUnavailableError("postgresql_unavailable") from exc


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
    devcon_configuration = configuration.deployment.devcon_read
    return KernelComponents(
        configuration=configuration,
        repository=repository,
        kernel=kernel,
        editorial_moments=EditorialMomentService(
            PostgresEditorialMomentRepository(configuration.postgres_dsn),
            kernel.clock,
        ),
        media_timing_evidence_repository=PostgresMediaTimingEvidenceRepository(
            configuration.postgres_dsn
        ),
        devcon_program_sync=(
            None
            if devcon_configuration is None
            else DevconProgramSync(
                repository=repository,
                source=DevconPublicProgramAdapter(devcon_configuration),
                clock=kernel.clock,
            )
        ),
    )


def load_kernel_components_from_environment(
    *,
    environment: dict[str, str] | None = None,
    clock: Clock | None = None,
    progress: KernelStartupProgress | None = None,
) -> KernelComponents | None:
    startup = progress if progress is not None else KernelStartupProgress()
    env = dict(os.environ) if environment is None else environment
    path = env.get("STAGEFLOW_KERNEL_CONFIG_PATH")
    if path is None:
        return None
    startup.configuration_supplied = True
    try:
        configuration = load_kernel_deployment_configuration(path, environment=env)
    except (OSError, ValueError):
        startup.configuration_valid = False
        raise
    startup.configuration_valid = True
    try:
        verify_kernel_schema(configuration.postgres_dsn)
        verify_editorial_schema(configuration.postgres_dsn)
        if (
            configuration.deployment.runtime_profile
            is RuntimeProfile.DEMO_SINGLE_STAGE
        ):
            verify_transcription_schema(configuration.postgres_dsn)
    except KernelDatabaseUnavailableError:
        startup.database_available = False
        raise
    except KernelSchemaMigrationRequiredError:
        startup.database_available = True
        raise
    startup.database_available = True
    components = build_kernel_components(configuration, clock=clock)
    try:
        event = components.repository.get_event_by_key(components.event_key)
        if event is not None:
            components.runtime = build_stageflow_runtime(
                configuration,
                stages=components.repository.list_stages(event.id),
                clock=components.kernel.clock,
            )
            components.compose_media_cycle()
            startup.runtime_composed = True
            components.reconcile_startup(event.id)
    except KernelStorageUnavailableError:
        startup.database_available = False
        raise
    return components


__all__ = [
    "KernelDatabaseUnavailableError",
    "KernelSchemaMigrationRequiredError",
    "KernelStartupProgress",
    "KernelComponents",
    "build_kernel_components",
    "load_kernel_components_from_environment",
    "verify_editorial_schema",
    "verify_kernel_schema",
    "verify_transcription_schema",
]
