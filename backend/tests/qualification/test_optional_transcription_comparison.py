"""Legacy comparisons are lazy, offline and optional, with no project dependency."""
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from qualification import render_benchmark, transcription_engines


@pytest.mark.parametrize("harness", ["render", "transcription"])
@pytest.mark.parametrize("installed", [False, True])
def test_operator_comparison_runtime_is_optional_and_offline(
    monkeypatch: pytest.MonkeyPatch, harness: str, installed: bool,
) -> None:
    def available(path: Path) -> bool:
        return True

    monkeypatch.setattr(Path, "is_dir", available)
    monkeypatch.setattr(Path, "is_file", available)
    calls: list[dict[str, Any]] = []

    def model(path: str, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace()

    def runtime(name: str) -> Any:
        assert name == "faster_whisper"
        if not installed:
            raise ImportError("private runtime detail")
        return SimpleNamespace(WhisperModel=model)

    def version(name: str) -> str:
        return "1.2.1" if name == "faster-whisper" else "4.8.1"

    monkeypatch.setattr(transcription_engines.importlib, "import_module", runtime)
    monkeypatch.setattr(transcription_engines, "_version", version)
    # Restore the render harness's process-local PATH adjustment after this test.
    monkeypatch.setenv("PATH", "synthetic")

    def build() -> None:
        if harness == "render":
            render_benchmark.build_transcription_job(
                (), model=str(Path.cwd()), cuda_library_directory=Path.cwd(),
                device="cuda", compute_type="float16", language="en")
        else:
            transcription_engines.FasterWhisperEngine(
                model=str(Path.cwd()), model_version="synthetic",
                device="cuda", compute_type="float16")

    assert calls == []
    if installed:
        build()
        assert calls == [{"device": "cuda", "compute_type": "float16", "local_files_only": True}]
    else:
        with pytest.raises((render_benchmark.BenchmarkError, transcription_engines.EvaluationError),
                           match="^faster_whisper_runtime_unavailable$"):
            build()
        assert calls == []
