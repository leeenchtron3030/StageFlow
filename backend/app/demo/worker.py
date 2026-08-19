from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from app.bootstrap.event_mode_kernel import load_kernel_components_from_environment
from app.contexts.work_execution import (
    ClaimRequest,
    EventNetworkPolicy,
    ExecutionLocality,
    TranscriptionWorker,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPressure,
)
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.infrastructure.transcription import (
    FasterWhisperExecutionAdapter,
    KernelMediaPathResolver,
)
from app.shared.ids import EntityId
from app.shared.time import SystemClock

IMPLEMENTATION_VERSION = "stageflow-demo-worker-1.0"


def _stable_id(value: str) -> EntityId:
    return EntityId(str(uuid5(NAMESPACE_URL, value)))


def _safe_write(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stageflow-demo-worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if not 0.1 <= arguments.poll_seconds <= 30:
        sys.stderr.write("stageflow_demo_worker_error=poll_interval_out_of_bounds\n")
        return 1
    try:
        components = load_kernel_components_from_environment()
        if components is None:
            raise RuntimeError("kernel_configuration_not_supplied")
        configuration = components.configuration
        transcription = configuration.deployment.local_transcription
        if transcription is None:
            raise RuntimeError("local_transcription_not_configured")
        event = components.repository.get_event_by_key(components.event_key)
        if event is None:
            raise RuntimeError("explicit_event_stage_bootstrap_required")

        clock = SystemClock()
        repository = PostgresWorkExecutionRepository(configuration.postgres_dsn)
        resolver = KernelMediaPathResolver(
            components.repository,
            source_roots=configuration.sources,
        )
        execution = FasterWhisperExecutionAdapter(
            transcription,
            resolver=resolver,
            clock=clock,
        )
        worker_id = _stable_id(
            f"stageflow:worker:{configuration.deployment.deployment_id}:"
            f"{configuration.deployment.node_id}:transcription"
        )
        now = clock.now()
        worker = repository.register_worker(
            Worker(
                id=worker_id,
                node_id=configuration.deployment.node_id,
                deployment_id=configuration.deployment.deployment_id,
                event_id=event.id,
                enabled=True,
                draining=False,
                implementation_version=IMPLEMENTATION_VERSION,
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        accepted_formats = tuple(
            sorted(
                {
                    extension.lstrip(".")
                    for stage in configuration.deployment.event.stages
                    for source in stage.sources
                    for extension in source.allowed_extensions
                }
            )
        )
        capability = repository.register_capability(
            WorkerCapability(
                id=_stable_id(
                    f"stageflow:capability:{worker.id.value}:"
                    f"{transcription.execution_profile_id}:"
                    f"{transcription.execution_profile_version}"
                ),
                worker_id=worker.id,
                operation_kind="transcription",
                operation_schema_version="v1",
                execution_profile_id=transcription.execution_profile_id,
                execution_profile_version=transcription.execution_profile_version,
                locality=ExecutionLocality.LOCAL,
                accepted_asset_formats=accepted_formats,
                supports_word_timing=True,
                supports_speaker_labels=False,
                provider_id=execution.provider_id,
                provider_version=execution.provider_version,
                model_id=transcription.model_id,
                model_version=transcription.model_version,
                runtime_id=execution.execution_tool_id,
                runtime_version=execution.runtime_version,
                configured_eligible=True,
                effective_from=now,
            )
        )
        service = TranscriptionWorker(
            repository=repository,
            execution_port=execution,
        )
        claim = ClaimRequest(
            worker_id=worker.id,
            network_policy=EventNetworkPolicy.LOCAL_ONLY,
            lease_duration=timedelta(minutes=5),
        )
        _safe_write(
            {
                "worker_id": worker.id.value,
                "event_id": event.id.value,
                "provider": execution.provider_id,
                "provider_version": execution.provider_version,
                "model": transcription.model_id,
                "model_version": transcription.model_version,
                "device": transcription.device,
                "compute_type": transcription.compute_type,
                "execution_profile": capability.execution_profile_id,
                "state": "available",
            }
        )

        while True:
            repository.record_presence(
                worker.id,
                ttl=timedelta(seconds=30),
                maximum_concurrency=1,
                health=WorkerHealth.AVAILABLE,
                pressure=WorkerPressure.NORMAL,
            )
            repository.reconcile_expired(limit=100)
            result = service.run_once(claim)
            if result.operation_id is not None:
                _safe_write(
                    {
                        "outcome": result.outcome.value,
                        "operation_id": result.operation_id.value,
                        "attempt_id": (
                            None
                            if result.attempt_id is None
                            else result.attempt_id.value
                        ),
                        "evidence_id": (
                            None
                            if result.evidence_id is None
                            else result.evidence_id.value
                        ),
                    }
                )
            if arguments.once:
                return 0
            if result.operation_id is None:
                time.sleep(arguments.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        sys.stderr.write(f"stageflow_demo_worker_error={type(exc).__name__}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
