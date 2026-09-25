"""Bounded, qualification-only NVENC rendering benchmark.

The harness reads closed media blocks and writes benchmark artifacts outside the
repository. It is measurement tooling only: it does not implement StageFlow rendering,
Assembly, Durable Operations, or worker capability matching.

Native arms require an explicit --ffmpeg executable and refuse GPL configurations.
Standalone outputs use <stem>.repetition-01.mp4 through the requested repetition
count (default 3, maximum 10); failed outputs are retained. All arms define
real_time_factor as process wall time / source duration (lower is faster), and
source_seconds_per_wall_second as source duration / process wall time (speed).
Native variance covers both ratios. Quality time is excluded
from encode timing. The native concurrency arm takes --baseline-native-cuda-report
from a fully successful standalone CUDA arm with matching binary hash and encode
settings, and uses its mean process wall time. CUDA hwaccel setup failures in stderr
invalidate a run even on exit 0; failed process diagnostics go only to the terminal.
Supply a non-private model directory basename and model-version label for reports.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from itertools import chain, zip_longest
from pathlib import Path
from threading import Barrier
from typing import Any, cast

HARNESS_NAME = "stageflow-nvenc-render-benchmark"
HARNESS_VERSION = "1.1"
LEGACY_HARNESS_VERSION = "1.0"
REPORT_SCHEMA = "stageflow.render-benchmark-report"
SCHEMA_VERSION = "1.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MAX_BLOCKS = 100
MAX_BLOCK_BYTES = 16 * 1024 * 1024 * 1024
MAX_TOTAL_DURATION_SECONDS = 8 * 60 * 60
DEFAULT_VIDEO_BIT_RATE = 8_000_000
DEFAULT_GOP_SIZE = 60
DEFAULT_PIXEL_FORMAT = "yuv420p"
MAX_REPETITIONS = 10
NATIVE_ARMS = ("native-cpu-nvenc", "native-cuda-nvenc")
SAFE_EXTENSION = re.compile(r"^\.[A-Za-z0-9]{1,10}$")
SSIM_VALUE = re.compile(r"(?:^|\s)All:([0-9]+(?:\.[0-9]+)?)")
PSNR_VALUE = re.compile(r"(?:^|\s)psnr_avg:([0-9]+(?:\.[0-9]+)?)")


class BenchmarkError(RuntimeError):
    """An operator-correctable benchmark failure with a safe message."""


@dataclass(frozen=True, slots=True)
class CorpusProbe:
    block_count: int
    total_duration_seconds: float
    width: int
    height: int
    frame_rate: Fraction
    minimum_source_frame_rate: Fraction
    maximum_source_frame_rate: Fraction
    fingerprint_sha256: str


@dataclass(frozen=True, slots=True)
class TimedResult:
    started: float
    ended: float
    value: Mapping[str, object]

    @property
    def elapsed_seconds(self) -> float:
        return self.ended - self.started


def _import_av() -> Any:
    try:
        return importlib.import_module("av")
    except (ImportError, OSError) as exc:
        raise BenchmarkError("pyav_runtime_unavailable") from exc


def _is_inside(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def require_external_input_directory(
    path: Path, *, repository_root: Path = REPOSITORY_ROOT
) -> Path:
    if not path.is_absolute():
        raise BenchmarkError("input_directory_must_be_absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BenchmarkError("input_directory_unavailable") from exc
    if not resolved.is_dir():
        raise BenchmarkError("input_directory_unavailable")
    if _is_inside(resolved, repository_root.resolve(strict=False)):
        raise BenchmarkError("input_directory_must_be_outside_repository")
    return resolved


def require_external_new_file(
    path: Path,
    *,
    suffixes: frozenset[str],
    repository_root: Path = REPOSITORY_ROOT,
) -> Path:
    if not path.is_absolute():
        raise BenchmarkError("output_path_must_be_absolute")
    resolved = path.resolve(strict=False)
    if _is_inside(resolved, repository_root.resolve(strict=False)):
        raise BenchmarkError("output_path_must_be_outside_repository")
    if resolved.suffix.casefold() not in suffixes:
        raise BenchmarkError("output_path_extension_unsupported")
    if resolved.exists():
        raise BenchmarkError("output_path_already_exists")
    return resolved


def discover_blocks(input_directory: Path, extension: str) -> tuple[Path, ...]:
    normalized = extension if extension.startswith(".") else f".{extension}"
    if SAFE_EXTENSION.fullmatch(normalized) is None:
        raise BenchmarkError("block_extension_invalid")
    blocks = tuple(
        sorted(
            (
                item.resolve(strict=True)
                for item in input_directory.iterdir()
                if item.is_file() and item.suffix.casefold() == normalized.casefold()
            ),
            key=lambda item: item.name.casefold(),
        )
    )
    if not 1 <= len(blocks) <= MAX_BLOCKS:
        raise BenchmarkError("block_count_out_of_bounds")
    for block in blocks:
        if block.parent != input_directory or block.is_symlink():
            raise BenchmarkError("media_block_must_be_direct_regular_file")
        size = block.stat().st_size
        if not 0 < size <= MAX_BLOCK_BYTES:
            raise BenchmarkError("media_block_size_out_of_bounds")
    return blocks


def _video_stream(container: Any) -> Any:
    streams = tuple(container.streams.video)
    if len(streams) != 1:
        raise BenchmarkError("each_block_requires_exactly_one_video_stream")
    return streams[0]


def _stream_duration_seconds(container: Any, stream: Any) -> float:
    if stream.duration is not None and stream.time_base is not None:
        value = float(stream.duration * stream.time_base)
    elif container.duration is not None:
        av = _import_av()
        value = float(container.duration) / float(av.time_base)
    else:
        raise BenchmarkError("media_duration_unavailable")
    if not math.isfinite(value) or value <= 0:
        raise BenchmarkError("media_duration_invalid")
    return value


def probe_corpus(blocks: Sequence[Path]) -> CorpusProbe:
    av = _import_av()
    durations: list[float] = []
    shape: tuple[int, int] | None = None
    frame_rate: Fraction | None = None
    observed_rates: list[Fraction] = []
    fingerprint = hashlib.sha256()
    for ordinal, block in enumerate(blocks, start=1):
        try:
            with av.open(str(block), mode="r") as container:
                stream = _video_stream(container)
                duration = _stream_duration_seconds(container, stream)
                rate = stream.average_rate
                if rate is None or rate <= 0:
                    raise BenchmarkError("video_frame_rate_unavailable")
                current_shape = (
                    int(stream.codec_context.width),
                    int(stream.codec_context.height),
                )
                current_rate = Fraction(rate)
        except BenchmarkError:
            raise
        except (OSError, ValueError) as exc:
            raise BenchmarkError("media_block_probe_failed") from exc
        if shape is None:
            shape = current_shape
            frame_rate = current_rate
        else:
            assert frame_rate is not None
            if shape != current_shape:
                raise BenchmarkError("media_blocks_require_matching_video_geometry")
            if abs((float(current_rate) / float(frame_rate)) - 1) > 0.01:
                raise BenchmarkError("media_block_frame_rate_variation_out_of_bounds")
        observed_rates.append(current_rate)
        durations.append(duration)
        fingerprint.update(
            f"{ordinal}:{block.stat().st_size}:{duration:.6f}:"
            f"{current_shape[0]}x{current_shape[1]}:{current_rate}\n".encode()
        )
    total_duration = sum(durations)
    if total_duration > MAX_TOTAL_DURATION_SECONDS:
        raise BenchmarkError("corpus_duration_out_of_bounds")
    assert shape is not None and frame_rate is not None
    return CorpusProbe(
        block_count=len(blocks),
        total_duration_seconds=total_duration,
        width=shape[0],
        height=shape[1],
        frame_rate=frame_rate,
        minimum_source_frame_rate=min(observed_rates),
        maximum_source_frame_rate=max(observed_rates),
        fingerprint_sha256=fingerprint.hexdigest(),
    )


def _encoder_options(encoder: str) -> dict[str, str]:
    if encoder == "h264_nvenc":
        return {"preset": "p4", "rc": "vbr"}
    if encoder == "libx264":
        return {"preset": "medium"}
    raise BenchmarkError("encoder_not_allowed")


def encoder_settings(encoder: str, bit_rate: int, gop_size: int) -> dict[str, object]:
    if not 100_000 <= bit_rate <= 100_000_000:
        raise BenchmarkError("video_bit_rate_out_of_bounds")
    if not 1 <= gop_size <= 1_000:
        raise BenchmarkError("gop_size_out_of_bounds")
    return {
        "encoder": encoder,
        "video_bit_rate": bit_rate,
        "gop_size": gop_size,
        "pixel_format": DEFAULT_PIXEL_FORMAT,
        "container": "mp4",
        "audio_included": False,
        "encoder_options": _encoder_options(encoder),
    }


def _source_frames(blocks: Sequence[Path], probe: CorpusProbe) -> Iterator[Any]:
    av = _import_av()
    time_base = Fraction(probe.frame_rate.denominator, probe.frame_rate.numerator)
    ordinal = 0
    for block in blocks:
        try:
            with av.open(str(block), mode="r") as container:
                stream = _video_stream(container)
                for frame in container.decode(stream):
                    normalized = frame.reformat(
                        width=probe.width,
                        height=probe.height,
                        format=DEFAULT_PIXEL_FORMAT,
                    )
                    normalized.pts = ordinal
                    normalized.time_base = time_base
                    ordinal += 1
                    yield normalized
        except BenchmarkError:
            raise
        except (OSError, ValueError) as exc:
            raise BenchmarkError("media_block_decode_failed") from exc


def encode_video(
    blocks: Sequence[Path],
    output_path: Path,
    probe: CorpusProbe,
    *,
    encoder: str,
    bit_rate: int,
    gop_size: int,
) -> dict[str, object]:
    av = _import_av()
    settings = encoder_settings(encoder, bit_rate, gop_size)
    if encoder not in av.codecs_available:
        raise BenchmarkError(f"encoder_unavailable:{encoder}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = output_path.with_name(f".{output_path.name}.{os.getpid()}.partial.mp4")
    if partial_path.exists():
        raise BenchmarkError("partial_output_path_already_exists")
    frame_count = 0
    started = time.perf_counter()
    try:
        with av.open(str(partial_path), mode="w", format="mp4") as output:
            stream = output.add_stream(encoder, rate=probe.frame_rate)
            stream.width = probe.width
            stream.height = probe.height
            stream.pix_fmt = DEFAULT_PIXEL_FORMAT
            stream.bit_rate = bit_rate
            stream.gop_size = gop_size
            stream.options = cast(dict[str, str], settings["encoder_options"])
            for frame in _source_frames(blocks, probe):
                for packet in stream.encode(frame):
                    output.mux(packet)
                frame_count += 1
            for packet in stream.encode():
                output.mux(packet)
        os.replace(partial_path, output_path)
    except BenchmarkError:
        partial_path.unlink(missing_ok=True)
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        partial_path.unlink(missing_ok=True)
        raise BenchmarkError(f"encoder_execution_failed:{encoder}") from exc
    elapsed = time.perf_counter() - started
    if elapsed <= 0 or frame_count <= 0:
        raise BenchmarkError("encoder_produced_no_frames")
    return {
        "wall_clock_seconds": elapsed,
        "real_time_factor": elapsed / probe.total_duration_seconds,
        "source_seconds_per_wall_second": probe.total_duration_seconds / elapsed,
        "output_size_bytes": output_path.stat().st_size,
        "encoded_frame_count": frame_count,
    }


def _output_frames(path: Path, probe: CorpusProbe) -> Iterator[Any]:
    av = _import_av()
    time_base = Fraction(probe.frame_rate.denominator, probe.frame_rate.numerator)
    with av.open(str(path), mode="r") as container:
        stream = _video_stream(container)
        for ordinal, frame in enumerate(container.decode(stream)):
            normalized = frame.reformat(
                width=probe.width,
                height=probe.height,
                format=DEFAULT_PIXEL_FORMAT,
            )
            normalized.pts = ordinal
            normalized.time_base = time_base
            yield normalized


def _metric_values(path: Path, pattern: re.Pattern[str]) -> list[float]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BenchmarkError("quality_metric_output_unavailable") from exc
    values = [float(match.group(1)) for match in pattern.finditer(text)]
    if not values or any(not math.isfinite(value) for value in values):
        raise BenchmarkError("quality_metric_output_invalid")
    return values


def _quality_metric(
    blocks: Sequence[Path],
    output_path: Path,
    probe: CorpusProbe,
    *,
    filter_name: str,
    pattern: re.Pattern[str],
) -> tuple[float, int]:
    av = _import_av()
    if filter_name not in av.filter.filters_available:
        raise BenchmarkError(f"quality_filter_unavailable:{filter_name}")
    source = _source_frames(blocks, probe)
    encoded = _output_frames(output_path, probe)
    try:
        first_source = next(source)
        first_encoded = next(encoded)
    except StopIteration as exc:
        raise BenchmarkError("quality_comparison_requires_frames") from exc
    with tempfile.TemporaryDirectory(prefix="stageflow-render-quality-") as directory:
        stats_path = Path(directory) / f"{filter_name}.log"
        graph = av.filter.Graph()
        source_input = graph.add_buffer(template=first_source, name="source")
        encoded_input = graph.add_buffer(template=first_encoded, name="encoded")
        metric = graph.add(filter_name, stats_file=str(stats_path))
        sink = graph.add("buffersink")
        source_input.link_to(metric, 0, 0)
        encoded_input.link_to(metric, 0, 1)
        metric.link_to(sink)
        graph.configure()
        count = 0
        sentinel = object()
        for source_frame, encoded_frame in zip_longest(
            chain((first_source,), source),
            chain((first_encoded,), encoded),
            fillvalue=sentinel,
        ):
            if source_frame is sentinel or encoded_frame is sentinel:
                raise BenchmarkError("quality_frame_count_mismatch")
            source_input.push(source_frame)
            encoded_input.push(encoded_frame)
            sink.pull()
            count += 1
        source_input.push(None)
        encoded_input.push(None)
        del sink, metric, encoded_input, source_input, graph
        gc.collect()
        values = _metric_values(stats_path, pattern)
    if len(values) != count:
        raise BenchmarkError("quality_metric_frame_count_mismatch")
    return sum(values) / len(values), count


def measure_quality(
    blocks: Sequence[Path], output_path: Path, probe: CorpusProbe
) -> dict[str, object]:
    started = time.perf_counter()
    with ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="render-quality"
    ) as pool:
        ssim_future = pool.submit(
            _quality_metric,
            blocks,
            output_path,
            probe,
            filter_name="ssim",
            pattern=SSIM_VALUE,
        )
        psnr_future = pool.submit(
            _quality_metric,
            blocks,
            output_path,
            probe,
            filter_name="psnr",
            pattern=PSNR_VALUE,
        )
        ssim, ssim_frames = ssim_future.result()
        psnr, psnr_frames = psnr_future.result()
    if ssim_frames != psnr_frames:
        raise BenchmarkError("quality_metric_frame_count_mismatch")
    return {
        "reference": "source_recording_blocks",
        "ssim_mean_frame_all": ssim,
        "psnr_mean_frame_average_db": psnr,
        "compared_frame_count": ssim_frames,
        "analysis_wall_clock_seconds": time.perf_counter() - started,
    }


def _gpu_summary() -> dict[str, object]:
    try:
        completed = subprocess.run(
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
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}
    if completed.returncode != 0:
        return {"available": False}
    first = completed.stdout.splitlines()[0].split(",", maxsplit=1)
    return {
        "available": True,
        "name": first[0].strip(),
        "driver_version": first[1].strip() if len(first) == 2 else "unreported",
    }


def environment_summary() -> dict[str, object]:
    av = _import_av()
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "pyav": av.__version__,
        "libavcodec": ".".join(
            str(value) for value in av.library_versions["libavcodec"]
        ),
        "gpu": _gpu_summary(),
    }


def corpus_summary(probe: CorpusProbe) -> dict[str, object]:
    return {
        "block_count": probe.block_count,
        "total_duration_seconds": probe.total_duration_seconds,
        "width": probe.width,
        "height": probe.height,
        "frame_rate": str(probe.frame_rate),
        "source_frame_rate_range": {
            "minimum": str(probe.minimum_source_frame_rate),
            "maximum": str(probe.maximum_source_frame_rate),
        },
        "frame_rate_normalization": "normalized_to_first_block_average_rate",
        "fingerprint_sha256": probe.fingerprint_sha256,
        "reference": "source_recording_blocks",
    }


def limitations() -> list[str]:
    return [
        "single_corpus_single_machine_not_throughput_or_hardware_qualification",
        "finite_single_runs_do_not_establish_thermal_steady_state",
        "concurrent_transcription_overlap_is_narrow_relative_to_encode",
        "video_only_benchmark_output_excludes_audio_encode_cost_and_size",
        "mean_frame_metrics_are_not_a_product_output_quality_threshold",
    ]


def base_report(kind: str, probe: CorpusProbe) -> dict[str, object]:
    return {
        "schema_name": REPORT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "harness": {
            "name": HARNESS_NAME,
            "version": HARNESS_VERSION if kind.startswith("native-") else LEGACY_HARNESS_VERSION,
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "epistemic_kind": "external_test_evidence",
        "authority_use_prohibited": True,
        "run_kind": kind,
        "status": "running",
        "corpus": corpus_summary(probe),
        "environment": environment_summary(),
        "limitations": limitations(),
    }


def run_encode_arm(
    blocks: Sequence[Path],
    output_path: Path,
    *,
    encoder: str,
    bit_rate: int,
    gop_size: int,
) -> dict[str, object]:
    probe = probe_corpus(blocks)
    report = base_report("nvenc" if encoder == "h264_nvenc" else "libx264", probe)
    report["settings"] = encoder_settings(encoder, bit_rate, gop_size)
    try:
        measurements = encode_video(
            blocks,
            output_path,
            probe,
            encoder=encoder,
            bit_rate=bit_rate,
            gop_size=gop_size,
        )
        measurements["quality"] = measure_quality(blocks, output_path, probe)
        report["measurements"] = measurements
        report["status"] = "succeeded"
    except BenchmarkError as exc:
        report["status"] = "failed"
        report["failure"] = {
            "code": str(exc).split(":", maxsplit=1)[0],
            "exception_type": type(exc).__name__,
            "software_fallback_used": False,
        }
    return report


def _load_baseline(
    path: Path, probe: CorpusProbe, *, kind: str = "nvenc"
) -> Mapping[str, object]:
    if not path.is_absolute():
        raise BenchmarkError("baseline_report_must_be_absolute")
    try:
        raw: object = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError("baseline_report_unavailable") from exc
    if not isinstance(raw, Mapping):
        raise BenchmarkError("baseline_report_invalid")
    report = cast(Mapping[str, object], raw)
    corpus_value = report.get("corpus")
    corpus = (
        cast(Mapping[str, object], corpus_value)
        if isinstance(corpus_value, Mapping)
        else None
    )
    if (
        report.get("schema_name") != REPORT_SCHEMA
        or report.get("run_kind") != kind
        or report.get("status") != "succeeded"
        or corpus is None
        or corpus.get("fingerprint_sha256") != probe.fingerprint_sha256
    ):
        raise BenchmarkError("baseline_report_incompatible")
    return report


def _measurement_float(report: Mapping[str, object], field: str) -> float:
    measurements_value = report.get("measurements")
    if not isinstance(measurements_value, Mapping):
        raise BenchmarkError("baseline_measurements_missing")
    measurements = cast(Mapping[str, object], measurements_value)
    value = measurements.get(field)
    if not isinstance(value, int | float) or value <= 0 or not math.isfinite(value):
        raise BenchmarkError(f"baseline_measurement_invalid:{field}")
    return float(value)


def _timed_after_barrier(
    barrier: Barrier, action: Callable[[], Mapping[str, object]]
) -> TimedResult:
    barrier.wait(timeout=60)
    started = time.perf_counter()
    value = action()
    return TimedResult(started=started, ended=time.perf_counter(), value=value)


def build_transcription_job(
    blocks: Sequence[Path],
    *,
    model: str,
    cuda_library_directory: Path,
    device: str,
    compute_type: str,
    language: str | None,
) -> tuple[Callable[[], Mapping[str, object]], float]:
    model_path = Path(model)
    if not model_path.is_absolute() or not model_path.is_dir():
        raise BenchmarkError("transcription_model_must_be_absolute_local_directory")
    if (
        not cuda_library_directory.is_absolute()
        or not cuda_library_directory.is_dir()
    ):
        raise BenchmarkError("cuda_library_directory_unavailable")
    os.environ["PATH"] = (
        f"{cuda_library_directory.resolve(strict=True)}{os.pathsep}"
        f"{os.environ.get('PATH', '')}"
    )
    try:
        runtime = importlib.import_module("faster_whisper")
        model_type: Any = runtime.WhisperModel
    except (ImportError, AttributeError, OSError) as exc:
        raise BenchmarkError("faster_whisper_runtime_unavailable") from exc
    initialized = time.perf_counter()
    try:
        whisper_model = model_type(
            str(model_path.resolve(strict=True)),
            device=device,
            compute_type=compute_type,
        )
    except (RuntimeError, OSError, ValueError) as exc:
        raise BenchmarkError("faster_whisper_model_initialization_failed") from exc
    initialization_seconds = time.perf_counter() - initialized

    def run() -> Mapping[str, object]:
        segment_count = 0
        for block in blocks:
            try:
                raw_segments, _ = whisper_model.transcribe(
                    str(block),
                    language=language,
                    beam_size=5,
                    word_timestamps=False,
                    vad_filter=False,
                    condition_on_previous_text=True,
                )
                segment_count += sum(1 for _ in raw_segments)
            except (RuntimeError, OSError, ValueError) as exc:
                raise BenchmarkError("cuda_transcription_failed") from exc
        return {
            "processed_block_count": len(blocks),
            "segment_count": segment_count,
        }

    return run, initialization_seconds


def _degradation_percent(concurrent: float, baseline: float) -> float:
    return ((concurrent / baseline) - 1) * 100


def concurrency_measurements(
    encode: TimedResult,
    transcription: TimedResult,
    *,
    baseline_encode_seconds: float,
    baseline_transcription_seconds: float,
) -> dict[str, float]:
    if baseline_encode_seconds <= 0 or baseline_transcription_seconds <= 0:
        raise BenchmarkError("concurrency_baseline_must_be_positive")
    overlap = max(
        0.0,
        min(encode.ended, transcription.ended)
        - max(encode.started, transcription.started),
    )
    return {
        "baseline_nvenc_wall_clock_seconds": baseline_encode_seconds,
        "encode_degradation_percent": _degradation_percent(
            encode.elapsed_seconds, baseline_encode_seconds
        ),
        "baseline_transcription_wall_clock_seconds": (
            baseline_transcription_seconds
        ),
        "concurrent_transcription_wall_clock_seconds": (
            transcription.elapsed_seconds
        ),
        "transcription_degradation_percent": _degradation_percent(
            transcription.elapsed_seconds, baseline_transcription_seconds
        ),
        "actual_overlap_seconds": overlap,
        "overlap_fraction_of_encode": overlap / encode.elapsed_seconds,
        "overlap_fraction_of_transcription": (
            overlap / transcription.elapsed_seconds
        ),
    }


def run_concurrent_arm(
    blocks: Sequence[Path],
    output_path: Path,
    *,
    baseline_report_path: Path,
    bit_rate: int,
    gop_size: int,
    transcription_model: str,
    transcription_model_version: str,
    cuda_library_directory: Path,
    transcription_device: str,
    transcription_compute_type: str,
    transcription_language: str | None,
) -> dict[str, object]:
    probe = probe_corpus(blocks)
    baseline = _load_baseline(baseline_report_path, probe)
    report = base_report("concurrent_nvenc_cuda_transcription", probe)
    report["settings"] = {
        "encode": encoder_settings("h264_nvenc", bit_rate, gop_size),
        "transcription": {
            "provider": "faster-whisper",
            "model_id": Path(transcription_model).name,
            "model_version": transcription_model_version,
            "device": transcription_device,
            "compute_type": transcription_compute_type,
            "language": transcription_language,
            "beam_size": 5,
            "word_timestamps": False,
            "vad_filter": False,
            "local_cuda_library_directory_configured": True,
        },
    }
    try:
        transcription_job, initialization_seconds = build_transcription_job(
            blocks,
            model=transcription_model,
            cuda_library_directory=cuda_library_directory,
            device=transcription_device,
            compute_type=transcription_compute_type,
            language=transcription_language,
        )
        baseline_started = time.perf_counter()
        baseline_transcription = transcription_job()
        baseline_transcription_seconds = time.perf_counter() - baseline_started
        barrier = Barrier(2)
        with ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="render-benchmark"
        ) as pool:
            encode_future = pool.submit(
                _timed_after_barrier,
                barrier,
                lambda: encode_video(
                    blocks,
                    output_path,
                    probe,
                    encoder="h264_nvenc",
                    bit_rate=bit_rate,
                    gop_size=gop_size,
                ),
            )
            transcription_future = pool.submit(
                _timed_after_barrier,
                barrier,
                transcription_job,
            )
            encode_result = encode_future.result()
            transcription_result = transcription_future.result()
        baseline_encode_seconds = _measurement_float(baseline, "wall_clock_seconds")
        measurements = dict(encode_result.value)
        measurements.update(
            {
                "quality_not_repeated": (
                    "concurrency_arm_measures_degradation_and_overlap;"
                    "quality_is_measured_by_standalone_encoder_arms"
                ),
                "transcription_model_initialization_seconds": initialization_seconds,
                **concurrency_measurements(
                    encode_result,
                    transcription_result,
                    baseline_encode_seconds=baseline_encode_seconds,
                    baseline_transcription_seconds=baseline_transcription_seconds,
                ),
                "transcription_baseline": dict(baseline_transcription),
                "transcription_concurrent": dict(transcription_result.value),
            }
        )
        report["measurements"] = measurements
        report["status"] = "succeeded"
    except BenchmarkError as exc:
        report["status"] = "failed"
        report["failure"] = {
            "code": str(exc).split(":", maxsplit=1)[0],
            "exception_type": type(exc).__name__,
            "software_fallback_used": False,
        }
    return report


def require_ffmpeg_binary(path: Path) -> Path:
    if not path.is_absolute():
        raise BenchmarkError("ffmpeg_path_must_be_absolute")
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise BenchmarkError("ffmpeg_binary_unavailable")
    except OSError as exc:
        raise BenchmarkError("ffmpeg_binary_unavailable") from exc
    return resolved


def parse_ffmpeg_version(output: str) -> tuple[str, bool]:
    lines = output.splitlines()
    # Only the first-line version identifier is retained, never compiler/configuration
    # text (which can contain build-machine paths). Reject non-version identifiers.
    match = re.match(
        r"^ffmpeg version ([A-Za-z0-9][A-Za-z0-9._+~-]*)(?:\s|$)",
        lines[0] if lines else "",
    )
    configurations = [line for line in lines if line.startswith("configuration:")]
    if match is None or len(configurations) != 1:
        raise BenchmarkError("ffmpeg_version_output_invalid")
    return match.group(1), "--enable-gpl" in configurations[0]


def identify_ffmpeg(path: Path) -> dict[str, object]:
    binary = require_ffmpeg_binary(path)
    try:
        with binary.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        result = subprocess.run(
            [str(binary), "-version"], check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BenchmarkError("ffmpeg_identification_failed") from exc
    if result.returncode != 0:
        raise BenchmarkError("ffmpeg_identification_failed")
    version, gpl = parse_ffmpeg_version(result.stdout)
    if gpl:
        raise BenchmarkError("ffmpeg_gpl_configuration_prohibited")
    return {"version": version, "sha256": digest, "gpl_enabled": gpl}


def concat_list_content(blocks: Sequence[Path]) -> str:
    lines = ["ffconcat version 1.0"]
    for block in blocks:
        if not block.is_absolute() or any(char in str(block) for char in "\r\n\0"):
            raise BenchmarkError("concat_block_path_invalid")
        quoted = block.as_posix().replace("'", "'\\''")
        lines.append(f"file '{quoted}'")
    return "\n".join(lines) + "\n"


@contextmanager
def native_concat_list(blocks: Sequence[Path], output_parent: Path) -> Generator[Path]:
    # Use the validated external output parent, not the process's possibly in-repo TMP.
    try:
        output_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="render-concat-", dir=output_parent) as name:
            path = require_external_new_file(
                Path(name) / "blocks.txt", suffixes=frozenset({".txt"})
            )
            path.write_text(concat_list_content(blocks), encoding="utf-8", newline="\n")
            yield path
    except OSError as exc:
        raise BenchmarkError("native_concat_io_failed") from exc


def native_needs_pixel_conversion(blocks: Sequence[Path]) -> bool:
    av = _import_av()
    formats: set[str] = set()
    try:
        for block in blocks:
            with av.open(str(block), mode="r") as container:
                pixel_format = _video_stream(container).codec_context.format
                if pixel_format is None:
                    raise BenchmarkError("native_source_pixel_format_unavailable")
                formats.add(str(pixel_format.name))
    except (OSError, ValueError) as exc:
        raise BenchmarkError("native_source_pixel_format_unavailable") from exc
    return not formats.issubset({"yuv420p", "nv12"})


def build_native_command(
    ffmpeg: Path, concat_path: Path, output_path: Path, probe: CorpusProbe, *,
    arm: str, bit_rate: int, gop_size: int, convert_pixels: bool,
) -> list[str]:
    binary = require_ffmpeg_binary(ffmpeg)
    encoder_settings("h264_nvenc", bit_rate, gop_size)
    if arm not in NATIVE_ARMS:
        raise BenchmarkError("native_arm_invalid")
    command = [str(binary), "-nostdin", "-hide_banner", "-y"]
    if arm == "native-cuda-nvenc":
        command += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    command += ["-f", "concat", "-safe", "0", "-i", str(concat_path), "-map", "0:v:0"]
    # Match ED-0073's sequential frame timestamps without duplicating/dropping frames.
    filters = [f"setpts=N*{probe.frame_rate.denominator}/({probe.frame_rate.numerator}*TB)"]
    if arm == "native-cuda-nvenc" and convert_pixels:
        filters.insert(0, "scale_cuda=format=nv12")
    command += ["-vf", ",".join(filters), "-fps_mode", "passthrough"]
    if arm == "native-cpu-nvenc":
        command += ["-pix_fmt", DEFAULT_PIXEL_FORMAT]
    # CUDA frames carry their software format; requesting yuv420p here would download
    # them. NV12 is the equivalent 8-bit 4:2:0 hardware surface for this output.
    command += [
        "-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr",
        "-b:v", str(bit_rate), "-g", str(gop_size), "-an", "-f", "mp4",
        "-progress", "pipe:1", "-nostats", str(output_path),
    ]
    return command


def parse_encoded_frame_count(output: str) -> int:
    entries = re.findall(r"(?:^|[\r\n])frame\s*=\s*([^\r\n]*)", output)
    if not entries:
        raise BenchmarkError("native_encoded_frame_count_unavailable")
    # Accept progress key=value lines and ordinary FFmpeg frame=... fps=... stats.
    match = re.fullmatch(r"([0-9]+)(?:\s+fps=.*)?\s*", entries[-1].strip())
    if match is None:
        raise BenchmarkError("native_encoded_frame_count_invalid")
    return int(match.group(1))


def native_failure(exc: BenchmarkError) -> dict[str, object]:
    return {
        "code": str(exc).split(":", maxsplit=1)[0],
        "exception_type": type(exc).__name__,
        "software_fallback_used": str(exc) == "native_cuda_decode_fallback",
    }


def cuda_decode_fallback(stderr: str) -> bool:
    """Recognize CUDA decoder setup failures, not generic CUDA/NVENC warnings.

    Match libavcodec's 'Failed setup for format cuda' diagnostic, or a same-line
    CUDA + hwaccel setup/initialisation failure (British or American spelling).
    This is a narrow failure guard, not proof that every frame used hardware decode.
    """
    return any(
        "cuda" in line.casefold()
        and re.search(
            r"\bfailed setup for format cuda\b|"
            r"\bhwaccel (?:setup|initiali[sz]ation) (?:failed|returned error)\b",
            line, re.IGNORECASE,
        ) is not None
        for line in stderr.splitlines()
    )


def encode_native_video(
    ffmpeg: Path, concat_path: Path, output_path: Path, probe: CorpusProbe, *,
    arm: str, bit_rate: int, gop_size: int, convert_pixels: bool,
) -> TimedResult:
    output = require_external_new_file(output_path, suffixes=frozenset({".mp4"}))
    command = build_native_command(
        ffmpeg, concat_path, output, probe, arm=arm, bit_rate=bit_rate,
        gop_size=gop_size, convert_pixels=convert_pixels,
    )
    # Exclusively claim a new file. -y is used only on this harness-owned output.
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb"):
            pass
    except OSError as exc:
        raise BenchmarkError("native_output_reservation_failed") from exc
    measurements: dict[str, object] = {
        "status": "failed", "exit_status": None, "encoded_frame_count": None,
        "quality": None,
    }
    stderr = ""
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError:
        ended = time.perf_counter()
        measurements["failure"] = native_failure(BenchmarkError("native_process_start_failed"))
    else:
        ended = time.perf_counter()
        stderr = result.stderr
        measurements["exit_status"] = result.returncode
        frame_error: BenchmarkError | None = None
        try:
            measurements["encoded_frame_count"] = parse_encoded_frame_count(result.stdout)
        except BenchmarkError as exc:
            frame_error = exc
        if arm == "native-cuda-nvenc" and cuda_decode_fallback(stderr):
            measurements["failure"] = native_failure(
                BenchmarkError("native_cuda_decode_fallback"))
        elif result.returncode != 0:
            measurements["failure"] = native_failure(
                BenchmarkError("native_encoder_execution_failed"))
        elif frame_error is not None:
            measurements["failure"] = native_failure(frame_error)
        elif measurements["encoded_frame_count"] == 0:
            measurements["failure"] = native_failure(BenchmarkError("encoder_produced_no_frames"))
        else:
            measurements["status"] = "succeeded"
    elapsed = ended - started
    measurements.update({
        "wall_clock_seconds": elapsed,
        "real_time_factor": elapsed / probe.total_duration_seconds if elapsed > 0 else None,
        "source_seconds_per_wall_second": (
            probe.total_duration_seconds / elapsed if elapsed > 0 else None
        ),
    })
    try:
        size = output.stat().st_size
        measurements["output_size_bytes"] = size
        if size == 0 or elapsed <= 0:
            raise BenchmarkError("native_output_or_timing_invalid")
    except (OSError, BenchmarkError):
        measurements.setdefault("output_size_bytes", None)
        if measurements["status"] == "succeeded":
            measurements["status"] = "failed"
            measurements["failure"] = native_failure(
                BenchmarkError("native_output_or_timing_invalid"))
    if measurements["status"] == "failed" and stderr:
        # Never attach raw diagnostics (which may include private paths) to reports.
        print("\n".join(stderr.splitlines()[-20:]), file=sys.stderr)
    return TimedResult(started, ended, measurements)


def native_variance(repetitions: Sequence[Mapping[str, object]]) -> dict[str, object]:
    successful = [item for item in repetitions if item.get("status") == "succeeded"]
    summary: dict[str, object] = {
        "successful_repetitions": len(successful), "standard_deviation_kind": "population",
    }
    for field in ("wall_clock_seconds", "real_time_factor", "source_seconds_per_wall_second"):
        values: list[float] = []
        for item in successful:
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise BenchmarkError("native_measurement_invalid")
            if value <= 0 or not math.isfinite(value):
                raise BenchmarkError("native_measurement_invalid")
            values.append(float(value))
        summary[field] = {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "standard_deviation": statistics.pstdev(values),
        } if values else None
    return summary


def native_output_paths(output: Path, repetitions: int) -> tuple[Path, ...]:
    if isinstance(repetitions, bool) or not 1 <= repetitions <= MAX_REPETITIONS:
        raise BenchmarkError("native_repetitions_out_of_bounds")
    require_external_new_file(output, suffixes=frozenset({".mp4"}))
    return tuple(
        require_external_new_file(
            output.with_name(f"{output.stem}.repetition-{index:02d}{output.suffix}"),
            suffixes=frozenset({".mp4"}),
        )
        for index in range(1, repetitions + 1)
    )


def native_report(
    arm: str, probe: CorpusProbe, identity: Mapping[str, object], *,
    bit_rate: int, gop_size: int, convert_pixels: bool,
) -> dict[str, object]:
    report = base_report(arm, probe)
    report["ffmpeg"] = dict(identity)
    report["settings"] = {
        **encoder_settings("h264_nvenc", bit_rate, gop_size),
        "decode": "software" if arm == "native-cpu-nvenc" else "cuda",
        "gpu_pixel_conversion": convert_pixels and arm != "native-cpu-nvenc",
        "real_time_factor_definition": "wall_clock_seconds / corpus_duration_seconds",
        "source_seconds_per_wall_second_definition": "corpus_duration_seconds / wall_clock_seconds",
    }
    report["limitations"] = [
        item for item in limitations()
        if item not in {"finite_single_runs_do_not_establish_thermal_steady_state",
                        "concurrent_transcription_overlap_is_narrow_relative_to_encode"}
    ] + ["finite_repetitions_do_not_establish_thermal_steady_state"]
    return report


def add_native_quality(
    measurements: dict[str, object], blocks: Sequence[Path], output: Path, probe: CorpusProbe,
) -> None:
    if measurements["status"] != "succeeded":
        return
    try:
        measurements["quality"] = measure_quality(blocks, output, probe)
    except BenchmarkError as exc:
        measurements["status"] = "failed"
        measurements["failure"] = native_failure(exc)
    except (OSError, ValueError, RuntimeError):
        measurements["status"] = "failed"
        measurements["failure"] = native_failure(
            BenchmarkError("native_quality_measurement_failed"))


def run_native_arm(
    blocks: Sequence[Path], output_path: Path, *, ffmpeg: Path, arm: str,
    repetitions: int, bit_rate: int, gop_size: int,
) -> dict[str, object]:
    outputs = native_output_paths(output_path, repetitions)
    binary = require_ffmpeg_binary(ffmpeg)
    identity = identify_ffmpeg(binary)
    probe = probe_corpus(blocks)
    convert = native_needs_pixel_conversion(blocks) if arm == "native-cuda-nvenc" else False
    report = native_report(
        arm, probe, identity, bit_rate=bit_rate, gop_size=gop_size, convert_pixels=convert,
    )
    runs: list[Mapping[str, object]] = []
    with native_concat_list(blocks, output_path.parent) as concat:
        for index, output in enumerate(outputs, start=1):
            measurements: dict[str, object]
            try:
                result = encode_native_video(
                    binary, concat, output, probe, arm=arm,
                    bit_rate=bit_rate, gop_size=gop_size, convert_pixels=convert,
                )
                measurements = dict(result.value)
                add_native_quality(measurements, blocks, output, probe)
            except BenchmarkError as exc:
                measurements = {
                    "status": "failed", "failure": native_failure(exc),
                    "exit_status": None, "wall_clock_seconds": None, "real_time_factor": None,
                    "encoded_frame_count": None, "output_size_bytes": None, "quality": None,
                }
            measurements["repetition"] = index
            runs.append(measurements)
    report["measurements"] = {"repetitions": runs, "variance": native_variance(runs)}
    report["status"] = (
        "succeeded" if all(run["status"] == "succeeded" for run in runs) else "failed"
    )
    return report


def load_native_baseline(
    path: Path, probe: CorpusProbe, *, identity: Mapping[str, object],
    bit_rate: int, gop_size: int, convert_pixels: bool,
) -> float:
    report = _load_baseline(path, probe, kind="native-cuda-nvenc")
    raw_identity = report.get("ffmpeg")
    baseline_identity: Mapping[str, object] = (
        cast(Mapping[str, object], raw_identity) if isinstance(raw_identity, Mapping) else {}
    )
    if baseline_identity.get("sha256") != identity["sha256"]:
        raise BenchmarkError("baseline_ffmpeg_sha256_mismatch")
    raw_settings = report.get("settings")
    settings: Mapping[str, object] = (
        cast(Mapping[str, object], raw_settings) if isinstance(raw_settings, Mapping) else {}
    )
    for field, expected in (
        ("video_bit_rate", bit_rate), ("gop_size", gop_size),
        ("gpu_pixel_conversion", convert_pixels),
    ):
        if settings.get(field) != expected:
            raise BenchmarkError(f"baseline_{field}_mismatch")
    measurements = report.get("measurements")
    if not isinstance(measurements, dict):
        raise BenchmarkError("baseline_measurements_missing")
    data = cast(dict[str, object], measurements)
    raw_runs = data.get("repetitions")
    if not isinstance(raw_runs, list):
        raise BenchmarkError("baseline_repetitions_invalid")
    raw_runs = cast(list[object], raw_runs)
    if not 1 <= len(raw_runs) <= MAX_REPETITIONS:
        raise BenchmarkError("baseline_repetitions_invalid")
    runs: list[Mapping[str, object]] = []
    for raw_run in raw_runs:
        if not isinstance(raw_run, dict):
            raise BenchmarkError("baseline_repetitions_invalid")
        run = cast(dict[str, object], raw_run)
        if run.get("status") != "succeeded" or run.get("exit_status") != 0:
            raise BenchmarkError("baseline_repetitions_invalid")
        runs.append(run)
    summary = native_variance(runs)
    if data.get("variance") != summary:
        raise BenchmarkError("baseline_variance_invalid")
    wall = cast(dict[str, float], summary["wall_clock_seconds"])
    return wall["mean"]


def run_native_concurrent_arm(
    blocks: Sequence[Path], output_path: Path, *, ffmpeg: Path,
    baseline_report_path: Path, bit_rate: int, gop_size: int,
    transcription_model: str, transcription_model_version: str,
    cuda_library_directory: Path, transcription_device: str,
    transcription_compute_type: str, transcription_language: str | None,
) -> dict[str, object]:
    require_external_new_file(output_path, suffixes=frozenset({".mp4"}))
    binary = require_ffmpeg_binary(ffmpeg)
    identity = identify_ffmpeg(binary)
    probe = probe_corpus(blocks)
    convert = native_needs_pixel_conversion(blocks)
    baseline_seconds = load_native_baseline(
        baseline_report_path, probe, identity=identity, bit_rate=bit_rate,
        gop_size=gop_size, convert_pixels=convert,
    )
    report = native_report(
        "native-concurrent", probe, identity, bit_rate=bit_rate,
        gop_size=gop_size, convert_pixels=convert,
    )
    report["settings"] = {
        "encode": report["settings"],
        "transcription": {
            "provider": "faster-whisper",
            "model_id": Path(transcription_model).name,
            "model_version": transcription_model_version,
            "device": transcription_device,
            "compute_type": transcription_compute_type,
            "language": transcription_language,
            "beam_size": 5,
            "word_timestamps": False,
            "vad_filter": False,
            "local_cuda_library_directory_configured": True,
        },
    }
    encode_process: TimedResult | None = None
    try:
        if transcription_device != "cuda":
            raise BenchmarkError("native_transcription_requires_cuda")
        job, initialization = build_transcription_job(
            blocks, model=transcription_model, cuda_library_directory=cuda_library_directory,
            device=transcription_device, compute_type=transcription_compute_type,
            language=transcription_language,
        )
        started = time.perf_counter()
        transcription_baseline = job()
        transcription_seconds = time.perf_counter() - started
        with native_concat_list(blocks, output_path.parent) as concat:
            def encode() -> Mapping[str, object]:
                nonlocal encode_process
                encode_process = encode_native_video(
                    binary, concat, output_path, probe,
                    arm="native-cuda-nvenc", bit_rate=bit_rate, gop_size=gop_size,
                    convert_pixels=convert,
                )
                return encode_process.value

            barrier = Barrier(2)
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="native-benchmark") as pool:
                encode_future = pool.submit(_timed_after_barrier, barrier, encode)
                transcription_future = pool.submit(_timed_after_barrier, barrier, job)
                encode_future.result()
                transcription_result = transcription_future.result()
        assert encode_process is not None
        measurements = dict(encode_process.value)
        measurements.update(concurrency_measurements(
            encode_process, transcription_result, baseline_encode_seconds=baseline_seconds,
            baseline_transcription_seconds=transcription_seconds,
        ))
        origin = min(encode_process.started, transcription_result.started)
        overlap_start = max(encode_process.started, transcription_result.started)
        overlap_end = min(encode_process.ended, transcription_result.ended)
        measurements["actual_overlap_window_seconds_from_first_job_start"] = (
            {"start": overlap_start - origin, "end": overlap_end - origin}
            if overlap_end > overlap_start else None
        )
        measurements["transcription_model_initialization_seconds"] = initialization
        measurements["transcription_baseline"] = dict(transcription_baseline)
        measurements["transcription_concurrent"] = dict(transcription_result.value)
        add_native_quality(measurements, blocks, output_path, probe)
        report["measurements"] = measurements
        report["status"] = measurements["status"]
    except BenchmarkError as exc:
        report["status"] = "failed"
        report["failure"] = native_failure(exc)
        if encode_process is not None:
            report["measurements"] = dict(encode_process.value)
    return report


def _atomic_write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise BenchmarkError("output_path_already_exists") from exc
        except OSError as exc:
            raise BenchmarkError("report_publication_failed") from exc
    finally:
        temporary.unlink(missing_ok=True)


def write_report(path: Path, report: Mapping[str, object]) -> None:
    content = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if str(REPOSITORY_ROOT) in content:
        raise BenchmarkError("report_contains_prohibited_private_content")
    _atomic_write_new(path, content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded, qualification-only StageFlow render benchmark."
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--input-directory", type=Path, required=True)
    common.add_argument("--block-extension", default=".mp4")
    common.add_argument("--output-video", type=Path, required=True)
    common.add_argument("--output-report", type=Path, required=True)
    common.add_argument("--video-bit-rate", type=int, default=DEFAULT_VIDEO_BIT_RATE)
    common.add_argument("--gop-size", type=int, default=DEFAULT_GOP_SIZE)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("nvenc", parents=[common])
    subparsers.add_parser("libx264", parents=[common])
    concurrent = subparsers.add_parser("concurrent", parents=[common])
    concurrent.add_argument("--baseline-nvenc-report", type=Path, required=True)
    for arm in NATIVE_ARMS:
        native = subparsers.add_parser(arm, parents=[common])
        native.add_argument("--ffmpeg", type=Path, required=True)
        native.add_argument(
            "--repetitions", type=int, default=3, choices=range(1, MAX_REPETITIONS + 1),
        )
    native_concurrent = subparsers.add_parser("native-concurrent", parents=[common])
    native_concurrent.add_argument("--ffmpeg", type=Path, required=True)
    native_concurrent.add_argument("--baseline-native-cuda-report", type=Path, required=True)
    for concurrency_parser in (concurrent, native_concurrent):
        concurrency_parser.add_argument("--transcription-model", required=True)
        concurrency_parser.add_argument("--transcription-model-version", required=True)
        concurrency_parser.add_argument("--cuda-library-directory", type=Path, required=True)
        concurrency_parser.add_argument("--transcription-device", default="cuda", choices=("cuda",))
        concurrency_parser.add_argument("--transcription-compute-type", default="float16")
        concurrency_parser.add_argument("--transcription-language")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        input_directory = require_external_input_directory(args.input_directory)
        blocks = discover_blocks(input_directory, str(args.block_extension))
        output_video = require_external_new_file(
            args.output_video, suffixes=frozenset({".mp4"})
        )
        output_report = require_external_new_file(
            args.output_report, suffixes=frozenset({".json"})
        )
        if args.command in {"concurrent", "native-concurrent"}:
            concurrency_runner = (
                run_native_concurrent_arm if args.command == "native-concurrent"
                else run_concurrent_arm
            )
            native_arguments = (
                {"ffmpeg": args.ffmpeg} if args.command == "native-concurrent" else {}
            )
            report = concurrency_runner(
                blocks,
                output_video,
                baseline_report_path=(
                    args.baseline_native_cuda_report if args.command == "native-concurrent"
                    else args.baseline_nvenc_report
                ),
                bit_rate=int(args.video_bit_rate),
                gop_size=int(args.gop_size),
                transcription_model=str(args.transcription_model),
                transcription_model_version=str(args.transcription_model_version),
                cuda_library_directory=args.cuda_library_directory,
                transcription_device=str(args.transcription_device),
                transcription_compute_type=str(args.transcription_compute_type),
                transcription_language=args.transcription_language,
                **native_arguments,
            )
        elif args.command in NATIVE_ARMS:
            report = run_native_arm(
                blocks, output_video, ffmpeg=args.ffmpeg, arm=args.command,
                repetitions=args.repetitions, bit_rate=args.video_bit_rate, gop_size=args.gop_size,
            )
        else:
            report = run_encode_arm(
                blocks,
                output_video,
                encoder="h264_nvenc" if args.command == "nvenc" else "libx264",
                bit_rate=int(args.video_bit_rate),
                gop_size=int(args.gop_size),
            )
        write_report(output_report, report)
    except BenchmarkError as exc:
        print(f"render benchmark failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"run_kind": report["run_kind"], "status": report["status"]},
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
