from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from time import sleep
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg

from app.bootstrap.event_mode_kernel import load_kernel_components_from_environment
from app.demo import cli as demo_cli
from app.infrastructure.devcon.session_publish import (
    DevconPublishError,
    DevconSessionPublishAdapter,
    RemoteDevconSession,
)

EXPECTED_DEMO_DATABASE = "stageflow_demo"
DEMO_DSN_SECRET = "STAGEFLOW_DEMO_POSTGRES_DSN"
DEVCON_API_KEY_SECRET = "STAGEFLOW_DEMO_DEVCON_API_KEY"
_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
_MAXIMUM_API_BYTES = 16 * 1024 * 1024
_PUBLIC_API_CONVERGENCE_DELAYS_SECONDS = (0.0, 65.0, 65.0, 65.0)


class DemoControllerError(RuntimeError):
    """The guarded Demo controller refused or could not complete an action."""


@dataclass(frozen=True, slots=True)
class SessionSelection:
    session_id: str
    activity_state: str
    package_state: str
    package_revision: int
    revision: int
    authoritative_start: str
    authoritative_end: str | None
    program_expectation_id: str | None


@dataclass(frozen=True, slots=True)
class DevconPublishCandidate:
    event_id: str
    remote_session_id: str
    transcript_text: str
    duration_seconds: int
    digest: str


