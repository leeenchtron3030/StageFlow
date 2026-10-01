"""Synthetic words and injected effects only; no media, models, GPU or executables."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import struct
import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/validation/transcription_engine_spike.py"
spec = importlib.util.spec_from_file_location("validation_transcription_engine_spike", SCRIPT)
assert spec is not None and spec.loader is not None
spike: Any = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = spike
spec.loader.exec_module(spike)


def constant(value: Any) -> Callable[..., Any]:
    def effect(*_args: Any, **_kwargs: Any) -> Any:
        return value
    return effect


def settings(**changes: Any) -> Any:
    return replace(spike.Settings(
        (Path("private-block.mp4"),), Path("private-model"), "cuda", "float16",
        Path("private-ffmpeg.exe"), Path("private-ffprobe.exe"),
    ), **changes)


def words(text: str, shift: float = 0) -> tuple[Any, ...]:
    return tuple(spike.Word(token, i + shift, i + shift + .5)
                 for i, token in enumerate(text.split()))


class FakeLoad:
    def __init__(self) -> None:
        self.running = True
        self.stopped = False

    def alive(self) -> bool:
        return self.running

    def stop(self) -> None:
        self.stopped = True
        self.running = False


class FakeEffects:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.loads: list[FakeLoad] = []
        self.unavailable = False
        self.dies = False
        self.fail_engine = ""
        self.fail_probe = False

    def warm_cache(self, block: Path) -> None:
        pass

    def warm_up(self, engine: str) -> None:
        pass

    def duration(self, block: Path) -> float:
        if self.fail_probe:
            raise RuntimeError("private-path secret timestamp")
        return 60

    def start_load(self, block: Path) -> FakeLoad:
        if self.unavailable:
            raise RuntimeError("private-driver-diagnostic")
        load = FakeLoad()
        self.loads.append(load)
        return load

    def measure(self, engine: str, block: Path) -> Any:
        self.calls.append(engine)
        if self.dies and self.loads:
            self.loads[-1].running = False
        if engine == self.fail_engine:
            print("private-stdout", file=sys.stdout)
            print("private-stderr", file=sys.stderr)
            raise RuntimeError("private-path transcript phrase title timestamp config")
        return spike.Measurement(words("Welcome to the stage private-phrase", .5), 1, 2, 3)


def invoke(
    effects: FakeEffects, config: Any = None, extra: list[str] | None = None,
) -> tuple[int, Any, str]:
    output, tables = io.StringIO(), io.StringIO()
    code = spike.main(["--blocks", "private-folder", *(extra or [])], output=output,
                      table_output=tables, loader=constant(config or settings()),
                      effects_factory=constant(effects))
    return code, json.loads(output.getvalue()), tables.getvalue()


def test_options_defaults_and_explicit_values() -> None:
    args = spike.parser().parse_args(["--blocks", "private-folder"])
    assert (args.profile, args.language, args.max_blocks, args.device) == (
        "conference", "en", 6, None)
    args = spike.parser().parse_args([
        "--blocks", "private-folder", "--device", "cpu", "--language", "en", "--max-blocks", "2",
        "--whisper-cpp-binary", "private-binary", "--whisper-cpp-model", "private-model",
        "--render-load", "--markdown",
    ])
    assert args.device == "cpu" and args.max_blocks == 2 and args.render_load and args.markdown
    assert args.whisper_cpp_binary == "private-binary"


@pytest.mark.parametrize("timeout", [60, 300, 3600, 14400])
def test_engine_timeout_option_reaches_settings(
    monkeypatch: pytest.MonkeyPatch, timeout: int,
) -> None:
    outside, config = fake_filesystem(monkeypatch)
    args = spike.parser().parse_args([
        "--blocks", str(outside), "--engine-timeout-seconds", str(timeout)])
    loaded = spike.load_settings(args, {"STAGEFLOW_KERNEL_CONFIG_PATH": str(config)})
    assert loaded.engine_timeout_seconds == timeout
    assert spike.parser().parse_args(["--blocks", "private"]).engine_timeout_seconds == 300
    assert settings().engine_timeout_seconds == 300


@pytest.mark.parametrize("timeout", ["59", "14401", "bad", "nan", "60.5"])
def test_invalid_engine_timeout_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, timeout: str,
) -> None:
    outside, config = fake_filesystem(monkeypatch)
    monkeypatch.setenv("STAGEFLOW_KERNEL_CONFIG_PATH", str(config))
    output = io.StringIO()
    assert spike.main(["--blocks", str(outside), "--engine-timeout-seconds", timeout],
                      output=output) == 1
    assert json.loads(output.getvalue()) == {"error_count": 1}


@pytest.mark.parametrize("argv", [[], ["--blocks", "x", "--device", "private-device"],
                                   ["--blocks", "x", "--language", "de"],
                                   ["--blocks", "x", "--profile", "private-profile"],
                                   ["--blocks", "x", "--max-blocks", "bad"], ["--unknown"]])
def test_invalid_options_are_sanitized(argv: list[str]) -> None:
    output = io.StringIO()
    assert spike.main(argv, output=output) == 1
    assert json.loads(output.getvalue()) == {"error_count": 1}


def fake_filesystem(monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    outside: Path = spike.REPOSITORY.parent / "synthetic-external"

    def resolve(path: Path, **_kwargs: Any) -> Path:
        return path

    def entries(path: Path) -> Iterator[Path]:
        return iter([path / "02.mp4", path / "01.wav"])

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "is_dir", constant(True))
    monkeypatch.setattr(Path, "is_file", constant(True))
    monkeypatch.setattr(Path, "is_symlink", constant(False))
    monkeypatch.setattr(Path, "is_junction", constant(False))
    monkeypatch.setattr(Path, "iterdir", entries)
    model, binary = outside / "model", outside / "tool.exe"
    config = (f'[local_transcription]\nmodel_path = {json.dumps(str(model))}\n'
              'device = "cuda"\ncompute_type = "float16"\n'
              f'[local_media_segmentation]\nffmpeg_path = {json.dumps(str(binary))}\n'
              f'[local_media_timing]\nffprobe_path = {json.dumps(str(binary))}\n').encode()
    monkeypatch.setattr(Path, "open", constant(io.BytesIO(config)))
    return outside, outside / "config.toml"


def test_read_only_config_sorted_blocks_limit_and_device_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside, config = fake_filesystem(monkeypatch)
    args = spike.parser().parse_args([
        "--blocks", str(outside), "--max-blocks", "1", "--device", "cpu"])
    loaded = spike.load_settings(args, {"STAGEFLOW_KERNEL_CONFIG_PATH": str(config)})
    assert loaded.blocks == (outside / "01.wav",)
    assert loaded.device == "cpu" and loaded.compute_type == "float16"
    assert loaded.model == outside / "model" and loaded.ffmpeg == outside / "tool.exe"


@pytest.mark.parametrize("problem", ["inside", "missing", "config_missing", "bad_device",
                                     "no_binary",
                                     "cpp_pair", "empty", "zero", "too_many", "symlink", "junction",
                                     "resolved_inside", "subdirectory", "batch", "tokenizer"])
def test_input_refusals(monkeypatch: pytest.MonkeyPatch, problem: str) -> None:
    outside, config = fake_filesystem(monkeypatch)
    args = spike.parser().parse_args(["--blocks", str(outside)])

    def file_exists(path: Path) -> bool:
        return (path.suffix != ".exe" if problem == "no_binary" else
                path.name != "tokenizer.json" if problem == "tokenizer" else path.suffix != ".wav")

    if problem == "inside":
        args.blocks = str(spike.REPOSITORY)
    elif problem == "missing":
        monkeypatch.setattr(Path, "is_dir", constant(False))
    elif problem == "config_missing":
        config = Path("")
    elif problem == "bad_device":
        args.device = "private-invalid"
    elif problem in {"no_binary", "tokenizer"}:
        monkeypatch.setattr(Path, "is_file", file_exists)
    elif problem == "cpp_pair":
        args.whisper_cpp_binary = "private-binary"
    elif problem == "empty":
        monkeypatch.setattr(Path, "iterdir", constant(iter([])))
    elif problem == "zero":
        args.max_blocks = 0
    elif problem == "too_many":
        args.max_blocks = 1001
    elif problem in {"symlink", "junction"}:
        monkeypatch.setattr(Path, "is_" + problem, constant(True))
    elif problem == "resolved_inside":
        monkeypatch.setattr(Path, "resolve", constant(spike.REPOSITORY))
    elif problem == "subdirectory":
        monkeypatch.setattr(Path, "is_file", file_exists)
    elif problem == "batch":
        args.whisper_cpp_binary, args.whisper_cpp_model = str(outside / "x.cmd"), str(outside / "m")
    with pytest.raises((ValueError, OSError)):
        spike.load_settings(args, {"STAGEFLOW_KERNEL_CONFIG_PATH": str(config)})


@pytest.mark.parametrize("raw", ["", "relative/path", "https://example.invalid/media",
                                "//host/share",
                                "\\\\host\\share", "bad\npath"])
def test_nonlocal_paths_refused_before_effects(raw: str) -> None:
    with pytest.raises(spike.Refusal):
        spike.local_path(raw)


def test_pcm_command_and_little_endian_conversion() -> None:
    command = spike.decode_command(Path("explicit.exe"), Path("private block.mp4"))
    assert command == ["explicit.exe", "-nostdin", "-hide_banner", "-loglevel", "error",
                       "-protocol_whitelist", "file,pipe", "-i", "private block.mp4", "-map",
                       "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]

    class FakeArray:
        def copy(self) -> list[float]:
            return [-1, 0, .5]

    def frombuffer(data: bytes, *, dtype: str) -> FakeArray:
        assert dtype == "<f4"
        assert struct.unpack("<3f", data) == (-1, 0, .5)
        return FakeArray()

    converted = spike.pcm_array(struct.pack("<3f", -1, 0, .5),
                                SimpleNamespace(frombuffer=frombuffer))
    assert converted == [-1, 0, .5]
    for invalid in (b"", b"123"):
        with pytest.raises(ValueError):
            spike.pcm_array(invalid)


def test_word_alignment_insertions_deletions_and_shifted_edges() -> None:
    baseline = words("One, two three four")
    candidate = (spike.Word("ONE", .2, .8), spike.Word("inserted", .8, .9),
                 spike.Word("three", 2.4, 3), spike.Word("four!", 3.6, 4.2))
    result = spike.word_agreement(baseline, candidate)
    assert result["matched_word_count"] == 3 and result["matched_word_fraction"] == .75
    assert result["start_delta_seconds"] == cast(Any, pytest).approx({"median": .4, "p95": .6})
    assert result["end_delta_seconds"] == cast(Any, pytest).approx({"median": .5, "p95": .7})
    assert spike.word_agreement((), candidate)["matched_word_fraction"] is None
    assert spike.word_agreement(baseline, ())["matched_word_fraction"] == 0


def test_repeated_words_disable_sequence_matcher_autojunk() -> None:
    result = spike.word_agreement(words("one " * 250), words("one " * 250, 1))
    assert result["matched_word_count"] == 250
    assert result["start_delta_seconds"] == {"median": 1, "p95": 1}


def test_catalog_cues_literal_normalized_nonoverlap_and_segment_boundary() -> None:
    phrases = spike.profile_phrases("conference")
    assert len(phrases) == len(set(phrases)) and ("welcome", "to", "the", "stage") in phrases
    custom = (("hello", "world"), ("one", "one"))
    hand_built = (*words("HELLO, World! one one one"),
                  spike.Word("hello", 6, 7, 1), spike.Word("world", 8, 9, 2))
    assert spike.cue_hits(hand_built, custom) == [(0, 0), (1, 2)]
    result = spike.cue_agreement([(0, 0), (0, 4), (1, 8)], [(0, 2), (0, 6.1), (2, 8)])
    assert result["cue_hit_count"] == 3 and result["matched_cue_hit_count"] == 1
    assert result["cue_hit_fraction"] == 1 / 3
    assert result["cue_delta_seconds"] == {"median": 2, "p95": 2}
    assert spike.cue_agreement([], [(0, 1)])["cue_hit_fraction"] is None


def test_cue_matching_is_one_to_one_and_maximizes_count() -> None:
    result = spike.cue_agreement([(0, 1), (0, 3)], [(0, 0), (0, 2)])
    assert result["matched_cue_hit_count"] == 2
    assert spike.cue_agreement([(0, 0), (0, 1)], [(0, .5)])["matched_cue_hit_count"] == 1


def test_aggregate_medians_p95_and_empty_evidence() -> None:
    assert spike.summary([1, 2, 3, 4]) == {"median": 2.5, "p95": 4}
    assert spike.summary(list(range(1, 21))) == {"median": 10.5, "p95": 19}
    assert spike.summary([]) == {"median": None, "p95": None}
    rows = [{"engine": "option_a", "pass_ordinal": 1, "render_load": "off", "status": "completed",
             "metrics": {"total_seconds": n, "nested": {"median": n}, "unavailable": None}}
            for n in (1, 2, 3, 4)]
    combined = spike.aggregate(rows)[0]
    assert combined["block_count"] == 4
    assert combined["metrics"]["total_seconds"] == {"sample_count": 4, "median": 2.5, "p95": 4}
    assert combined["metrics"]["nested_median"] == combined["metrics"]["total_seconds"]
    assert "unavailable" not in combined["metrics"]


@pytest.mark.parametrize("unavailable,dies,expected", [(False, False, "active"),
                                                     (True, False, "unavailable"),
                                                     (False, True, "unavailable")])
def test_render_second_pass_and_unavailable_continuation(
    unavailable: bool, dies: bool, expected: str,
) -> None:
    effects = FakeEffects()
    effects.unavailable, effects.dies = unavailable, dies
    code, report, _ = invoke(effects, settings(render_load=True))
    assert code == 0 and report["error_count"] == 0
    assert effects.calls == ["baseline", "option_a"] * 2
    assert [r["render_load"] for r in report["measurements"]] == ["off", "off", expected, expected]
    assert all(load.stopped for load in effects.loads)
    assert len(report["aggregates"]) == 4


@pytest.mark.parametrize("engine", ["baseline", "option_a", "option_b"])
def test_partial_failure_exit_three_preserves_completed_and_sanitizes(engine: str) -> None:
    effects = FakeEffects()
    effects.fail_engine = engine
    code, report, table = invoke(
        effects, settings(cpp_binary=Path("private-binary"), render_load=True), ["--markdown"])
    assert code == 3 and report["error_count"] == 2
    assert sum(r["status"] == "completed" for r in report["measurements"]) == 4
    assert all(load.stopped for load in effects.loads)
    assert all(r["failure_code"] == "engine_failed" for r in report["measurements"]
               if r["status"] == "failed")
    if engine == "baseline":
        assert report["measurements"][1]["metrics"]["word_agreement"] is None
    rendered = json.dumps(report) + table
    for private in ("private", "Welcome", "phrase", "timestamp", "config", ".mp4", "C:\\"):
        assert private not in rendered


def test_probe_failure_partial_without_running_engines() -> None:
    effects = FakeEffects()
    effects.fail_probe = True
    code, report, _ = invoke(effects)
    assert code == 3 and not effects.calls
    assert report["failures"] == [{"ordinal": 1, "failure_code": "probe_failed"}]


def test_success_rtf_baseline_parity_and_numeric_only_report() -> None:
    code, report, _ = invoke(FakeEffects())
    assert code == 0 and report["error_count"] == 0
    metrics = report["measurements"][0]["metrics"]
    assert metrics["real_time_factor"] == 20 and metrics["total_seconds"] == 3
    assert metrics["word_agreement"]["matched_word_fraction"] == 1
    assert metrics["cue_agreement"]["cue_hit_fraction"] == 1
    allowed = {"cuda", "conference", "baseline", "option_a", "off", "completed"}

    def check(value: Any) -> None:
        if isinstance(value, dict):
            for item in cast(dict[str, Any], value).values():
                check(item)
        elif isinstance(value, list):
            for item in cast(list[Any], value):
                check(item)
        elif isinstance(value, str):
            assert value in allowed
        else:
            assert value is None or type(value) in (int, float)

    check(report)


def test_cpp_flags_and_token_offsets_subwords_and_invalid_json() -> None:
    config = settings(device="cpu", cpp_binary=Path("cpp.exe"), cpp_model=Path("model.bin"))
    command = spike.cpp_command(config, Path("audio.wav"), Path("out"))
    assert command == ["cpp.exe", "-m", "model.bin", "-f", "audio.wav", "-l", "en", "-bs", "5",
                       "-ojf", "-of", "out", "-ml", "1000000", "-sow", "-ng"]
    assert "-ng" not in spike.cpp_command(replace(config, device="cuda"), Path("a"), Path("o"))
    assert spike.decode_command(Path("f"), Path("b"), Path("w"))[-6:] == [
        "-c:a", "pcm_s16le", "-f", "wav", "-y", "w"]
    payload = {"transcription": [{"tokens": [
        {"text": "[_BEG_]"}, {"text": " hello", "offsets": {"from": 100, "to": 200}},
        {"text": "world", "offsets": {"from": 200, "to": 400}},
        {"text": "!", "offsets": {"from": 400, "to": 400}},
        {"text": " next", "offsets": {"from": 500, "to": 800}},
    ]}]}
    assert spike.cpp_words(payload) == (
        spike.Word(" helloworld!", .1, .4), spike.Word(" next", .5, .8))
    assert spike.cue_hits(spike.cpp_words(payload), (("helloworld", "next"),)) == [(0, .1)]
    with pytest.raises(KeyError):
        spike.cpp_words({"transcription": [{"text": "private-text"}]})


@pytest.mark.parametrize("engine,fail", [
    ("baseline", False), ("option_a", False), ("baseline", True)])
def test_faster_whisper_settings_lazy_iteration_and_separate_decode_timing(
    monkeypatch: pytest.MonkeyPatch, engine: str, fail: bool,
) -> None:
    clock = [0.0]
    sentinel = object()

    def decode(*_args: Any, **_kwargs: Any) -> object:
        clock[0] += 2
        return sentinel

    provider = SimpleNamespace(decode_audio=decode)
    monkeypatch.setattr(spike.importlib, "import_module", constant(provider))
    monkeypatch.setattr(spike.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(spike, "pcm_array", constant(sentinel))

    def command(_command: list[str]) -> bytes:
        clock[0] += 2
        return b"fake-pcm"

    def transcribe(audio: Any, **kwargs: Any) -> Any:
        assert kwargs == {"language": "en", "beam_size": 5, "word_timestamps": True,
                          "vad_filter": False, "condition_on_previous_text": True}
        if engine == "baseline":
            assert audio == "private-block.mp4"
            provider.decode_audio(audio)
        else:
            assert audio is sentinel
        clock[0] += 1

        def generate() -> Any:
            clock[0] += 4
            if fail:
                raise RuntimeError("private-provider-error")
            yield SimpleNamespace(words=[SimpleNamespace(word="synthetic", start=1, end=2)])

        return generate(), None

    effects = spike.LocalEffects(settings())
    effects.model = SimpleNamespace(transcribe=transcribe)
    effects.command = command
    if fail:
        with pytest.raises(RuntimeError):
            effects.measure(engine, Path("private-block.mp4"))
    else:
        result = effects.measure(engine, Path("private-block.mp4"))
        assert (result.decode_seconds, result.inference_seconds, result.total_seconds) == (2, 5, 7)
        assert result.words == (spike.Word("synthetic", 1, 2),)
    assert provider.decode_audio is decode


def test_local_model_factory_reused_offline_and_loading_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infrastructure.transcription import faster_whisper

    clock = [0.0]
    factory_calls: list[Any] = []

    def transcribe(*_args: Any, **_kwargs: Any) -> Any:
        clock[0] += 1
        return [], None

    def factory(path: str, **kwargs: Any) -> Any:
        factory_calls.append((path, kwargs))
        clock[0] += 100
        return SimpleNamespace(transcribe=transcribe)

    monkeypatch.setattr(faster_whisper, "_default_model_factory", constant(factory))
    monkeypatch.setattr(spike, "local_path", constant(Path("tokenizer.json")))
    monkeypatch.setattr(spike.importlib, "import_module",
                        constant(SimpleNamespace(decode_audio=constant(None))))
    monkeypatch.setattr(spike.time, "perf_counter", lambda: clock[0])
    effect = spike.LocalEffects(settings())
    for _ in range(2):
        assert effect.measure("baseline", Path("block")).total_seconds == 1
    assert factory_calls == [("private-model", {
        "device": "cuda", "compute_type": "float16", "local_files_only": True,
    })]


def test_subprocess_commands_capture_diagnostics_and_probe_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def execute(command: list[str], **kwargs: Any) -> Any:
        calls.append(command)
        assert kwargs == {"check": True, "stdout": spike.subprocess.PIPE,
                          "stderr": spike.subprocess.DEVNULL, "stdin": spike.subprocess.DEVNULL,
                          "timeout": 7200}
        return SimpleNamespace(stdout=b'{"format":{"duration":"12.5"}}')

    monkeypatch.setattr(spike.subprocess, "run", execute)
    assert spike.LocalEffects(settings()).duration(Path("private-block.mp4")) == 12.5
    assert calls == [["private-ffprobe.exe", "-v", "error", "-protocol_whitelist", "file,pipe",
                      "-show_entries", "format=duration", "-of", "json", "private-block.mp4"]]


@pytest.mark.parametrize("ready", [False, True])
def test_render_subprocess_requires_encoded_frames_and_reaps(
    monkeypatch: pytest.MonkeyPatch, ready: bool,
) -> None:
    class Process:
        stdout = io.BytesIO(b"frame=1\n" if ready else b"frame=0\n")
        stopped = False

        def poll(self) -> int | None:
            return 0 if self.stopped else None

        def terminate(self) -> None:
            self.stopped = True

        def wait(self, **_kwargs: Any) -> int:
            assert self.stopped
            return 0

    process = Process()

    def launch(command: list[str], **kwargs: Any) -> Process:
        assert command[:1] == ["explicit-ffmpeg"]
        assert command[command.index("-c:v") + 1] == "h264_nvenc"
        assert command[command.index("-stream_loop") + 1] == "-1"
        assert command[-3:] == ["-f", "null", "-"]
        assert kwargs["stderr"] == spike.subprocess.DEVNULL
        return process

    # Run the injected reader synchronously; no process or waiting in this test.
    def thread(*, target: Callable[[], None], **_kwargs: Any) -> Any:
        return SimpleNamespace(start=target, join=constant(None))

    event = SimpleNamespace(set=constant(None), wait=constant(ready))
    monkeypatch.setattr(spike.subprocess, "Popen", launch)
    monkeypatch.setattr(spike, "Thread", thread)
    monkeypatch.setattr(spike, "Event", constant(event))
    if ready:
        load = spike.RenderLoad(Path("explicit-ffmpeg"), Path("private-block"))
        assert load.alive()
        load.stop()
    else:
        with pytest.raises(RuntimeError):
            spike.RenderLoad(Path("explicit-ffmpeg"), Path("private-block"))
    assert process.stopped and process.stdout.closed


def test_native_and_python_diagnostics_suppressed_on_failure(
    capfd: pytest.CaptureFixture[str],
) -> None:
    import os

    def loader(*_args: Any) -> Any:
        print("private-python-text")
        os.write(1, b"private-native-transcript\n")
        os.write(2, b"private-native-path\n")
        raise ValueError("private-config")

    assert spike.main(["--blocks", "unused"], loader=loader, native_quiet=True) == 1
    captured = capfd.readouterr()
    assert json.loads(captured.out) == {"error_count": 1}
    assert captured.err == ""
    print("restored")
    assert capfd.readouterr().out == "restored\n"


@pytest.mark.parametrize("fails", [False, True])
def test_cpp_effect_decode_inference_and_private_scratch_cleanup(
    monkeypatch: pytest.MonkeyPatch, fails: bool,
) -> None:
    clock = [0.0]
    commands: list[list[str]] = []
    closed: list[bool] = []

    class Scratch:
        def __enter__(self) -> str:
            return "private-scratch"

        def __exit__(self, *_args: Any) -> None:
            closed.append(True)

    def command(args: list[str]) -> bytes:
        commands.append(args)
        clock[0] += 2 if len(commands) == 1 else 5
        if len(commands) == 2 and fails:
            raise RuntimeError("private-subprocess-diagnostic")
        return b""

    monkeypatch.setattr(spike.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(spike, "local_path", constant(Path("external-temp")))
    monkeypatch.setattr(spike.tempfile, "gettempdir", constant("external-temp"))
    monkeypatch.setattr(spike.tempfile, "TemporaryDirectory", constant(Scratch()))
    monkeypatch.setattr(Path, "read_text", constant('{"transcription": []}'))
    effect = spike.LocalEffects(settings(cpp_binary=Path("cpp"), cpp_model=Path("model")))
    effect.command = command
    if fails:
        with pytest.raises(RuntimeError):
            effect.measure("option_b", Path("private-block"))
    else:
        result = effect.measure("option_b", Path("private-block"))
        assert (result.decode_seconds, result.inference_seconds, result.total_seconds) == (2, 5, 7)
    assert closed == [True] and len(commands) == 2
    assert commands[0][-6:-1] == ["-c:a", "pcm_s16le", "-f", "wav", "-y"]
    assert commands[1][0] == "cpp" and "-ojf" in commands[1]


@pytest.mark.parametrize("cpp", [False, True])
def test_cache_warmup_order_alternation_and_comparison_when_baseline_last(cpp: bool) -> None:
    events: list[Any] = []

    class OrderedEffects(FakeEffects):
        def warm_cache(self, block: Path) -> None:
            events.append(("cache", block))

        def warm_up(self, engine: str) -> None:
            events.append(("warm", engine))

        def measure(self, engine: str, block: Path) -> Any:
            events.append(("measure", engine, block))
            return super().measure(engine, block)

    blocks = (Path("private-one"), Path("private-two"))
    config = settings(blocks=blocks, render_load=True,
                      cpp_binary=Path("private-cli") if cpp else None)
    code, report, _ = invoke(OrderedEffects(), config)
    engines = list(spike.ENGINES if cpp else spike.ENGINES[:2])
    assert code == 0
    expected: list[Any] = [("warm", engine) for engine in engines]
    for _ in range(2):
        for block, order in zip(blocks, (engines, engines[::-1]), strict=True):
            expected.append(("cache", block))
            expected.extend(("measure", engine, block) for engine in order)
    assert events == expected
    assert len(report["measurements"]) == len(engines) * 4
    for row in report["measurements"]:
        order = engines if row["ordinal"] == 1 else engines[::-1]
        assert row["first_engine"] == order[0]
        assert row["engine_ordinal"] == order.index(row["engine"]) + 1
        assert row["metrics"]["word_agreement"]["matched_word_fraction"] == 1
        assert row["metrics"]["cue_agreement"]["cue_hit_fraction"] == 1
        assert row["metrics"]["total_seconds"] == 3
    assert all(row["block_count"] == 2 for row in report["aggregates"])


@pytest.mark.parametrize("device", ["cuda", "cpu"])
def test_preflight_failure_closed_partial_without_measurement(device: str) -> None:
    class Unavailable(FakeEffects):
        def warm_up(self, engine: str) -> None:
            raise RuntimeError("private CUDA DLL path")

    effects = Unavailable()
    code, report, _ = invoke(effects, settings(device=device))
    assert code == 3 and report["error_count"] == 2
    assert not effects.calls and report["aggregates"] == []
    expected = "cuda_runtime_unavailable" if device == "cuda" else "warm_up_failed"
    assert all(row["failure_code"] == expected for row in report["measurements"])
    assert "private" not in json.dumps(report)


def test_silence_warmup_consumes_lazy_inference_outside_timing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    silence = object()

    def zeros(count: int, *, dtype: str) -> object:
        assert (count, dtype) == (16000, "float32")
        return silence

    def transcribe(audio: Any, **kwargs: Any) -> Any:
        assert audio is silence
        assert kwargs == {"language": "en", "beam_size": 5, "word_timestamps": True,
                          "vad_filter": False, "condition_on_previous_text": True}

        def segments() -> Any:
            events.append("inference")
            yield SimpleNamespace(words=[])

        return segments(), None

    def no_clock() -> float:
        pytest.fail("warm-up must not use the measurement clock")

    effect = spike.LocalEffects(settings())
    effect.model = SimpleNamespace(transcribe=transcribe)
    monkeypatch.setattr(spike.importlib, "import_module", constant(SimpleNamespace(zeros=zeros)))
    monkeypatch.setattr(spike.time, "perf_counter", no_clock)
    effect.warm_up("baseline")
    effect.warm_up("option_a")
    assert events == ["inference", "inference"]


def test_cache_reads_each_byte_once_in_bounded_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    reads: list[int] = []

    class Source(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            assert size is not None
            reads.append(size)
            return super().read(size)

    source = Source(bytes(2 * 1024 * 1024 + 1))
    monkeypatch.setattr(Path, "open", constant(source))
    spike.LocalEffects(settings()).warm_cache(Path("private-block"))
    assert reads == [1024 * 1024] * 4
    assert source.closed


class NoisyEngine(spike.LocalEffects):
    def warm_up(self, engine: str) -> None:
        pass

    def measure(self, engine: str, block: Path) -> Any:
        # Larger than a pipe buffer, at both Python and native descriptor boundaries.
        for fd in (1, 2):
            os.write(fd, b"private-native-diagnostic " * 16384)
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetStdHandle.argtypes = [wintypes.DWORD]
            kernel.GetStdHandle.restype = wintypes.HANDLE
            kernel.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                         ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
            kernel.WriteFile.restype = wintypes.BOOL
            data = b"private-Windows-native-diagnostic " * 16384
            written = wintypes.DWORD()
            for number in (-11, -12):
                assert kernel.WriteFile(kernel.GetStdHandle(number), data, len(data),
                                        ctypes.byref(written), None)
                assert written.value == len(data)
        print("private-python-diagnostic " * 16384)
        raise RuntimeError("private Library cublas64_12.dll cannot be loaded")


def test_large_native_writer_failure_returns_exit_three_and_sanitized_report(
) -> None:
    # A subprocess watchdog bounds a regression that blocks in os.write. No elapsed
    # wall-time assertion; fake engine only, with no media/model/GPU dependency.
    source = """
