import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest

from app.contexts.rendering.contracts import (
    RENDER_PRESETS,
    FFmpegIdentity,
    RenderActor,
    RenderAdjustments,
    RenderPreset,
    effective_profile,
)
from app.contexts.rendering.service import RenderWorker
from app.infrastructure.media_timing.ffprobe import RenderStreamFacts
from app.infrastructure.rendering import ffmpeg as ffmpeg_module
from app.infrastructure.rendering.execution import LocalRenderExecution
from app.infrastructure.rendering.ffmpeg import EncodingResult, FFmpegAdapter
from app.infrastructure.rendering.storage import OutputStore, StoredContent
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_render_work_execution import NOW
from tests.test_rendering_phase_b import MemoryRendering, plan_for


@pytest.mark.parametrize("preset", RENDER_PRESETS)
@pytest.mark.parametrize("adjusted", [False, True])
def test_effective_ffmpeg_arguments_without_filesystem(
    preset: RenderPreset, adjusted: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = effective_profile(preset, RenderAdjustments(preset.video_min, preset.audio_choices[0])
                                if adjusted else RenderAdjustments())
    adapter = object.__new__(FFmpegAdapter)
    adapter.binary = Path.cwd() / "synthetic-ffmpeg"
    adapter.identity = FFmpegIdentity("synthetic", "a" * 64)
    monkeypatch.setattr(adapter, "_identify", Mock(return_value=adapter.identity))
    monkeypatch.setattr(adapter, "_probe",
                        Mock(return_value=RenderStreamFacts(("h264",), ("aac",))))
    def safe(path: Path) -> Path:
        return path
    monkeypatch.setattr(ffmpeg_module, "safe_path", safe)
    monkeypatch.setattr(Path, "write_text", Mock())
    store = Mock(spec=OutputStore)
    store.temp = Path.cwd() / "synthetic-temp"
    @contextmanager
    def temporary(suffix: str) -> Generator[Path]:
        yield store.temp / ("temporary" + suffix)
    store.temporary.side_effect = temporary
    encode = Mock(return_value=EncodingResult(60, 2_000_000))
    monkeypatch.setattr(adapter, "_encode", encode)
    adapter.render([Path.cwd() / "synthetic.mp4"], store.temp / "out.mp4", store, profile, Mock())
    video, audio = [call.args[0] for call in encode.call_args_list]
    assert video[video.index("-vf") + 1] == (
        f"scale_cuda={profile.width}:{profile.height}:format=nv12")
    assert video[video.index("-b:v") + 1] == str(profile.bit_rate)
    assert audio[audio.index("-b:a") + 1] == str(profile.audio_bit_rate)
    assert video[video.index("-c:v") + 1] == "h264_nvenc"
    assert audio[audio.index("-c:v") + 1] == "copy"


def test_worker_rechecks_bounds_before_execution() -> None:
    memory = MemoryRendering()
    profile = RENDER_PRESETS[0].profile
    operation = memory.service().request_render(memory.source.revision.id, profile,
        RenderActor(EntityId.new()), EntityId.new())
    memory.work.operations[operation.id] = replace(operation,
        input=replace(operation.input, video_bit_rate=1))
    execution = Mock()
    result = RenderWorker(cast(Any, memory.work), memory, execution, profile).run_once(
        memory.claim_request())
    assert result is not None and result.last_reason_code == "render_profile_unsupported"
    assert result.status.value == "terminal_failed"
    execution.execute.assert_not_called()


def test_sidecar_effective_bitrates_and_output_frozen_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = MemoryRendering()
    profile = RENDER_PRESETS[0].profile
    memory.service().request_render(memory.source.revision.id, profile,
                                    RenderActor(EntityId.new()), EntityId.new())
    claim = memory.work.claim_next(memory.claim_request())
    assert claim is not None
    profile = effective_profile(RENDER_PRESETS[1], RenderAdjustments(20_000_000, 320_000))
    claim = replace(claim, operation=replace(claim.operation, input=replace(claim.operation.input,
        execution_profile_id=profile.id, execution_profile_version=profile.version,
        video_bit_rate=20_000_000, audio_bit_rate=320_000, event_render_setting_version=2)))
    plan = plan_for(memory.source)
    plan = replace(plan, profile=profile, inputs=(plan.inputs[0],),
                   manifest=replace(plan.manifest, profile_id=profile.id,
                                    profile_version=profile.version))
    ffmpeg = Mock()
    ffmpeg.identity = FFmpegIdentity("synthetic", "a" * 64)
    ffmpeg.render.return_value = EncodingResult(60, 2_000_000)
    store = Mock()
    @contextmanager
    def temporary(suffix: str) -> Generator[Path]:
        yield Path("synthetic" + suffix)
    store.temporary.side_effect = temporary
    store.publish.side_effect = [StoredContent("video", "a" * 64, 100),
                                 StoredContent("manifest", "b" * 64, 100)]
    documents: list[dict[str, Any]] = []
    def write(path: Path, data: str, **kwargs: Any) -> int:
        documents.append(json.loads(data))
        return len(data)
    monkeypatch.setattr(Path, "write_text", write)
    execution = LocalRenderExecution(ffmpeg, store, Mock(), Mock(), Mock(), FixedClock(NOW))
    output = execution.execute(cast(Any, claim), plan, Mock())
    assert (documents[0]["video_bit_rate"], documents[0]["audio_bit_rate"]) == (20_000_000, 320_000)
    assert (documents[0]["profile_id"], documents[0]["profile_version"]) == (profile.id, "1")
    assert (output.video_bit_rate, output.audio_bit_rate,
            output.event_render_setting_version) == (20_000_000, 320_000, 2)
