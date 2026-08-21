from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import POINTER, Structure, byref, c_size_t, sizeof
from ctypes.wintypes import BOOL, DWORD, HANDLE
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg

from app.bootstrap.event_mode_kernel import (
    KernelComponents,
    build_kernel_components,
    load_kernel_components_from_environment,
)
from app.contexts.production.event_mode_kernel import (
    AssociationStatus,
    EpistemicKind,
    SessionPackageState,
    StartSessionRequest,
)
from app.contexts.production.event_mode_kernel.repository import (
    KernelConflictError,
    KernelStorageUnavailableError,
)
from app.core.config.deployment import load_kernel_deployment_configuration
from app.shared.ids import EntityId


class _ProcessMemoryCounters(Structure):
    _fields_ = [
        ("cb", DWORD),
        ("page_fault_count", DWORD),
        ("peak_working_set_size", c_size_t),
        ("working_set_size", c_size_t),
        ("quota_peak_paged_pool_usage", c_size_t),
        ("quota_paged_pool_usage", c_size_t),
        ("quota_peak_non_paged_pool_usage", c_size_t),
        ("quota_non_paged_pool_usage", c_size_t),
        ("pagefile_usage", c_size_t),
        ("peak_pagefile_usage", c_size_t),
        ("private_usage", c_size_t),
    ]


def _working_set_bytes() -> int:
    native_windll = getattr(ctypes, "windll", None)
    if native_windll is None:
        raise OSError("Windows process memory APIs are unavailable")
    counters = _ProcessMemoryCounters()
    counters.cb = sizeof(counters)
    get_current_process = native_windll.kernel32.GetCurrentProcess
    get_current_process.restype = HANDLE
    get_process_memory_info = native_windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        HANDLE,
        POINTER(_ProcessMemoryCounters),
        DWORD,
    ]
    get_process_memory_info.restype = BOOL
    handle = get_current_process()
    ok = get_process_memory_info(handle, byref(counters), counters.cb)
    if not ok:
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.working_set_size or 0)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _components(config_path: Path) -> KernelComponents:
    loaded = load_kernel_components_from_environment(
        environment={
            **os.environ,
            "STAGEFLOW_KERNEL_CONFIG_PATH": str(config_path),
        }
    )
    if loaded is None:
        raise RuntimeError("qualification_configuration_not_loaded")
    return loaded


def prepare(root: Path) -> dict[str, Any]:
    main = root / "media" / "main"
    studio = root / "media" / "studio"
    main.mkdir(parents=True, exist_ok=True)
    studio.mkdir(parents=True, exist_ok=True)
    config_path = root / "kernel.toml"
    config_path.write_text(
        f"""
schema_version = "1.0"
deployment_id = "razer-kernel-qualification"
node_id = "razer-reference-node"
node_role = "node"
event_mode = "event"
network_policy = "local_only"
postgres_dsn_secret_ref = "KERNEL_DSN"

[resources]
maximum_concurrent_assessments = 2
maximum_cpu_percentage = 20
maximum_memory_bytes = 536870912
minimum_stable_seconds = 1

[event]
key = "razer-qualification-20260809"
name = "Razer Durable Kernel Qualification"

[[event.stages]]
key = "main"
name = "Main Stage"

[[event.stages.sources]]
key = "main-source"
path = "{main.as_posix()}"
maximum_candidates = 1000

[[event.stages]]
key = "studio"
name = "Studio Stage"

[[event.stages.sources]]
key = "studio-source"
path = "{studio.as_posix()}"
maximum_candidates = 1000
""".strip(),
        encoding="utf-8",
    )
    return {
        "config_path": str(config_path),
        "main_source": str(main),
        "studio_source": str(studio),
    }


