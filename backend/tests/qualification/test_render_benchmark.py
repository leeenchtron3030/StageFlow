from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from io import BufferedReader
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from typing import cast

import pytest
from qualification import render_benchmark as benchmark
from qualification.render_benchmark import (
    BenchmarkError,
    CorpusProbe,
    TimedResult,
)


def _probe() -> CorpusProbe:
    return CorpusProbe(
        block_count=11,
        total_duration_seconds=660.0,
        width=1920,
        height=1080,
        frame_rate=Fraction(30, 1),
        minimum_source_frame_rate=Fraction(2997, 100),
        maximum_source_frame_rate=Fraction(30, 1),
        fingerprint_sha256="a" * 64,
    )


def test_harness_is_directly_executable_with_finite_subcommands() -> None:
    backend_root = benchmark.REPOSITORY_ROOT / "backend"

    result = subprocess.run(
        [
            sys.executable,
            "tests/qualification/render_benchmark.py",
            "--help",
        ],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Bounded, qualification-only StageFlow render benchmark" in result.stdout
    for command in ("nvenc", "libx264", "concurrent", *benchmark.NATIVE_ARMS, "native-concurrent"):
        assert command in result.stdout


def test_paths_must_be_absolute_external_and_new(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = tmp_path / "source"
    source.mkdir()

    assert (
        benchmark.require_external_input_directory(
            source.resolve(), repository_root=repository
        )
        == source.resolve()
    )
    with pytest.raises(BenchmarkError, match="absolute"):
        benchmark.require_external_input_directory(
            Path("relative"), repository_root=repository
        )
    with pytest.raises(BenchmarkError, match="outside_repository"):
        benchmark.require_external_input_directory(
            repository.resolve(), repository_root=repository
        )
    with pytest.raises(BenchmarkError, match="outside_repository"):
        benchmark.require_external_new_file(
            repository / "result.json",
            suffixes=frozenset({".json"}),
            repository_root=repository,
        )

    output = (tmp_path / "external" / "result.json").resolve()
    assert (
        benchmark.require_external_new_file(
            output,
            suffixes=frozenset({".json"}),
            repository_root=repository,
        )
        == output
    )
    output.parent.mkdir()
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(BenchmarkError, match="already_exists"):
        benchmark.require_external_new_file(
            output,
            suffixes=frozenset({".json"}),
            repository_root=repository,
        )


def test_discovery_is_direct_bounded_and_deterministically_sorted(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "B.mp4").write_bytes(b"b")
    (source / "a.MP4").write_bytes(b"a")
    (source / "ignored.mov").write_bytes(b"x")
    nested = source / "nested"
    nested.mkdir()
    (nested / "hidden.mp4").write_bytes(b"x")

    blocks = benchmark.discover_blocks(source.resolve(), ".mp4")

    assert [block.name for block in blocks] == ["a.MP4", "B.mp4"]
    with pytest.raises(BenchmarkError, match="extension_invalid"):
        benchmark.discover_blocks(source.resolve(), "../mp4")


def test_probe_normalizes_small_average_rate_variation_and_rejects_large_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocks = (tmp_path / "a.mp4", tmp_path / "b.mp4")
    for block in blocks:
        block.write_bytes(b"fixture")
    rates = {"a.mp4": Fraction(30, 1), "b.mp4": Fraction(299, 10)}

    class FakeContainer:
        duration = None

        def __init__(self, rate: Fraction) -> None:
            stream = SimpleNamespace(
                average_rate=rate,
                duration=60,
                time_base=Fraction(1, 1),
                codec_context=SimpleNamespace(width=1920, height=1080),
            )
            self.streams = SimpleNamespace(video=(stream,))

        def __enter__(self) -> FakeContainer:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class FakeAv:
        time_base = 1_000_000

        @staticmethod
        def open(path: str, *, mode: str) -> FakeContainer:
            assert mode == "r"
            return FakeContainer(rates[Path(path).name])

    monkeypatch.setattr(benchmark, "_import_av", lambda: FakeAv())

    probe = benchmark.probe_corpus(blocks)

    assert probe.frame_rate == Fraction(30, 1)
    assert probe.minimum_source_frame_rate == Fraction(299, 10)
    assert probe.maximum_source_frame_rate == Fraction(30, 1)

    rates["b.mp4"] = Fraction(25, 1)
    with pytest.raises(BenchmarkError, match="variation_out_of_bounds"):
        benchmark.probe_corpus(blocks)


def test_encode_arm_records_metrics_and_omits_private_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_path = tmp_path / "private" / "block.mp4"
    output = tmp_path / "external" / "render.mp4"

    def fake_probe(_: Sequence[Path]) -> CorpusProbe:
        return _probe()

    def fake_environment() -> dict[str, object]:
        return {"gpu": {"name": "fixture-gpu"}}

    def fake_encode(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "wall_clock_seconds": 10.0,
            "real_time_factor": 10 / 660,
            "source_seconds_per_wall_second": 66.0,
            "output_size_bytes": 1234,
            "encoded_frame_count": 19_800,
        }

    def fake_quality(*_: object) -> dict[str, object]:
        return {
            "reference": "source_recording_blocks",
            "ssim_mean_frame_all": 0.99,
            "psnr_mean_frame_average_db": 40.0,
            "compared_frame_count": 19_800,
        }

    monkeypatch.setattr(benchmark, "probe_corpus", fake_probe)
    monkeypatch.setattr(benchmark, "environment_summary", fake_environment)
    monkeypatch.setattr(benchmark, "encode_video", fake_encode)
    monkeypatch.setattr(benchmark, "measure_quality", fake_quality)

    report = benchmark.run_encode_arm(
        (private_path,),
        output,
        encoder="h264_nvenc",
        bit_rate=8_000_000,
        gop_size=60,
    )
    serialized = json.dumps(report)

    assert report["status"] == "succeeded"
    assert report["run_kind"] == "nvenc"
    measurements = cast(Mapping[str, object], report["measurements"])
    quality = cast(Mapping[str, object], measurements["quality"])
    settings = cast(Mapping[str, object], report["settings"])
    assert quality["ssim_mean_frame_all"] == 0.99
    assert settings["encoder"] == "h264_nvenc"
    assert str(private_path) not in serialized
    assert str(output) not in serialized


def test_encoder_failure_is_recorded_without_software_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_probe(_: Sequence[Path]) -> CorpusProbe:
        return _probe()

    def fake_environment() -> dict[str, object]:
        return {}

    monkeypatch.setattr(benchmark, "probe_corpus", fake_probe)
    monkeypatch.setattr(benchmark, "environment_summary", fake_environment)

    def fail(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise BenchmarkError("encoder_execution_failed:h264_nvenc")

    monkeypatch.setattr(benchmark, "encode_video", fail)

    report = benchmark.run_encode_arm(
        (tmp_path / "private.mp4",),
        tmp_path / "render.mp4",
        encoder="h264_nvenc",
        bit_rate=8_000_000,
        gop_size=60,
    )

    assert report["status"] == "failed"
    assert report["failure"] == {
        "code": "encoder_execution_failed",
        "exception_type": "BenchmarkError",
        "software_fallback_used": False,
    }


def test_concurrency_metrics_record_actual_narrow_overlap_and_degradation() -> None:
    measurements = benchmark.concurrency_measurements(
        TimedResult(started=100.0, ended=120.0, value={}),
        TimedResult(started=105.0, ended=113.0, value={}),
        baseline_encode_seconds=10.0,
        baseline_transcription_seconds=5.0,
    )

    assert measurements["actual_overlap_seconds"] == 8.0
    assert measurements["overlap_fraction_of_encode"] == 0.4
    assert measurements["overlap_fraction_of_transcription"] == 1.0
    assert measurements["encode_degradation_percent"] == 100.0
    assert math.isclose(measurements["transcription_degradation_percent"], 60.0)


def test_baseline_must_be_successful_nvenc_run_over_same_corpus(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "nvenc.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_name": benchmark.REPORT_SCHEMA,
                "run_kind": "nvenc",
                "status": "succeeded",
                "corpus": {"fingerprint_sha256": "a" * 64},
                "measurements": {"wall_clock_seconds": 4.0},
            }
        ),
        encoding="utf-8",
    )

    loaded = benchmark._load_baseline(  # pyright: ignore[reportPrivateUsage]
        baseline.resolve(), _probe()
    )
    assert loaded["run_kind"] == "nvenc"
    assert (
        benchmark._measurement_float(  # pyright: ignore[reportPrivateUsage]
            loaded, "wall_clock_seconds"
        )
        == 4.0
    )

    mismatched = CorpusProbe(
        block_count=11,
        total_duration_seconds=660.0,
        width=1920,
        height=1080,
        frame_rate=Fraction(30, 1),
        minimum_source_frame_rate=Fraction(2997, 100),
        maximum_source_frame_rate=Fraction(30, 1),
        fingerprint_sha256="b" * 64,
    )
    with pytest.raises(BenchmarkError, match="incompatible"):
        benchmark._load_baseline(  # pyright: ignore[reportPrivateUsage]
            baseline.resolve(), mismatched
        )


def test_report_publication_is_new_file_only_and_contains_no_paths(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "result.json"
    report = {
        "schema_name": benchmark.REPORT_SCHEMA,
        "run_kind": "concurrent_nvenc_cuda_transcription",
        "settings": {"transcription": {"model_id": "large-v3-turbo"}},
    }

    benchmark.write_report(report_path, report)

    text = report_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert "large-v3-turbo" in text
    with pytest.raises(BenchmarkError, match="already_exists"):
        benchmark.write_report(report_path, report)


def test_required_limitations_are_explicit() -> None:
    values = benchmark.limitations()

    assert "single_corpus_single_machine_not_throughput_or_hardware_qualification" in values
    assert "finite_single_runs_do_not_establish_thermal_steady_state" in values
    assert "concurrent_transcription_overlap_is_narrow_relative_to_encode" in values


def test_transcription_requires_explicit_local_model_and_cuda_directories(
    tmp_path: Path,
) -> None:
    with pytest.raises(BenchmarkError, match="absolute_local_directory"):
        benchmark.build_transcription_job(
            (),
            model="large-v3-turbo",
            cuda_library_directory=tmp_path,
            device="cuda",
            compute_type="float16",
            language=None,
        )


def test_transcription_requires_available_cuda_directory(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    with pytest.raises(BenchmarkError, match="cuda_library_directory_unavailable"):
        benchmark.build_transcription_job(
            (), model=str(model.resolve()), cuda_library_directory=tmp_path / "missing-cuda",
            device="cuda", compute_type="float16", language=None,
        )


@pytest.fixture
def native_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Model an external output boundary inside pytest's sandbox-owned directory.
    original = benchmark.require_external_new_file

    def validate(path: Path, *, suffixes: frozenset[str]) -> Path:
        return original(path, suffixes=suffixes, repository_root=tmp_path / "repository")

    monkeypatch.setattr(benchmark, "require_external_new_file", validate)
    def probe(_: Sequence[Path]) -> CorpusProbe:
        return _probe()

    def environment() -> dict[str, object]:
        return {}

    def conversion(_: Sequence[Path]) -> bool:
        return False

    def quality(*_: object) -> dict[str, object]:
        return {"ssim_mean_frame_all": 0.99, "psnr_mean_frame_average_db": 42.0}

    monkeypatch.setattr(benchmark, "probe_corpus", probe)
    monkeypatch.setattr(benchmark, "environment_summary", environment)
    monkeypatch.setattr(benchmark, "native_needs_pixel_conversion", conversion)
    monkeypatch.setattr(benchmark, "measure_quality", quality)
    binary = tmp_path / "tool.exe"
    binary.write_bytes(b"synthetic executable identity; never executed")
    return binary


def test_explicit_binary_identification_hash_and_no_path_lookup(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "")
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0,
            "ffmpeg version n8.1.2 Copyright (c) FFmpeg developers\n"
            "configuration: --disable-libx264 --disable-libx265\n", "")

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    identity = benchmark.identify_ffmpeg(native_setup)
    assert identity == {"version": "n8.1.2", "gpl_enabled": False,
                        "sha256": hashlib.sha256(native_setup.read_bytes()).hexdigest()}
    assert calls == [[str(native_setup.resolve()), "-version"]]
    assert str(native_setup) not in json.dumps(identity)
    for path in (Path("tool.exe"), native_setup.parent / "missing.exe", native_setup.parent):
        with pytest.raises(BenchmarkError, match="absolute|unavailable"):
            benchmark.identify_ffmpeg(path)
    assert len(calls) == 1


@pytest.mark.parametrize("configuration,gpl", [
    ("--enable-gpl --enable-nvenc", True), ("--disable-gpl --enable-nvenc", False),
])
def test_version_configuration_detection_and_gpl_refusal(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, configuration: str, gpl: bool,
) -> None:
    output = f"ffmpeg version n8.1.2 Copyright (c)\nconfiguration: {configuration}\n"
    assert benchmark.parse_ffmpeg_version(output) == ("n8.1.2", gpl)
    def run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, output, "")

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    if gpl:
        with pytest.raises(BenchmarkError, match="gpl_configuration_prohibited"):
            benchmark.run_native_arm((), native_setup.parent / "render.mp4", ffmpeg=native_setup,
                arm="native-cpu-nvenc", repetitions=3, bit_rate=8_000_000, gop_size=60)
    else:
        assert benchmark.identify_ffmpeg(native_setup)["gpl_enabled"] is False


@pytest.mark.parametrize("output", ["", "garbled", "ffmpeg version n8.1.2\n",
    "ffmpeg version /private/tool\nconfiguration: --disable-gpl\n"])
def test_malformed_version_is_typed_failure(output: str) -> None:
    with pytest.raises(BenchmarkError, match="version_output_invalid"):
        benchmark.parse_ffmpeg_version(output)


@pytest.mark.parametrize("arm,convert", [
    ("native-cpu-nvenc", False), ("native-cuda-nvenc", False), ("native-cuda-nvenc", True),
])
def test_native_command_preserves_encoder_settings_and_gpu_frames(
    native_setup: Path, arm: str, convert: bool,
) -> None:
    command = benchmark.build_native_command(native_setup, native_setup.parent / "concat.txt",
        native_setup.parent / "render.mp4", _probe(), arm=arm,
        bit_rate=9_000_000, gop_size=48, convert_pixels=convert)
    assert isinstance(command, list)
    assert command[0] == str(native_setup.resolve())
    for option, value in {"-c:v": "h264_nvenc", "-preset": "p4", "-rc": "vbr",
                          "-b:v": "9000000", "-g": "48", "-progress": "pipe:1"}.items():
        assert command[command.index(option) + 1] == value
    assert "-an" in command and "-nostdin" in command and "-y" in command
    assert command[command.index("-f") + 1] == "concat"
    assert command[-6:-4] == ["-f", "mp4"]
    assert command[command.index("-fps_mode") + 1] == "passthrough"
    assert "setpts=N*1/(30*TB)" in command[command.index("-vf") + 1]
    if arm == "native-cuda-nvenc":
        assert command[command.index("-hwaccel") + 1] == "cuda"
        assert command[command.index("-hwaccel_output_format") + 1] == "cuda"
        assert command.index("-hwaccel") < command.index("-i")
        assert "-pix_fmt" not in command
        assert ("scale_cuda=format=nv12" in command[command.index("-vf") + 1]) is convert
        assert "hwdownload" not in " ".join(command)
    else:
        assert "-hwaccel" not in command
        assert command[command.index("-pix_fmt") + 1] == "yuv420p"


def test_concat_quotes_apostrophes_and_uses_external_output_parent(
    native_setup: Path,
) -> None:
    block = native_setup.parent / "a block's.mp4"
    expected = block.as_posix().replace("'", "'\\''")
    with benchmark.native_concat_list((block,), native_setup.parent) as path:
        assert path.parent.parent == native_setup.parent
        assert path.read_text(encoding="utf-8") == f"ffconcat version 1.0\nfile '{expected}'\n"
        assert path.read_bytes() == f"ffconcat version 1.0\nfile '{expected}'\n".encode()
    assert not path.exists()
    with pytest.raises(BenchmarkError, match="concat_block_path_invalid"):
        benchmark.concat_list_content((Path("relative.mp4"),))


@pytest.mark.parametrize("output,count", [
    ("frame=1\nfps=20\nprogress=continue\nframe=19700\nprogress=end\n", 19700),
    ("frame=    4 fps=1.2 q=1\rframe=   42 fps=3.4 q=2\r", 42),
    ("frame=0\nprogress=end\n", 0),
])
def test_native_frame_count_parsing(output: str, count: int) -> None:
    assert benchmark.parse_encoded_frame_count(output) == count


@pytest.mark.parametrize("output", ["", "fps=30", "frame=garbled", "frame=-3",
                                        "frame=4\nframe=unknown", "frame=1.5"])
def test_native_frame_count_missing_or_garbled_is_not_estimated(output: str) -> None:
    with pytest.raises(BenchmarkError, match="native_encoded_frame_count"):
        benchmark.parse_encoded_frame_count(output)


def test_repetitions_record_process_failure_continue_and_sanitize_report(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outputs: list[Path] = []
    diagnostics = [f"synthetic diagnostic {index}" for index in range(25)]

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert not kwargs.get("shell", False)
        if command[-1] == "-version":
            return subprocess.CompletedProcess(command, 0,
                "ffmpeg version n8.1.2\nconfiguration: --disable-gpl\n", "")
        output = Path(command[-1])
        assert output.exists() and output.stat().st_size == 0
        outputs.append(output)
        output.write_bytes(b"synthetic output")
        return subprocess.CompletedProcess(command, 7 if len(outputs) == 2 else 0,
            "frame=42\nprogress=end\n", "\n".join(diagnostics))

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    report = benchmark.run_native_arm((native_setup.parent / "block.mp4",),
        native_setup.parent / "render.mp4", ffmpeg=native_setup, arm="native-cpu-nvenc",
        repetitions=3, bit_rate=8_000_000, gop_size=60)
    data = cast(dict[str, object], report["measurements"])
    runs = cast(list[dict[str, object]], data["repetitions"])
    assert report["status"] == "failed"
    assert len(outputs) == len(set(outputs)) == len(runs) == 3
    assert [item["status"] for item in runs] == ["succeeded", "failed", "succeeded"]
    assert runs[1]["exit_status"] == 7 and runs[1]["encoded_frame_count"] == 42
    assert runs[1]["quality"] is None
    assert runs[1]["failure"] == {"code": "native_encoder_execution_failed",
        "exception_type": "BenchmarkError", "software_fallback_used": False}
    assert cast(dict[str, object], data["variance"])["successful_repetitions"] == 2
    for item in runs:
        assert float(cast(float, item["wall_clock_seconds"])) > 0
        assert item["output_size_bytes"] == len(b"synthetic output")
        assert math.isclose(cast(float, item["real_time_factor"]),
                            cast(float, item["wall_clock_seconds"]) / 660)
        assert math.isclose(cast(float, item["source_seconds_per_wall_second"]),
                            660 / cast(float, item["wall_clock_seconds"]))
    captured = capsys.readouterr()
    assert captured.err.splitlines() == diagnostics[-20:]
    assert captured.out == ""
    destination = native_setup.parent / "report.json"
    benchmark.write_report(destination, report)
    assert str(native_setup.parent) not in destination.read_text(encoding="utf-8")
    assert "synthetic diagnostic" not in destination.read_text(encoding="utf-8")
    settings = cast(dict[str, object], report["settings"])
    assert settings["real_time_factor_definition"] == "wall_clock_seconds / corpus_duration_seconds"
    assert settings["source_seconds_per_wall_second_definition"] == (
        "corpus_duration_seconds / wall_clock_seconds")
    assert report["harness"] == {"name": benchmark.HARNESS_NAME, "version": "1.1"}


@pytest.mark.parametrize("failure", ["start", "frames", "empty", "quality"])
def test_native_failures_remain_typed_with_exit_status(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    def identity(_: Path) -> dict[str, object]:
        return {}

    monkeypatch.setattr(benchmark, "identify_ffmpeg", identity)

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if failure == "start":
            raise OSError(str(native_setup))
        if failure != "empty":
            Path(command[-1]).write_bytes(b"fixture")
        return subprocess.CompletedProcess(command, 0,
            "garbled" if failure == "frames" else "frame=42\n", "")

    def quality(*_: object) -> dict[str, object]:
        raise BenchmarkError("quality_frame_count_mismatch")

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    if failure == "quality":
        monkeypatch.setattr(benchmark, "measure_quality", quality)
    report = benchmark.run_native_arm((), native_setup.parent / "render.mp4",
        ffmpeg=native_setup, arm="native-cpu-nvenc", repetitions=1,
        bit_rate=8_000_000, gop_size=60)
    runs = cast(dict[str, list[dict[str, object]]], report["measurements"])["repetitions"]
    assert report["status"] == "failed" and runs[0]["status"] == "failed"
    assert runs[0]["exit_status"] == (None if failure == "start" else 0)
    assert cast(dict[str, object], runs[0]["failure"])["exception_type"] == "BenchmarkError"
    assert str(native_setup) not in json.dumps(report)


def test_native_variance_uses_successes_and_population_standard_deviation() -> None:
    runs: list[Mapping[str, object]] = [
        {"status": "succeeded", "wall_clock_seconds": 2.0, "real_time_factor": 0.25,
         "source_seconds_per_wall_second": 4.0},
        {"status": "failed", "wall_clock_seconds": 1000.0, "real_time_factor": 125.0,
         "source_seconds_per_wall_second": 0.008},
        {"status": "succeeded", "wall_clock_seconds": 4.0, "real_time_factor": 0.5,
         "source_seconds_per_wall_second": 2.0},
    ]
    summary = benchmark.native_variance(runs)
    assert summary["standard_deviation_kind"] == "population"
    assert summary["successful_repetitions"] == 2
    assert summary["wall_clock_seconds"] == {"min": 2.0, "max": 4.0,
                                             "mean": 3.0, "standard_deviation": 1.0}
    assert summary["real_time_factor"] == {"min": 0.25, "max": 0.5,
                                           "mean": 0.375, "standard_deviation": 0.125}
    assert summary["source_seconds_per_wall_second"] == {"min": 2.0, "max": 4.0,
                                                         "mean": 3.0, "standard_deviation": 1.0}
    assert benchmark.native_variance([])["wall_clock_seconds"] is None
    assert cast(dict[str, float], benchmark.native_variance(runs[:1])[
        "wall_clock_seconds"])["standard_deviation"] == 0


def _native_baseline_report() -> dict[str, object]:
    runs: list[Mapping[str, object]] = [{"status": "succeeded", "exit_status": 0,
        "wall_clock_seconds": wall, "real_time_factor": wall / 660,
        "source_seconds_per_wall_second": 660 / wall} for wall in (2.0, 4.0, 6.0)]
    return {"schema_name": benchmark.REPORT_SCHEMA, "schema_version": "1.0",
        "run_kind": "native-cuda-nvenc", "status": "succeeded",
        "ffmpeg": {"version": "n8.1.2", "sha256": "b" * 64, "gpl_enabled": False},
        "settings": {"video_bit_rate": 8_000_000, "gop_size": 60, "gpu_pixel_conversion": False},
        "corpus": {"fingerprint_sha256": _probe().fingerprint_sha256},
        "measurements": {"repetitions": runs, "variance": benchmark.native_variance(runs)}}


@pytest.mark.parametrize("defect", [None, "kind", "status", "corpus", "mean", "runs", "nan"])
def test_native_baseline_validates_same_corpus_success_and_mean(
    tmp_path: Path, defect: str | None,
) -> None:
    report = _native_baseline_report()
    if defect == "kind":
        report["run_kind"] = "nvenc"
    elif defect == "status":
        report["status"] = "failed"
    elif defect == "corpus":
        report["corpus"] = {"fingerprint_sha256": "b" * 64}
    data = cast(dict[str, object], report["measurements"])
    if defect == "mean":
        data["variance"] = {"wall_clock_seconds": {"mean": 5.0}}
    elif defect == "runs":
        data["repetitions"] = []
    elif defect == "nan":
        cast(list[dict[str, object]], data["repetitions"])[0]["wall_clock_seconds"] = math.nan
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    if defect is None:
        assert benchmark.load_native_baseline(path, _probe(), identity={"sha256": "b" * 64},
            bit_rate=8_000_000, gop_size=60, convert_pixels=False) == 4.0
    else:
        with pytest.raises(BenchmarkError):
            benchmark.load_native_baseline(path, _probe(), identity={"sha256": "b" * 64},
                bit_rate=8_000_000, gop_size=60, convert_pixels=False)


@pytest.mark.parametrize("section,field,value,code", [
    ("ffmpeg", "sha256", "c" * 64, "baseline_ffmpeg_sha256_mismatch"),
    ("settings", "video_bit_rate", 9_000_000, "baseline_video_bit_rate_mismatch"),
    ("settings", "gop_size", 48, "baseline_gop_size_mismatch"),
    ("settings", "gpu_pixel_conversion", True, "baseline_gpu_pixel_conversion_mismatch"),
])
def test_native_baseline_rejects_binary_and_settings_mismatches(
    tmp_path: Path, section: str, field: str, value: object, code: str,
) -> None:
    report = _native_baseline_report()
    cast(dict[str, object], report[section])[field] = value
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(BenchmarkError, match=f"^{code}$"):
        benchmark.load_native_baseline(path, _probe(), identity={"sha256": "b" * 64},
            bit_rate=8_000_000, gop_size=60, convert_pixels=False)


@pytest.mark.parametrize("arm", ["native-cuda-nvenc", "native-concurrent", "native-cpu-nvenc"])
@pytest.mark.parametrize("stderr,fallback", [
    ("Failed setup for format cuda: hwaccel initialisation returned error", True),
    ("CUDA hwaccel initialization failed", True),
    ("CUDA hwaccel setup failed", True),
    ("hwaccel initialisation returned error for CUDA", True),
    ("", False),
    ("CUDA hwaccel initialization succeeded\nNVENC warning: setup failed", False),
    ("Failed setup for format vaapi: hwaccel initialisation returned error", False),
])
def test_native_cuda_fallback_is_retained_as_failed_even_on_exit_zero(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    arm: str, stderr: str, fallback: bool,
) -> None:
    def identity(_: Path) -> dict[str, object]:
        return {"version": "n8.1.2", "sha256": "b" * 64, "gpl_enabled": False}

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(b"synthetic output")
        return subprocess.CompletedProcess(command, 0, "frame=42\nprogress=end\n", stderr)

    def build_job(*_: object, **__: object) -> tuple[Callable[[], Mapping[str, object]], float]:
        return lambda: {"processed_block_count": 11, "segment_count": 3}, 0.5

    monkeypatch.setattr(benchmark, "identify_ffmpeg", identity)
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    monkeypatch.setattr(benchmark, "build_transcription_job", build_job)
    output = native_setup.parent / "render.mp4"
    if arm == "native-concurrent":
        baseline = native_setup.parent / "baseline.json"
        baseline.write_text(json.dumps(_native_baseline_report()), encoding="utf-8")
        report = benchmark.run_native_concurrent_arm((), output, ffmpeg=native_setup,
            baseline_report_path=baseline, bit_rate=8_000_000, gop_size=60,
            transcription_model=str(native_setup.parent / "model"),
            transcription_model_version="synthetic-version",
            cuda_library_directory=native_setup.parent,
            transcription_device="cuda", transcription_compute_type="float16",
            transcription_language="en")
        runs = [cast(dict[str, object], report["measurements"])]
    else:
        report = benchmark.run_native_arm((), output, ffmpeg=native_setup, arm=arm,
            repetitions=3, bit_rate=8_000_000, gop_size=60)
        data = cast(dict[str, object], report["measurements"])
        runs = cast(list[dict[str, object]], data["repetitions"])
        assert len(runs) == 3
    failed = fallback and arm != "native-cpu-nvenc"
    assert report["status"] == ("failed" if failed else "succeeded")
    for repetition in runs:
        assert repetition["status"] == report["status"]
        assert repetition["exit_status"] == 0
        assert repetition["encoded_frame_count"] == 42
        if failed:
            assert repetition["failure"] == {"code": "native_cuda_decode_fallback",
                "exception_type": "BenchmarkError", "software_fallback_used": True}
            assert repetition["quality"] is None
        else:
            assert "failure" not in repetition
            assert repetition["quality"] is not None
    captured = capsys.readouterr()
    assert captured.err == ((stderr + "\n") * len(runs) if failed else "")
    destination = native_setup.parent / "report.json"
    benchmark.write_report(destination, report)
    if stderr:
        assert stderr not in destination.read_text(encoding="utf-8")


def test_native_outputs_refuse_repository_and_existing_repetitions(tmp_path: Path) -> None:
    with pytest.raises(BenchmarkError, match="outside_repository"):
        benchmark.native_output_paths(benchmark.REPOSITORY_ROOT / "render.mp4", 3)
    for count in (0, 11):
        with pytest.raises(BenchmarkError, match="repetitions_out_of_bounds"):
            benchmark.native_output_paths(tmp_path / "render.mp4", count)


def test_native_output_collision_preflights_every_repetition(native_setup: Path) -> None:
    existing = native_setup.parent / "render.repetition-02.mp4"
    existing.write_bytes(b"existing")
    with pytest.raises(BenchmarkError, match="already_exists"):
        benchmark.native_output_paths(native_setup.parent / "render.mp4", 3)
    assert existing.read_bytes() == b"existing"
    assert not (native_setup.parent / "render.repetition-01.mp4").exists()


@pytest.mark.parametrize("arm", ["nvenc", "libx264", "concurrent", *benchmark.NATIVE_ARMS,
                                  "native-concurrent"])
def test_legacy_and_native_commands_parse_without_changing_legacy_defaults(arm: str) -> None:
    arguments = [arm, "--input-directory", "source", "--output-video", "output.mp4",
                 "--output-report", "report.json"]
    if arm.startswith("native-"):
        arguments += ["--ffmpeg", "tool.exe"]
    if arm in {"concurrent", "native-concurrent"}:
        arguments += ["--baseline-nvenc-report" if arm == "concurrent"
                      else "--baseline-native-cuda-report", "baseline.json",
                      "--transcription-model", "model", "--transcription-model-version", "v1",
                      "--cuda-library-directory", "libraries"]
    parsed = benchmark.build_parser().parse_args(arguments)
    assert parsed.command == arm and parsed.video_bit_rate == 8_000_000 and parsed.gop_size == 60
    assert parsed.block_extension == ".mp4"
    if arm in benchmark.NATIVE_ARMS:
        assert parsed.repetitions == 3
        with pytest.raises(SystemExit):
            benchmark.build_parser().parse_args([*arguments, "--repetitions", "11"])


@pytest.mark.parametrize("encode_fails,transcription_fails", [(False, False), (True, False),
                                                            (False, True)])
def test_native_concurrency_uses_mean_baseline_process_overlap_and_deferred_quality(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
    encode_fails: bool, transcription_fails: bool,
) -> None:
    baseline = native_setup.parent / "baseline.json"
    baseline.write_text(json.dumps(_native_baseline_report()), encoding="utf-8")
    transcription_calls: list[int] = []
    quality_calls: list[int] = []
    barriers: list[Barrier] = []

    def identity(_: Path) -> dict[str, object]:
        return {"version": "n8.1.2", "sha256": "b" * 64, "gpl_enabled": False}

    def build_job(*_: object, **kwargs: object) -> tuple[Callable[[], Mapping[str, object]], float]:
        assert kwargs["device"] == "cuda"

        def job() -> Mapping[str, object]:
            transcription_calls.append(1)
            if transcription_fails and len(transcription_calls) == 2:
                raise BenchmarkError("cuda_transcription_failed")
            return {"processed_block_count": 11, "segment_count": 3}

        return job, 0.5

    def encode(*_: object, **kwargs: object) -> TimedResult:
        assert kwargs["arm"] == "native-cuda-nvenc"
        values: dict[str, object] = {"status": "failed" if encode_fails else "succeeded",
            "exit_status": 9 if encode_fails else 0, "wall_clock_seconds": 20.0,
            "real_time_factor": 20 / 660, "source_seconds_per_wall_second": 33.0,
            "encoded_frame_count": 42, "output_size_bytes": 123,
            "quality": None}
        if encode_fails:
            values["failure"] = benchmark.native_failure(
                BenchmarkError("native_encoder_execution_failed"))
        return TimedResult(100.0, 120.0, values)

    def timed(barrier: Barrier, action: Callable[[], Mapping[str, object]]) -> TimedResult:
        barriers.append(barrier)
        barrier.wait(timeout=5)
        values = action()
        # Wrapper duration deliberately differs from encode process duration.
        return (TimedResult(90.0, 121.0, values) if "exit_status" in values
                else TimedResult(105.0, 113.0, values))

    def quality(*_: object) -> dict[str, object]:
        assert len(transcription_calls) == 2
        quality_calls.append(1)
        return {"ssim_mean_frame_all": 0.99, "psnr_mean_frame_average_db": 42.0}

    monkeypatch.setattr(benchmark, "identify_ffmpeg", identity)
    monkeypatch.setattr(benchmark, "build_transcription_job", build_job)
    monkeypatch.setattr(benchmark, "encode_native_video", encode)
    monkeypatch.setattr(benchmark, "_timed_after_barrier", timed)
    monkeypatch.setattr(benchmark, "measure_quality", quality)
    report = benchmark.run_native_concurrent_arm((), native_setup.parent / "render.mp4",
        ffmpeg=native_setup, baseline_report_path=baseline, bit_rate=8_000_000, gop_size=60,
        transcription_model=str(native_setup.parent / "model"),
        transcription_model_version="synthetic-version",
        cuda_library_directory=native_setup.parent, transcription_device="cuda",
        transcription_compute_type="float16", transcription_language=None)
    assert len(transcription_calls) == 2 and len(barriers) == 2 and barriers[0] is barriers[1]
    measurements = cast(dict[str, object], report["measurements"])
    assert measurements["exit_status"] == (9 if encode_fails else 0)
    if not transcription_fails:
        assert measurements["baseline_nvenc_wall_clock_seconds"] == 4.0
        assert measurements["encode_degradation_percent"] == 400.0
        assert measurements["actual_overlap_seconds"] == 8.0
        assert measurements["actual_overlap_window_seconds_from_first_job_start"] == {
            "start": 5.0, "end": 13.0}
        assert measurements["overlap_fraction_of_encode"] == 0.4
    assert report["status"] == ("failed" if encode_fails or transcription_fails else "succeeded")
    assert len(quality_calls) == (0 if encode_fails or transcription_fails else 1)
    assert str(native_setup.parent) not in json.dumps(report)
    settings = cast(dict[str, object], report["settings"])
    assert settings["transcription"] == {
        "provider": "faster-whisper", "model_id": "model", "model_version": "synthetic-version",
        "device": "cuda", "compute_type": "float16", "language": None,
        "beam_size": 5, "word_timestamps": False, "vad_filter": False,
        "local_cuda_library_directory_configured": True,
    }


@pytest.mark.parametrize("formats,convert", [(["yuv420p", "nv12"], False),
                                           (["yuv420p10le", "yuv420p"], True)])
def test_native_pixel_conversion_is_only_requested_when_source_requires_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, formats: list[str], convert: bool,
) -> None:
    class Container:
        def __init__(self, pixel_format: str) -> None:
            self.streams = SimpleNamespace(video=(SimpleNamespace(
                codec_context=SimpleNamespace(format=SimpleNamespace(name=pixel_format))),))

        def __enter__(self) -> Container:
            return self

        def __exit__(self, *_: object) -> None:
            pass

    class Av:
        @staticmethod
        def open(path: str, *, mode: str) -> Container:
            assert mode == "r"
            return Container(formats[int(Path(path).stem)])

    monkeypatch.setattr(benchmark, "_import_av", Av)
    assert benchmark.native_needs_pixel_conversion(
        (tmp_path / "0.mp4", tmp_path / "1.mp4")) is convert


def test_legacy_report_version_remains_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def environment() -> dict[str, object]:
        return {}

    monkeypatch.setattr(benchmark, "environment_summary", environment)
    for kind in ("nvenc", "libx264", "concurrent_nvenc_cuda_transcription"):
        assert benchmark.base_report(kind, _probe())["harness"] == {
            "name": benchmark.HARNESS_NAME, "version": "1.0"}


def _parallel_arguments() -> list[str]:
    return ["native-parallel", "--input-directory", "source", "--output-video", "output.mp4",
            "--output-report", "report.json", "--ffmpeg", "tool.exe"]


@pytest.mark.parametrize("extra", [[], ["--parallelism", "8,1,3", "--repetitions", "5",
                                       "--discard-verified-outputs"]])
def test_parallel_cli_defaults_and_bounds(extra: list[str]) -> None:
    args = benchmark.build_parser().parse_args([*_parallel_arguments(), *extra])
    assert args.parallelism == ((1, 3, 8) if extra else (1, 2, 3, 4))
    assert args.repetitions == (5 if extra else 2)
    assert args.discard_verified_outputs == bool(extra)
    assert args.video_bit_rate == 8_000_000 and args.gop_size == 60


@pytest.mark.parametrize("extra", [
    ["--parallelism", value] for value in ("", "0,1", "1,9", "1,1", "2,3", "1,x", "1,2,")
] + [["--repetitions", value] for value in ("0", "6", "1.5")])
def test_parallel_cli_rejects_invalid_settings(extra: list[str]) -> None:
    with pytest.raises(SystemExit):
        benchmark.build_parser().parse_args([*_parallel_arguments(), *extra])


def test_parallel_requires_explicit_ffmpeg() -> None:
    with pytest.raises(SystemExit):
        benchmark.build_parser().parse_args(_parallel_arguments()[:-2])


def _parallel_levels(report: Mapping[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], cast(dict[str, object], report["measurements"])["levels"])


def _parallel_runs(level: Mapping[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], level["repetitions"])


def _parallel_encodes(run: Mapping[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], run["encodes"])


def _fake_parallel_process(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
    if command[-1] == "-version":
        return subprocess.CompletedProcess(command, 0,
            "ffmpeg version n8.1.2\nconfiguration: --disable-gpl\n", "")
    Path(command[-1]).write_bytes(b"synthetic identical bytes")
    return subprocess.CompletedProcess(command, 0, "frame=42\n", "")


def _run_parallel(
    binary: Path, *, parallelism: tuple[int, ...] = (1, 2, 3), repetitions: int = 1,
    discard: bool = False,
) -> dict[str, object]:
    return benchmark.run_native_parallel_arm(
        (), binary.parent / "render.mp4", ffmpeg=binary,
        parallelism=parallelism, repetitions=repetitions, bit_rate=8_000_000, gop_size=60,
        discard_verified_outputs=discard,
    )


def test_parallel_process_windows_efficiency_variance_and_barrier(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(benchmark.subprocess, "run", _fake_parallel_process)
    barriers: list[Barrier] = []
    arrivals: list[int] = []
    real_barrier = Barrier

    def barrier(parties: int) -> Barrier:
        result = real_barrier(parties, action=lambda: arrivals.append(parties), timeout=5)
        barriers.append(result)
        return result

    calls: list[Path] = []

    def encode(binary: Path, concat: Path, output: Path, probe: CorpusProbe,
               **kwargs: object) -> TimedResult:
        n = int(output.name.split(".parallel-")[1].split(".")[0])
        index = int(output.name.split(".encode-")[1].split(".")[0])
        rep = int(output.stem.split("repetition-")[1])
        assert arrivals[-1] == n  # Every worker crossed the same barrier before encoding.
        assert kwargs["classify_session_refusal"] is True
        assert kwargs["arm"] == "native-cuda-nvenc"
        calls.append(output)
        output.write_bytes(b"synthetic identical bytes")
        start = 100.0 + index - 1
        wall = 10.0 if rep == 1 else 20.0
        return TimedResult(start, start + wall, {
            "status": "succeeded", "exit_status": 0, "wall_clock_seconds": wall,
            "real_time_factor": wall / 660, "source_seconds_per_wall_second": 660 / wall,
            "encoded_frame_count": 42, "output_size_bytes": output.stat().st_size,
            "quality": None,
        })

    monkeypatch.setattr(benchmark, "Barrier", barrier)
    monkeypatch.setattr(benchmark, "encode_native_video", encode)
    report = _run_parallel(native_setup, parallelism=(2, 1), repetitions=2)
    assert report["status"] == "succeeded"
    assert arrivals == [1, 1, 2, 2] and len(barriers) == 4 and len(calls) == 6
    first, second = _parallel_levels(report)
    variance = cast(dict[str, object], first["variance"])
    assert variance["wall_clock_seconds"] == {
        "min": 10.0, "max": 20.0, "mean": 15.0, "standard_deviation": 5.0}
    assert variance["source_seconds_per_wall_second"] == {
        "min": 33.0, "max": 66.0, "mean": 49.5, "standard_deviation": 16.5}
    run = _parallel_runs(second)[0]
    aggregate = cast(dict[str, object], run["aggregate"])
    assert aggregate["window_seconds_from_group_start"] == {"start": 0.0, "end": 11.0}
    assert aggregate["source_seconds_per_wall_second"] == 120.0
    assert aggregate["scaling_efficiency"] == 120 / (2 * 49.5)
    assert _parallel_encodes(run)[1]["start_seconds_from_group_start"] == 1.0
    assert _parallel_encodes(run)[1]["end_seconds_from_group_start"] == 11.0
    assert report["harness"] == {"name": benchmark.HARNESS_NAME, "version": "1.2"}


@pytest.mark.parametrize("diagnostic,code", [
    ("OpenEncodeSessionEx failed: out of memory", "nvenc_session_unavailable"),
    ("No capable devices found", "nvenc_session_unavailable"),
    ("synthetic encoder failure", "native_encoder_execution_failed"),
    ("Failed setup for format cuda", "native_cuda_decode_fallback"),
])
def test_parallel_refusal_and_fallback_continue_without_retry(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, diagnostic: str, code: str,
) -> None:
    calls: list[str] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = _fake_parallel_process(command, **kwargs)
        if command[-1] != "-version":
            calls.append(command[-1])
        if ".parallel-2.encode-1." in command[-1]:
            return subprocess.CompletedProcess(command,
                0 if code == "native_cuda_decode_fallback" else 1, result.stdout, diagnostic)
        return result

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    report = _run_parallel(native_setup, discard=True)
    levels = _parallel_levels(report)
    failed = _parallel_runs(levels[1])[0]
    assert report["status"] == "failed" and len(calls) == 6
    failure = _parallel_encodes(failed)[0]
    assert cast(dict[str, object], failure["failure"])["code"] == code
    assert failure["exit_status"] == (0 if code == "native_cuda_decode_fallback" else 1)
    assert failure["output_sha256"] is not None and failure["output_discarded"] is False
    assert cast(dict[str, object], failed["aggregate"])["source_seconds_per_wall_second"] is None
    assert cast(dict[str, object], levels[1]["variance"])["successful_repetitions"] == 0
    assert _parallel_runs(levels[2])[0]["status"] == "succeeded"
    assert len(list(native_setup.parent.glob("render.*.mp4"))) == 2
    encoded = json.dumps(report)
    assert diagnostic not in encoded and str(native_setup.parent) not in encoded


@pytest.mark.parametrize("discard", [False, True])
def test_parallel_hash_identity_quality_fallback_and_discard(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, discard: bool,
) -> None:
    calls: list[Path] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = _fake_parallel_process(command, **kwargs)
        if ".parallel-2.encode-2." in command[-1]:
            Path(command[-1]).write_bytes(b"different synthetic bytes")
        return result

    def quality(_: Sequence[Path], output: Path, __: CorpusProbe) -> dict[str, object]:
        calls.append(output)
        return {"ssim_mean_frame_all": 0.98, "psnr_mean_frame_average_db": 40.0}

    source = native_setup.parent / "source.mp4"
    source.write_bytes(b"synthetic identical bytes")
    unrelated = native_setup.parent / "unrelated.mp4"
    unrelated.write_bytes(source.read_bytes())
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    monkeypatch.setattr(benchmark, "measure_quality", quality)
    report = benchmark.run_native_parallel_arm(
        (source,), native_setup.parent / "render.mp4", ffmpeg=native_setup,
        parallelism=(1, 2), repetitions=1, bit_rate=8_000_000, gop_size=60,
        discard_verified_outputs=discard,
    )
    levels = _parallel_levels(report)
    identical, different = _parallel_encodes(_parallel_runs(levels[1])[0])
    assert identical["is_reference"] is False and different["is_reference"] is False
    assert identical["quality_equivalent"] is True and identical["quality"] is None
    assert identical["output_discarded"] is discard
    assert different["quality_equivalent"] is False and different["output_discarded"] is False
    assert different["quality"] == {"ssim_mean_frame_all": 0.98, "psnr_mean_frame_average_db": 40.0}
    assert len(calls) == 1 and calls[0].exists()
    assert source.read_bytes() == unrelated.read_bytes() == b"synthetic identical bytes"
    data = cast(dict[str, object], report["measurements"])
    assert data["reference_output_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(list(native_setup.parent.glob("render.*.mp4"))) == (2 if discard else 3)
    assert cast(dict[str, object], report["ffmpeg"]) == {
        "version": "n8.1.2", "sha256": hashlib.sha256(native_setup.read_bytes()).hexdigest(),
        "gpl_enabled": False}
    destination = native_setup.parent / "report.json"
    benchmark.write_report(destination, report)
    assert str(native_setup.parent) not in destination.read_text(encoding="utf-8")


@pytest.mark.parametrize("error_type,code", [
    (BenchmarkError, "native_output_reservation_failed"),
    (RuntimeError, "native_parallel_encode_failed"),
])
def test_parallel_worker_exception_retains_unowned_file_and_other_workers_finish(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception], code: str,
) -> None:
    monkeypatch.setattr(benchmark.subprocess, "run", _fake_parallel_process)
    original = benchmark.encode_native_video
    outsider = native_setup.parent / "render.parallel-2.encode-1.repetition-01.mp4"

    def encode(binary: Path, concat: Path, output: Path, probe: CorpusProbe, *,
               arm: str, bit_rate: int, gop_size: int, convert_pixels: bool,
               classify_session_refusal: bool = False) -> TimedResult:
        if output == outsider:
            output.write_bytes(b"synthetic identical bytes")
            raise error_type(f"native_output_reservation_failed:{output}")
        return original(binary, concat, output, probe, arm=arm, bit_rate=bit_rate,
                        gop_size=gop_size, convert_pixels=convert_pixels,
                        classify_session_refusal=classify_session_refusal)

    monkeypatch.setattr(benchmark, "encode_native_video", encode)
    report = _run_parallel(native_setup, discard=True)
    assert report["status"] == "failed" and outsider.exists()
    failure = _parallel_encodes(_parallel_runs(_parallel_levels(report)[1])[0])[0]
    assert failure["output_sha256"] is None and failure["exit_status"] is None
    assert failure["timing_scope"] == "worker_exception"
    assert cast(dict[str, object], failure["failure"])["code"] == code
    assert _parallel_runs(_parallel_levels(report)[2])[0]["status"] == "succeeded"
    assert str(outsider) not in json.dumps(report)


@pytest.mark.parametrize("reference_repetition", [1, 2])
def test_parallel_reference_survives_discard(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, reference_repetition: int,
) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = _fake_parallel_process(command, **kwargs)
        if reference_repetition == 2 and ".parallel-1.encode-1.repetition-01." in command[-1]:
            return subprocess.CompletedProcess(command, 1, result.stdout,
                                               "OpenEncodeSessionEx failed")
        return result

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    report = _run_parallel(native_setup, parallelism=(1, 2), repetitions=2, discard=True)
    baseline_runs = _parallel_runs(_parallel_levels(report)[0])
    reference = _parallel_encodes(baseline_runs[reference_repetition - 1])[0]
    assert reference["is_reference"] is True
    assert reference["byte_identical_to_reference"] is None
    assert reference["quality_equivalent"] is None and reference["quality"] is None
    assert reference["output_discarded"] is False
    output = native_setup.parent / (
        f"render.parallel-1.encode-1.repetition-{reference_repetition:02d}.mp4")
    assert hashlib.sha256(output.read_bytes()).hexdigest() == reference["output_sha256"]
    data = cast(dict[str, object], report["measurements"])
    assert data["reference_output_sha256"] == reference["output_sha256"]
    encodes = [encode for level in _parallel_levels(report)
               for run in _parallel_runs(level) for encode in _parallel_encodes(run)]
    assert sum(encode["is_reference"] is True for encode in encodes) == 1
    assert all(encode["output_discarded"] is True for encode in encodes
               if encode is not reference and encode["status"] == "succeeded")
    assert len(list(native_setup.parent.glob("render.*.mp4"))) == reference_repetition


def test_parallel_barrier_timeout_records_failures_and_continues(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[tuple[int, float | None]] = []
    calls: list[str] = []

    class ExpiringBarrier(Barrier):
        def wait(self, timeout: float | None = None) -> int:
            waits.append((self.parties, timeout))
            # Expire immediately for N=2; exercise a real broken barrier without a delay.
            return super().wait(timeout=0 if self.parties == 2 else timeout)

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command[-1])
        return _fake_parallel_process(command, **kwargs)

    monkeypatch.setattr(benchmark, "Barrier", ExpiringBarrier)
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    report = _run_parallel(native_setup, discard=True)
    assert sorted(waits) == [(1, 60), (2, 60), (2, 60), (3, 60), (3, 60), (3, 60)]
    assert len(calls) == 5  # Identity probe, one baseline, three later encodes; no retry.
    assert not any(".parallel-2." in call for call in calls)
    first, failed, later = [_parallel_runs(level)[0] for level in _parallel_levels(report)]
    assert first["status"] == later["status"] == "succeeded"
    assert report["status"] == failed["status"] == "failed"
    aggregate = cast(dict[str, object], failed["aggregate"])
    assert aggregate["source_seconds_per_wall_second"] is None
    assert aggregate["scaling_efficiency"] is None
    for encode in _parallel_encodes(failed):
        assert encode["status"] == "failed" and encode["timing_scope"] == "worker_exception"
        assert cast(dict[str, object], encode["failure"])["code"] == (
            "native_parallel_barrier_failed")
        assert encode["exit_status"] is None and encode["output_sha256"] is None
        assert encode["output_discarded"] is False


def test_parallel_failed_baseline_has_no_reference_or_efficiency(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = _fake_parallel_process(command, **kwargs)
        if ".parallel-1." in command[-1]:
            return subprocess.CompletedProcess(
                command, 1, result.stdout, "No capable devices found")
        return result

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    report = _run_parallel(native_setup, discard=True)
    data = cast(dict[str, object], report["measurements"])
    assert data["reference_output_sha256"] is None
    assert data["baseline_mean_source_seconds_per_wall_second"] is None
    for level in _parallel_levels(report):
        repetition = _parallel_runs(level)[0]
        assert cast(dict[str, object], repetition["aggregate"])["scaling_efficiency"] is None
        assert all(e["output_discarded"] is False for e in _parallel_encodes(repetition))
    assert report["status"] == "failed"


def test_parallel_preflights_all_outputs_and_refuses_collisions(native_setup: Path) -> None:
    output = native_setup.parent / "render.mp4"
    existing = native_setup.parent / "render.parallel-3.encode-3.repetition-02.mp4"
    existing.write_bytes(b"existing synthetic bytes")
    with pytest.raises(BenchmarkError, match="already_exists"):
        benchmark.parallel_output_paths(output, (1, 2, 3), 2)
    assert list(native_setup.parent.glob("render.*.mp4")) == [existing]
    assert existing.read_bytes() == b"existing synthetic bytes"


@pytest.mark.parametrize("path", [Path("relative.mp4"), benchmark.REPOSITORY_ROOT / "render.mp4"])
def test_parallel_rejects_nonexternal_outputs(path: Path) -> None:
    with pytest.raises(BenchmarkError, match="absolute|outside_repository"):
        benchmark.parallel_output_paths(path, (1, 2), 2)


@pytest.mark.parametrize("gpl", [False, True])
def test_parallel_cli_dispatch_identity_and_gpl_refusal(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, gpl: bool,
) -> None:
    original_input = benchmark.require_external_input_directory

    def input_directory(path: Path) -> Path:
        return original_input(path, repository_root=native_setup.parent / "repository")

    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if gpl:
            return subprocess.CompletedProcess(command, 0,
                "ffmpeg version n8.1.2\nconfiguration: --enable-gpl\n", "")
        return _fake_parallel_process(command, **kwargs)

    source = native_setup.parent / "source"
    source.mkdir()
    (source / "block.mp4").write_bytes(b"synthetic source")
    report = native_setup.parent / "report.json"
    monkeypatch.setattr(benchmark, "require_external_input_directory", input_directory)
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    result = benchmark.main(["native-parallel", "--input-directory", str(source),
        "--output-video", str(native_setup.parent / "render.mp4"), "--output-report", str(report),
        "--ffmpeg", str(native_setup), "--parallelism", "1,2", "--repetitions", "1"])
    assert result == (2 if gpl else 0)
    assert len(calls) == (1 if gpl else 4)
    assert report.exists() is not gpl
    assert (source / "block.mp4").read_bytes() == b"synthetic source"


@pytest.mark.parametrize("fault", ["hash", "changed", "quality", "source_alias"])
def test_parallel_verification_faults_preserve_files_and_continue(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    source = native_setup.parent / "source.mp4"
    source.write_bytes(b"synthetic identical bytes")
    affected = native_setup.parent / "render.parallel-2.encode-2.repetition-01.mp4"
    original_digest = hashlib.file_digest

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[-1] == str(affected) and fault == "source_alias":
            # Model a substituted source alias after the native encoder reserves a file.
            # The empty reservation is the only file replaced, never the source.
            affected.unlink()
            affected.hardlink_to(source)
            return subprocess.CompletedProcess(command, 0, "frame=42\n", "")
        result = _fake_parallel_process(command, **kwargs)
        if command[-1] == str(affected) and fault == "quality":
            affected.write_bytes(b"different synthetic bytes")
        return result

    def digest(handle: BufferedReader, algorithm: str) -> object:
        if getattr(handle, "name", None) == str(affected):
            if fault == "hash":
                raise OSError(str(affected))
            result = original_digest(handle, algorithm)
            if fault == "changed":
                affected.write_bytes(b"changed synthetic bytes after hashing")
            return result
        return original_digest(handle, algorithm)

    def quality(*_: object) -> dict[str, object]:
        raise RuntimeError(str(affected))

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    monkeypatch.setattr(benchmark.hashlib, "file_digest", digest)
    monkeypatch.setattr(benchmark, "measure_quality", quality)
    report = _run_parallel(native_setup, discard=True)
    failure = _parallel_encodes(_parallel_runs(_parallel_levels(report)[1])[0])[1]
    assert failure["status"] == "failed" and failure["output_discarded"] is False
    assert affected.exists() and source.read_bytes() == b"synthetic identical bytes"
    assert report["status"] == "failed"
    assert _parallel_runs(_parallel_levels(report)[2])[0]["status"] == "succeeded"
    assert str(affected) not in json.dumps(report)


def test_parallel_uses_later_successful_baseline_repetition_without_retry(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command[-1])
        result = _fake_parallel_process(command, **kwargs)
        if ".parallel-1.encode-1.repetition-01." in command[-1]:
            return subprocess.CompletedProcess(command, 1, result.stdout,
                                               "OpenEncodeSessionEx failed")
        return result

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    report = _run_parallel(native_setup, parallelism=(1, 2), repetitions=2)
    first, second = _parallel_levels(report)
    assert cast(dict[str, object], first["variance"])["successful_repetitions"] == 1
    assert _parallel_runs(first)[0]["status"] == "failed"
    assert _parallel_runs(first)[1]["status"] == "succeeded"
    assert all(run["status"] == "succeeded" for run in _parallel_runs(second))
    assert len(calls) == 7  # One identity probe, six encodes; no retry.


@pytest.mark.parametrize("command", ["native-parallel", *benchmark.NATIVE_ARMS])
def test_session_refusal_classification_is_opt_in_for_earlier_arms(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch, command: str,
) -> None:
    def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = _fake_parallel_process(arguments, **kwargs)
        if arguments[-1] == "-version":
            return result
        return subprocess.CompletedProcess(arguments, 1, result.stdout, "No capable devices found")

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    if command == "native-parallel":
        report = _run_parallel(native_setup, parallelism=(1,))
        encode = _parallel_encodes(_parallel_runs(_parallel_levels(report)[0])[0])[0]
    else:
        report = benchmark.run_native_arm((), native_setup.parent / "render.mp4",
            ffmpeg=native_setup, arm=command, repetitions=1, bit_rate=8_000_000, gop_size=60)
        data = cast(dict[str, object], report["measurements"])
        encode = cast(list[dict[str, object]], data["repetitions"])[0]
    assert cast(dict[str, object], encode["failure"])["code"] == (
        "nvenc_session_unavailable" if command == "native-parallel"
        else "native_encoder_execution_failed")
    assert report["harness"] == {"name": benchmark.HARNESS_NAME,
                                 "version": "1.2" if command == "native-parallel" else "1.1"}


def test_parallel_hash_failure_does_not_hide_session_refusal(
    native_setup: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = _fake_parallel_process(command, **kwargs)
        if ".parallel-2.encode-1." in command[-1]:
            # A failed process whose reserved output is also unavailable to the verifier.
            Path(command[-1]).unlink()
            return subprocess.CompletedProcess(command, 1, result.stdout,
                                               "OpenEncodeSessionEx failed")
        return result

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    report = _run_parallel(native_setup)
    failure = _parallel_encodes(_parallel_runs(_parallel_levels(report)[1])[0])[0]
    assert cast(dict[str, object], failure["failure"])["code"] == "nvenc_session_unavailable"
    assert cast(dict[str, object], failure["verification_failure"])["code"] == (
        "parallel_output_verification_failed")
    assert _parallel_runs(_parallel_levels(report)[2])[0]["status"] == "succeeded"
