"""Private offline effects and numeric helpers for ED-0126 validation tools."""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import subprocess
import tomllib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from transcription_engine_spike import Parser, Refusal, local_path, quiet_output

REPOSITORY = Path(__file__).resolve().parents[2]
VERSION = 2


def np_module() -> Any:
    return importlib.import_module("numpy")


def external(raw: str, *, directory: bool = False, output: bool = False) -> Path:
    if output:
        path = Path(raw)
        if not path.is_absolute() or path.name in ("", ".", ".."):
            raise Refusal()
        parent = local_path(str(path.parent), directory=True, external=True)
        target = parent / path.name
        if target.exists() or target.is_symlink():
            target = local_path(str(target), external=True)
        if target.is_relative_to(REPOSITORY):
            raise Refusal()
        return target
    return local_path(raw, directory=directory, external=True)


def utc(value: str) -> float:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?"
                    r"(?:Z|[+-]\d{2}:\d{2})", value) is None:
        raise Refusal()
    return datetime.fromisoformat(value).timestamp()


def iso(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def key(*values: Any) -> str:
    return hashlib.sha256(json.dumps([VERSION, *values], sort_keys=True,
                                    allow_nan=False).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    # Serialize before opening, so invalid numeric output cannot truncate a report.
    text = json.dumps(value, allow_nan=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def output_collisions(outputs: list[Path], inputs: list[Path]) -> None:
    resolved = [p.resolve() for p in outputs]
    if len(set(resolved)) != len(resolved) or set(resolved).intersection(
            p.resolve() for p in inputs):
        raise Refusal()
    # Resolve symlinks above; samefile also catches hard links where supported.
    for index, output in enumerate(outputs):
        if output.exists() and any(p.exists() and output.samefile(p)
                                   for p in [*inputs, *outputs[:index]]):
            raise Refusal()


def command(args: list[str], *, data: bytes | None = None, include_stderr: bool = False) -> bytes:
    result = subprocess.run(args, input=data, stdin=subprocess.DEVNULL if data is None else None,
                            capture_output=True, timeout=7200,
                            check=False)
    if result.returncode:
        raise Refusal()
    return result.stdout + (result.stderr if include_stderr else b"")


def tool(raw: str | None) -> Path | None:
    if not raw:
        return None
    try:
        path = local_path(raw)
    except (OSError, ValueError):
        return None
    if path.suffix.lower() in {".bat", ".cmd", ".ps1"}:
        raise Refusal()
    return path


def ffmpeg_tool(raw: str | None) -> Path | None:
    path = tool(raw)
    if path is not None:
        version = command([str(path), "-version"]).decode("utf-8", "replace")
        if "--enable-gpl" in version or "--enable-nonfree" in version:
            raise Refusal()
        if not re.match(r"ff(?:mpeg|probe) version ", version):
            raise Refusal()
    return path


def config(path: str) -> dict[str, Any]:
    with local_path(path).open("rb") as stream:
        return tomllib.load(stream)


def probe(binary: Path, path: Path) -> dict[str, Any]:
    return json.loads(command([str(binary), "-v", "error", "-protocol_whitelist", "file,pipe",
                               "-show_format", "-show_streams", "-of", "json", str(path)]))


def decode(binary: Path, path: Path, rate: int = 8000) -> Any:
    data = command([str(binary), "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                    "-i", str(path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(rate),
                    "-f", "f32le", "pipe:1"])
    array = np_module().frombuffer(data, dtype="<f4").copy()
    if not len(array) or not np_module().isfinite(array).all():
        raise Refusal()
    return array


def correlate(signal: Any, reference: Any) -> Any:
    """Bounded FFTs; float32 audio/output with float64 local energy accumulation."""
    np = np_module()
    x, y = np.asarray(signal, dtype=np.float32), np.asarray(reference, dtype=np.float32)
    if x.ndim != 1 or y.ndim != 1 or not len(y) or len(y) > len(x):
        return np.empty(0)
    count = len(x) - len(y) + 1
    result = np.empty(count, dtype=np.float32)
    for start in range(0, count, 262144):
        end = min(count, start + 262144)
        result[start:end] = _correlate_chunk(x[start:end + len(y) - 1], y)
    return result


def _correlate_chunk(x: Any, y: Any) -> Any:
    np = np_module()
    y = y - y.mean()
    energy = float(y @ y)
    size = 1 << (len(x) + len(y) - 2).bit_length()
    numerator = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(y[::-1], size), size)
    numerator = numerator[len(y) - 1:len(x)]
    sums = np.concatenate(([0.0], np.cumsum(x, dtype=np.float64)))
    squares = np.concatenate(([0.0], np.cumsum(x * x, dtype=np.float64)))
    local = squares[len(y):] - squares[:-len(y)]
    local -= (sums[len(y):] - sums[:-len(y)]) ** 2 / len(y)
    denominator = np.sqrt(np.maximum(local, 0) * energy)
    return np.clip(np.divide(numerator, denominator, out=np.zeros_like(numerator),
                             where=denominator > 1e-12), -1, 1)


def decode_chunks(binary: Path, path: Path, overlap: int,
                  rate: int = 8000) -> Iterator[tuple[int, Any]]:
    """Decode 60 s cores with a reference-length lookahead; never capture a full file."""
    np = np_module()
    core = 60 * rate
    start = 0
    while True:
        raw = command([str(binary), "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                       "-ss", str(start / rate), "-i", str(path), "-t",
                       str((core + overlap) / rate), "-map", "0:a:0", "-vn", "-ac", "1",
                       "-ar", str(rate), "-f", "f32le", "pipe:1"])
        audio = np.frombuffer(raw, dtype="<f4")
        if not np.isfinite(audio).all():
            raise Refusal()
        if not len(audio):
            return
        yield start, audio
        if len(audio) <= core:
            return
        start += core


def finite(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise Refusal()
    return result


__all__ = ["Parser", "Refusal", "quiet_output"]