import test_validation_transcription_engine_spike as t
effect = t.NoisyEngine(t.settings())
effect.warm_cache = t.constant(None)
effect.duration = t.constant(60)
raise SystemExit(t.spike.main(['--blocks', 'private'], loader=t.constant(t.settings()),
    effects_factory=t.constant(effect), native_quiet=True))
"""
    completed = spike.subprocess.run(
        [sys.executable, "-B", "-c", source], cwd=Path(__file__).parent,
        stdout=spike.subprocess.PIPE, stderr=spike.subprocess.PIPE, timeout=15, check=False)
    report = json.loads(completed.stdout)
    assert completed.returncode == 3 and report["error_count"] == 2
    assert [row["failure_code"] for row in report["measurements"]] == [
        "cuda_runtime_unavailable"] * 2
    assert b"private" not in completed.stdout and b"cublas" not in completed.stdout
    assert completed.stderr == b""


@pytest.mark.parametrize("action,deadline", [("warm_up", 60), ("measure", 300)])
def test_worker_timeout_is_bounded_and_reaped(
    monkeypatch: pytest.MonkeyPatch, action: str, deadline: int,
) -> None:
    events: list[Any] = []

    def send(request: Any) -> None:
        events.append(request)

    def poll(seconds: int) -> bool:
        events.append(seconds)
        return False

    def join(**kwargs: Any) -> None:
        events.append(kwargs)

    connection = SimpleNamespace(
        send=send, poll=poll,
        close=lambda: events.append("connection_closed"))
    worker = SimpleNamespace(
        is_alive=constant(True), terminate=lambda: events.append("terminate"),
        join=join, kill=lambda: events.append("kill"),
        close=lambda: events.append("worker_closed"))
    effect = spike.GuardedEffects(settings())
    effect.connection, effect.worker = connection, worker
    with pytest.raises(spike.EngineTimeout):
        effect.call(action, "baseline")
    assert events == [(action, "baseline", None), deadline, "connection_closed", "terminate",
                      {"timeout": 5}, "kill", {"timeout": 5}, "worker_closed"]
    assert effect.worker is None and effect.connection is None


def test_measured_timeout_preserves_other_engine_results() -> None:
    class TimeoutEffects(FakeEffects):
        def measure(self, engine: str, block: Path) -> Any:
            if engine == "baseline":
                raise spike.EngineTimeout()
            return super().measure(engine, block)

    code, report, _ = invoke(TimeoutEffects())
    assert code == 3 and report["error_count"] == 1
    assert report["measurements"][0]["failure_code"] == "engine_timeout"
    assert report["measurements"][1]["status"] == "completed"


@pytest.mark.parametrize("timeout", [60, 3600, 14400])
@pytest.mark.parametrize("action", ["warm_up", "measure"])
def test_worker_poll_uses_configured_measurement_deadline(
    action: str, timeout: int,
) -> None:
    deadlines: list[int] = []

    def poll(seconds: int) -> bool:
        deadlines.append(seconds)
        return True

    effect = spike.GuardedEffects(settings(engine_timeout_seconds=timeout))
    effect.worker = object()
    effect.connection = SimpleNamespace(
        send=constant(None), poll=poll,
        recv=constant((True, None)))
    effect.call(action, "baseline")
    assert deadlines == [60 if action == "warm_up" else timeout]


@pytest.mark.parametrize("timeout", [60, 300, 3600, 14400])
def test_worker_decoder_deadline_precedes_configured_measurement_deadline(timeout: int) -> None:
    def recv() -> Any:
        raise EOFError()

    effect = spike.LocalEffects(settings(engine_timeout_seconds=timeout))
    connection = SimpleNamespace(recv=recv, close=constant(None))
    spike.engine_worker(connection, effect.settings, constant(effect))
    assert effect.command_timeout == timeout - 10


def test_worker_start_failure_closes_unstarted_process_and_reports_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def start() -> None:
        raise OSError("private spawn failure")

    connection = SimpleNamespace(close=lambda: events.append("parent_closed"))
    child = SimpleNamespace(close=lambda: events.append("child_closed"))
    worker = SimpleNamespace(start=start, close=lambda: events.append("worker_closed"))
    context = SimpleNamespace(Pipe=constant((connection, child)), Process=constant(worker))
    monkeypatch.setattr(spike.multiprocessing, "get_context", constant(context))
    effect = spike.GuardedEffects(settings())
    effect.warm_cache, effect.duration = constant(None), constant(60)
    output = io.StringIO()
    assert spike.main(["--blocks", "private"], output=output, loader=constant(settings()),
                      effects_factory=constant(effect)) == 3
    assert events == ["worker_closed", "child_closed", "parent_closed"]
    assert effect.worker is None and effect.connection is None
    assert json.loads(output.getvalue())["error_count"] == 2
    assert "private" not in output.getvalue()
    assert [row["failure_code"] for row in json.loads(output.getvalue())["measurements"]] == [
        "worker_start_failed", "worker_start_failed"]


@pytest.mark.parametrize("failure,expected", [
    (RuntimeError("private Library cublas64_12.dll cannot be loaded"),
     "cuda_runtime_unavailable"),
    (RuntimeError("private Library cudnn64_9.dll cannot be loaded"),
     "cuda_runtime_unavailable"),
    (ImportError("private faster_whisper import failure"), "warm_up_failed"),
    (ValueError("private model path invalid"), "warm_up_failed"),
    (ValueError("private compute type unsupported"), "warm_up_failed"),
])
def test_worker_warmup_transports_classified_closed_codes(
    failure: Exception, expected: str,
) -> None:
    responses: list[Any] = []
    requests = iter([("warm_up", "baseline", None)])

    def recv() -> Any:
        try:
            return next(requests)
        except StopIteration:
            raise EOFError() from None

    class Failed(FakeEffects):
        def warm_up(self, engine: str) -> None:
            raise failure

    connection = SimpleNamespace(recv=recv, send=responses.append, close=constant(None))
    spike.engine_worker(connection, settings(), constant(Failed()))
    assert responses == [(False, expected)]
    assert "private" not in json.dumps(responses)


@pytest.mark.parametrize("reason,expected", [
    ("cuda_runtime_unavailable", "cuda_runtime_unavailable"),
    ("provider_runtime_unavailable", "warm_up_failed"),
    ("provider_model_unavailable", "warm_up_failed"),
    ("private arbitrary reason", "warm_up_failed"),
])
def test_typed_provider_warmup_failure_respects_reason_code(reason: str, expected: str) -> None:
    from app.contexts.transcription_evidence.application import TranscriptionExecutionError

    class Failed(FakeEffects):
        def warm_up(self, engine: str) -> None:
            raise TranscriptionExecutionError(
                reason, retryable=False, diagnostic_summary="private CUDA diagnostic")

    code, report, _ = invoke(Failed())
    assert code == 3
    assert [row["failure_code"] for row in report["measurements"]] == [expected] * 2
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("response,expected", [
    ("cuda_runtime_unavailable", "cuda_runtime_unavailable"),
    ("warm_up_failed", "warm_up_failed"),
    ("private unexpected IPC", "warm_up_failed"),
    (None, "warm_up_timeout"),
])
def test_parent_warmup_closed_failures_and_preflight_timeout(
    response: str | None, expected: str,
) -> None:
    deadlines: list[int] = []

    def poll(seconds: int) -> bool:
        deadlines.append(seconds)
        return response is not None

    effect = spike.GuardedEffects(settings(engine_timeout_seconds=3600))
    effect.connection = SimpleNamespace(
        send=constant(None), poll=poll, recv=constant((False, response)), close=constant(None))
    effect.worker = SimpleNamespace(
        is_alive=constant(False), join=constant(None), close=constant(None))
    effect.duration, effect.warm_cache = constant(60), constant(None)
    code, report = spike.run(effect.settings, effect)
    assert code == 3
    assert [row["failure_code"] for row in report["measurements"]] == [expected] * 2
    assert deadlines == [60]
    assert effect.worker is None and effect.connection is None
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("failure", [
    RuntimeError("private CUDA DLL failure"),
    spike.subprocess.CalledProcessError(1, "private-cli"),
    spike.subprocess.TimeoutExpired("private-cli", 60),
])
def test_option_b_warmup_failures_always_use_generic_closed_code(failure: Exception) -> None:
    class Failed(FakeEffects):
        def warm_up(self, engine: str) -> None:
            if engine == "option_b":
                raise failure

    code, report, _ = invoke(Failed(), settings(cpp_binary=Path("private-cli")))
    assert code == 3 and report["error_count"] == 1
    assert [row["status"] for row in report["measurements"]] == [
        "completed", "completed", "failed"]
    assert report["measurements"][-1]["failure_code"] == "warm_up_failed"
    assert "private" not in json.dumps(report)


def test_worker_transports_success_and_closed_failure_then_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[Any] = []
    closed: list[bool] = []
    requests = iter([("warm_up", "baseline", None),
                     ("measure", "baseline", Path("private")),
                     ("measure", "option_a", Path("private"))])

    def recv() -> Any:
        try:
            return next(requests)
        except StopIteration:
            raise EOFError() from None

    effect = FakeEffects()
    effect.fail_engine = "option_a"
    connection = SimpleNamespace(recv=recv, send=responses.append,
                                 close=lambda: closed.append(True))
    spike.engine_worker(connection, settings(), constant(effect))
    assert responses[0] == (True, None)
    assert responses[1][0] is True and responses[1][1].total_seconds == 3
    assert responses[2] == (False, "engine_failed")
    assert closed == [True]


@pytest.mark.parametrize("failure,device,expected", [
    (RuntimeError("private inference diagnostic"), "cuda", "engine_failed"),
    (spike.WorkerFailure("decode_failed"), "cuda", "decode_failed"),
    (RuntimeError("private Library cublas64_12.dll cannot be loaded"),
     "cuda", "cuda_runtime_unavailable"),
    (RuntimeError("private Library cudnn64_9.dll cannot be loaded"),
     "cuda", "cuda_runtime_unavailable"),
    (RuntimeError("private CUDA diagnostic"), "cpu", "engine_failed"),
    (spike.EngineTimeout("private deadline"), "cuda", "engine_timeout"),
    (spike.subprocess.TimeoutExpired("private-cli", 60), "cuda", "engine_timeout"),
])
def test_worker_measurement_transports_classified_closed_codes(
    failure: Exception, device: str, expected: str,
) -> None:
    responses: list[Any] = []
    closed: list[bool] = []
    requests = iter([("warm_up", "baseline", None),
                     ("measure", "baseline", Path("private-block"))])

    def recv() -> Any:
        try:
            return next(requests)
        except StopIteration:
            raise EOFError() from None

    class Failed(FakeEffects):
        def measure(self, engine: str, block: Path) -> Any:
            raise failure

    connection = SimpleNamespace(recv=recv, send=responses.append,
                                 close=lambda: closed.append(True))
    spike.engine_worker(connection, settings(device=device), constant(Failed()))
    assert responses == [(True, None), (False, expected)]
    assert closed == [True]
    assert "private" not in json.dumps(responses)


@pytest.mark.parametrize("response,expected", [
    ("engine_failed", "engine_failed"),
    ("decode_failed", "decode_failed"),
    ("cuda_runtime_unavailable", "cuda_runtime_unavailable"),
    ("engine_timeout", "engine_timeout"),
    ("private unexpected IPC", "engine_failed"),
    (None, "engine_failed"),
])
def test_parent_measurement_codes_reach_partial_report_and_reap_worker(
    response: str | None, expected: str,
) -> None:
    closed: list[str] = []
    effect = spike.GuardedEffects(settings())
    effect.connection = SimpleNamespace(
        send=constant(None), poll=constant(True), recv=constant((False, response)),
        close=lambda: closed.append("connection"))
    effect.worker = SimpleNamespace(
        is_alive=constant(False), join=constant(None), close=lambda: closed.append("worker"))
    effect.duration, effect.warm_cache, effect.warm_up = (
        constant(60), constant(None), constant(None))
    guarded_measure = effect.measure

    def measure(engine: str, block: Path) -> Any:
        return (guarded_measure(engine, block) if engine == "baseline"
                else spike.Measurement((), 1, 2, 3))

    effect.measure = measure
    code, report = spike.run(effect.settings, effect)
    assert code == 3 and report["error_count"] == 1
    assert report["measurements"][0]["failure_code"] == expected
    assert report["measurements"][1]["status"] == "completed"
    assert closed == ["connection", "worker"]
    assert effect.worker is None and effect.connection is None
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("engine", ["baseline", "option_a", "option_b"])
@pytest.mark.parametrize("timeout", [False, True])
def test_decode_failures_are_classified_at_each_engine_boundary(
    monkeypatch: pytest.MonkeyPatch, engine: str, timeout: bool,
) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> Any:
        if timeout:
            raise spike.subprocess.TimeoutExpired("private-decoder", 60)
        raise RuntimeError("private decode diagnostic")

    provider = SimpleNamespace(decode_audio=fail)
    monkeypatch.setattr(spike.importlib, "import_module", constant(provider))
    monkeypatch.setattr(spike, "local_path", constant(Path("private-scratch")))
    closed: list[bool] = []

    class Scratch:
        def __enter__(self) -> str:
            return "private-scratch"

        def __exit__(self, *_args: Any) -> None:
            closed.append(True)

    monkeypatch.setattr(spike.tempfile, "TemporaryDirectory", constant(Scratch()))

    def transcribe(*_args: Any, **_kwargs: Any) -> Any:
        return provider.decode_audio()

    effect = spike.LocalEffects(settings())
    effect.model = SimpleNamespace(transcribe=transcribe)
    effect.command = fail
    with pytest.raises((spike.WorkerFailure, spike.EngineTimeout)) as caught:
        effect.measure(engine, Path("private-block"))
    expected = "engine_timeout" if timeout else "decode_failed"
    assert spike.measurement_failure(caught.value, engine, "cuda") == expected
    assert provider.decode_audio is fail
    if engine == "option_b":
        assert closed == [True]


def test_cache_failure_in_second_pass_preserves_first_pass_and_later_block() -> None:
    blocks = (Path("private-one"), Path("private-two"))
    cache_calls: list[Path] = []

    class UnreadableLater(FakeEffects):
        def warm_cache(self, block: Path) -> None:
            cache_calls.append(block)
            if len(cache_calls) == 3:
                raise OSError("private unreadable block")

    code, report, _ = invoke(UnreadableLater(), settings(blocks=blocks, render_load=True))
    assert code == 3 and report["error_count"] == 1
    assert cache_calls == list(blocks) * 2
    assert [(row["pass_ordinal"], row["ordinal"]) for row in report["measurements"]] == [
        (1, 1), (1, 1), (1, 2), (1, 2), (2, 2), (2, 2)]
    assert all(row["status"] == "completed" for row in report["measurements"])
    assert report["failures"] == [{"ordinal": 1, "failure_code": "cache_warm_failed"}]
    assert "private" not in json.dumps(report)


def test_cuda_preflight_failure_still_runs_optional_engine() -> None:
    class Partial(FakeEffects):
        def warm_up(self, engine: str) -> None:
            if engine == "baseline":
                raise RuntimeError("private runtime unavailable")

    effects = Partial()
    code, report, _ = invoke(effects, settings(cpp_binary=Path("private-cli")))
    assert code == 3 and report["error_count"] == 2
    assert effects.calls == ["option_b"]
    assert report["measurements"][-1]["status"] == "completed"
    assert report["measurements"][-1]["metrics"]["word_agreement"] is None


def test_cache_failure_is_sanitized_and_does_not_run_engines() -> None:
    class Unreadable(FakeEffects):
        def warm_cache(self, block: Path) -> None:
            raise OSError("private unreadable block")

    effects = Unreadable()
    code, report, _ = invoke(effects)
    assert code == 3 and not effects.calls
    assert report["failures"] == [{"ordinal": 1, "failure_code": "cache_warm_failed"}]
