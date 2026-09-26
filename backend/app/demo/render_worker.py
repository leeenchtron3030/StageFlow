"""Explicit, default-off, one-lease local render worker."""
import argparse
import base64
import json
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.bootstrap.event_mode_kernel import load_kernel_components_from_environment
from app.contexts.rendering.contracts import FIRST_RENDER_PROFILE, FFmpegIdentity, RenderError
from app.contexts.rendering.service import RenderWorker
from app.contexts.work_execution import (
    ClaimRequest,
    EventNetworkPolicy,
    ExecutionLocality,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPressure,
)
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.infrastructure.rendering.execution import LocalRenderExecution
from app.infrastructure.rendering.ffmpeg import FFmpegAdapter
from app.infrastructure.rendering.storage import OutputStore, PackagingContentResolver
from app.infrastructure.transcription import KernelMediaPathResolver
from app.shared.ids import EntityId
from app.shared.time import SystemClock


def render_capability(
    worker_id: EntityId, identity: FFmpegIdentity, nvenc: bool, observed_at: datetime,
) -> WorkerCapability:
    token = base64.urlsafe_b64encode(identity.version.encode("ascii")).decode("ascii").rstrip("=")
    return WorkerCapability(
        EntityId.new(), worker_id, "render", "v1", FIRST_RENDER_PROFILE.id,
        FIRST_RENDER_PROFILE.version, ExecutionLocality.LOCAL, None, False, False,
        None, None, None, None, "ffmpeg:" + token, identity.sha256, nvenc, observed_at,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stageflow-render-worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1)
    args = parser.parse_args(argv)
    try:
        if not 0.1 <= args.poll_seconds <= 30:
            raise ValueError("poll_interval_out_of_bounds")
        components = load_kernel_components_from_environment()
        if components is None:
            raise ValueError("kernel_configuration_not_supplied")
        config = components.configuration
        local = config.deployment.local_render
        if local is None or not local.enabled:
            raise ValueError("local_render_not_enabled")
        event = components.repository.get_event_by_key(components.event_key)
        if event is None:
            raise ValueError("explicit_event_stage_bootstrap_required")
        clock = SystemClock()
        ffmpeg = FFmpegAdapter(Path(local.ffmpeg_path))
        store = OutputStore(Path(local.output_root))
        execution = LocalRenderExecution(
            ffmpeg, store, PackagingContentResolver(Path(local.packaging_content_root)),
            KernelMediaPathResolver(components.repository, source_roots=config.sources),
            components.repository, clock,
        )
        repository = PostgresRenderRepository(config.postgres_dsn)
        worker_id = EntityId(str(uuid5(NAMESPACE_URL,
            f"stageflow:worker:{config.deployment.deployment_id}:{config.deployment.node_id}:render")))
        now = clock.now()
        repository.register_worker(Worker(
            worker_id, config.deployment.node_id, config.deployment.deployment_id, event.id,
            True, False, "stageflow-render-worker-1", 1, now, now,
        ))
        profile = FIRST_RENDER_PROFILE
        nvenc = ffmpeg.nvenc_available()
        repository.register_render_capability(render_capability(
            worker_id, ffmpeg.identity, nvenc, now,
        ))
        service = RenderWorker(repository, repository, execution, profile)
        request = ClaimRequest(worker_id, EventNetworkPolicy.LOCAL_ONLY,
                               timedelta(minutes=5), "render")
        while True:
            repository.record_presence(worker_id, ttl=timedelta(seconds=30), maximum_concurrency=1,
                                       health=(WorkerHealth.AVAILABLE if nvenc
                                               else WorkerHealth.DEGRADED),
                                       pressure=WorkerPressure.NORMAL)
            repository.reconcile_expired(limit=100)
            result = service.run_once(request) if nvenc else None
            if result is not None:
                sys.stdout.write(json.dumps({"operation_id": result.id.value,
                                             "state": result.status.value}) + "\n")
                sys.stdout.flush()
            if args.once:
                return 0 if nvenc else 1
            if result is None:
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        code = exc.code.value if isinstance(exc, RenderError) else "render_worker_unavailable"
        sys.stderr.write("stageflow_render_worker_error=" + code + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
