from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CONTROLLER = ROOT / "scripts" / "demo" / "StageFlow-Demo.ps1"
LAUNCHER = ROOT / "scripts" / "demo" / "Start-StageFlowDemo.ps1"


def _source() -> str:
    return CONTROLLER.read_text(encoding="utf-8")


def test_controller_exposes_only_the_bounded_action_set() -> None:
    source = _source()

    for action in (
        "prepare",
        "start",
        "status",
        "diagnose",
        "stop",
        "rehearsal-report",
    ):
        assert f'"{action}"' in source
    assert "cleanup" not in source.casefold()
    assert "DROP " not in source
    assert "DELETE FROM" not in source
    assert "Remove-Item" not in source


def test_controller_imports_only_named_user_values_without_printing_them() -> None:
    source = _source()

    assert '[Environment]::GetEnvironmentVariable($Name, "User")' in source
    for name in (
        "STAGEFLOW_DEMO_POSTGRES_DSN",
        "STAGEFLOW_API_SHARED_SECRET",
        "STAGEFLOW_DEMO_CONFIG_PATH",
        "STAGEFLOW_DEMO_CUDA_RUNTIME_PATH",
        "STAGEFLOW_DEMO_OPERATOR_ID",
    ):
        assert name in source
    assert "STAGEFLOW_TEST_POSTGRES_DSN" not in source
    assert source.count('Import-RequiredSecret "STAGEFLOW_API_SHARED_SECRET"') == 3
    assert "$env:STAGEFLOW_API_SHARED_SECRET = $null" in source
    assert "STAGEFLOW_VALIDATION_DSN" not in source
    assert "postgresql://" not in source.casefold()
    assert re.search(r'Write-(?:Host|Output).*\$(?:apiKey|value)', source) is None


def test_controller_verifies_database_before_prepare_or_launcher_start() -> None:
    source = _source()

    assert 'Invoke-DemoPython -Arguments @("verify-database")' in source
    prepare = source.index('"prepare" {')
    prepare_call = source.index('Invoke-DemoPython -Arguments @("prepare")', prepare)
    start = source.index("function Start-DemoStack")
    verify = source.index('Invoke-DemoPython -Arguments @("verify-database")', start)
    launch = source.index("Start-Process", start)

    assert prepare < prepare_call
    assert start < verify < launch


def test_controller_inherits_cuda_only_through_process_scope_and_existing_launcher() -> None:
    source = _source()

    assert '$env:PATH = $RuntimePath + [System.IO.Path]::PathSeparator + $originalPath' in source
    assert "$env:PATH = $originalPath" in source
    assert '"-CudaRuntimePath"' in source
    assert "Start-StageFlowDemo.ps1" in source
    assert 'SetEnvironmentVariable($Name, $value, "Process")' in source
    assert 'SetEnvironmentVariable($Name, $value, "User")' not in source
    assert 'SetEnvironmentVariable($Name, $value, "Machine")' not in source


def test_controller_resolves_operator_and_session_without_uuid_copy_paste() -> None:
    source = _source()

    assert 'Invoke-DemoPython -Arguments @("operator-id")' in source
    assert 'Invoke-DemoPython -Arguments @("status")' in source
    parameter_start = source.index("param(")
    parameter_end = source.index(")\n\n", parameter_start)
    assert "session_id" not in source[parameter_start:parameter_end]


def test_publication_is_absent_from_supported_workflow() -> None:
    source = _source()

    assert "Publish-Devcon" not in source
    assert '"publish", "--expected-digest"' not in source
    assert "STAGEFLOW_DEMO_DEVCON_API_KEY" not in source
    assert "publish-devcon" not in source.split("#>", 1)[0]
    assert "publish-devcon" not in LAUNCHER.read_text(encoding="utf-8")


def test_stop_targets_only_the_recorded_launcher_tree() -> None:
    source = _source()

    assert "Test-RecordedLauncherLive" in source
    assert "$rootId = [int]$state.launcher_pid" in source
    assert "ParentProcessId -eq $processId" in source
    assert "Stop-Process -Id $processId" in source
    assert "Stop-Process -Name" not in source
    assert "taskkill" not in source.casefold()


def test_report_and_console_contract_do_not_emit_transcript_or_secret_values() -> None:
    source = _source()

    assert '"Transcription Evidence:' in source
    assert "transcript_text" not in source
    assert "duration_seconds" not in source
    assert "raw_provider" not in source
    assert "DSN=" not in source
    assert "apiKey=" not in source

def test_lifecycle_state_handles_optional_operator_and_json_timestamps() -> None:
    source = _source()

    assert "$null -ne $OperatorId" in source
    assert "$OperatorId.ToString" in source
    assert "[DateTimeOffset]$State.launcher_started_at" in source
    assert "$process.StartTime.ToUniversalTime().Ticks" in source
    assert "$recordedStart.UtcDateTime.Ticks" in source
    assert 'Add-Member -NotePropertyName "stopped_at"' in source
    assert "$state.stopped_at =" not in source

def test_status_surfaces_bounded_autonomy_program_and_worker_currentness() -> None:
    source = _source()

    assert '$payload.PSObject.Properties["automation"]' in source
    assert '"Automation: $($automation.state) owner=$($automation.owner)"' in source
    assert '"Media reconciliation: cycles=$($automation.media_cycle_count)' in source
    assert '"Program refresh: cycles=$($automation.program_refresh_count)' in source
    assert '"Program: current=$($payload.program.current) withdrawn=$($payload.program.withdrawn)' in source  # noqa: E501
    assert 'current=$($payload.worker.current)' in source
    assert 'gpu_transcription=$($payload.worker.gpu_transcription)' in source
    assert 'failure_at=$($automation.media_last_failure_at)' in source
    assert 'failure_at=$($automation.program_last_failure_at)' in source


@pytest.mark.skipif(
    shutil.which("pwsh") is None and shutil.which("powershell.exe") is None,
    reason="PowerShell is required to execute the launcher status function",
)
def test_status_reads_neutral_program_with_unchanged_displayed_text() -> None:
    source = _source()
    start = source.index("function Show-DemoStatus {")
    end = source.index("\n}\n", start) + 2
    status_function = source[start:end]
    payload: dict[str, object] = {
        "event": {"event_key": "example-event", "event_id": "event-id"},
        "stage": {"stage_key": "main", "stage_id": "stage-id"},
        "session": None,
        "media": {
            "registered": 5, "associated": 4, "stabilizing": 1,
            "unresolved": 1, "conflicting": 0,
        },
        "operations": {"counts": {"succeeded": 2}, "terminal_failures": []},
        "worker": {
            "state": "available", "current": True, "available": 1,
            "capacity": 1, "gpu_transcription": "ready",
        },
        "transcript_evidence": {"complete": 2, "count": 3},
        "moments": {"count": 1},
        "program": {
            "current": 3, "withdrawn": 1, "status": "current",
            "last_successful_refresh": "refresh-marker",
            "cached_program_expectations": 4,
        },
        "devcon": {
            "current": 99, "withdrawn": 99, "status": "legacy-unused",
            "last_successful_refresh": "legacy-unused",
            "cached_program_expectations": 99,
        },
    }
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "function Import-RequiredSecret {}\n"
        f"function Invoke-DemoPython {{ '{json.dumps(payload)}' }}\n"
        + status_function + "\nShow-DemoStatus\n"
    )
    result = subprocess.run(
        [shutil.which("pwsh") or "powershell.exe", "-NoProfile", "-NonInteractive",
         "-Command", script],
        capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    assert result.stdout == os.linesep.encode().join([
        b"STAGEFLOW DEMO STATUS",
        b"Event: example-event [event-id]",
        b"Stage: main [stage-id]",
        b"Session: NONE",
        b"Media: registered=5 associated=4 stabilizing=1 unresolved=1 conflicting=0",
        b"Operations: succeeded=2",
        b"Terminal failures: 0",
        b"Worker: available current=True available=1 capacity=1 gpu_transcription=ready",
        b"Transcription Evidence: complete=2 total=3 (evidence only)",
        b"Moments: 1",
        b"Program: current=3 withdrawn=1 status=current last=refresh-marker",
        b"Program cached expectations: 4",
        b"",
    ])


@pytest.mark.skipif(
    shutil.which("powershell.exe") is None,
    reason="Windows PowerShell 5.1 is only available on Windows hosts",
)
def test_launcher_refuses_windows_powershell_with_version_error() -> None:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER),
            "-ConfigPath",
            "unused.toml",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode != 0
    assert "7.3" in result.stderr
    assert "Start-StageFlowDemo.ps1" in result.stderr
