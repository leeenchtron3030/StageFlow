from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config.deployment import load_kernel_deployment_configuration

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = REPOSITORY_ROOT / "scripts" / "validation" / "Invoke-StageFlowValidation.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")


def run_controller(
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        pytest.skip("PowerShell is not available")
    command = [POWERSHELL, "-NoProfile"]
    if Path(POWERSHELL).name.casefold().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", str(CONTROLLER), *arguments])
    return subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def validation_environment(database: str, *, secret: str = "controller-secret") -> dict[str, str]:
    environment = os.environ.copy()
    environment["STAGEFLOW_VALIDATION_DSN"] = (
        f"postgresql://validation_user:{secret}@localhost:5432/{database}"
    )
    return environment


def validation_root(tmp_path: Path) -> Path:
    return tmp_path / "stageflow-validation"


def write_matching_artifacts(root: Path, *, run: int = 3) -> tuple[Path, Path, Path]:
    token = f"run-{run:03d}"
    media = root / "media" / token
    media.mkdir(parents=True)
    config = root / f"kernel-{token}.toml"
    config.write_text(
        f"""
schema_version = "1.0"
deployment_id = "stageflow-validation-{token}"
postgres_dsn_secret_ref = "STAGEFLOW_VALIDATION_DSN"

[event]
key = "real-event-validation-{token}"

[[event.stages]]
key = "main"

[[event.stages.sources]]
key = "main-source"
path = "{media.as_posix()}"
maximum_candidates = 100
allowed_extensions = [".mp4"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    run_file = root / f"{token}.json"
    run_file.write_text(
        json.dumps(
            {
                "configuration": {
                    "deployment_id": f"stageflow-validation-{token}",
                    "event_key": f"real-event-validation-{token}",
                },
                "sessions": {},
                "status_snapshots": [],
            }
        ),
        encoding="utf-8",
    )
    return config, run_file, media


def write_logging_fake_uv(tmp_path: Path) -> Path:
    fake_uv = tmp_path / "logging-fake-uv.ps1"
    fake_uv.write_text(
        """
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ToolArguments)
Add-Content -LiteralPath $env:STAGEFLOW_CONTROLLER_TEST_LOG -Value ($ToolArguments -join ' ')
exit 0
""".strip()
        + "\n",
        encoding="ascii",
    )
    return fake_uv


def write_session_updating_fake_uv(tmp_path: Path) -> Path:
    fake_uv = tmp_path / "session-updating-fake-uv.ps1"
    fake_uv.write_text(
        """
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ToolArguments)
$runIndex = [Array]::IndexOf($ToolArguments, '--run-file')
$labelIndex = [Array]::IndexOf($ToolArguments, '--session-label')
$atIndex = [Array]::IndexOf($ToolArguments, '--at')
if ($runIndex -lt 0 -or $labelIndex -lt 0 -or $atIndex -lt 0) { exit 2 }
if ($env:STAGEFLOW_CONTROLLER_TEST_DELAY_MILLISECONDS) {
    Start-Sleep -Milliseconds ([int]$env:STAGEFLOW_CONTROLLER_TEST_DELAY_MILLISECONDS)
}
if ($env:STAGEFLOW_CONTROLLER_TEST_LOG) {
    Add-Content -LiteralPath $env:STAGEFLOW_CONTROLLER_TEST_LOG -Value ($ToolArguments -join ' ')
}
$state = Get-Content -LiteralPath $ToolArguments[$runIndex + 1] -Raw | ConvertFrom-Json
$label = $ToolArguments[$labelIndex + 1]
$authorityAt = $ToolArguments[$atIndex + 1]
if ($ToolArguments -contains 'start-session') {
    $session = [pscustomobject]@{
        activity_state = 'presentation_active'
        authoritative_start = $authorityAt
        authoritative_end = $null
    }
}
elseif ($ToolArguments -contains 'end-session') {
    $session = $state.sessions.PSObject.Properties[$label].Value
    $session.activity_state = 'presentation_ended'
    $session.authoritative_end = $authorityAt
}
else { exit 2 }
$state.sessions | Add-Member -NotePropertyName $label -NotePropertyValue $session -Force
$encoding = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText(
    $ToolArguments[$runIndex + 1],
    (($state | ConvertTo-Json -Depth 20) + "`n"),
    $encoding
)
exit 0
""".strip()
        + "\n",
        encoding="ascii",
    )
    return fake_uv


def start_lock_holder(
    tmp_path: Path,
    *,
    lock_path: Path,
    offset: int,
    action: str,
) -> tuple[subprocess.Popen[str], Path]:
    if POWERSHELL is None:
        pytest.skip("PowerShell is not available")
    ready = tmp_path / f"lock-{offset}.ready"
    release = tmp_path / f"lock-{offset}.release"
    holder = tmp_path / f"hold-lock-{offset}.ps1"
    holder.write_text(
        """
