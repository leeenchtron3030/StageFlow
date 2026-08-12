from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from qualification import real_event_playback as playback
from qualification.real_event_playback import (
    REPOSITORY_ROOT,
    RunFiles,
    ValidationRunnerError,
    drive_bounded_cycles,
    ensure_run_file_outside_repository,
    initialize_state,
    latest_recorded_stop,
    main,
    media_block_payload,
    record_command,
    require_isolated_database_confirmation,
    retained_operation_id,
)

from app.contexts.production.event_mode_kernel import (
    EpistemicKind,
    MediaCandidate,
    MediaRegistrationState,
    ResourceObservation,
)
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    load_kernel_deployment_configuration,
)
from app.shared.ids import EntityId


def write_configuration(path: Path, source: Path) -> None:
    path.write_text(
        f"""
schema_version = "1.0"
deployment_id = "real-event-validation-test"
node_id = "validation-node"
node_role = "development"
event_mode = "rehearsal"
network_policy = "local_only"
postgres_dsn_secret_ref = "VALIDATION_RUNNER_TEST_DSN"

[resources]
minimum_stable_seconds = 1

[event]
key = "real-event-validation-test"
name = "Real Event Validation Test"

[[event.stages]]
key = "main"
name = "Main Stage"

[[event.stages.sources]]
key = "main-source"
path = "{source.as_posix()}"
maximum_candidates = 100
allowed_extensions = [".mp4"]
""".strip(),
        encoding="utf-8",
    )


