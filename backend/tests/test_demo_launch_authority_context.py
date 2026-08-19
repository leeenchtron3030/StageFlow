from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

import pytest

import app.demo.controller as controller

ROOT = Path(__file__).parents[2]
LAUNCHER = ROOT / "scripts" / "demo" / "Start-StageFlowDemo.ps1"
CONTROLLER = ROOT / "scripts" / "demo" / "StageFlow-Demo.ps1"
PYTHON_CONTROLLER = ROOT / "backend" / "app" / "demo" / "controller.py"


def test_launcher_generates_a_process_scoped_cryptographic_launch_context() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "[byte[]]::new(32)" in source
    assert "[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)" in source
    assert '.TrimEnd("=").Replace("+", "-").Replace("/", "_")' in source
    assert "Math.random" not in source
    assert source.index("app.demo.cli preflight") < source.index(
        "STAGEFLOW_DEMO_LAUNCH_CONTEXT = (New-DemoLaunchContext)"
    )
    frontend = source[source.index("$frontendParameters = @{") :]
    assert "Environment = @{" in frontend
    assert "STAGEFLOW_DEMO_LAUNCH_CONTEXT = (New-DemoLaunchContext)" in frontend
    assert source.count("STAGEFLOW_DEMO_LAUNCH_CONTEXT") == 1
    assert re.search(r"Write-(?:Host|Output).*LaunchContext", source, re.IGNORECASE) is None


def test_controller_lifecycle_sources_have_no_session_start_authority_path() -> None:
    sources = {
        "controller": CONTROLLER.read_text(encoding="utf-8"),
        "launcher": LAUNCHER.read_text(encoding="utf-8"),
        "python_controller": PYTHON_CONTROLLER.read_text(encoding="utf-8"),
    }

    for source in sources.values():
        assert "sessions/start" not in source
        assert ".start_session(" not in source
    assert "human_session_start" not in sources["controller"]
    assert "human_session_start" not in sources["launcher"]


def test_prepare_runs_only_preflight_bootstrap_and_program_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_cli_main(arguments: Sequence[str]) -> int:
        calls.append(tuple(arguments))
        return 0

    monkeypatch.setattr(controller, "_verify_database", lambda: "stageflow_demo")
    monkeypatch.setattr(controller.demo_cli, "main", fake_cli_main)

    assert controller.main(["prepare"]) == 0
    assert calls == [("preflight",), ("bootstrap",), ("sync-program",)]
