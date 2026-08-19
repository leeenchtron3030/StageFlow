from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.bootstrap.event_mode_kernel import (
    KernelComponents,
    load_kernel_components_from_environment,
)
from app.contexts.work_execution import TranscriptionOperationInput
from app.core.config.deployment import RuntimeProfile
from app.infrastructure.devcon import DevconReadError
from app.infrastructure.transcription import FasterWhisperExecutionAdapter
from app.shared.ids import EntityId
from app.shared.time import SystemClock


def _components() -> KernelComponents:
    components = load_kernel_components_from_environment()
    if components is None:
        raise RuntimeError("kernel_configuration_not_supplied")
    if (
        components.configuration.deployment.runtime_profile
        is not RuntimeProfile.DEMO_SINGLE_STAGE
    ):
        raise RuntimeError("demo_single_stage_profile_required")
    return components


def _stable_id(kind: str, deployment_id: str) -> EntityId:
    return EntityId(str(uuid5(NAMESPACE_URL, f"stageflow:{kind}:{deployment_id}")))


def _safe_write(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


class _ProbeResolver:
    def resolve(self, input: TranscriptionOperationInput) -> Path:
        del input
        raise RuntimeError("preflight_resolver_has_no_media")


def _preflight() -> int:
    components = _components()
    deployment = components.configuration.deployment
    source_available = all(
        Path(source.path).exists()
        for stage in deployment.event.stages
        for source in stage.sources
    )
    if not source_available:
        raise RuntimeError("configured_media_source_unavailable")
    if components.devcon_program_sync is None:
        raise RuntimeError("devcon_read_not_configured")
    fetched_count = components.devcon_program_sync.probe()
    if fetched_count == 0:
        raise RuntimeError("configured_devcon_program_empty")
    transcription = deployment.local_transcription
    if transcription is None:
        raise RuntimeError("local_transcription_not_configured")
    gpu = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version",
            "--format=csv,noheader",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if gpu.returncode != 0 or not gpu.stdout.strip():
        raise RuntimeError("nvidia_cuda_gpu_unavailable")
    execution = FasterWhisperExecutionAdapter(
        transcription,
        resolver=_ProbeResolver(),
        clock=SystemClock(),
    )
    _safe_write(
        {
            "command": "preflight",
            "runtime_profile": deployment.runtime_profile.value,
            "database_available": True,
            "media_sources_available": True,
            "devcon_read_available": True,
            "devcon_program_items": fetched_count,
            "transcription_provider": execution.provider_id,
            "transcription_provider_version": execution.provider_version,
            "transcription_model": transcription.model_id,
            "transcription_model_version": transcription.model_version,
            "transcription_device": transcription.device,
            "transcription_compute_type": transcription.compute_type,
            "gpu_available": True,
        }
    )
    return 0


def _bootstrap() -> int:
    components = _components()
    deployment = components.configuration.deployment
    event = components.repository.get_event_by_key(components.event_key)
    if event is None:
        status = components.explicit_bootstrap(
            operation_id=_stable_id("demo-bootstrap", deployment.deployment_id),
            actor_id=_stable_id("demo-operator", deployment.deployment_id),
        )
    else:
        status = components.status()
        if status is None:
            raise RuntimeError("demo_bootstrap_status_unavailable")
    _safe_write(
        {
            "command": "bootstrap",
            "runtime_profile": deployment.runtime_profile.value,
            "event_id": status.event_id.value,
            "event_key": status.event_key,
            "stage_count": len(status.stages),
            "ready": status.ready,
        }
    )
    return 0


def _sync_program() -> int:
    components = _components()
    result = components.sync_devcon_program()
    _safe_write(
        {
            "command": "sync-program",
            "event_id": result.event_id.value,
            "stage_id": result.stage_id.value,
            "expectations_synchronized": len(result.expectations),
            "provider": "devcon",
            "evidence_kind": "external",
        }
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stageflow-demo")
    parser.add_argument(
        "command",
        choices=("preflight", "bootstrap", "sync-program"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "preflight":
            return _preflight()
        if arguments.command == "bootstrap":
            return _bootstrap()
        return _sync_program()
    except (DevconReadError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f"stageflow_demo_error={exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
