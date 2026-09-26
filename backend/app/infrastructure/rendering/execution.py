import json
from collections.abc import Callable
from pathlib import Path

from app.contexts.assembly.contracts import ExternalContent
from app.contexts.production.event_mode_kernel.repository import EventModeKernelRepository
from app.contexts.rendering.contracts import RenderedOutput, RenderError, RenderPlan, RenderReason
from app.contexts.transcription_evidence import TranscriptionExecutionError
from app.contexts.work_execution import (
    OperationClaim,
    RenderOperationInput,
    TranscriptionOperationInput,
)
from app.infrastructure.transcription import KernelMediaPathResolver
from app.shared.ids import EntityId
from app.shared.time import Clock

from .ffmpeg import FFmpegAdapter
from .storage import OutputStore, PackagingContentResolver, StoredContent


class LocalRenderExecution:
    def __init__(
        self, ffmpeg: FFmpegAdapter, store: OutputStore, packaging: PackagingContentResolver,
        media: KernelMediaPathResolver, kernel: EventModeKernelRepository, clock: Clock,
    ) -> None:
        self.ffmpeg, self.store, self.packaging = ffmpeg, store, packaging
        self.media, self.kernel, self.clock = media, kernel, clock

    def execute(
        self, claim: OperationClaim[RenderOperationInput], plan: RenderPlan,
        heartbeat: Callable[[], None],
    ) -> RenderedOutput:
        published: list[StoredContent] = []
        try:
            paths: list[Path] = []
            for item in plan.inputs:
                heartbeat()
                if isinstance(item.reference, ExternalContent):
                    paths.append(self.packaging.resolve(item.reference))
                else:
                    asset = self.kernel.get_asset(item.reference.asset_id)
                    if asset is None:
                        raise RenderError(RenderReason.INPUT_MISSING)
                    # Reuse the established Kernel resolver without changing transcription behavior.
                    paths.append(self.media.resolve(TranscriptionOperationInput(
                        asset.id, asset.manifest_id, "1", "mp4", plan.profile.id,
                        plan.profile.version, None, False, False, False,
                    )))
            with self.store.temporary(".mp4") as video, self.store.temporary(".json") as sidecar:
                encoded = self.ffmpeg.render(paths, video, self.store, plan.profile, heartbeat)
                # Reverify external content after execution: changed bytes never receive identity.
                for item in plan.inputs:
                    if isinstance(item.reference, ExternalContent):
                        self.packaging.resolve(item.reference)
                sidecar.write_text(json.dumps({
                    "schema": "stageflow.render-manifest.v1",
                    "assembly_revision_id": plan.manifest.assembly_revision_id.value,
                    "event_id": plan.manifest.event_id.value,
                    "session_id": plan.manifest.session_id.value,
                    "profile_id": plan.manifest.profile_id,
                    "profile_version": plan.manifest.profile_version,
                    "metadata": [{"field": m.field.value, "values": list(m.values),
                                  "source": m.source, "source_id": m.source_id.value,
                                  "source_revision": m.source_revision}
                                 for m in plan.manifest.metadata],
                }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                heartbeat()
                content = self.store.publish(video)
                published.append(content)
                manifest = self.store.publish(sidecar)
                published.append(manifest)
                return RenderedOutput(
                    EntityId.new(), plan.revision.id, plan.profile.id, plan.profile.version,
                    claim.operation.id, claim.attempt.id, content.key, content.sha256,
                    manifest.key, manifest.sha256, content.byte_size, "video/mp4",
                    encoded.duration_microseconds, encoded.frame_count, self.ffmpeg.identity,
                    self.clock.now(),
                )
        except TranscriptionExecutionError as exc:
            raise RenderError(RenderReason.INPUT_MISSING, retryable=exc.retryable) from None
        except Exception as exc:
            for content in published:
                self.store.discard_unregistered(content)
            if isinstance(exc, OSError):
                raise RenderError(RenderReason.STORE_UNAVAILABLE, retryable=True) from None
            raise

    def discard_unregistered(self, output: RenderedOutput) -> None:
        try:
            self.store.discard_unregistered(StoredContent(
                output.content_key, output.sha256, output.byte_size,
            ))
        finally:
            self.store.discard_unregistered(StoredContent(
                output.manifest_content_key, output.manifest_sha256, 0,
            ))