param([string]$LockPath,[string]$ReadyPath,[string]$ReleasePath,[int]$Offset,[string]$Action)
$stream = [System.IO.FileStream]::new(
    $LockPath,
    [System.IO.FileMode]::OpenOrCreate,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::ReadWrite
)
try {
    if ($stream.Length -lt 2) { $stream.SetLength(2); $stream.Flush($true) }
    $stream.Lock($Offset, 1)
    $metadata = @{
        schema_version = '1.0'
        action = $Action
        runner_pid = $PID
        started_at = [DateTimeOffset]::UtcNow.ToString('o')
    } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($LockPath + '.json', $metadata + "`n")
    [System.IO.File]::WriteAllText($ReadyPath, 'ready')
    while (-not (Test-Path -LiteralPath $ReleasePath)) { Start-Sleep -Milliseconds 25 }
}
finally {
    try { $stream.Unlock($Offset, 1) } catch { }
    $stream.Dispose()
}
""".strip()
        + "\n",
        encoding="ascii",
    )
    command = [POWERSHELL, "-NoProfile"]
    if Path(POWERSHELL).name.casefold().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(
        [
            "-File",
            str(holder),
            "-LockPath",
            str(lock_path),
            "-ReadyPath",
            str(ready),
            "-ReleasePath",
            str(release),
            "-Offset",
            str(offset),
            "-Action",
            action,
        ]
    )
    process = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = time.monotonic() + 10
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.025)
    if not ready.exists():
        stdout, stderr = process.communicate(timeout=5)
        pytest.fail(f"lock holder did not start: {stdout}\n{stderr}")
    return process, release


def test_prepare_dry_run_derives_paths_and_constructs_only_existing_runner_commands(
    tmp_path: Path,
) -> None:
    root = validation_root(tmp_path)
    secret = "must-not-appear"

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "Prepare",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        sys.executable,
        "-DryRun",
        environment=validation_environment("stageflow_validation_003", secret=secret),
    )

    assert result.returncode == 0, result.stderr
    assert "kernel-run-003.toml" in result.stdout
    assert "media\\run-003" in result.stdout or "media/run-003" in result.stdout
    assert "'initialize'" in result.stdout
    assert "'migrate'" in result.stdout
    assert "'bootstrap'" in result.stdout
    assert "'status'" in result.stdout
    assert "real_event_playback.py" in result.stdout
    assert secret not in result.stdout
    assert secret not in result.stderr
    assert not root.exists()


def test_validation_boundary_accepts_exact_named_segment_on_native_path(
    tmp_path: Path,
) -> None:
    root = tmp_path / "nested" / "stageflow-validation"

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "Prepare",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        sys.executable,
        "-DryRun",
        environment=validation_environment("stageflow_validation_003"),
    )

    assert result.returncode == 0, result.stderr
    assert "validation_root_must_include_stageflow-validation_directory" not in result.stderr
    assert not root.exists()


def test_prepare_refuses_an_existing_run_artifact_without_overwriting_it(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    root.mkdir(parents=True)
    existing = root / "run-003.json"
    existing.write_text("preserve-me", encoding="utf-8")

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "Prepare",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        sys.executable,
        environment=validation_environment("stageflow_validation_003"),
    )

    assert result.returncode != 0
    assert "prepare_refuses_existing_artifact" in result.stderr
    assert existing.read_text(encoding="utf-8") == "preserve-me"


def test_prepare_generates_configuration_accepted_by_current_kernel_schema(
    tmp_path: Path,
) -> None:
    root = validation_root(tmp_path)
    fake_psql = tmp_path / "fake-psql.ps1"
    fake_psql.write_text(
        """
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ToolArguments)
if ($ToolArguments -contains '--version') { Write-Output 'psql (fake) 16.0'; exit 0 }
Write-Output ($env:PGDATABASE + '|16.0')
exit 0
""".strip()
        + "\n",
        encoding="ascii",
    )
    fake_uv = tmp_path / "fake-uv.ps1"
    fake_uv.write_text(
        """
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ToolArguments)
if ($ToolArguments -contains '--version') { Write-Output 'fake tool version'; exit 0 }
$commandIndex = [Array]::IndexOf($ToolArguments, 'initialize')
if ($commandIndex -ge 0) {
    $runFileIndex = [Array]::IndexOf($ToolArguments, '--run-file')
    $runFile = $ToolArguments[$runFileIndex + 1]
    $json = '{"configuration":{' +
        '"deployment_id":"stageflow-validation-run-003",' +
        '"event_key":"real-event-validation-run-003"},' +
        '"sessions":{},"status_snapshots":[]}'
    [System.IO.File]::WriteAllText($runFile, $json, [System.Text.Encoding]::UTF8)
}
exit 0
""".strip()
        + "\n",
        encoding="ascii",
    )
    environment = validation_environment("stageflow_validation_003")

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "Prepare",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(fake_uv),
        "-PsqlPath",
        str(fake_psql),
        environment=environment,
    )

    assert result.returncode == 0, result.stderr
    config_path = root / "kernel-run-003.toml"
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    configuration = load_kernel_deployment_configuration(config_path, environment=environment)
    assert raw["schema_version"] == "1.0"
    assert raw["event_mode"] == "event"
    assert raw["network_policy"] == "local_only"
    assert len(configuration.deployment.event.stages) == 1
    assert configuration.deployment.event.stages[0].key == "main"
    assert len(configuration.deployment.event.stages[0].sources) == 1
    assert configuration.deployment.event.stages[0].sources[0].path == (
        root / "media" / "run-003"
    ).as_posix()
    manifest_text = (root / "run-003.environment.json").read_text(encoding="utf-8")
    assert "controller-secret" not in manifest_text
    assert "stageflow_validation_003" in manifest_text


def test_prepare_rejects_database_name_that_does_not_match_the_run_without_leaking_secret(
    tmp_path: Path,
) -> None:
    secret = "do-not-leak-this-password"

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "Prepare",
        "-ValidationRoot",
        str(validation_root(tmp_path)),
        "-UvPath",
        sys.executable,
        "-DryRun",
        environment=validation_environment("stageflow_validation_002", secret=secret),
    )

    assert result.returncode != 0
    assert "validation_database_run_mismatch" in result.stderr
    assert "stageflow_validation_003" in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr


def test_controller_protects_run_002_even_for_a_dry_run(tmp_path: Path) -> None:
    result = run_controller(
        "-Run",
        "2",
        "-Action",
        "Prepare",
        "-ValidationRoot",
        str(validation_root(tmp_path)),
        "-DryRun",
        environment=validation_environment("stageflow_validation_002"),
    )

    assert result.returncode != 0
    assert "protected_baseline_run" in result.stderr


def test_offline_checkpoint_interprets_attention_without_invoking_runtime(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    root.mkdir(parents=True)
    (root / "run-003.json").write_text(
        json.dumps(
            {
                "sessions": {
                    "session-a": {
                        "activity_state": "presentation_ended",
                        "authoritative_end": "2026-08-11T12:00:00-07:00",
                        "package_state": "assembling",
                        "package_revision": 0,
                        "revision": 2,
                    }
                },
                "status_snapshots": [
                    {
                        "database_available": True,
                        "ready": True,
                        "recovering": False,
                        "attention_codes": [],
                        "stages": [
                            {
                                "stage_key": "main",
                                "discovered": 20,
                                "stabilizing": 1,
                                "registered": 19,
                                "associated": 18,
                                "unresolved": 1,
                                "conflicting": 0,
                                "session_activity_state": "presentation_ended",
                                "session_package_state": "assembling",
                                "session_package_revision": 0,
                                "attention_codes": ["media_association_unresolved"],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "Checkpoint",
        "-ValidationRoot",
        str(root),
        "-Offline",
    )

    assert result.returncode == 0, result.stderr
    assert "stabilizing=1" in result.stdout
    assert "unresolved=1" in result.stdout
    assert "Session session-a: activity=presentation_ended" in result.stdout
    assert "review required" in result.stdout
    assert "media_association_unresolved" in result.stdout


def test_child_runner_failure_exit_code_is_propagated(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    write_matching_artifacts(root)
    fake_uv = tmp_path / "fake-uv.ps1"
    fake_uv.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\nexit 7\n",
        encoding="ascii",
    )

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "Status",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(fake_uv),
        environment=validation_environment("stageflow_validation_003"),
    )

    assert result.returncode == 7
    assert "validation_runner_failed_with_exit_code:7" in result.stderr


def test_package_ready_stops_before_transition_when_session_is_active(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    _, run_file, _ = write_matching_artifacts(root)
    run_file.write_text(
        json.dumps(
            {
                "configuration": {
                    "deployment_id": "stageflow-validation-run-003",
                    "event_key": "real-event-validation-run-003",
                },
                "sessions": {
                    "main": {
                        "activity_state": "presentation_active",
                        "authoritative_end": None,
                        "package_state": "assembling",
                    }
                },
                "status_snapshots": [
                    {
                        "database_available": True,
                        "ready": True,
                        "recovering": False,
                        "attention_codes": [],
                        "stages": [
                            {
                                "stage_key": "main",
                                "stabilizing": 0,
                                "unresolved": 0,
                                "conflicting": 0,
                                "attention_codes": [],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    invocation_log = tmp_path / "fake-uv.log"
    fake_uv = tmp_path / "successful-fake-uv.ps1"
    fake_uv.write_text(
        """
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ToolArguments)
Add-Content -LiteralPath $env:STAGEFLOW_CONTROLLER_TEST_LOG -Value ($ToolArguments -join ' ')
exit 0
""".strip()
        + "\n",
        encoding="ascii",
    )
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "PackageReady",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(fake_uv),
        "-ConfirmHumanAuthority",
        environment=environment,
    )

    assert result.returncode != 0
    assert "package_ready_requires_authoritative_presentation_end" in result.stderr
    invocations = invocation_log.read_text(encoding="utf-8")
    assert " status " in f" {invocations} "
    assert "package-ready" not in invocations


def test_authoritative_action_requires_explicit_human_confirmation(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    write_matching_artifacts(root)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "StartSession",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        sys.executable,
        "-DryRun",
        environment=validation_environment("stageflow_validation_003"),
    )

    assert result.returncode != 0
    assert "human_authority_confirmation_required" in result.stderr


@pytest.mark.parametrize(
    ("action", "field", "initial_sessions", "extra"),
    [
        ("StartSession", "authoritative_start", {}, []),
        (
            "EndSession",
            "authoritative_end",
            {
                "session-a": {
                    "activity_state": "presentation_active",
                    "authoritative_start": "2026-08-12T10:00:00+00:00",
                    "authoritative_end": None,
                }
            },
            ["-Reason", "operator-declared-end"],
        ),
    ],
)
def test_explicit_authority_timestamp_is_forwarded_and_used_unchanged(
    tmp_path: Path,
    action: str,
    field: str,
    initial_sessions: dict[str, object],
    extra: list[str],
) -> None:
    root = validation_root(tmp_path)
    _, run_file, _ = write_matching_artifacts(root)
    state = json.loads(run_file.read_text(encoding="utf-8"))
    state["sessions"] = initial_sessions
    run_file.write_text(json.dumps(state), encoding="utf-8")
    invocation_log = tmp_path / "authority-invocation.log"
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)
    authority_at = "2026-08-12T10:30:45.123456-07:00"

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        action,
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_session_updating_fake_uv(tmp_path)),
        "-SessionLabel",
        "session-a",
        "-At",
        authority_at,
        "-ConfirmHumanAuthority",
        *extra,
        environment=environment,
    )

    assert result.returncode == 0, result.stderr
    persisted = json.loads(run_file.read_text(encoding="utf-8"))
    assert persisted["sessions"]["session-a"][field] == authority_at
    assert f"--at {authority_at}" in invocation_log.read_text(encoding="utf-8")


def test_now_is_captured_before_slow_runner_processing(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    _, run_file, _ = write_matching_artifacts(root)
    invocation_log = tmp_path / "authority-invocation.log"
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)
    environment["STAGEFLOW_CONTROLLER_TEST_DELAY_MILLISECONDS"] = "1200"
    wall_start = datetime.now(UTC)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "StartSession",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_session_updating_fake_uv(tmp_path)),
        "-SessionLabel",
        "session-a",
        "-ConfirmHumanAuthority",
        environment=environment,
    )
    wall_end = datetime.now(UTC)

    assert result.returncode == 0, result.stderr
    persisted = json.loads(run_file.read_text(encoding="utf-8"))
    captured_text = persisted["sessions"]["session-a"]["authoritative_start"]
    captured = datetime.fromisoformat(captured_text)
    invocation = invocation_log.read_text(encoding="utf-8")
    assert wall_start <= captured <= wall_end
    assert (wall_end - captured).total_seconds() >= 1.0
    assert "--at now" not in invocation
    assert f"--at {captured_text}" in invocation


@pytest.mark.parametrize(
    ("action", "phase", "label", "initial_sessions", "extra", "expected"),
    [
        (
            "StartSession",
            "SessionA",
            "session-a",
            {},
            [],
            "SESSION A ACTIVE \u2014 SAFE TO BEGIN RECORDING",
        ),
        (
            "EndSession",
            "SessionA",
            "session-a",
            {
                "session-a": {
                    "activity_state": "presentation_active",
                    "authoritative_start": "2026-08-12T10:00:00+00:00",
                    "authoritative_end": None,
                }
            },
            ["-Reason", "operator-declared-end"],
            "SESSION A ENDED \u2014 KEEP RECORDING; WAITING FOR SESSION B AUTHORITY",
        ),
        (
            "StartSession",
            "SessionB",
            "session-b",
            {
                "session-a": {
                    "activity_state": "presentation_ended",
                    "authoritative_start": "2026-08-12T10:00:00+00:00",
                    "authoritative_end": "2026-08-12T10:30:00+00:00",
                }
            },
            ["-PredecessorSessionLabel", "session-a"],
            "SESSION B ACTIVE \u2014 SAFE TO CONTINUE TURNOVER INGEST",
        ),
        (
            "EndSession",
            "SessionB",
            "session-b",
            {
                "session-a": {
                    "activity_state": "presentation_ended",
                    "authoritative_start": "2026-08-12T10:00:00+00:00",
                    "authoritative_end": "2026-08-12T10:30:00+00:00",
                },
                "session-b": {
                    "activity_state": "presentation_active",
                    "authoritative_start": "2026-08-12T10:31:00+00:00",
                    "authoritative_end": None,
                },
            },
            ["-PredecessorSessionLabel", "session-a", "-Reason", "operator-declared-end"],
            "SESSION B ENDED \u2014 SAFE TO STOP RECORDING",
        ),
    ],
)
def test_turnover_boundaries_emit_exact_live_operation_checkpoints(
    tmp_path: Path,
    action: str,
    phase: str,
    label: str,
    initial_sessions: dict[str, object],
    extra: list[str],
    expected: str,
) -> None:
    root = validation_root(tmp_path)
    _, run_file, _ = write_matching_artifacts(root)
    state = json.loads(run_file.read_text(encoding="utf-8"))
    state["sessions"] = initial_sessions
    run_file.write_text(json.dumps(state), encoding="utf-8")

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        action,
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_session_updating_fake_uv(tmp_path)),
        "-TurnoverGuard",
        "-TurnoverPhase",
        phase,
        "-SessionLabel",
        label,
        "-ConfirmHumanAuthority",
        *extra,
        environment=validation_environment("stageflow_validation_003"),
    )

    assert result.returncode == 0, result.stderr
    assert expected in result.stdout


def test_guarded_turnover_drive_refuses_without_expected_session(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    write_matching_artifacts(root)
    invocation_log = tmp_path / "fake-uv.log"
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "DriveCycles",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_logging_fake_uv(tmp_path)),
        "-TurnoverGuard",
        "-TurnoverPhase",
        "SessionA",
        "-SessionLabel",
        "session-a",
        "-MaxCycles",
        "1",
        environment=environment,
    )

    assert result.returncode != 0
    assert "WAITING FOR HUMAN AUTHORITY" in result.stdout
    assert "expected_session=session-a" in result.stdout
    assert "activity=not_realized" in result.stdout
    assert "turnover_drive_requires_presentation_active:session-a" in result.stderr
    assert not invocation_log.exists()


def test_guarded_turnover_drive_allows_presentation_active_session(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    _, run_file, _ = write_matching_artifacts(root)
    state = json.loads(run_file.read_text(encoding="utf-8"))
    state["sessions"] = {
        "session-a": {
            "activity_state": "presentation_active",
            "authoritative_start": "2026-08-12T10:00:00+00:00",
            "authoritative_end": None,
        }
    }
    state["media_blocks"] = {}
    run_file.write_text(json.dumps(state), encoding="utf-8")
    invocation_log = tmp_path / "fake-uv.log"
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "DriveCycles",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_logging_fake_uv(tmp_path)),
        "-TurnoverGuard",
        "-TurnoverPhase",
        "SessionA",
        "-SessionLabel",
        "session-a",
        "-MaxCycles",
        "1",
        environment=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "activity=presentation_active" in result.stdout
    assert "Qualification runtime estimate" in result.stdout
    assert "drive-cycles" in invocation_log.read_text(encoding="utf-8")


def test_session_b_turnover_phase_requires_authoritative_session_a_end(
    tmp_path: Path,
) -> None:
    root = validation_root(tmp_path)
    _, run_file, _ = write_matching_artifacts(root)
    state = json.loads(run_file.read_text(encoding="utf-8"))
    state["sessions"] = {
        "session-a": {
            "activity_state": "presentation_ended",
            "authoritative_end": None,
        },
        "session-b": {
            "activity_state": "presentation_active",
            "authoritative_start": "2026-08-12T11:00:00+00:00",
            "authoritative_end": None,
        },
    }
    run_file.write_text(json.dumps(state), encoding="utf-8")

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "DriveCycles",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_logging_fake_uv(tmp_path)),
        "-TurnoverGuard",
        "-TurnoverPhase",
        "SessionB",
        "-SessionLabel",
        "session-b",
        "-PredecessorSessionLabel",
        "session-a",
        "-MaxCycles",
        "1",
        environment=validation_environment("stageflow_validation_003"),
    )

    assert result.returncode != 0
    assert "WAITING FOR HUMAN AUTHORITY" in result.stdout
    assert "session=session-a activity=presentation_ended authoritative_end=absent" in result.stdout
    assert "turnover_predecessor_requires_authoritative_presentation_end:session-a" in result.stderr


def test_unguarded_sessionless_drive_remains_allowed(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    write_matching_artifacts(root)
    invocation_log = tmp_path / "fake-uv.log"
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "DriveCycles",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_logging_fake_uv(tmp_path)),
        "-MaxCycles",
        "1",
        environment=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "drive-cycles" in invocation_log.read_text(encoding="utf-8")


def test_oversized_drive_cycles_is_refused_with_smaller_suggestion(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    _, run_file, _ = write_matching_artifacts(root)
    state = json.loads(run_file.read_text(encoding="utf-8"))
    state["media_blocks"] = {f"candidate-{index}": {} for index in range(35)}
    run_file.write_text(json.dumps(state), encoding="utf-8")
    invocation_log = tmp_path / "fake-uv.log"
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "DriveCycles",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_logging_fake_uv(tmp_path)),
        "-MaxCycles",
        "60",
        environment=environment,
    )

    assert result.returncode != 0
    assert "effective_candidates=35" in result.stdout
    assert "suggested_max_cycles=7" in result.stdout
    assert "drive_cycles_estimated_runtime_exceeds_interactive_budget" in result.stderr
    assert not invocation_log.exists()


def test_drive_estimate_uses_accumulated_eligible_source_entries(tmp_path: Path) -> None:
    root = validation_root(tmp_path)
    _, run_file, media = write_matching_artifacts(root)
    state = json.loads(run_file.read_text(encoding="utf-8"))
    state["media_blocks"] = {f"candidate-{index}": {} for index in range(5)}
    run_file.write_text(json.dumps(state), encoding="utf-8")
    for index in range(32):
        (media / f"segment-{index:03d}.mp4").touch()
    (media / ".hidden.mp4").touch()
    (media / "segment.partial").touch()
    (media / "segment.mov").touch()
    nested = media / "nested"
    nested.mkdir()
    (nested / "nested.mp4").touch()
    invocation_log = tmp_path / "fake-uv.log"
    environment = validation_environment("stageflow_validation_003")
    environment["STAGEFLOW_CONTROLLER_TEST_LOG"] = str(invocation_log)

    result = run_controller(
        "-Run",
        "3",
        "-Action",
        "DriveCycles",
        "-ValidationRoot",
        str(root),
        "-UvPath",
        str(write_logging_fake_uv(tmp_path)),
        "-MaxCycles",
        "7",
        environment=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "durable_candidates=5" in result.stdout
    assert "source_eligible_entries=32" in result.stdout
    assert "source_count_status=available" in result.stdout
    assert "effective_candidates=32" in result.stdout
    assert "estimated_seconds=120.4" in result.stdout
    assert "drive-cycles" in invocation_log.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("lock_offset", "active_action"),
    [(0, "Cycle"), (1, "DriveCycles")],
)
def test_active_controller_or_surviving_child_refuses_overlapping_mutation(
    tmp_path: Path,
    lock_offset: int,
    active_action: str,
) -> None:
    root = validation_root(tmp_path)
    write_matching_artifacts(root)
    lock_path = root / "run-003.operation.lock"
    process, release = start_lock_holder(
        tmp_path,
        lock_path=lock_path,
        offset=lock_offset,
        action=active_action,
    )
    secret = "must-remain-redacted"
    try:
        result = run_controller(
            "-Run",
            "3",
            "-Action",
            "Status",
            "-ValidationRoot",
            str(root),
            "-UvPath",
            sys.executable,
            environment=validation_environment(
                "stageflow_validation_003", secret=secret
            ),
        )
    finally:
        release.write_text("release", encoding="ascii")
        process.communicate(timeout=10)

    assert result.returncode != 0
    assert "qualification_operation_already_active" in result.stderr
    assert f"action={active_action}" in result.stderr
    assert "HOST TIMEOUT DOES NOT PROVE CHILD TERMINATION" in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr
