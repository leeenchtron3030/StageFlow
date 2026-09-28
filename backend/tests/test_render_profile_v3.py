import json
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.api.v1 import rendering as rendering_api
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.media_timing_evidence.inspection import MediaTimingError
from app.contexts.rendering.contracts import (
    CURRENT_RENDER_PROFILE,
    RENDER_PROFILE_V1,
    RENDER_PROFILE_V2,
    FFmpegIdentity,
    RenderError,
    RenderReason,
    require_profile,
)
from app.core.config.deployment import LocalRenderConfiguration
from app.demo import render_worker
from app.infrastructure.media_timing.ffprobe import (
    RENDER_INPUT_FORMATS,
    FFprobeAdapter,
    RenderStreamFacts,
)
from app.infrastructure.rendering import ffmpeg as ffmpeg_module
from app.infrastructure.rendering.ffmpeg import FFmpegAdapter
from app.infrastructure.rendering.storage import OutputStore
from app.shared.time import FixedClock
from tests.test_media_timing_inspection import fake_ffprobe as fake_ffprobe
from tests.test_render_work_execution import NOW
from tests.test_rendering_phase_b import fake_ffmpeg as fake_ffmpeg
from tests.test_rendering_phase_b import synthetic_probe


def test_v3_audio_fields_exact_immutable_and_history_has_no_audio() -> None:
    profile = CURRENT_RENDER_PROFILE
    assert profile.version == "3"
    assert (profile.audio_codec, profile.audio_sample_rate, profile.audio_channels,
            profile.audio_bit_rate) == ("aac", 48000, 2, 192000)
    for name in ("audio_sample_rate", "audio_channels", "audio_bit_rate"):
        assert type(getattr(profile, name)) is int
        with pytest.raises(FrozenInstanceError):
            setattr(profile, name, 1)
        for invalid in (True, 48000.0, "48000", 0, -1):
            with pytest.raises(RenderError, match="render_profile_unsupported"):
                replace(profile, **{name: invalid})
        with pytest.raises(RenderError, match="render_profile_unsupported"):
            require_profile(replace(profile, **{name: None}))
    assert type(profile.audio_codec) is str
    with pytest.raises(FrozenInstanceError):
        profile.__setattr__("audio_codec", None)
    for old in (RENDER_PROFILE_V1, RENDER_PROFILE_V2):
        assert (old.audio_codec, old.audio_sample_rate, old.audio_channels,
                old.audio_bit_rate) == (None, None, None, None)
        with pytest.raises(RenderError, match="render_profile_unsupported"):
            require_profile(old)
    assert replace(RENDER_PROFILE_V2, version="3", audio_codec="aac", audio_sample_rate=48000,
                   audio_channels=2, audio_bit_rate=192000) == profile


def test_optional_probe_config_worker_refusal_and_api_unaffected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    external = Path(Path.cwd().anchor) / "synthetic-render-configuration"
    values: dict[str, Any] = dict(enabled=True, ffmpeg_path=str(external / "ffmpeg"),
                  output_root=str(external / "output"),
                  packaging_content_root=str(external / "packaging"))
    local = LocalRenderConfiguration(**values)
    assert local.ffprobe_path is None
    configured = LocalRenderConfiguration(**values, ffprobe_path=str(external / "ffprobe"))
    assert configured.ffprobe_path == str(external / "ffprobe")
    assert str(external) not in repr(configured)
    for path in ("relative", str(Path(__file__)), str(external / ".." / "ffprobe"),
                 str(external / "ffprobe.cmd"), str(external / "ffprobe.bat"),
                 str(external / "ffprobe") + "\n", "//host/share/ffprobe"):
        with pytest.raises(ValueError):
            LocalRenderConfiguration(**values, ffprobe_path=path)
    components = Mock(spec=KernelComponents)
    components.configuration = SimpleNamespace(
        deployment=SimpleNamespace(local_render=local, deployment_id="synthetic"),
        postgres_dsn="synthetic-unused")
    components.kernel = SimpleNamespace(clock=FixedClock(NOW))
    monkeypatch.setattr(render_worker, "load_kernel_components_from_environment",
                        Mock(return_value=components))
    assert render_worker.main(["--once"]) == 1
    assert capsys.readouterr().err == (
        "stageflow_render_worker_error=local_render_ffprobe_path_required\n")
    components.repository.get_event_by_key.assert_not_called()
    app = FastAPI()
    app.state.kernel = components
    request = Request({"type": "http", "app": app})
    assert vars(rendering_api)["_service"](request) is not None


@pytest.mark.parametrize("audio", [False, True])
def test_render_probe_normalizes_only_stream_facts(
    fake_ffprobe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, audio: bool,
) -> None:
    # Reuse the no-shell native subprocess wrapper, supplying the render-specific fake.
    fake_ffprobe.write_text(
        'import json, sys\n'
        'if "-version" in sys.argv:\n'
        ' print("ffprobe version 8.0.1 synthetic"); print("configuration: --disable-gpl")\n'
        'else:\n'
        ' assert sys.argv[1:-1] == ["-protocol_whitelist", "file", "-v", "error", '
        '"-print_format", "json", "-format_whitelist", ' + repr(RENDER_INPUT_FORMATS) +
        ', "-show_streams"]\n'
        ' print(json.dumps({"streams": [{"codec_type": "video", "codec_name": "h264"}]' +
        (' + [{"codec_type": "audio", "codec_name": "aac", "sample_rate": "44100", '
         '"channels": 1}]' if audio else '') + '}))\n', encoding="utf-8")
    probe = FFprobeAdapter(fake_ffprobe, FixedClock(NOW))
    media = tmp_path / "synthetic.mp4"
    media.write_bytes(b"synthetic")
    beat = Mock()
    result = probe.render_streams(media, beat)
    assert result.video_codecs == ("h264",) and result.has_audio is audio
    beat.assert_called_once_with()
    monkeypatch.setattr(probe, "_run", Mock(return_value=b'{"streams": [null]}'))
    monkeypatch.setattr(probe, "_identify", Mock(return_value=probe.identity))
    with pytest.raises(MediaTimingError, match="media_timing_output_invalid"):
        probe.render_streams(media, beat)


@pytest.mark.parametrize("facts", [
    RenderStreamFacts(("h264",), ()),
    RenderStreamFacts(("h264",), ("aac", "aac")),
    RenderStreamFacts(("h264", "h264"), ("aac",)),
    RenderStreamFacts(("hevc",), ("aac",)),
    RenderStreamFacts(("h264",), ("mp3",)),
])
def test_output_stream_mismatch_never_publishes(
    fake_ffmpeg: Path, tmp_path: Path, facts: RenderStreamFacts,
) -> None:
    probe = cast(Any, synthetic_probe())
    probe.render_streams.side_effect = [RenderStreamFacts(("h264",), ("aac",)), facts]
    adapter = FFmpegAdapter(fake_ffmpeg, probe)
    store = OutputStore(tmp_path)
    source = tmp_path / "synthetic.mp4"
    source.write_bytes(b"synthetic")
    with store.temporary(".mp4") as output:
        with pytest.raises(RenderError, match="render_output_invalid"):
            adapter.render([source], output, store, CURRENT_RENDER_PROFILE, Mock())
    assert list(store.temp.iterdir()) == []
    assert set(tmp_path.iterdir()) == {source, fake_ffmpeg, store.temp}


@pytest.mark.parametrize("code,expected", [
    ("input_missing", RenderReason.INPUT_MISSING),
    ("media_timing_output_invalid", RenderReason.INTERNAL),
    ("media_timing_tool_refused", RenderReason.INTERNAL),
    ("media_timing_timeout", RenderReason.INTERNAL),
])
def test_probe_failure_is_typed_and_never_becomes_silence(
    code: str, expected: RenderReason,
) -> None:
    adapter = object.__new__(FFmpegAdapter)
    probe = Mock(spec=FFprobeAdapter)
    adapter.ffprobe = probe
    probe.render_streams.side_effect = MediaTimingError(code, retryable=True)
    with pytest.raises(RenderError) as failure:
        cast(Any, adapter)._probe(Path("synthetic"), Mock())
    assert failure.value.code == expected and failure.value.retryable
    with pytest.raises(RenderError, match="render_output_invalid"):
        cast(Any, adapter)._probe(Path("synthetic"), Mock(), output=True)


@pytest.mark.parametrize("empty_inputs", [True, False], ids=["empty", "no_video"])
def test_render_refuses_missing_video_inputs(
    monkeypatch: pytest.MonkeyPatch, empty_inputs: bool,
) -> None:
    adapter = object.__new__(FFmpegAdapter)
    adapter.identity = FFmpegIdentity("synthetic", "a" * 64)
    monkeypatch.setattr(adapter, "_identify", Mock(return_value=adapter.identity))
    probe = Mock(spec=FFprobeAdapter)
    probe.render_streams.return_value = RenderStreamFacts((), ("aac",))
    adapter.ffprobe = probe
    encode = Mock()
    monkeypatch.setattr(adapter, "_encode", encode)
    def safe(path: Path) -> Path:
        return path

    monkeypatch.setattr(ffmpeg_module, "safe_path", safe)
    store = Mock(spec=OutputStore)
    store.temp = Path.cwd() / "synthetic-temp"
    inputs = [] if empty_inputs else [Path.cwd() / "synthetic-audio-only.mp4"]
    heartbeat = Mock()

    with pytest.raises(RenderError) as failure:
        adapter.render(inputs, store.temp / "out.mp4", store,
                       CURRENT_RENDER_PROFILE, heartbeat)

    assert failure.value.code == RenderReason.INPUT_MISSING
    if empty_inputs:
        probe.render_streams.assert_not_called()
    else:
        probe.render_streams.assert_called_once_with(inputs[0], heartbeat)
    encode.assert_not_called()
    store.temporary.assert_not_called()


def test_render_probe_renews_heartbeat_after_poll_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = object.__new__(FFprobeAdapter)
    probe.binary = Path.cwd() / "synthetic-ffprobe"
    probe.timeout, probe.output_limit = 30, 1_048_576
    probe.identity = cast(Any, object())
    monkeypatch.setattr(probe, "_identify", Mock(return_value=probe.identity))
    monkeypatch.setattr(Path, "is_file", Mock(return_value=True))
    process = Mock()
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.stdout = BytesIO(b'{"streams": [{"codec_type": "video", "codec_name": "h264"}]}')
    process.returncode = 0
    # The fake ffprobe outlasts the first five-second poll, then completes.
    process.wait.side_effect = [subprocess.TimeoutExpired("synthetic-ffprobe", 5), 0]
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=process))
    heartbeat = Mock()

    facts = probe.render_streams(Path.cwd() / "synthetic.mp4", heartbeat)

    assert facts == RenderStreamFacts(("h264",), ())
    assert process.wait.call_count == 2
    assert process.wait.call_args_list[0].kwargs["timeout"] == 5
    assert heartbeat.call_count > 1
    process.kill.assert_not_called()