def scenario(config_path: Path, result_path: Path) -> dict[str, Any]:
    configuration = load_kernel_deployment_configuration(config_path)
    components = build_kernel_components(configuration)
    source_paths = {
        key: Path(value) for key, value in configuration.sources.items()
    }
    (source_paths["main-source"] / "main-clear-001.mp4").write_bytes(
        b"main-clear-synthetic-media"
    )
    (source_paths["studio-source"] / "studio-conflict-001.mp4").write_bytes(
        b"studio-conflict-synthetic-media"
    )
    (source_paths["studio-source"] / "studio-unresolved-001.mp4").write_bytes(
        b"studio-unresolved-synthetic-media"
    )
    first = components.explicit_bootstrap(
        operation_id=EntityId.new(), actor_id=EntityId.new()
    )
    event_id = first.event_id
    stages = {
        stage.key: stage.id for stage in components.repository.list_stages(event_id)
    }
    actor_id = EntityId.new()
    expectation = components.kernel.record_program_expectation(
        event_id=event_id,
        key="main-keynote",
        title="Main Qualification Keynote",
        speakers=("Qualification Speaker",),
        stage_id=stages["main"],
        planned_start=datetime.now(UTC),
        planned_end=datetime.now(UTC) + timedelta(minutes=45),
        external_references={"qualification": "program-001"},
    )
    components.kernel.record_program_expectation(
        event_id=event_id,
        key="studio-program",
        title="Studio Qualification Program",
        stage_id=stages["studio"],
        planned_start=datetime.now(UTC),
        external_references={"qualification": "program-002"},
    )
    started_at = datetime.now(UTC)
    session = components.kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=event_id,
            stage_id=stages["main"],
            program_expectation_id=expectation.id,
            actor_id=actor_id,
            authoritative_start=started_at,
            requested_at=started_at,
        )
    )
    time.sleep(1.1)
    media_cycle = components.run_media_cycle(event_id=event_id, scope="scenario")
    studio_candidates = [
        item
        for item in media_cycle.candidate_results
        if item.source_binding_key == "studio-source"
    ]
    if len(studio_candidates) != 2:
        raise AssertionError("expected_two_studio_candidates")
    conflict_candidate = components.repository.get_candidate(
        studio_candidates[0].candidate_id
    )
    if conflict_candidate is None:
        raise AssertionError("conflict_candidate_missing")
    conflict = components.kernel.assign_asset(
        operation_id=EntityId.new(),
        asset_id=conflict_candidate.proposed_asset_id,
        session_id=session.id,
        actor_id=actor_id,
        reason="qualification_cross_stage_conflict",
    )
    if conflict.status is not AssociationStatus.CONFLICT:
        raise AssertionError("expected_cross_stage_conflict")
    before_proposal = components.repository.get_session(session.id)
    proposal = components.kernel.propose_session_boundary(
        session_id=session.id,
        boundary_kind="end",
        boundary_at=started_at + timedelta(minutes=45),
        epistemic_kind=EpistemicKind.DERIVED,
        proposer_id=EntityId.new(),
        evidence_ids=(EntityId.new(),),
        policy_id="qualification-boundary-policy",
        policy_version="1.0",
        reason="advisory qualification proposal",
    )
    if components.repository.get_session(session.id) != before_proposal:
        raise AssertionError("proposal_modified_authoritative_session")
    ended = components.kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=session.id,
        boundary_kind="end",
        boundary_at=datetime.now(UTC),
        actor_id=actor_id,
        reason="human_ended_qualification_presentation",
    )
    trailing_path = source_paths["main-source"] / "main-trailing-001.mp4"
    trailing_path.write_bytes(b"valid-trailing-synthetic-media")
    components.run_media_cycle(event_id=event_id, scope="trailing-discovery")
    time.sleep(1.1)
    trailing_cycle = components.run_media_cycle(
        event_id=event_id, scope="trailing-registration"
    )
    trailing_result = next(
        item
        for item in trailing_cycle.candidate_results
        if item.source_binding_key == "main-source" and item.outcome == "registered"
    )
    trailing_candidate = components.repository.get_candidate(
        trailing_result.candidate_id
    )
    if trailing_candidate is None:
        raise AssertionError("trailing_candidate_missing")
    trailing_association = components.kernel.assign_asset(
        operation_id=EntityId.new(),
        asset_id=trailing_candidate.proposed_asset_id,
        session_id=session.id,
        actor_id=actor_id,
        reason="human_confirmed_valid_trailing_media",
    )
    components.kernel.mark_package_ready(session.id)
    completed = components.kernel.complete_package(
        operation_id=EntityId.new(),
        session_id=session.id,
        actor_id=actor_id,
        approved=True,
        reason="qualification_package_approved",
    )
    status = components.status()
    if status is None:
        raise AssertionError("status_missing")
    main_status = next(stage for stage in status.stages if stage.stage_key == "main")
    studio_status = next(
        stage for stage in status.stages if stage.stage_key == "studio"
    )
    if studio_status.unresolved_media < 1 or studio_status.conflicting_media < 1:
        raise AssertionError("unresolved_or_conflict_projection_missing")
    if completed.package_state is not SessionPackageState.COMPLETE:
        raise AssertionError("package_not_complete")
    result: dict[str, Any] = {
        "executed_at": datetime.now(UTC).isoformat(),
        "event_id": event_id.value,
        "stage_ids": {key: value.value for key, value in stages.items()},
        "expectation_id": expectation.id.value,
        "session_id": session.id.value,
        "authoritative_start": session.authoritative_start.isoformat(),
        "authoritative_end": ended.authoritative_end.isoformat()
        if ended.authoritative_end
        else None,
        "proposal_id": proposal.id.value,
        "proposal_did_not_mutate_authority": True,
        "initial_cycle": {
            "candidates_seen": media_cycle.candidates_seen,
            "assets_registered": media_cycle.assets_registered,
        },
        "trailing_association": trailing_association.status.value,
        "package_state": completed.package_state.value,
        "package_revision": completed.package_revision,
        "producer_status": {
            "ready": status.ready,
            "recent_media": len(status.recent_media),
            "boundary_proposals": len(status.boundary_proposals),
            "main_registered": main_status.registered_media,
            "main_associated": main_status.associated_media,
            "studio_registered": studio_status.registered_media,
            "studio_unresolved": studio_status.unresolved_media,
            "studio_conflicting": studio_status.conflicting_media,
            "attention_codes": list(status.attention_codes),
        },
    }
    _write_json(result_path, result)
    return result


