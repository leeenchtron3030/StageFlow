from __future__ import annotations

from pathlib import Path

import pytest
from qualification import durable_kernel_razer as harness


def test_non_windows_endurance_reports_typed_skip_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_run(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        raise AssertionError("Windows endurance implementation ran")

    monkeypatch.setattr(harness, "endurance", must_not_run)
    result_path = tmp_path / "result.json"

    result = harness.endurance_for_platform(
        tmp_path / "unused.toml",
        result_path,
        1.0,
        platform_name="linux",
    )

    assert result == {
        "status": "skipped",
        "reason": "unsupported_platform",
        "required_platform": "win32",
    }
    assert result_path.read_text(encoding="utf-8").strip().startswith("{")


def test_windows_endurance_delegates_without_changing_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected: dict[str, object] = {"status": "completed"}
    calls: list[tuple[Path, Path, float]] = []

    def record(config: Path, result: Path, duration: float) -> dict[str, object]:
        calls.append((config, result, duration))
        return expected

    monkeypatch.setattr(harness, "endurance", record)
    config_path = tmp_path / "kernel.toml"
    result_path = tmp_path / "result.json"

    result = harness.endurance_for_platform(
        config_path,
        result_path,
        2.5,
        platform_name="win32",
    )

    assert result is expected
    assert calls == [(config_path, result_path, 2.5)]