def test_runner_is_directly_executable_from_backend() -> None:
    backend_root = REPOSITORY_ROOT / "backend"

    result = subprocess.run(
        [
            sys.executable,
            "tests/qualification/real_event_playback.py",
            "--help",
        ],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Bounded, non-production StageFlow real-event validation runner" in result.stdout


def test_initialize_loads_configuration_without_persisting_source_or_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "external-media"
    source.mkdir()
    config = tmp_path / "kernel.toml"
    write_configuration(config, source)
    dsn = "postgresql://validation:secret@127.0.0.1:59999/validation_only"
    monkeypatch.setenv("VALIDATION_RUNNER_TEST_DSN", dsn)
    run_file = tmp_path / "results" / "run.json"

    result = main(
        [
            "initialize",
            "--config",
            str(config),
            "--run-file",
            str(run_file),
            "--mode",
            "vmix",
            "--corpus-item",
            "reference-main-001",
            "--source-assumption",
            "segment_duration=approximately_60_seconds",
        ]
    )

    assert result == 0
    state_text = run_file.read_text(encoding="utf-8")
    state = json.loads(state_text)
    assert state["configuration"]["event_key"] == "real-event-validation-test"
    assert state["corpus"]["item_id"] == "reference-main-001"
    assert state["source_assumptions"] == {
        "segment_duration": "approximately_60_seconds"
    }
    assert str(source) not in state_text
    assert dsn not in state_text
    summary_text = run_file.with_suffix(".md").read_text(encoding="utf-8")
    assert "Corpus item: `reference-main-001`" in summary_text
    assert "Stages: `main`" in summary_text
    assert "`segment_duration`: approximately_60_seconds" in summary_text
    assert "No bounded media cycles recorded" in summary_text
    assert "No fresh-process reconstruction recorded" in summary_text
    assert "Did media cadence feel noisy?" in summary_text
    assert str(source) not in summary_text
    assert dsn not in summary_text


def test_run_files_refuse_repository_output() -> None:
    with pytest.raises(
        ValidationRunnerError, match="run_file_must_be_outside_repository"
    ):
        RunFiles(REPOSITORY_ROOT / "validation-run.json")


def test_isolated_database_acknowledgement_is_mandatory() -> None:
    with pytest.raises(
        ValidationRunnerError,
        match="isolated_validation_database_acknowledgement_required",
    ):
        require_isolated_database_confirmation(False)

    require_isolated_database_confirmation(True)


def test_operation_identity_is_retained_and_conflicting_override_fails() -> None:
    state: dict[str, object] = {"operation_ids": {}}
    supplied = "00000000-0000-0000-0000-000000000101"

    first = retained_operation_id(state, key="session_start:main", supplied=supplied)
    replay = retained_operation_id(state, key="session_start:main")

    assert first == replay == EntityId(supplied)
    with pytest.raises(ValidationRunnerError, match="operation_id_conflict"):
        retained_operation_id(
            state,
            key="session_start:main",
            supplied="00000000-0000-0000-0000-000000000102",
        )


@pytest.mark.parametrize(
    ("command", "captured_field"),
    [("start-session", "authoritative_start"), ("end-session", "boundary_at")],
)
def test_session_commands_use_explicit_authority_timestamp(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    captured_field: str,
) -> None:
    authority_text = "2026-08-12T10:30:45.123456-07:00"
    captured: dict[str, datetime] = {}

    class FakeKernel:
        def start_session(self, request: Any) -> object:
            captured["authoritative_start"] = request.authoritative_start
            return object()

        def correct_session_boundary(self, **values: object) -> object:
            boundary_at = values["boundary_at"]
            assert isinstance(boundary_at, datetime)
            captured["boundary_at"] = boundary_at
            return object()

    components = SimpleNamespace(kernel=FakeKernel())
    event_id = EntityId("00000000-0000-0000-0000-000000000501")
    stage_id = EntityId("00000000-0000-0000-0000-000000000502")
    def fake_compose(_: EffectiveKernelConfiguration) -> Any:
        return components

    def fake_require_event(_: Any) -> EntityId:
        return event_id

    def fake_stage_id_for_key(*_: Any) -> EntityId:
        return stage_id

    def ignore_update_session(*_: Any) -> None:
        return None

    def empty_session_payload(_: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(playback, "compose_without_reconciliation", fake_compose)
    monkeypatch.setattr(playback, "require_event", fake_require_event)
    monkeypatch.setattr(playback, "stage_id_for_key", fake_stage_id_for_key)
    monkeypatch.setattr(playback, "update_session", ignore_update_session)
    monkeypatch.setattr(playback, "session_payload", empty_session_payload)
    state: dict[str, Any] = {
        "actor_id": "00000000-0000-0000-0000-000000000503",
        "operation_ids": {},
        "sessions": {
            "session-a": {
                "session_id": "00000000-0000-0000-0000-000000000504"
            }
        },
    }
    args = Namespace(
        command=command,
        confirm_isolated_validation_database=True,
        session_label="session-a",
        operation_id=None,
        stage_key="main",
        expectation_key=None,
        at=authority_text,
        title="Session A",
        reason="operator-declared-end",
    )

    configuration = cast(EffectiveKernelConfiguration, object())
    playback._command_result(  # pyright: ignore[reportPrivateUsage]
        configuration, state, args
    )

    assert captured[captured_field] == datetime.fromisoformat(authority_text)


def test_command_recording_is_deterministic_and_preserves_failure() -> None:
    state: dict[str, object] = {"commands": []}
    instants = iter(
        (
            datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
            datetime(2026, 8, 10, 10, 0, 1, tzinfo=UTC),
        )
    )
    monotonic = iter((10.0, 10.25))

    def fail() -> None:
        raise ValidationRunnerError("bounded_failure")

    with pytest.raises(ValidationRunnerError, match="bounded_failure"):
        record_command(
            state,
            name="cycle",
            action=fail,
            details={"database_acknowledged": True},
            now=lambda: next(instants),
            monotonic=lambda: next(monotonic),
        )

    assert state["commands"] == [
        {
            "sequence": 1,
            "command": "cycle",
            "invoked_at": "2026-08-10T10:00:00+00:00",
            "details": {"database_acknowledged": True},
            "completed_at": "2026-08-10T10:00:01+00:00",
            "duration_seconds": 0.25,
            "outcome": "failed",
            "error_type": "ValidationRunnerError",
            "error": "bounded_failure",
        }
    ]


def test_cycle_driver_is_finite_cadenced_and_cleanly_interruptible() -> None:
    current = 0.0
    sleeps: list[float] = []

    def monotonic() -> float:
        return current

    def sleep(seconds: float) -> None:
        nonlocal current
        sleeps.append(seconds)
        current += seconds

    results, interrupted = drive_bounded_cycles(
        lambda sequence: {"sequence": sequence},
        maximum_cycles=3,
        cycle_every_seconds=2.0,
        sleep=sleep,
        monotonic=monotonic,
    )

    assert results == [{"sequence": 1}, {"sequence": 2}, {"sequence": 3}]
    assert sleeps == [2.0, 2.0]
    assert interrupted is False

    def interrupt_after_first(sequence: int) -> dict[str, object]:
        if sequence == 2:
            raise KeyboardInterrupt
        return {"sequence": sequence}

    results, interrupted = drive_bounded_cycles(
        interrupt_after_first,
        maximum_cycles=5,
        cycle_every_seconds=0,
    )
    assert results == [{"sequence": 1}]
    assert interrupted is True


def test_cycle_driver_uses_start_to_start_target_without_overlapping_slow_cycles() -> None:
    current = 0.0
    starts: list[float] = []
    sleeps: list[float] = []

    def monotonic() -> float:
        return current

    def sleep(seconds: float) -> None:
        nonlocal current
        sleeps.append(seconds)
        current += seconds

    def run_slow_cycle(sequence: int) -> dict[str, int]:
        nonlocal current
        starts.append(current)
        current += 3.0
        return {"sequence": sequence}

    results, interrupted = drive_bounded_cycles(
        run_slow_cycle,
        maximum_cycles=3,
        cycle_every_seconds=2.0,
        sleep=sleep,
        monotonic=monotonic,
    )

    assert results == [{"sequence": 1}, {"sequence": 2}, {"sequence": 3}]
    assert starts == [0.0, 3.0, 6.0]
    assert sleeps == []
    assert interrupted is False


def test_cycle_driver_rejects_unbounded_values() -> None:
    with pytest.raises(ValidationRunnerError, match="cycle_count_out_of_bounds"):
        drive_bounded_cycles(
            lambda sequence: {"sequence": sequence},
            maximum_cycles=0,
            cycle_every_seconds=1,
        )
    with pytest.raises(ValidationRunnerError, match="cycle_interval_out_of_bounds"):
        drive_bounded_cycles(
            lambda sequence: {"sequence": sequence},
            maximum_cycles=1,
            cycle_every_seconds=-1,
        )


def test_media_block_record_omits_path_and_labels_mtime_as_proxy(tmp_path: Path) -> None:
    observed_at = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    candidate = MediaCandidate(
        id=EntityId("00000000-0000-0000-0000-000000000201"),
        proposed_asset_id=EntityId("00000000-0000-0000-0000-000000000202"),
        stage_id=EntityId("00000000-0000-0000-0000-000000000203"),
        source_binding_key="main-source",
        source_reference=str(tmp_path / "private" / "segment-001.mp4"),
        discovered_at=observed_at,
        last_observed_at=observed_at,
        state=MediaRegistrationState.STABILIZING,
        revision=1,
    )
    observation = ResourceObservation(
        id=EntityId("00000000-0000-0000-0000-000000000204"),
        candidate_id=candidate.id,
        observation_kind="asset_resource_snapshot",
        epistemic_kind=EpistemicKind.OBSERVED,
        observed_at=observed_at,
        recorded_at=observed_at + timedelta(milliseconds=1),
        facts={"filesystem_modified_at": "2026-08-10T09:59:58+00:00"},
    )

    block = media_block_payload(
        candidate=candidate,
        observations=(observation,),
        asset=None,
        association=None,
        include_filename=False,
    )

    assert block["filename"] is None
    assert str(tmp_path) not in json.dumps(block)
    assert block["filesystem_mtime_proxy"] == "2026-08-10T09:59:58+00:00"
    assert block["filesystem_mtime_is_block_close_truth"] is False


def test_initialize_state_uses_external_manifest_basename_and_no_runtime_candidate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "external-media"
    source.mkdir()
    config_path = tmp_path / "kernel.toml"
    write_configuration(config_path, source)
    manifest = tmp_path / "private-corpus-manifest.yaml"
    manifest.write_text("schema_version: '1.0'\n", encoding="utf-8")
    configuration = load_kernel_deployment_configuration(
        config_path,
        environment={
            "VALIDATION_RUNNER_TEST_DSN": (
                "postgresql://validation@127.0.0.1:59999/validation_only"
            )
        },
    )

    state = initialize_state(
        configuration,
        run_id="00000000-0000-0000-0000-000000000301",
        actor_id="00000000-0000-0000-0000-000000000302",
        mode="direct",
        corpus_manifest=manifest,
        corpus_item_id="reference-main-001",
        include_filenames=False,
        source_assumptions={},
        now=lambda: datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
    )

    assert state["corpus"] == {
        "manifest_reference": "external:private-corpus-manifest.yaml",
        "item_id": "reference-main-001",
    }
    assert state["media_blocks"] == {}
    assert "postgres_dsn" not in json.dumps(state)


def test_run_file_path_validation_accepts_external_json(tmp_path: Path) -> None:
    expected = (tmp_path / "run.json").resolve()
    assert ensure_run_file_outside_repository(expected) == expected


def test_reconstruction_uses_latest_recorded_stop() -> None:
    state: dict[str, object] = {
        "process_stops": [
            {"stopped_at": "2026-08-10T10:00:00+00:00"},
            {"stopped_at": "2026-08-10T11:00:00+00:00"},
        ]
    }
    assert latest_recorded_stop(state) == "2026-08-10T11:00:00+00:00"


def runner_state(tmp_path: Path) -> dict[str, Any]:
    source = tmp_path / "external-media"
    source.mkdir(exist_ok=True)
    config_path = tmp_path / "kernel.toml"
    write_configuration(config_path, source)
    configuration = load_kernel_deployment_configuration(
        config_path,
        environment={
            "VALIDATION_RUNNER_TEST_DSN": (
                "postgresql://validation@127.0.0.1:59999/validation_only"
            )
        },
    )
    return initialize_state(
        configuration,
        run_id="00000000-0000-0000-0000-000000000401",
        actor_id="00000000-0000-0000-0000-000000000402",
        mode="direct",
        corpus_manifest=None,
        corpus_item_id="atomic-evidence",
        include_filenames=False,
        source_assumptions={},
    )


def test_run_file_atomic_write_remains_valid_json(tmp_path: Path) -> None:
    run_file = tmp_path / "evidence" / "run-004.json"
    files = RunFiles(run_file)
    state = runner_state(tmp_path)

    with files.operation_lock(action="test-atomic-write"):
        files.save(state)

    assert json.loads(run_file.read_text(encoding="utf-8"))["run_id"] == state["run_id"]
    assert not list(run_file.parent.glob(f".{run_file.name}.*.tmp"))


def test_stale_writer_cannot_erase_newer_run_record_evidence(tmp_path: Path) -> None:
    run_file = tmp_path / "evidence" / "run-004.json"
    initial = RunFiles(run_file)
    state = runner_state(tmp_path)
    with initial.operation_lock(action="initialize-evidence"):
        initial.save(state)

    stale_files = RunFiles(run_file)
    stale = stale_files.load()
    current_files = RunFiles(run_file)
    current = current_files.load()
    current["anomalies"].append({"text": "newer-evidence"})
    current_files.save(current)

    stale["anomalies"].append({"text": "stale-evidence"})
    with pytest.raises(
        ValidationRunnerError, match="run_file_concurrent_update_detected"
    ):
        stale_files.save(stale)

    preserved = json.loads(run_file.read_text(encoding="utf-8"))
    assert preserved["anomalies"] == [{"text": "newer-evidence"}]


def test_incremental_cycle_checkpoint_preserves_running_command_and_completed_cycle(
    tmp_path: Path,
) -> None:
    run_file = tmp_path / "evidence" / "run-004.json"
    files = RunFiles(run_file)
    state = runner_state(tmp_path)
    with files.operation_lock(action="initialize-evidence"):
        files.save(state)

    active_files = RunFiles(run_file)
    active = active_files.load()

    def action() -> dict[str, object]:
        started = json.loads(run_file.read_text(encoding="utf-8"))
        assert started["commands"][-1]["outcome"] == "running"

        def run_once(sequence: int) -> dict[str, object]:
            if sequence == 2:
                raise KeyboardInterrupt
            entry: dict[str, object] = {
                "sequence": sequence,
                "scope": "incremental-test",
            }
            active["cycles"].append(entry)
            return entry

        cycles, interrupted = drive_bounded_cycles(
            run_once,
            maximum_cycles=3,
            cycle_every_seconds=0,
            on_cycle_completed=lambda _: active_files.save(active),
        )
        return {"cycles": cycles, "interrupted": interrupted}

    record_command(
        active,
        name="drive-cycles",
        action=action,
        on_started=lambda: active_files.save(active),
    )

    checkpoint = json.loads(run_file.read_text(encoding="utf-8"))
    assert checkpoint["cycles"] == [{"scope": "incremental-test", "sequence": 1}]
    assert checkpoint["commands"][-1]["command"] == "drive-cycles"
    assert checkpoint["commands"][-1]["outcome"] == "running"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows byte-range lock regression")
def test_direct_runner_lock_refuses_concurrent_mutation(tmp_path: Path) -> None:
    run_file = tmp_path / "evidence" / "run-004.json"
    first = RunFiles(run_file)
    second = RunFiles(run_file)

    with first.operation_lock(action="drive-cycles"):
        with pytest.raises(
            ValidationRunnerError, match="qualification_operation_already_active"
        ):
            with second.operation_lock(action="status"):
                pytest.fail("concurrent runner unexpectedly acquired the run lock")