def resolve_required_secret(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise DemoControllerError(f"required_secret_unavailable:{name}")
    return value


def validate_database_identity(database_name: str) -> str:
    normalized = database_name.strip().casefold()
    rejected_markers = ("test", "worker", "validation", "qualification", "pytest")
    if any(marker in normalized for marker in rejected_markers):
        raise DemoControllerError("demo_database_qualification_identity_rejected")
    if normalized != EXPECTED_DEMO_DATABASE:
        raise DemoControllerError("demo_database_identity_mismatch")
    return EXPECTED_DEMO_DATABASE


def verify_demo_database(
    dsn: str,
    *,
    connector: Callable[[str], Any] = psycopg.connect,
) -> str:
    try:
        with connector(dsn) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            row = connection.execute(
                "SELECT current_database() AS database_name"
            ).fetchone()
            if row is None:
                raise DemoControllerError("demo_database_identity_unavailable")
            database_name = str(row[0])
            validate_database_identity(database_name)
            migration = connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM stageflow.schema_migration
                    WHERE version = '0008_demo_vertical_slice'
                ) AS migration_present
                """
            ).fetchone()
            if migration is None or not bool(migration[0]):
                raise DemoControllerError("demo_database_schema_not_ready")
            return EXPECTED_DEMO_DATABASE
    except DemoControllerError:
        raise
    except (psycopg.Error, OSError, ValueError):
        raise DemoControllerError("demo_database_unavailable") from None


def _as_mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise DemoControllerError(code)
    return cast(Mapping[str, object], value)


def _as_sequence(value: object, code: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise DemoControllerError(code)
    return cast(Sequence[object], value)


def _required_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DemoControllerError(code)
    return value.strip()


def _required_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DemoControllerError(code)
    return value


def _session_from_mapping(item: Mapping[str, object]) -> SessionSelection:
    end = item.get("authoritative_end")
    if end is not None and not isinstance(end, str):
        raise DemoControllerError("demo_session_authoritative_end_invalid")
    expectation = item.get("program_expectation_id")
    if expectation is not None and not isinstance(expectation, str):
        raise DemoControllerError("demo_session_program_expectation_invalid")
    return SessionSelection(
        session_id=_required_text(item.get("session_id"), "demo_session_id_invalid"),
        activity_state=_required_text(
            item.get("activity_state"), "demo_session_activity_state_invalid"
        ),
        package_state=_required_text(
            item.get("package_state"), "demo_session_package_state_invalid"
        ),
        package_revision=_required_int(
            item.get("package_revision"), "demo_session_package_revision_invalid"
        ),
        revision=_required_int(item.get("revision"), "demo_session_revision_invalid"),
        authoritative_start=_required_text(
            item.get("authoritative_start"),
            "demo_session_authoritative_start_invalid",
        ),
        authoritative_end=end,
        program_expectation_id=expectation,
    )


def resolve_current_session(
    kernel_status: Mapping[str, object],
) -> SessionSelection | None:
    stages = _as_sequence(kernel_status.get("stages"), "demo_stage_projection_invalid")
    if len(stages) != 1:
        raise DemoControllerError("demo_stage_projection_ambiguous")
    stage = _as_mapping(stages[0], "demo_stage_projection_invalid")
    candidates: dict[str, SessionSelection] = {}
    for field in ("assembling_sessions", "recent_sessions"):
        for value in _as_sequence(
            stage.get(field, ()), "demo_session_projection_invalid"
        ):
            selection = _session_from_mapping(
                _as_mapping(value, "demo_session_projection_invalid")
            )
            existing = candidates.get(selection.session_id)
            if existing is not None and existing != selection:
                raise DemoControllerError("demo_session_projection_conflict")
            candidates[selection.session_id] = selection
    explicit_id = stage.get("session_id")
    if explicit_id is not None:
        session_id = _required_text(explicit_id, "demo_session_id_invalid")
        selected = candidates.get(session_id)
        if selected is None:
            raise DemoControllerError("demo_current_session_projection_missing")
        return selected
    active = [
        item
        for item in candidates.values()
        if item.activity_state == "presentation_active"
    ]
    if len(active) == 1:
        return active[0]
    if len(active) > 1:
        raise DemoControllerError("demo_current_session_ambiguous")
    if not candidates:
        return None
    if len(candidates) == 1:
        return next(iter(candidates.values()))
    raise DemoControllerError("demo_current_session_ambiguous")


def summarize_demo_state(
    kernel_status: Mapping[str, object],
    workspace: Mapping[str, object] | None,
    *,
    worker_summary: Mapping[str, object] | None = None,
) -> dict[str, object]:
    selection = resolve_current_session(kernel_status)
    stage = _as_mapping(
        _as_sequence(kernel_status.get("stages"), "demo_stage_projection_invalid")[0],
        "demo_stage_projection_invalid",
    )
    report: dict[str, object] = {
        "schema_version": "stageflow-demo-rehearsal-report-v1",
        "runtime_profile": kernel_status.get("runtime_profile"),
        "ready": bool(kernel_status.get("ready")),
        "database_available": bool(kernel_status.get("database_available")),
        "event": {
            "event_id": kernel_status.get("event_id"),
            "event_key": kernel_status.get("event_key"),
        },
        "stage": {
            "stage_id": stage.get("stage_id"),
            "stage_key": stage.get("key"),
            "source_available": stage.get("source_available"),
        },
        "media": {
            key: _required_int(stage.get(key, 0), "demo_media_count_invalid")
            for key in (
                "discovered",
                "stabilizing",
                "ready",
                "registered",
                "associated",
                "unresolved",
                "conflicting",
            )
        },
        "devcon": {
            "cached_program_expectations": len(
                _as_sequence(
                    kernel_status.get("program_expectations", ()),
                    "demo_program_projection_invalid",
                )
            ),
            "provider": "devcon",
        },
        "worker": dict(worker_summary or {"state": "unknown"}),
    }
    if selection is None:
        report.update(
            {
                "session": None,
                "package": None,
                "operations": {"counts": {}, "terminal_failures": ()},
                "transcript_evidence": {"count": 0, "complete": 0, "items": ()},
                "moments": {"count": 0},
            }
        )
        return report
    if workspace is None:
        raise DemoControllerError("demo_workspace_required")
    if workspace.get("session_id") != selection.session_id:
        raise DemoControllerError("demo_workspace_session_mismatch")
    operations = [
        _as_mapping(item, "demo_operation_projection_invalid")
        for item in _as_sequence(
            workspace.get("operations", ()), "demo_operation_projection_invalid"
        )
    ]
    terminal_failures = tuple(
        {
            "operation_id": item.get("operation_id"),
            "attempt_count": item.get("attempt_count"),
            "max_attempts": item.get("max_attempts"),
            "reason_code": item.get("last_reason_code"),
        }
        for item in operations
        if item.get("status") == "terminal_failed"
    )
    work = _as_mapping(workspace.get("work"), "demo_work_projection_invalid")
    counts = _as_mapping(work.get("counts", {}), "demo_work_counts_invalid")
    evidence = [
        _as_mapping(item, "demo_transcript_evidence_projection_invalid")
        for item in _as_sequence(
            workspace.get("transcript_evidence", ()),
            "demo_transcript_evidence_projection_invalid",
        )
    ]
    evidence_items = tuple(
        {
            "evidence_id": item.get("evidence_id"),
            "status": item.get("status"),
            "revision": item.get("revision"),
            "provider": item.get("provider_id"),
            "provider_version": item.get("provider_version"),
            "model": item.get("model_id"),
            "model_version": item.get("model_version"),
            "segment_count": len(
                _as_sequence(
                    item.get("segments", ()),
                    "demo_transcript_segment_projection_invalid",
                )
            ),
        }
        for item in evidence
    )
    moments = _as_sequence(
        workspace.get("moments", ()), "demo_moment_projection_invalid"
    )
    report.update(
        {
            "session": {
                "session_id": selection.session_id,
                "activity_state": selection.activity_state,
                "revision": selection.revision,
            },
            "package": {
                "state": selection.package_state,
                "revision": selection.package_revision,
                "approved": selection.package_state == "complete",
            },
            "operations": {
                "counts": {str(key): value for key, value in counts.items()},
                "terminal_failures": terminal_failures,
                "truncated": bool(workspace.get("operations_truncated")),
            },
            "transcript_evidence": {
                "label": "Transcription Evidence",
                "authority": "evidence_only_not_authoritative_session_transcript",
                "count": len(evidence),
                "complete": sum(item.get("status") == "complete" for item in evidence),
                "items": evidence_items,
                "truncated": bool(workspace.get("transcript_assets_truncated")),
            },
            "moments": {"count": len(moments)},
        }
    )
    return report


def _parse_aware(value: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise DemoControllerError(code) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DemoControllerError(code)
    return parsed


def build_devcon_publish_candidate(
    kernel_status: Mapping[str, object],
    workspace: Mapping[str, object],
) -> DevconPublishCandidate:
    selection = resolve_current_session(kernel_status)
    if selection is None:
        raise DemoControllerError("demo_publish_session_unavailable")
    if selection.activity_state != "presentation_ended":
        raise DemoControllerError("demo_publish_presentation_not_ended")
    if selection.package_state != "complete":
        raise DemoControllerError("demo_publish_package_not_approved")
    if selection.authoritative_end is None:
        raise DemoControllerError("demo_publish_session_end_unavailable")
    if selection.program_expectation_id is None:
        raise DemoControllerError("demo_publish_program_expectation_unavailable")
    expectations = [
        cast(Mapping[str, object], item)
        for item in _as_sequence(
            kernel_status.get("program_expectations", ()),
            "demo_program_projection_invalid",
        )
        if isinstance(item, dict)
        and cast(Mapping[str, object], item).get("expectation_id")
        == selection.program_expectation_id
    ]
    if len(expectations) != 1:
        raise DemoControllerError("demo_publish_program_expectation_ambiguous")
    expectation = expectations[0]
    event_id = _required_text(
        expectation.get("external_event_id"), "demo_publish_remote_event_unavailable"
    )
    remote_session_id = _required_text(
        expectation.get("external_session_id"),
        "demo_publish_remote_session_unavailable",
    )
    if bool(workspace.get("transcript_assets_truncated")):
        raise DemoControllerError("demo_publish_transcript_projection_truncated")
    evidence = [
        _as_mapping(item, "demo_transcript_evidence_projection_invalid")
        for item in _as_sequence(
            workspace.get("transcript_evidence", ()),
            "demo_transcript_evidence_projection_invalid",
        )
    ]
    if not evidence or any(item.get("status") != "complete" for item in evidence):
        raise DemoControllerError("demo_publish_complete_transcript_evidence_required")
    media_order: dict[str, tuple[str, str]] = {}
    for item in _as_sequence(
        kernel_status.get("recent_media", ()), "demo_media_projection_invalid"
    ):
        media = _as_mapping(item, "demo_media_projection_invalid")
        asset_id = media.get("asset_id")
        if isinstance(asset_id, str):
            media_order[asset_id] = (
                str(media.get("media_started_at") or "9999"),
                asset_id,
            )
    ordered = sorted(
        evidence,
        key=lambda item: media_order.get(
            str(item.get("asset_id")), ("9999", str(item.get("asset_id")))
        ),
    )
    transcript_parts: list[str] = []
    for item in ordered:
        if bool(item.get("segments_truncated")):
            raise DemoControllerError("demo_publish_transcript_projection_truncated")
        for segment_value in _as_sequence(
            item.get("segments", ()), "demo_transcript_segment_projection_invalid"
        ):
            segment = _as_mapping(
                segment_value, "demo_transcript_segment_projection_invalid"
            )
            text = _required_text(
                segment.get("text"), "demo_publish_transcript_segment_empty"
            )
            transcript_parts.append(" ".join(text.split()))
    transcript_text = "\n".join(transcript_parts).strip()
    if not transcript_text:
        raise DemoControllerError("demo_publish_transcript_empty")
    started = _parse_aware(
        selection.authoritative_start, "demo_publish_session_start_invalid"
    )
    ended = _parse_aware(
        selection.authoritative_end, "demo_publish_session_end_invalid"
    )
    duration_seconds = round((ended - started).total_seconds())
    if duration_seconds <= 0:
        raise DemoControllerError("demo_publish_duration_invalid")
    digest_input = json.dumps(
        {
            "event_id": event_id,
            "remote_session_id": remote_session_id,
            "transcript_text": transcript_text,
            "duration": duration_seconds,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return DevconPublishCandidate(
        event_id=event_id,
        remote_session_id=remote_session_id,
        transcript_text=transcript_text,
        duration_seconds=duration_seconds,
        digest=hashlib.sha256(digest_input).hexdigest(),
    )


def preview_devcon_publish(
    candidate: DevconPublishCandidate,
    *,
    credential_available: bool,
    adapter: DevconSessionPublishAdapter,
) -> dict[str, object]:
    remote = adapter.get_session(candidate.remote_session_id)
    identity_verified = (
        remote.session_id == candidate.remote_session_id
        and remote.event_id == candidate.event_id
    )
    if not identity_verified:
        raise DemoControllerError("demo_publish_remote_identity_mismatch")
    return {
        "event": candidate.event_id,
        "target_session": candidate.remote_session_id,
        "fields": ("transcript_text", "duration"),
        "remote_identity_verified": True,
        "package_approved": True,
        "credential_available": credential_available,
        "candidate_digest": candidate.digest,
    }


def _session_matches_candidate(
    remote: RemoteDevconSession, candidate: DevconPublishCandidate
) -> bool:
    return (
        remote.session_id == candidate.remote_session_id
        and remote.event_id == candidate.event_id
        and remote.transcript_text == candidate.transcript_text
        and remote.duration_seconds == candidate.duration_seconds
    )


def execute_devcon_publish(
    candidate: DevconPublishCandidate,
    *,
    expected_digest: str,
    confirmed: bool,
    api_key: str,
    adapter: DevconSessionPublishAdapter,
    api_convergence_delays_seconds: Sequence[float] = (
        _PUBLIC_API_CONVERGENCE_DELAYS_SECONDS
    ),
    sleeper: Callable[[float], None] = sleep,
) -> dict[str, object]:
    if not confirmed:
        raise DemoControllerError("demo_publish_human_confirmation_required")
    if candidate.digest != expected_digest:
        raise DemoControllerError("demo_publish_candidate_changed")
    convergence_delays = tuple(api_convergence_delays_seconds)
    if (
        not convergence_delays
        or len(convergence_delays) > 4
        or any(
            not isfinite(delay) or delay < 0 or delay > 120
            for delay in convergence_delays
        )
        or sum(convergence_delays) > 195
    ):
        raise ValueError("demo_publish_api_convergence_bounds_invalid")
    remote = adapter.get_session(candidate.remote_session_id)
    if (
        remote.session_id != candidate.remote_session_id
        or remote.event_id != candidate.event_id
    ):
        raise DemoControllerError("demo_publish_remote_identity_mismatch")
    adapter.put_enrichment(
        session_id=candidate.remote_session_id,
        api_key=api_key,
        transcript_text=candidate.transcript_text,
        duration_seconds=candidate.duration_seconds,
    )
    try:
        durable = adapter.get_durable_session(
            event_id=candidate.event_id,
            session_id=candidate.remote_session_id,
        )
    except DevconPublishError:
        raise DemoControllerError(
            "demo_publish_write_accepted_durable_git_unavailable"
        ) from None
    if not _session_matches_candidate(durable, candidate):
        raise DemoControllerError(
            "demo_publish_write_accepted_durable_git_mismatch"
        )

    public_api_observed = False
    public_api_converged = False
    for delay in convergence_delays:
        if delay:
            sleeper(delay)
        try:
            read_back = adapter.get_session(candidate.remote_session_id)
        except DevconPublishError:
            continue
        public_api_observed = True
        if (
            read_back.session_id != candidate.remote_session_id
            or read_back.event_id != candidate.event_id
        ):
            raise DemoControllerError("demo_publish_public_api_identity_mismatch")
        if _session_matches_candidate(read_back, candidate):
            public_api_converged = True
            break

    if public_api_converged:
        publication_status = "published_durable_api_converged"
        public_api_state = "converged"
    elif public_api_observed:
        publication_status = "published_durable_api_stale"
        public_api_state = "stale"
    else:
        publication_status = "published_durable_api_unavailable"
        public_api_state = "unavailable"

    return {
        "event": candidate.event_id,
        "target_session": candidate.remote_session_id,
        "fields": ("transcript_text", "duration"),
        "remote_identity_verified": True,
        "write_accepted": True,
        "durable_persistence_verified": True,
        "public_api_convergence_verified": public_api_converged,
        "public_api_state": public_api_state,
        "publication_status": publication_status,
        "read_back_verified": public_api_converged,
        "durability_verified": True,
        "candidate_digest": candidate.digest,
    }


def _get_api_json(url: str) -> Mapping[str, object]:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "StageFlow-Demo-Controller/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310
            if response.status != 200:
                raise DemoControllerError(f"demo_api_http_status_{response.status}")
            body = response.read(_MAXIMUM_API_BYTES + 1)
    except HTTPError as exc:
        raise DemoControllerError(f"demo_api_http_status_{exc.code}") from None
    except (OSError, TimeoutError, URLError, ValueError):
        raise DemoControllerError("demo_api_unavailable") from None
    if len(body) > _MAXIMUM_API_BYTES:
        raise DemoControllerError("demo_api_response_too_large")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DemoControllerError("demo_api_response_invalid") from None
    return _as_mapping(payload, "demo_api_response_invalid")


def _live_state() -> tuple[Mapping[str, object], Mapping[str, object] | None]:
    kernel = _get_api_json(f"{_API_BASE_URL}/kernel/status")
    selection = resolve_current_session(kernel)
    if selection is None:
        return kernel, None
    workspace = _get_api_json(
        f"{_API_BASE_URL}/demo/sessions/{selection.session_id}/workspace"
    )
    return kernel, workspace


def _worker_summary(dsn: str, event_id: object, deployment_id: object) -> dict[str, object]:
    if not isinstance(event_id, str) or not isinstance(deployment_id, str):
        return {"state": "unknown", "registered": 0, "available": 0}
    try:
        with psycopg.connect(dsn) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """
                SELECT w.enabled, w.draining, p.health_state,
                       p.expires_at > statement_timestamp() AS presence_current
                FROM stageflow.work_worker w
                LEFT JOIN stageflow.work_worker_presence p
                  ON p.worker_id = w.worker_id
                WHERE w.deployment_id = %s AND w.event_id = %s
                ORDER BY w.worker_id
                LIMIT 20
                """,
                (deployment_id, event_id),
            ).fetchall()
    except psycopg.Error:
        return {"state": "unavailable", "registered": 0, "available": 0}
    available = sum(
        bool(row[0])
        and not bool(row[1])
        and row[2] in ("available", "degraded")
        and bool(row[3])
        for row in rows
    )
    return {
        "state": "available" if available else "not_current",
        "registered": len(rows),
        "available": available,
    }


def _dsn() -> str:
    return resolve_required_secret(os.environ, DEMO_DSN_SECRET)


def _verify_database() -> str:
    return verify_demo_database(_dsn())


def _prepare() -> dict[str, object]:
    _verify_database()
    if demo_cli.main(["preflight"]) != 0:
        raise DemoControllerError("demo_prepare_preflight_failed")
    _verify_database()
    if demo_cli.main(["bootstrap"]) != 0:
        raise DemoControllerError("demo_prepare_bootstrap_failed")
    _verify_database()
    if demo_cli.main(["sync-program"]) != 0:
        raise DemoControllerError("demo_prepare_program_sync_failed")
    return {"action": "prepare", "database_verified": True, "prepared": True}


def _operator_id() -> str:
    dsn = _dsn()
    _verify_database()
    components = load_kernel_components_from_environment()
    if components is None:
        raise DemoControllerError("demo_configuration_required")
    status = components.status()
    if status is None or len(status.stages) != 1:
        raise DemoControllerError("demo_operator_session_unavailable")
    sessions = components.repository.list_sessions_for_stage(status.stages[0].stage_id)
    active = [item for item in sessions if item.activity_state.value == "presentation_active"]
    selected = active[0] if len(active) == 1 else sessions[0] if len(sessions) == 1 else None
    if selected is None:
        raise DemoControllerError("demo_operator_session_ambiguous")
    try:
        with psycopg.connect(dsn) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """
                SELECT DISTINCT actor_id::text FROM (
                    SELECT actor_id FROM stageflow.session_boundary_history
                    WHERE session_id = %s AND actor_id IS NOT NULL
                    UNION ALL
                    SELECT actor_id FROM stageflow.session_package_ready_history
                    WHERE session_id = %s
                    UNION ALL
                    SELECT actor_id FROM stageflow.editorial_candidate_moment
                    WHERE session_id = %s
                ) AS actors
                """,
                (selected.id.value, selected.id.value, selected.id.value),
            ).fetchall()
    except psycopg.Error:
        raise DemoControllerError("demo_operator_identity_unavailable") from None
    if len(rows) != 1:
        raise DemoControllerError("demo_operator_identity_ambiguous")
    return str(rows[0][0])


def _report() -> tuple[dict[str, object], Mapping[str, object], Mapping[str, object] | None]:
    dsn = _dsn()
    _verify_database()
    kernel, workspace = _live_state()
    components = load_kernel_components_from_environment()
    deployment_id = (
        None if components is None else components.configuration.deployment.deployment_id
    )
    summary = summarize_demo_state(
        kernel,
        workspace,
        worker_summary=_worker_summary(dsn, kernel.get("event_id"), deployment_id),
    )
    return summary, kernel, workspace


def _safe_write(payload: Mapping[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stageflow-demo-controller")
    parser.add_argument(
        "command",
        choices=(
            "verify-database",
            "prepare",
            "status",
            "operator-id",
            "rehearsal-report",
            "publish-preview",
            "publish",
        ),
    )
    parser.add_argument("--output")
    parser.add_argument("--expected-digest")
    parser.add_argument("--confirmed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "verify-database":
            _safe_write({"database": _verify_database(), "verified": True})
            return 0
        if arguments.command == "prepare":
            _safe_write(_prepare())
            return 0
        if arguments.command == "operator-id":
            sys.stdout.write(_operator_id() + "\n")
            return 0
        summary, kernel, workspace = _report()
        if arguments.command == "status":
            _safe_write(summary)
            return 0
        if arguments.command == "rehearsal-report":
            if not arguments.output:
                raise DemoControllerError("demo_report_output_required")
            output = Path(arguments.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _safe_write({"report_written": True, "schema_version": summary["schema_version"]})
            return 0
        if workspace is None:
            raise DemoControllerError("demo_publish_session_unavailable")
        candidate = build_devcon_publish_candidate(kernel, workspace)
        adapter = DevconSessionPublishAdapter()
        if arguments.command == "publish-preview":
            credential = os.environ.get(DEVCON_API_KEY_SECRET)
            _safe_write(
                preview_devcon_publish(
                    candidate,
                    credential_available=bool(credential and credential.strip()),
                    adapter=adapter,
                )
            )
            return 0
        if not arguments.expected_digest:
            raise DemoControllerError("demo_publish_expected_digest_required")
        api_key = resolve_required_secret(os.environ, DEVCON_API_KEY_SECRET)
        _safe_write(
            execute_devcon_publish(
                candidate,
                expected_digest=arguments.expected_digest,
                confirmed=arguments.confirmed,
                api_key=api_key,
                adapter=adapter,
            )
        )
        return 0
    except (DemoControllerError, DevconPublishError, ValueError) as exc:
        sys.stderr.write(f"stageflow_demo_controller_error={exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEMO_DSN_SECRET",
    "DEVCON_API_KEY_SECRET",
    "DemoControllerError",
    "DevconPublishCandidate",
    "EXPECTED_DEMO_DATABASE",
    "SessionSelection",
    "build_devcon_publish_candidate",
    "execute_devcon_publish",
    "main",
    "preview_devcon_publish",
    "resolve_current_session",
    "resolve_required_secret",
    "summarize_demo_state",
    "validate_database_identity",
    "verify_demo_database",
]