def reconcile(config_path: Path, result_path: Path) -> dict[str, Any]:
    components = _components(config_path)
    status = components.status()
    if status is None:
        raise AssertionError("recovered_status_missing")
    result: dict[str, Any] = {
        "executed_at": datetime.now(UTC).isoformat(),
        "event_id": status.event_id.value,
        "ready": status.ready,
        "reconciliation_status": status.latest_reconciliation.status.value
        if status.latest_reconciliation
        else None,
        "stage_ids": [stage.stage_id.value for stage in status.stages],
        "session_ids": [
            session.session_id.value
            for stage in status.stages
            for session in stage.assembling_sessions
        ],
        "registered_media": sum(stage.registered_media for stage in status.stages),
        "associated_media": sum(stage.associated_media for stage in status.stages),
        "unresolved_media": sum(stage.unresolved_media for stage in status.stages),
        "conflicting_media": sum(stage.conflicting_media for stage in status.stages),
        "boundary_proposals": len(status.boundary_proposals),
        "recent_media": len(status.recent_media),
        "attention_codes": list(status.attention_codes),
    }
    _write_json(result_path, result)
    return result


def _database_sample(dsn: str, event_id: EntityId) -> dict[str, int]:
    with psycopg.connect(dsn) as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()),
              pg_database_size(current_database()),
              (SELECT count(*) FROM stageflow.session WHERE event_id = %s),
              (SELECT count(*) FROM stageflow.media_candidate c JOIN stageflow.stage s
                 ON s.stage_id = c.stage_id WHERE s.event_id = %s),
              (SELECT count(*) FROM stageflow.completed_media_asset_registry a
                 JOIN stageflow.stage s ON s.stage_id = a.stage_id WHERE s.event_id = %s)
            """,
            (event_id.value, event_id.value, event_id.value),
        ).fetchone()
    if row is None:
        raise AssertionError("database_sample_missing")
    return {
        "connections": int(row[0]),
        "database_bytes": int(row[1]),
        "sessions": int(row[2]),
        "candidates": int(row[3]),
        "assets": int(row[4]),
    }


def endurance(
    config_path: Path,
    result_path: Path,
    duration_seconds: float,
) -> dict[str, Any]:
    configuration = load_kernel_deployment_configuration(config_path)
    components = _components(config_path)
    event = components.repository.get_event_by_key(components.event_key)
    if event is None:
        raise AssertionError("endurance_event_missing")
    event_id = event.id
    stages = {
        stage.key: stage.id
        for stage in components.repository.list_stages(event_id)
    }
    actor_id = EntityId.new()
    for key, stage_id in stages.items():
        try:
            components.kernel.start_session(
                StartSessionRequest(
                    operation_id=EntityId.new(),
                    event_id=event_id,
                    stage_id=stage_id,
                    actor_id=actor_id,
                    authoritative_start=datetime.now(UTC),
                    requested_at=datetime.now(UTC),
                    title=f"Endurance {key}",
                )
            )
        except KernelConflictError as exc:
            if "active_session" not in str(exc):
                raise
    started = time.monotonic()
    cpu_started = time.process_time()
    run_token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    samples: list[dict[str, Any]] = []
    segment_count = 0
    while time.monotonic() - started < duration_seconds:
        segment_count += 1
        for source_key, source_path in configuration.sources.items():
            Path(
                source_path,
                f"endurance-{run_token}-{source_key}-{segment_count:05d}.mp4",
            ).write_bytes(
                f"segment:{source_key}:{segment_count}".encode() * 4096
            )
        first = components.run_media_cycle(event_id=event_id, scope="endurance-observe")
        time.sleep(configuration.deployment.resources.minimum_stable_seconds + 0.05)
        second = components.run_media_cycle(event_id=event_id, scope="endurance-register")
        elapsed = time.monotonic() - started
        database = _database_sample(configuration.postgres_dsn, event_id)
        samples.append(
            {
                "elapsed_seconds": round(elapsed, 3),
                "working_set_bytes": _working_set_bytes(),
                "process_cpu_seconds": round(time.process_time() - cpu_started, 3),
                "candidates_seen": first.candidates_seen + second.candidates_seen,
                "assets_registered": first.assets_registered + second.assets_registered,
                **database,
            }
        )
    elapsed = time.monotonic() - started
    cpu_seconds = time.process_time() - cpu_started
    status = components.status()
    if status is None:
        raise AssertionError("endurance_status_missing")
    result: dict[str, Any] = {
        "executed_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(elapsed, 3),
        "segment_batches": segment_count,
        "segments_created": segment_count * len(configuration.sources),
        "process_cpu_seconds": round(cpu_seconds, 3),
        "average_process_cpu_percent_of_host": round(
            cpu_seconds / elapsed / max(os.cpu_count() or 1, 1) * 100, 3
        ),
        "working_set_start_bytes": samples[0]["working_set_bytes"],
        "working_set_end_bytes": samples[-1]["working_set_bytes"],
        "working_set_peak_bytes": max(
            int(sample["working_set_bytes"]) for sample in samples
        ),
        "final_database": _database_sample(configuration.postgres_dsn, event_id),
        "final_attention_codes": list(status.attention_codes),
        "samples": samples,
    }
    _write_json(result_path, result)
    return result


def endurance_for_platform(
    config_path: Path,
    result_path: Path,
    duration_seconds: float,
    *,
    platform_name: str | None = None,
) -> dict[str, Any]:
    selected_platform = sys.platform if platform_name is None else platform_name
    if selected_platform != "win32":
        result: dict[str, Any] = {
            "status": "skipped",
            "reason": "unsupported_platform",
            "required_platform": "win32",
        }
        _write_json(result_path, result)
        return result
    return endurance(config_path, result_path, duration_seconds)


def proxy(root: Path, result_path: Path, duration_seconds: float) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    block = os.urandom(8 * 1024 * 1024)
    started = time.monotonic()
    cpu_started = time.process_time()
    bytes_written = 0
    iterations = 0
    while time.monotonic() - started < duration_seconds:
        target = root / f"recording-proxy-{iterations % 4}.bin"
        target.write_bytes(block)
        bytes_written += len(block)
        digest = block
        for _ in range(12):
            digest = hashlib.sha256(digest).digest()
        iterations += 1
        time.sleep(0.1)
    elapsed = time.monotonic() - started
    result: dict[str, Any] = {
        "executed_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(elapsed, 3),
        "iterations": iterations,
        "bytes_written": bytes_written,
        "process_cpu_seconds": round(time.process_time() - cpu_started, 3),
        "retained_bytes": sum(path.stat().st_size for path in root.iterdir()),
    }
    _write_json(result_path, result)
    return result


def postgresql_recovery_correction(
    config_path: Path,
    result_path: Path,
    *,
    pg_ctl: Path,
    data_directory: Path,
    postgres_log: Path,
    start_options: str,
) -> dict[str, Any]:
    components = _components(config_path)
    status = components.status()
    if status is None:
        status = components.explicit_bootstrap(
            operation_id=EntityId.new(), actor_id=EntityId.new()
        )
    if not status.ready or status.latest_reconciliation is None:
        raise AssertionError("pre_outage_kernel_not_ready")
    pre_outage_id = status.latest_reconciliation.id

    subprocess.run(
        [str(pg_ctl), "-D", str(data_directory), "stop", "-m", "fast"],
        check=True,
    )
    try:
        try:
            components.status()
        except KernelStorageUnavailableError:
            pass
        else:
            raise AssertionError("postgresql_loss_not_observed")
    finally:
        subprocess.run(
            [
                str(pg_ctl),
                "-D",
                str(data_directory),
                "-l",
                str(postgres_log),
                "-o",
                start_options,
                "start",
            ],
            check=True,
        )

    before_reconciliation = components.status()
    if before_reconciliation is None:
        raise AssertionError("post_outage_status_missing")
    if before_reconciliation.ready or not before_reconciliation.recovering:
        raise AssertionError("post_outage_status_reused_stale_reconciliation")
    if before_reconciliation.latest_reconciliation is None:
        raise AssertionError("pre_outage_reconciliation_missing")
    if before_reconciliation.latest_reconciliation.id != pre_outage_id:
        raise AssertionError("reconciliation_advanced_before_recovery_run")

    recovered = components.reconcile_postgresql_recovery()
    if recovered is None or not recovered.ready or recovered.latest_reconciliation is None:
        raise AssertionError("successful_recovery_did_not_restore_readiness")
    if recovered.latest_reconciliation.id == pre_outage_id:
        raise AssertionError("successful_recovery_reused_old_reconciliation")
    successful_recovery_id = recovered.latest_reconciliation.id

    subprocess.run(
        [str(pg_ctl), "-D", str(data_directory), "stop", "-m", "fast"],
        check=True,
    )
    try:
        try:
            components.status()
        except KernelStorageUnavailableError:
            pass
        else:
            raise AssertionError("second_postgresql_loss_not_observed")
    finally:
        subprocess.run(
            [
                str(pg_ctl),
                "-D",
                str(data_directory),
                "-l",
                str(postgres_log),
                "-o",
                start_options,
                "start",
            ],
            check=True,
        )

    source = Path(components.configuration.deployment.event.stages[0].sources[0].path)
    unavailable_source = source.with_name(f"{source.name}.recovery-unavailable")
    source.rename(unavailable_source)
    try:
        failed = components.reconcile_postgresql_recovery()
        if failed is None or failed.ready or not failed.recovering:
            raise AssertionError("failed_reconciliation_restored_readiness")
        if failed.latest_reconciliation is None:
            raise AssertionError("failed_reconciliation_missing")
        failed_recovery_id = failed.latest_reconciliation.id
    finally:
        unavailable_source.rename(source)

    final = components.reconcile_postgresql_recovery()
    if final is None or not final.ready or final.latest_reconciliation is None:
        raise AssertionError("final_recovery_did_not_restore_readiness")
    result: dict[str, Any] = {
        "executed_at": datetime.now(UTC).isoformat(),
        "pre_outage_reconciliation_id": pre_outage_id.value,
        "successful_recovery_reconciliation_id": successful_recovery_id.value,
        "failed_recovery_reconciliation_id": failed_recovery_id.value,
        "final_reconciliation_id": final.latest_reconciliation.id.value,
        "before_reconciliation_ready": before_reconciliation.ready,
        "before_reconciliation_recovering": before_reconciliation.recovering,
        "failed_reconciliation_ready": failed.ready,
        "failed_reconciliation_recovering": failed.recovering,
        "final_ready": final.ready,
    }
    _write_json(result_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--root", type=Path, required=True)
    scenario_parser = subparsers.add_parser("scenario")
    scenario_parser.add_argument("--config", type=Path, required=True)
    scenario_parser.add_argument("--result", type=Path, required=True)
    reconcile_parser = subparsers.add_parser("reconcile")
    reconcile_parser.add_argument("--config", type=Path, required=True)
    reconcile_parser.add_argument("--result", type=Path, required=True)
    endurance_parser = subparsers.add_parser("endurance")
    endurance_parser.add_argument("--config", type=Path, required=True)
    endurance_parser.add_argument("--result", type=Path, required=True)
    endurance_parser.add_argument("--duration-seconds", type=float, required=True)
    proxy_parser = subparsers.add_parser("proxy")
    proxy_parser.add_argument("--root", type=Path, required=True)
    proxy_parser.add_argument("--result", type=Path, required=True)
    proxy_parser.add_argument("--duration-seconds", type=float, required=True)
    recovery_parser = subparsers.add_parser("postgresql-recovery-correction")
    recovery_parser.add_argument("--config", type=Path, required=True)
    recovery_parser.add_argument("--result", type=Path, required=True)
    recovery_parser.add_argument("--pg-ctl", type=Path, required=True)
    recovery_parser.add_argument("--data-directory", type=Path, required=True)
    recovery_parser.add_argument("--postgres-log", type=Path, required=True)
    recovery_parser.add_argument("--start-options", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.root)
    elif args.command == "scenario":
        result = scenario(args.config, args.result)
    elif args.command == "reconcile":
        result = reconcile(args.config, args.result)
    elif args.command == "endurance":
        result = endurance_for_platform(args.config, args.result, args.duration_seconds)
    elif args.command == "postgresql-recovery-correction":
        result = postgresql_recovery_correction(
            args.config,
            args.result,
            pg_ctl=args.pg_ctl,
            data_directory=args.data_directory,
            postgres_log=args.postgres_log,
            start_options=args.start_options,
        )
    else:
        result = proxy(args.root, args.result, args.duration_seconds)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
