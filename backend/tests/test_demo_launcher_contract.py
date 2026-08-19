from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
LAUNCHER = ROOT / "scripts" / "demo" / "Start-StageFlowDemo.ps1"
EXAMPLE = ROOT / "examples" / "demo-single-stage.toml.example"


def test_demo_launcher_keeps_backend_loopback_and_ui_on_selected_lan() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert '[guid]$OperatorId' in source
    assert '$env:STAGEFLOW_DEMO_OPERATOR_ID = $OperatorId.ToString("D")' in source
    assert '"--host", "127.0.0.1"' in source
    assert '"--hostname", $producerIp' in source
    assert 'STAGEFLOW_DEMO_API_BASE_URL = "http://127.0.0.1:' in source
    assert 'STAGEFLOW_KERNEL_STATUS_URL = "http://127.0.0.1:' in source
    assert "0.0.0.0" not in source


def test_demo_launcher_scopes_the_isolated_cuda_runtime_to_owned_processes() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "[string]$CudaRuntimePath" in source
    assert '"cublas64_12.dll"' in source
    assert source.index("$env:PATH = $resolvedCudaRuntimePath") < source.index(
        "app.demo.cli preflight"
    )
    assert "$env:PATH = $originalPath" in source
    assert "SetEnvironmentVariable" not in source


def test_demo_launcher_preflights_before_start_and_cleans_only_owned_processes() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert source.index("app.demo.cli preflight") < source.index("Start-Process")
    assert source.index("app.demo.cli bootstrap") < source.index("Start-Process")
    assert source.index("app.demo.cli sync-program") < source.index("Start-Process")
    assert source.count("$ownedProcesses.Add(") == 3
    assert "finally {" in source
    assert "Stop-OwnedProcess $process" in source
    assert "Stop-Process -Id $processId" in source
    assert "Stop-Process -Name" not in source
    assert "taskkill" not in source.casefold()


def test_demo_launcher_and_example_never_embed_or_print_a_dsn() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    example = EXAMPLE.read_text(encoding="utf-8")

    assert "postgres_dsn_secret_ref" in example
    assert "postgresql://" not in example.casefold()
    assert "postgres://" not in example.casefold()
    assert "STAGEFLOW_DEMO_POSTGRES_DSN" not in launcher
    assert re.search(r"Write-(?:Host|Output).*DSN", launcher, re.IGNORECASE) is None


def test_demo_example_keeps_accepted_profile_and_cuda_contract() -> None:
    example = EXAMPLE.read_text(encoding="utf-8")

    assert 'runtime_profile = "demo-single-stage"' in example
    assert 'provider = "faster-whisper"' in example
    assert 'model_id = "large-v3-turbo"' in example
    assert 'device = "cuda"' in example
    assert 'compute_type = "float16"' in example
