from __future__ import annotations

import re
from pathlib import Path

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
        "publish-devcon",
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
        "STAGEFLOW_DEMO_CONFIG_PATH",
        "STAGEFLOW_DEMO_CUDA_RUNTIME_PATH",
        "STAGEFLOW_DEMO_OPERATOR_ID",
        "STAGEFLOW_DEMO_DEVCON_API_KEY",
    ):
        assert name in source
    assert "STAGEFLOW_TEST_POSTGRES_DSN" not in source
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


def test_publish_requires_explicit_confirmation_and_never_follows_session_end() -> None:
    source = _source()

    assert 'Read-Host "Publish this StageFlow enrichment to Devcon? [y/N]"' in source
    assert "$ConfirmHumanAuthority.IsPresent" in source
    assert '"publish", "--expected-digest"' in source
    assert '"--confirmed"' in source
    assert "publish-devcon" not in LAUNCHER.read_text(encoding="utf-8")
    assert source.count("Publish-Devcon") == 2


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
