from __future__ import annotations

import json
import math
import subprocess
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
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


def test_harness_is_directly_executable_with_three_finite_subcommands() -> None:
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
    assert "{nvenc,libx264,concurrent}" in result.stdout


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

    model = tmp_path / "model"
    model.mkdir()
    with pytest.raises(BenchmarkError, match="cuda_library_directory_unavailable"):
        benchmark.build_transcription_job(
            (),
            model=str(model.resolve()),
            cuda_library_directory=tmp_path / "missing-cuda",
            device="cuda",
            compute_type="float16",
            language=None,
        )