@pytest.mark.parametrize("mode", ["success", "fail", "stage2_fail"])
def test_two_stages_mixed_audio_cleanup_and_stage2_measurements(
    fake_ffmpeg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    monkeypatch.setenv("STAGEFLOW_FAKE_RENDER", mode)
    probe = cast(Any, synthetic_probe())
    probe.render_streams.side_effect = [
        RenderStreamFacts(("h264",), ("aac", "mp3")),
        RenderStreamFacts(("h264",), ()),
        RenderStreamFacts(("h264",), ("aac",)),
    ]
    adapter = FFmpegAdapter(fake_ffmpeg, probe)
    original = cast(Any, adapter)._encode
    commands: list[list[str]] = []
    beats = Mock()

    def encode(command: list[str], heartbeat: Any) -> Any:
        commands.append(command)
        result = original(command, heartbeat)
        return replace(result, frame_count=120, duration_microseconds=4_000_000) if (
            command[command.index("-c:v") + 1] == "copy") else result

    monkeypatch.setattr(adapter, "_encode", encode)
    store = OutputStore(tmp_path)
    sources = [tmp_path / "audio.mp4", tmp_path / "silent.mp4"]
    for source in sources:
        source.write_bytes(b"synthetic")
    with store.temporary(".mp4") as output:
        if mode == "success":
            result = adapter.render(sources, output, store, CURRENT_RENDER_PROFILE, beats)
            assert result.frame_count == 120 and result.duration_microseconds == 4_000_000
            assert len(commands) == 3 and beats.call_count == 6
            assert "0:a:0" in commands[0] and "lavfi" not in commands[0]
            assert "1:a:0" in commands[1] and "anullsrc=r=48000:cl=stereo" in commands[1]
            assert sum("h264_nvenc" in command for command in commands) == 2
            assert sum("aac" in command for command in commands) == 1
            assert all("Frozen title" not in str(command) for command in commands)
        else:
            with pytest.raises(RenderError, match="ffmpeg_exit_nonzero"):
                adapter.render(sources, output, store, CURRENT_RENDER_PROFILE, beats)
            assert len(commands) == (1 if mode == "fail" else 3)
    assert list(store.temp.iterdir()) == []


@pytest.mark.parametrize("stage", [1, 2, 3])
def test_cancellation_cleans_all_intermediates(
    fake_ffmpeg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: int,
) -> None:
    adapter = FFmpegAdapter(fake_ffmpeg, synthetic_probe())
    original = cast(Any, adapter)._encode
    calls = 0

    def encode(command: list[str], heartbeat: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == stage:
            Path(command[-1]).write_bytes(b"partial")
            raise KeyboardInterrupt
        return original(command, heartbeat)

    monkeypatch.setattr(adapter, "_encode", encode)
    store = OutputStore(tmp_path)
    source = tmp_path / "synthetic.mp4"
    source.write_bytes(b"synthetic")
    with store.temporary(".mp4") as output:
        with pytest.raises(KeyboardInterrupt):
            adapter.render([source, source], output, store, CURRENT_RENDER_PROFILE, Mock())
    assert list(store.temp.iterdir()) == []


@pytest.mark.parametrize("failure_stage", [None, 1, 2, 3])
@pytest.mark.parametrize("failure_kind", ["exit", "cancel", "cuda", "nvenc"])
def test_pipeline_process_heartbeats_and_cleanup_without_filesystem(
    monkeypatch: pytest.MonkeyPatch, failure_stage: int | None, failure_kind: str,
) -> None:
    adapter = object.__new__(FFmpegAdapter)
    adapter.binary = Path.cwd() / "synthetic-ffmpeg"
    adapter.identity = FFmpegIdentity("synthetic", "a" * 64)
    monkeypatch.setattr(adapter, "_identify", Mock(return_value=adapter.identity))
    probe = Mock(spec=FFprobeAdapter)
    probe.render_streams.side_effect = [
        RenderStreamFacts(("h264",), ("aac",)),
        RenderStreamFacts(("h264",), ()),
        RenderStreamFacts(("h264",), ("aac",)),
    ]
    adapter.ffprobe = probe
    store = Mock(spec=OutputStore)
    store.temp = Path.cwd() / "synthetic-temp"
    active: set[Path] = set()
    allocated: list[Path] = []

    @contextmanager
    def temporary(suffix: str) -> Generator[Path]:
        path = store.temp / (str(len(allocated)) + suffix)
        active.add(path)
        allocated.append(path)
        try:
            yield path
        finally:
            active.remove(path)

    store.temporary.side_effect = temporary
    def safe(path: Path) -> Path:
        return path

    monkeypatch.setattr(ffmpeg_module, "safe_path", safe)
    written: list[str] = []
    def write(path: Path, text: str, **kwargs: object) -> int:
        written.append(text)
        return len(text)

    monkeypatch.setattr(Path, "write_text", write)
    commands: list[list[str]] = []
    processes: list[Mock] = []
    current_stage = 0

    def launch(command: list[str], **kwargs: Any) -> Mock:
        nonlocal current_stage
        current_stage += 1
        commands.append(command)
        assert kwargs["shell"] is False
        assert len(active) == (current_stage if current_stage < 3 else 3)
        process = Mock()
        process.__enter__ = Mock(return_value=process)
        process.__exit__ = Mock(return_value=False)
        fails = current_stage == failure_stage
        process.returncode = 1 if fails and failure_kind in {"exit", "nvenc"} else 0
        stderr = ("Failed setup for format cuda" if fails and failure_kind == "cuda" else
                  "OpenEncodeSessionEx failed" if fails and failure_kind == "nvenc" else "")
        # Each stage must renew its lease while waiting, even without progress output.
        process.communicate.side_effect = [
            subprocess.TimeoutExpired("synthetic", 5),
            (f"frame={current_stage * 60}\nout_time_us={current_stage * 2000000}\n", stderr),
        ]
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", launch)
    beats: list[int] = []

    def heartbeat() -> None:
        beats.append(current_stage)
        if failure_kind == "cancel" and current_stage == failure_stage:
            raise KeyboardInterrupt

    source = Path.cwd() / "synthetic-input"
    sources = [source, source.with_name("synthetic-input-second")]
    if failure_stage is None:
        result = adapter.render(sources, store.temp / "out.mp4", store,
                                CURRENT_RENDER_PROFILE, heartbeat)
        assert (result.frame_count, result.duration_microseconds) == (180, 6_000_000)
        assert len(commands) == 3 and len(beats) == 9
        assert commands[0][commands[0].index("-c:v") + 1] == "h264_nvenc"
        assert "0:a:0" in commands[0] and "lavfi" not in commands[0]
        assert "1:a:0" in commands[1] and "anullsrc=r=48000:cl=stereo" in commands[1]
        assert commands[2][commands[2].index("-c:v") + 1] == "copy"
        assert commands[2][commands[2].index("-c:a") + 1] == "aac"
        assert len(written) == 1 and "synthetic-input" not in written[0]
        assert [command[command.index("-i") + 1] for command in commands[:2]] == [
            str(path) for path in sources
        ]
        assert [Path(command[-1]).name for command in commands[:2]] == ["0.mov", "1.mov"]
        assert [line for line in written[0].splitlines() if line.startswith("file ")] == [
            f"file '{(store.temp / name).as_posix()}'" for name in ("0.mov", "1.mov")
        ]
        assert commands[2][commands[2].index("-i") + 1] == str(allocated[2])
        assert probe.render_streams.call_count == 3
    else:
        error = KeyboardInterrupt if failure_kind == "cancel" else RenderError
        with pytest.raises(error) as failure:
            adapter.render(sources, store.temp / "out.mp4", store,
                           CURRENT_RENDER_PROFILE, heartbeat)
        assert len(commands) == failure_stage
        if isinstance(failure.value, RenderError):
            assert failure.value.code == {
                "exit": RenderReason.EXIT_NONZERO, "cuda": RenderReason.CUDA_FALLBACK,
                "nvenc": RenderReason.NVENC_UNAVAILABLE,
            }[failure_kind]
        if failure_kind == "cancel":
            processes[-1].kill.assert_called_once_with()
            assert processes[-1].communicate.call_count == 2
    assert active == set()


@pytest.mark.parametrize("value", [8_000_000.0, True, "8000000"])
def test_equal_or_caller_text_video_settings_never_reach_process(value: object) -> None:
    with pytest.raises(RenderError, match="render_profile_unsupported"):
        require_profile(replace(CURRENT_RENDER_PROFILE, bit_rate=cast(int, value)))


@pytest.mark.parametrize("streams,expected", [
    ([{"codec_type": "video", "codec_name": "h264"}], False),
    ([{"codec_type": "video", "codec_name": "h264"},
      {"codec_type": "audio", "codec_name": "pcm_s16le", "sample_rate": "44100",
       "channels": 1}], True),
    ([{"codec_type": "video", "codec_name": "h264"},
      {"codec_type": "audio", "codec_name": "aac", "sample_rate": "96000",
       "channels": 6}], True),
    (None, None), ([], None), ([None], None),
    ([{"codec_type": "audio"}], None),
    ([{"codec_type": "audio", "codec_name": "/private/path"}], None),
])
def test_probe_stream_parsing_without_filesystem(
    monkeypatch: pytest.MonkeyPatch, streams: object, expected: bool | None,
) -> None:
    probe = object.__new__(FFprobeAdapter)
    probe.identity = cast(Any, object())
    monkeypatch.setattr(probe, "_identify", Mock(return_value=probe.identity))
    run = Mock(return_value=json.dumps({"streams": streams}).encode())
    monkeypatch.setattr(probe, "_run", run)
    monkeypatch.setattr(Path, "is_file", Mock(return_value=True))
    path = Path.cwd() / "synthetic"
    beat = Mock()
    if expected is None:
        with pytest.raises(MediaTimingError, match="media_timing_output_invalid"):
            probe.render_streams(path, beat)
    else:
        facts = probe.render_streams(path, beat)
        assert facts.has_audio is expected and facts.video_codecs == ("h264",)
    beat.assert_called_once_with()
    assert run.call_args.args[0] == [
        "-protocol_whitelist", "file", "-v", "error", "-print_format", "json",
        "-format_whitelist", RENDER_INPUT_FORMATS, "-show_streams", str(path),
    ]
