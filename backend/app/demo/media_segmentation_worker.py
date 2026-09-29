"""Explicit default-off CPU inspection worker with bounded concurrency."""
import argparse
import json
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.bootstrap.event_mode_kernel import load_kernel_components_from_environment
from app.contexts.production.media_segmentation_evidence.contracts import (
    CURRENT_SEGMENTATION_PROFILE,
    MediaSegmentationError,
)
from app.contexts.production.media_segmentation_evidence.worker import MediaSegmentationWorker
from app.contexts.rendering.contracts import FFmpegIdentity
from app.contexts.transcription_evidence import TranscriptionExecutionError
from app.contexts.work_execution import (
    ClaimRequest,
    EventNetworkPolicy,
    ExecutionLocality,
    MediaSegmentationOperationInput,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPressure,
)
from app.infrastructure.media_segmentation.ffmpeg import FFmpegSegmentationAdapter
from app.infrastructure.postgres.media_segmentation_repository import (
    PostgresMediaSegmentationRepository,
)
from app.infrastructure.transcription import KernelMediaPathResolver
from app.shared.ids import EntityId
from app.shared.time import SystemClock


@dataclass(frozen=True, slots=True)
class SegmentationPathResolver:
    kernel: KernelMediaPathResolver

    def resolve(self, input: MediaSegmentationOperationInput) -> Path:
        try:
            return self.kernel.resolve(input)
        except TranscriptionExecutionError as exc:
            raise MediaSegmentationError("input_missing", retryable=exc.retryable) from None
        except OSError:
            raise MediaSegmentationError("input_missing", retryable=True) from None


def segmentation_capability(worker_id: EntityId, identity: FFmpegIdentity,
                      observed_at: datetime) -> WorkerCapability:
    profile = CURRENT_SEGMENTATION_PROFILE
    return WorkerCapability(
        EntityId.new(), worker_id, "media_segmentation", "v1", profile.id, profile.version,
        ExecutionLocality.LOCAL, None, False, False, None, None, None, None,
        "ffmpeg-cpu:" + identity.version, identity.sha256, True, observed_at,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stageflow-media-segmentation-worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1)
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        if not 0.1 <= args.poll_seconds <= 30 or not 1 <= args.concurrency <= 8:
            raise ValueError("media_segmentation_worker_bounds_invalid")
        components = load_kernel_components_from_environment()
        if components is None:
            raise ValueError("kernel_configuration_not_supplied")
        config = components.configuration
        local = config.deployment.local_media_segmentation
        if local is None or not local.enabled:
            raise ValueError("local_media_segmentation_not_enabled")
        if local.ffmpeg_path is None:
            raise ValueError("local_media_segmentation_path_required")
        event = components.repository.get_event_by_key(components.event_key)
        if event is None:
            raise ValueError("explicit_event_stage_bootstrap_required")
        clock = SystemClock()
        inspector = FFmpegSegmentationAdapter(Path(local.ffmpeg_path), clock)
        repository = PostgresMediaSegmentationRepository(config.postgres_dsn)
        worker_id = EntityId(str(uuid5(NAMESPACE_URL,
            f"stageflow:worker:{config.deployment.deployment_id}:"
            f"{config.deployment.node_id}:media-segmentation")))
        now = clock.now()
        repository.register_worker(Worker(worker_id, config.deployment.node_id,
            config.deployment.deployment_id, event.id, True, False,
            "stageflow-media-segmentation-worker-1", 1, now, now))
        repository.register_capability(segmentation_capability(worker_id, inspector.identity, now))
        service = MediaSegmentationWorker(repository, repository, SegmentationPathResolver(
            KernelMediaPathResolver(components.repository, source_roots=config.sources)),
            inspector, clock, args.concurrency)
        request = ClaimRequest(worker_id, EventNetworkPolicy.LOCAL_ONLY,
                               timedelta(minutes=5), "media_segmentation")
        # Each decode renews its lease and worker presence; submissions stay bounded.
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            while True:
                repository.record_presence(worker_id, ttl=timedelta(minutes=2),
                    maximum_concurrency=args.concurrency, health=WorkerHealth.AVAILABLE,
                    pressure=WorkerPressure.NORMAL)
                repository.reconcile_expired(limit=100)
                futures = [pool.submit(service.run_once, request) for _ in range(args.concurrency)]
                for future in futures:
                    result = future.result()
                    if result is not None:
                        sys.stdout.write(json.dumps({"operation_id": result.id.value,
                                                     "state": result.status.value}) + "\n")
                        sys.stdout.flush()
                if args.once:
                    return 0
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        code = (exc.code if isinstance(exc, MediaSegmentationError)
                else "media_segmentation_worker_unavailable")
        sys.stderr.write("stageflow_media_segmentation_worker_error=" + code + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
