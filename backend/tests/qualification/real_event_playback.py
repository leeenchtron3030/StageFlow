# ruff: noqa: E402
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, BinaryIO, Protocol, cast

# The runner is intentionally executable as a file from ``backend/``. Python otherwise
# places only ``backend/tests/qualification`` on ``sys.path`` for that invocation.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.bootstrap.event_mode_kernel import (
    KernelComponents,
    build_kernel_components,
    load_kernel_components_from_environment,
)
from app.bootstrap.media_cycle import MediaCycleResult
from app.bootstrap.runtime_factory import build_stageflow_runtime
from app.contexts.production.event_mode_kernel import (
    EventOperationalStatus,
    MediaAssociation,
    MediaCandidate,
    RegisteredMediaAsset,
    ResourceObservation,
    Session,
    SessionPackageState,
    StartSessionRequest,
)
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    load_kernel_deployment_configuration,
)
from app.infrastructure.postgres import PostgresMigrationRunner
from app.shared.ids import EntityId

RUNNER_NAME = "stageflow-real-event-playback-validation"
RUNNER_SCHEMA_VERSION = "1.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MAX_CYCLE_COUNT = 10_000
MAX_CYCLE_INTERVAL_SECONDS = 3_600.0
MEDIA_PROJECTION_LIMIT = 100
DATABASE_ACKNOWLEDGEMENT = "--confirm-isolated-validation-database"
CONTROLLER_LOCK_TOKEN_ENVIRONMENT = "STAGEFLOW_VALIDATION_CONTROLLER_LOCK_TOKEN"
CONTROLLER_LOCK_PATH_ENVIRONMENT = "STAGEFLOW_VALIDATION_CONTROLLER_LOCK_PATH"

UX_QUESTIONS: Mapping[str, str] = {
    "media_cadence_noisy": "Did media cadence feel noisy?",
    "turnover_context_obvious": "Was Session context obvious during turnover?",
    "trailing_media_duration": (
        "How long after presentation end did useful trailing media continue?"
    ),
    "block_detail_frequency": (
        "How often would a Producer actually need block-level detail?"
    ),
    "surprising_associations": "Were any media associations surprising?",
    "mission_control_useful": "What information would have been useful on Mission Control?",
    "mission_control_distracting": "What information would have been distracting?",
}


class CycleComponents(Protocol):
    def run_media_cycle(self, *, event_id: EntityId, scope: str) -> MediaCycleResult: ...


class ValidationRunnerError(RuntimeError):
    """A safe, operator-correctable validation-runner failure."""


def required_object(value: Any, error: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationRunnerError(error)
    return cast(dict[str, Any], value)


def required_list(value: Any, error: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationRunnerError(error)
    return cast(list[Any], value)


def optional_object(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def safe_error(exc: BaseException) -> str:
    message = str(exc).strip()
    lowered = message.casefold()
    if "://" in message or "password" in lowered or "dsn" in lowered:
        return "sensitive diagnostic redacted; inspect local console/runtime logs"
    return (message or type(exc).__name__)[:500]


def _lock_byte(handle: BinaryIO, offset: int) -> None:
    handle.seek(offset)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.lockf(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB, 1, offset)


def _unlock_byte(handle: BinaryIO, offset: int) -> None:
    handle.seek(offset)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.lockf(handle.fileno(), fcntl.LOCK_UN, 1, offset)


def _read_lock_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _lock_diagnostic(path: Path) -> str:
    metadata = _read_lock_metadata(path)
    action = str(metadata.get("action") or "unknown")
    process_id = str(metadata.get("runner_pid") or metadata.get("controller_pid") or "unknown")
    started_at = str(metadata.get("started_at") or "unknown")
    return f"action={action} pid={process_id} started_at={started_at}"


def _write_lock_metadata(path: Path, metadata: Mapping[str, Any]) -> None:
    payload = (json.dumps(dict(metadata), sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload)


@contextmanager
def qualification_run_lock(run_file: Path, *, action: str) -> Generator[None]:
    """Hold the runner region of one cooperative host-local qualification lock."""

    lock_path = run_file.with_suffix(".operation.lock")
    metadata_path = Path(str(lock_path) + ".json")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    controller_token = os.environ.get(CONTROLLER_LOCK_TOKEN_ENVIRONMENT)
    controller_path = os.environ.get(CONTROLLER_LOCK_PATH_ENVIRONMENT)
    inherited_controller = False
    if controller_token and controller_path:
        try:
            inherited_controller = Path(controller_path).resolve() == lock_path.resolve()
        except OSError:
            inherited_controller = False
        if inherited_controller:
            inherited_controller = (
                _read_lock_metadata(metadata_path).get("token") == controller_token
            )

    handle = cast(BinaryIO, lock_path.open("a+b", buffering=0))
    owned_offsets: list[int] = []
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() < 2:
            handle.write(b"\0" * (2 - handle.tell()))
            handle.flush()
            os.fsync(handle.fileno())
        if not inherited_controller:
            try:
                _lock_byte(handle, 0)
                owned_offsets.append(0)
            except OSError as exc:
                raise ValidationRunnerError(
                    "qualification_operation_already_active:"
                    f"{_lock_diagnostic(metadata_path)}; "
                    "host timeout does not prove child termination"
                ) from exc
        try:
            _lock_byte(handle, 1)
            owned_offsets.append(1)
        except OSError as exc:
            raise ValidationRunnerError(
                "qualification_operation_already_active:"
                f"{_lock_diagnostic(metadata_path)}; "
                "host timeout does not prove child termination"
            ) from exc

        metadata = _read_lock_metadata(metadata_path) if inherited_controller else {}
        metadata.update(
            {
                "schema_version": "1.0",
                "action": action,
                "runner_pid": os.getpid(),
                "started_at": metadata.get("started_at") or utc_now().isoformat(),
                "run_file": str(run_file),
            }
        )
        if controller_token:
            metadata["token"] = controller_token
        _write_lock_metadata(metadata_path, metadata)
        yield
    finally:
        for offset in reversed(owned_offsets):
            try:
                _unlock_byte(handle, offset)
            except OSError:
                pass
        handle.close()


def parse_aware_time(value: str, *, now: Callable[[], datetime] = utc_now) -> datetime:
    parsed = now() if value.casefold() == "now" else datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationRunnerError("timestamp_must_be_timezone_aware")
    return parsed


def parse_key_values(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key.strip() or not item.strip():
            raise ValidationRunnerError("expected_key_equals_value")
        normalized = key.strip()
        if normalized in result:
            raise ValidationRunnerError(f"duplicate_key:{normalized}")
        result[normalized] = item.strip()
    return result


def require_isolated_database_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise ValidationRunnerError(
            "isolated_validation_database_acknowledgement_required:"
            f"{DATABASE_ACKNOWLEDGEMENT}"
        )


def ensure_run_file_outside_repository(
    path: Path, *, repository_root: Path = REPOSITORY_ROOT
) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    root = repository_root.resolve(strict=False)
    if resolved == root or resolved.is_relative_to(root):
        raise ValidationRunnerError("run_file_must_be_outside_repository")
    if resolved.suffix.casefold() != ".json":
        raise ValidationRunnerError("run_file_must_use_json_extension")
    return resolved


def corpus_manifest_reference(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve(strict=True)
    if resolved.is_relative_to(REPOSITORY_ROOT):
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    return f"external:{resolved.name}"


def configuration_summary(
    configuration: EffectiveKernelConfiguration,
) -> dict[str, Any]:
    deployment = configuration.deployment
    return {
        "schema_version": deployment.schema_version,
        "deployment_id": deployment.deployment_id,
        "node_id": deployment.node_id,
        "node_role": deployment.node_role.value,
        "event_mode": deployment.event_mode.value,
        "network_policy": deployment.network_policy.value,
        "event_key": deployment.event.key,
        "event_name": deployment.event.name,
        "stages": [
            {
                "key": stage.key,
                "name": stage.name,
                "source_binding_keys": [source.key for source in stage.sources],
                "allowed_extensions": {
                    source.key: list(source.allowed_extensions) for source in stage.sources
                },
            }
            for stage in deployment.event.stages
        ],
        "minimum_stable_seconds": deployment.resources.minimum_stable_seconds,
    }


def initialize_state(
    configuration: EffectiveKernelConfiguration,
    *,
    run_id: str | None,
    actor_id: str | None,
    mode: str,
    corpus_manifest: Path | None,
    corpus_item_id: str | None,
    include_filenames: bool,
    source_assumptions: Mapping[str, str],
    now: Callable[[], datetime] = utc_now,
) -> dict[str, Any]:
    resolved_run_id = EntityId.new() if run_id is None else EntityId.parse(run_id)
    resolved_actor_id = EntityId.new() if actor_id is None else EntityId.parse(actor_id)
    return {
        "schema_version": RUNNER_SCHEMA_VERSION,
        "runner": RUNNER_NAME,
        "run_id": resolved_run_id.value,
        "created_at": now().isoformat(),
        "updated_at": now().isoformat(),
        "mode": mode,
        "actor_id": resolved_actor_id.value,
        "configuration": configuration_summary(configuration),
        "corpus": {
            "manifest_reference": corpus_manifest_reference(corpus_manifest),
            "item_id": corpus_item_id,
        },
        "source_assumptions": dict(sorted(source_assumptions.items())),
        "include_safe_filenames": include_filenames,
        "operation_ids": {},
        "event": None,
        "expectations": {},
        "sessions": {},
        "cycles": [],
        "commands": [],
        "status_snapshots": [],
        "media_blocks": {},
        "process_stops": [],
        "reconstructions": [],
        "ux_observations": {
            key: {"question": question, "answer": None, "recorded_at": None}
            for key, question in UX_QUESTIONS.items()
        },
        "anomalies": [],
        "limitations": [
            "vMix block-close truth is external; filesystem mtime is only a proxy",
            "readiness and registration timestamps are available only for bounded recent media",
            "the runner is validation tooling, not a watcher or production control surface",
        ],
    }


def validate_state(state: Mapping[str, Any]) -> None:
    if state.get("schema_version") != RUNNER_SCHEMA_VERSION:
        raise ValidationRunnerError("unsupported_run_file_schema")
    if state.get("runner") != RUNNER_NAME:
        raise ValidationRunnerError("run_file_runner_mismatch")
    EntityId.parse(str(state.get("run_id")))
    EntityId.parse(str(state.get("actor_id")))


def validate_configuration_matches_state(
    configuration: EffectiveKernelConfiguration, state: Mapping[str, Any]
) -> None:
    recorded = required_object(
        state.get("configuration"), "run_file_configuration_missing"
    )
    current = configuration_summary(configuration)
    for key in ("schema_version", "deployment_id", "event_key"):
        if recorded.get(key) != current[key]:
            raise ValidationRunnerError(f"run_file_configuration_mismatch:{key}")


def retained_operation_id(
    state: dict[str, Any], *, key: str, supplied: str | None = None
) -> EntityId:
    operations = required_object(
        state.setdefault("operation_ids", {}), "operation_identity_state_invalid"
    )
    existing = operations.get(key)
    if existing is not None:
        existing_id = EntityId.parse(str(existing))
        if supplied is not None and EntityId.parse(supplied) != existing_id:
            raise ValidationRunnerError(f"operation_id_conflict:{key}")
        return existing_id
    operation_id = EntityId.new() if supplied is None else EntityId.parse(supplied)
    operations[key] = operation_id.value
    return operation_id


def latest_recorded_stop(state: Mapping[str, Any]) -> str | None:
    stops = required_list(state.get("process_stops", []), "process_stop_state_invalid")
    if not stops:
        return None
    latest = required_object(stops[-1], "process_stop_record_invalid")
    value = latest.get("stopped_at")
    return None if value is None else str(value)


def record_command(
    state: dict[str, Any],
    *,
    name: str,
    action: Callable[[], Any],
    details: Mapping[str, Any] | None = None,
    on_started: Callable[[], None] | None = None,
    now: Callable[[], datetime] = utc_now,
    monotonic: Callable[[], float] = perf_counter,
) -> Any:
    commands = required_list(
        state.setdefault("commands", []), "command_history_invalid"
    )
    entry: dict[str, Any] = {
        "sequence": len(commands) + 1,
        "command": name,
        "invoked_at": now().isoformat(),
        "details": dict(details or {}),
        "outcome": "running",
    }
    commands.append(entry)
    started = monotonic()
    try:
        if on_started is not None:
            on_started()
        result = action()
    except BaseException as exc:
        entry.update(
            {
                "completed_at": now().isoformat(),
                "duration_seconds": max(0.0, monotonic() - started),
                "outcome": "failed",
                "error_type": type(exc).__name__,
                "error": safe_error(exc),
            }
        )
        raise
    entry.update(
        {
            "completed_at": now().isoformat(),
            "duration_seconds": max(0.0, monotonic() - started),
            "outcome": "completed",
        }
    )
    return result


def drive_bounded_cycles(
    run_once: Callable[[int], dict[str, Any]],
    *,
    maximum_cycles: int,
    cycle_every_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = perf_counter,
    on_cycle_completed: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    if maximum_cycles < 1 or maximum_cycles > MAX_CYCLE_COUNT:
        raise ValidationRunnerError("cycle_count_out_of_bounds")
    if cycle_every_seconds < 0 or cycle_every_seconds > MAX_CYCLE_INTERVAL_SECONDS:
        raise ValidationRunnerError("cycle_interval_out_of_bounds")
    results: list[dict[str, Any]] = []
    next_start = monotonic()
    interrupted = False
    try:
        for index in range(maximum_cycles):
            if index:
                delay = next_start - monotonic()
                if delay > 0:
                    sleep(delay)
            result = run_once(index + 1)
            results.append(result)
            if on_cycle_completed is not None:
                on_cycle_completed(result)
            next_start += cycle_every_seconds
    except KeyboardInterrupt:
        interrupted = True
    return results, interrupted


class RunFiles:
    def __init__(self, json_path: Path) -> None:
        self.json_path = ensure_run_file_outside_repository(json_path)
        self.markdown_path = self.json_path.with_suffix(".md")
        self.lock_path = self.json_path.with_suffix(".operation.lock")
        self._expected_json_digest: str | None = None

    def exists(self) -> bool:
        return self.json_path.exists()

    def load(self) -> dict[str, Any]:
        try:
            raw = self.json_path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationRunnerError("run_file_unreadable") from exc
        if not isinstance(value, dict):
            raise ValidationRunnerError("run_file_root_must_be_object")
        state = cast(dict[str, Any], value)
        validate_state(state)
        self._expected_json_digest = hashlib.sha256(raw).hexdigest()
        return state

    def operation_lock(self, *, action: str) -> AbstractContextManager[None]:
        return qualification_run_lock(self.json_path, action=action)

    def save(self, state: dict[str, Any]) -> None:
        validate_state(state)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        current_digest = (
            hashlib.sha256(self.json_path.read_bytes()).hexdigest()
            if self.json_path.exists()
            else None
        )
        if current_digest != self._expected_json_digest:
            raise ValidationRunnerError(
                "run_file_concurrent_update_detected: newer external evidence preserved"
            )
        state["updated_at"] = utc_now().isoformat()
        json_text = json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        markdown_text = render_markdown_summary(state)
        self._atomic_write(self.json_path, json_text)
        self._expected_json_digest = hashlib.sha256(json_text.encode("utf-8")).hexdigest()
        self._atomic_write(self.markdown_path, markdown_text)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def render_markdown_summary(state: Mapping[str, Any]) -> str:
    configuration = optional_object(state.get("configuration"))
    corpus = optional_object(state.get("corpus"))
    source_assumptions = optional_object(state.get("source_assumptions"))
    event = optional_object(state.get("event"))
    sessions = optional_object(state.get("sessions"))
    media = optional_object(state.get("media_blocks"))
    cycles = required_list(state.get("cycles", []), "cycle_state_invalid")
    commands = required_list(state.get("commands", []), "command_history_invalid")
    process_stops = required_list(
        state.get("process_stops", []), "process_stop_state_invalid"
    )
    reconstructions = required_list(
        state.get("reconstructions", []), "reconstruction_state_invalid"
    )
    counts = {"associated": 0, "unresolved": 0, "conflict": 0, "none": 0}
    for value in media.values():
        item = optional_object(value)
        status = str(item.get("association_status") or "none")
        counts[status] = counts.get(status, 0) + 1
    lines = [
        "# Real-Event Playback Validation Local Summary",
        "",
        "> Local validation output. Review and sanitize before copying any content into Git.",
        "",
        "## Run",
        "",
        f"- Run ID: `{state.get('run_id')}`",
        f"- Mode: `{state.get('mode')}`",
        f"- Corpus item: `{corpus.get('item_id') or 'not recorded'}`",
        f"- Corpus manifest: `{corpus.get('manifest_reference') or 'not recorded'}`",
        f"- Event: `{event.get('event_id') or 'not bootstrapped'}` / "
        f"`{configuration.get('event_key', 'unknown')}`",
        "- Stages: "
        + ", ".join(
            f"`{optional_object(item).get('key')}`"
            for item in required_list(configuration.get("stages", []), "stage_state_invalid")
        ),
        f"- Sessions recorded: {len(sessions)}",
        f"- Media blocks recorded: {len(media)}",
        f"- Associations: {counts['associated']} associated, {counts['unresolved']} "
        f"unresolved, {counts['conflict']} conflict, {counts['none']} without outcome",
        "- Production/Event readiness claimed: **No**",
        "",
        "## Source and vMix assumptions",
        "",
    ]
    if source_assumptions:
        lines.extend(
            f"- `{key}`: {value}" for key, value in sorted(source_assumptions.items())
        )
    else:
        lines.append("- None recorded.")
    lines.extend([
        "",
        "## Operation identities",
        "",
    ])
    operations = optional_object(state.get("operation_ids"))
    if operations:
        lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(operations.items()))
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Sessions", ""])
    if sessions:
        for label, value in sorted(sessions.items()):
            item = optional_object(value)
            lines.append(
                f"- `{label}`: `{item.get('session_id')}`, activity "
                f"`{item.get('activity_state')}`, package `{item.get('package_state')}` "
                f"revision `{item.get('package_revision')}`"
            )
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Timing measurements", ""])
    if commands:
        for value in commands:
            item = optional_object(value)
            lines.append(
                f"- Command {item.get('sequence')} `{item.get('command')}`: "
                f"{item.get('invoked_at')} to {item.get('completed_at')} "
                f"({item.get('duration_seconds')} seconds, {item.get('outcome')})"
            )
    else:
        lines.append("- No commands recorded.")
    if cycles:
        durations = [
            float(item["duration_seconds"])
            for value in cycles
            if (item := optional_object(value)).get("duration_seconds") is not None
        ]
        candidates_seen = sum(
            int(optional_object(value).get("candidates_seen") or 0) for value in cycles
        )
        assets_registered = sum(
            int(optional_object(value).get("assets_registered") or 0) for value in cycles
        )
        source_failures = sum(
            len(
                required_list(
                    optional_object(value).get("source_failures", []),
                    "source_failure_state_invalid",
                )
            )
            for value in cycles
        )
        first_cycle = optional_object(cycles[0])
        last_cycle = optional_object(cycles[-1])
        lines.extend(
            [
                f"- Bounded cycles: {len(cycles)} from {first_cycle.get('invoked_at')} "
                f"to {last_cycle.get('completed_at')}",
                f"- Cycle totals: {candidates_seen} candidates seen, "
                f"{assets_registered} assets registered, {source_failures} source failures",
                "- Cycle duration seconds (min/average/max): "
                + (
                    f"{min(durations):.6f} / {sum(durations) / len(durations):.6f} / "
                    f"{max(durations):.6f}"
                    if durations
                    else "not available"
                ),
            ]
        )
    else:
        lines.append("- No bounded media cycles recorded.")
    media_timings = [optional_object(value) for value in media.values()]
    discoveries = sum(item.get("discovered_at") is not None for item in media_timings)
    readiness = sum(item.get("readiness_at") is not None for item in media_timings)
    registrations = sum(item.get("registration_at") is not None for item in media_timings)
    associations = sum(
        item.get("association_decided_at") is not None for item in media_timings
    )
    lines.extend(
        [
            "- Media timing availability: "
            f"{discoveries} discovery, {readiness} readiness, {registrations} registration, "
            f"{associations} association timestamps",
            "- Filesystem modification times, where present, remain proxies and are not "
            "vMix block-close truth.",
            "",
            "## Stop and reconstruction",
            "",
        ]
    )
    if process_stops:
        lines.extend(
            f"- Stop recorded at {optional_object(value).get('stopped_at')}: "
            f"{optional_object(value).get('reason')}"
            for value in process_stops
        )
    else:
        lines.append("- No process stop recorded.")
    if reconstructions:
        for value in reconstructions:
            item = optional_object(value)
            status = optional_object(item.get("status"))
            reconciliation = optional_object(status.get("reconciliation"))
            lines.append(
                f"- Restart invoked {item.get('restart_invoked_at')}; reconstruction "
                f"completed {item.get('reconstruction_completed_at')}; ready "
                f"`{status.get('ready')}`; reconciliation "
                f"`{reconciliation.get('status') or 'not recorded'}` completed "
                f"{reconciliation.get('completed_at') or 'not recorded'}"
            )
    else:
        lines.append("- No fresh-process reconstruction recorded.")
    lines.extend(["", "## UX observation worksheet", ""])
    observations = optional_object(state.get("ux_observations"))
    for key, value in observations.items():
        item = optional_object(value)
        lines.extend(
            [
                f"### {item.get('question', key)}",
                "",
                str(item.get("answer") or "_Not recorded._"),
                "",
            ]
        )
    lines.extend(["## Anomalies", ""])
    anomalies = required_list(state.get("anomalies", []), "anomaly_state_invalid")
    if anomalies:
        lines.extend(f"- {optional_object(item).get('text')}" for item in anomalies)
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Limitations", ""])
    limitations = required_list(state.get("limitations", []), "limitation_state_invalid")
    lines.extend(f"- {item}" for item in limitations)
    lines.append("")
    return "\n".join(lines)


def compose_without_reconciliation(
    configuration: EffectiveKernelConfiguration,
) -> KernelComponents:
    components = build_kernel_components(configuration)
    event = components.repository.get_event_by_key(configuration.deployment.event.key)
    if event is not None:
        components.runtime = build_stageflow_runtime(
            configuration,
            stages=components.repository.list_stages(event.id),
            clock=components.kernel.clock,
        )
        components.compose_media_cycle()
    return components


def require_event(components: KernelComponents) -> EntityId:
    event = components.repository.get_event_by_key(components.event_key)
    if event is None:
        raise ValidationRunnerError("event_not_bootstrapped")
    return event.id


def stage_id_for_key(
    components: KernelComponents, event_id: EntityId, stage_key: str | None
) -> EntityId:
    stages = components.repository.list_stages(event_id)
    if stage_key is None:
        if len(stages) != 1:
            raise ValidationRunnerError("stage_key_required_for_multi_stage_event")
        return stages[0].id
    stage = components.repository.get_stage_by_key(event_id, stage_key)
    if stage is None:
        raise ValidationRunnerError(f"stage_not_found:{stage_key}")
    return stage.id


def session_payload(session: Session) -> dict[str, Any]:
    return {
        "session_id": session.id.value,
        "event_id": session.event_id.value,
        "stage_id": session.stage_id.value,
        "program_expectation_id": (
            None
            if session.program_expectation_id is None
            else session.program_expectation_id.value
        ),
        "title": session.title,
        "activity_state": session.activity_state.value,
        "package_state": session.package_state.value,
        "package_revision": session.package_revision,
        "revision": session.revision,
        "authoritative_start": iso(session.authoritative_start),
        "authoritative_end": iso(session.authoritative_end),
        "created_at": iso(session.created_at),
        "updated_at": iso(session.updated_at),
    }


def status_payload(status: EventOperationalStatus) -> dict[str, Any]:
    reconciliation = status.latest_reconciliation
    return {
        "captured_at": utc_now().isoformat(),
        "event_id": status.event_id.value,
        "event_key": status.event_key,
        "database_available": status.database_available,
        "ready": status.ready,
        "recovering": status.recovering,
        "reconciliation": (
            None
            if reconciliation is None
            else {
                "id": reconciliation.id.value,
                "status": reconciliation.status.value,
                "scope": reconciliation.scope,
                "started_at": iso(reconciliation.started_at),
                "completed_at": iso(reconciliation.completed_at),
                "candidates_seen": reconciliation.candidates_seen,
                "assets_registered": reconciliation.assets_registered,
                "failure_code": reconciliation.failure_code,
            }
        ),
        "stages": [
            {
                "stage_id": stage.stage_id.value,
                "stage_key": stage.stage_key,
                "source_available": stage.source_available,
                "active_or_assembling_session_id": (
                    None
                    if stage.active_or_assembling_session_id is None
                    else stage.active_or_assembling_session_id.value
                ),
                "session_activity_state": (
                    None
                    if stage.session_activity_state is None
                    else stage.session_activity_state.value
                ),
                "session_package_state": (
                    None
                    if stage.session_package_state is None
                    else stage.session_package_state.value
                ),
                "session_package_revision": stage.session_package_revision,
                "last_media_arrived_at": iso(stage.last_media_arrived_at),
                "discovered": stage.discovered_media,
                "stabilizing": stage.stabilizing_media,
                "ready_media": stage.ready_media,
                "registered": stage.registered_media,
                "associated": stage.associated_media,
                "unresolved": stage.unresolved_media,
                "conflicting": stage.conflicting_media,
                "attention_codes": list(stage.attention_codes),
            }
            for stage in status.stages
        ],
        "attention_codes": list(status.attention_codes),
        "recent_media_truncation_limit": MEDIA_PROJECTION_LIMIT,
    }


def latest_observation(
    observations: Sequence[ResourceObservation], kind: str
) -> ResourceObservation | None:
    matching = [item for item in observations if item.observation_kind == kind]
    return max(matching, key=lambda item: (item.observed_at, item.id.value), default=None)


def first_ready_at(observations: Sequence[ResourceObservation]) -> datetime | None:
    ready = [
        item.observed_at
        for item in observations
        if item.observation_kind == "asset_readiness_evaluation"
        and item.facts.get("ready") is True
    ]
    return min(ready, default=None)


def media_block_payload(
    *,
    candidate: MediaCandidate,
    observations: Sequence[ResourceObservation],
    asset: RegisteredMediaAsset | None,
    association: MediaAssociation | None,
    include_filename: bool,
) -> dict[str, Any]:
    snapshot = latest_observation(observations, "asset_resource_snapshot")
    filesystem_mtime = None if snapshot is None else snapshot.facts.get(
        "filesystem_modified_at"
    )
    return {
        "candidate_id": candidate.id.value,
        "proposed_asset_id": candidate.proposed_asset_id.value,
        "asset_id": None if asset is None else asset.id.value,
        "stable_media_identity": (
            candidate.proposed_asset_id.value if asset is None else asset.id.value
        ),
        "filename": Path(candidate.source_reference).name if include_filename else None,
        "stage_id": candidate.stage_id.value,
        "source_binding_key": candidate.source_binding_key,
        "discovered_at": iso(candidate.discovered_at),
        "last_observed_at": iso(candidate.last_observed_at),
        "filesystem_mtime_proxy": filesystem_mtime,
        "filesystem_mtime_is_block_close_truth": False,
        "readiness_at": iso(first_ready_at(observations)),
        "registration_at": None if asset is None else iso(asset.registered_at),
        "registration_state": candidate.state.value,
        "association_status": None if association is None else association.status.value,
        "association_authority": (
            None if association is None else association.authority.value
        ),
        "session_id": (
            None
            if association is None or association.session_id is None
            else association.session_id.value
        ),
        "association_decided_at": (
            None if association is None else iso(association.decided_at)
        ),
        "association_revision": None if association is None else association.revision,
        "association_reason_codes": (
            [] if association is None else list(association.reason_codes)
        ),
        "association_policy_id": None if association is None else association.policy_id,
        "association_policy_version": (
            None if association is None else association.policy_version
        ),
        "association_actor_id": (
            None
            if association is None or association.actor_id is None
            else association.actor_id.value
        ),
        "unresolved_or_conflict": (
            association is not None and association.status.value in {"unresolved", "conflict"}
        ),
    }


def refresh_media_blocks(
    components: KernelComponents, state: dict[str, Any], event_id: EntityId
) -> None:
    include_filename = bool(state.get("include_safe_filenames", False))
    blocks = required_object(
        state.setdefault("media_blocks", {}), "media_block_state_invalid"
    )
    for projection in components.repository.list_recent_media(
        event_id, limit=MEDIA_PROJECTION_LIMIT
    ):
        candidate = components.repository.get_candidate(projection.candidate_id)
        if candidate is None:
            continue
        asset = (
            None
            if projection.asset_id is None
            else components.repository.get_asset(projection.asset_id)
        )
        association = (
            None
            if projection.asset_id is None
            else components.repository.get_association(projection.asset_id)
        )
        observations = components.repository.list_observations(candidate.id)
        blocks[candidate.id.value] = media_block_payload(
            candidate=candidate,
            observations=observations,
            asset=asset,
            association=association,
            include_filename=include_filename,
        )


def capture_status(
    components: KernelComponents, state: dict[str, Any], *, reason: str
) -> dict[str, Any]:
    status = components.status()
    if status is None:
        raise ValidationRunnerError("event_status_unavailable")
    snapshot = status_payload(status)
    snapshot["reason"] = reason
    snapshots = required_list(
        state.setdefault("status_snapshots", []), "status_snapshot_state_invalid"
    )
    snapshots.append(snapshot)
    refresh_media_blocks(components, state, status.event_id)
    return snapshot


def execute_cycle(
    components: KernelComponents,
    state: dict[str, Any],
    *,
    scope: str,
    sequence: int,
    now: Callable[[], datetime] = utc_now,
    monotonic: Callable[[], float] = perf_counter,
) -> dict[str, Any]:
    event_id = require_event(components)
    invoked_at = now()
    started = monotonic()
    result = components.run_media_cycle(event_id=event_id, scope=scope)
    completed_at = now()
    entry = {
        "sequence": sequence,
        "scope": result.scope,
        "invoked_at": invoked_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": max(0.0, monotonic() - started),
        "candidates_seen": result.candidates_seen,
        "assets_registered": result.assets_registered,
        "source_failures": list(result.source_failures),
        "candidate_results": [
            {
                "candidate_id": item.candidate_id.value,
                "source_binding_key": item.source_binding_key,
                "state": item.state.value,
                "outcome": item.outcome,
                "failure_code": item.failure_code,
            }
            for item in result.candidate_results
        ],
    }
    cycles = required_list(state.setdefault("cycles", []), "cycle_state_invalid")
    cycles.append(entry)
    refresh_media_blocks(components, state, event_id)
    return entry


def state_session(state: Mapping[str, Any], label: str) -> dict[str, Any]:
    sessions = required_object(state.get("sessions"), "session_state_invalid")
    return required_object(
        sessions.get(label), f"session_label_not_found:{label}"
    )


def update_session(state: dict[str, Any], label: str, session: Session) -> None:
    sessions = required_object(
        state.setdefault("sessions", {}), "session_state_invalid"
    )
    sessions[label] = session_payload(session)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded, non-production StageFlow real-event validation runner."
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, required=True)
    common.add_argument("--run-file", type=Path, required=True)
    confirmed = argparse.ArgumentParser(add_help=False, parents=[common])
    confirmed.add_argument(DATABASE_ACKNOWLEDGEMENT, action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("initialize", parents=[common])
    initialize.add_argument("--run-id")
    initialize.add_argument("--actor-id")
    initialize.add_argument("--mode", choices=("direct", "vmix"), default="vmix")
    initialize.add_argument("--corpus-manifest", type=Path)
    initialize.add_argument("--corpus-item")
    initialize.add_argument("--include-filenames", action="store_true")
    initialize.add_argument("--source-assumption", action="append", default=[])

    subparsers.add_parser("migrate", parents=[confirmed])
    bootstrap = subparsers.add_parser("bootstrap", parents=[confirmed])
    bootstrap.add_argument("--operation-id")

    expectation = subparsers.add_parser("expectation", parents=[confirmed])
    expectation.add_argument("--key", required=True)
    expectation.add_argument("--title", required=True)
    expectation.add_argument("--stage-key")
    expectation.add_argument("--speaker", action="append", default=[])
    expectation.add_argument("--planned-start")
    expectation.add_argument("--planned-end")
    expectation.add_argument("--external-reference", action="append", default=[])

    start = subparsers.add_parser("start-session", parents=[confirmed])
    start.add_argument("--session-label", default="main")
    start.add_argument("--stage-key")
    start.add_argument("--at", required=True)
    start.add_argument("--title")
    start.add_argument("--expectation-key")
    start.add_argument("--operation-id")

    cycle = subparsers.add_parser("cycle", parents=[confirmed])
    cycle.add_argument("--scope", default="validation-manual")

    drive = subparsers.add_parser("drive-cycles", parents=[confirmed])
    drive.add_argument("--scope", default="validation-live")
    drive.add_argument("--cycle-every-seconds", type=float, required=True)
    drive.add_argument("--max-cycles", type=int, required=True)

    end = subparsers.add_parser("end-session", parents=[confirmed])
    end.add_argument("--session-label", default="main")
    end.add_argument("--at", required=True)
    end.add_argument("--reason", required=True)
    end.add_argument("--operation-id")

    assignment = subparsers.add_parser("assign-asset", parents=[confirmed])
    assignment.add_argument("--asset-id", required=True)
    assignment.add_argument("--session-label", required=True)
    assignment.add_argument("--reason", required=True)
    assignment.add_argument("--operation-id")

    package_ready = subparsers.add_parser("package-ready", parents=[confirmed])
    package_ready.add_argument("--session-label", default="main")

    completion = subparsers.add_parser("complete-package", parents=[confirmed])
    completion.add_argument("--session-label", default="main")
    decision = completion.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", action="store_true")
    completion.add_argument("--reason", required=True)
    completion.add_argument("--operation-id")

    subparsers.add_parser("status", parents=[confirmed])
    subparsers.add_parser("reconcile", parents=[confirmed])
    reconstruct = subparsers.add_parser("reconstruct", parents=[confirmed])
    reconstruct.add_argument("--stop-at")

    stop = subparsers.add_parser("record-stop", parents=[common])
    stop.add_argument("--at", required=True)
    stop.add_argument("--reason", default="operator_requested_validation_stop")

    ux = subparsers.add_parser("ux-note", parents=[common])
    ux.add_argument("--field", choices=tuple(UX_QUESTIONS), required=True)
    ux.add_argument("--answer", required=True)

    anomaly = subparsers.add_parser("anomaly", parents=[common])
    anomaly.add_argument("--text", required=True)
    return parser


def _confirmed(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "confirm_isolated_validation_database", False))


def _command_result(
    configuration: EffectiveKernelConfiguration,
    state: dict[str, Any],
    args: argparse.Namespace,
    *,
    checkpoint: Callable[[], None] | None = None,
) -> dict[str, Any]:
    command = str(args.command)
    if command == "record-stop":
        stopped_at = parse_aware_time(str(args.at))
        stop = {"stopped_at": stopped_at.isoformat(), "reason": str(args.reason)}
        required_list(
            state.setdefault("process_stops", []), "process_stop_state_invalid"
        ).append(stop)
        return stop
    if command == "ux-note":
        observations = required_object(
            state.get("ux_observations"), "ux_observation_state_invalid"
        )
        item = required_object(
            observations.get(str(args.field)), "ux_observation_field_invalid"
        )
        item["answer"] = str(args.answer)
        item["recorded_at"] = utc_now().isoformat()
        return item
    if command == "anomaly":
        item = {"recorded_at": utc_now().isoformat(), "text": str(args.text)}
        required_list(state.setdefault("anomalies", []), "anomaly_state_invalid").append(
            item
        )
        return item

    require_isolated_database_confirmation(_confirmed(args))
    if command == "migrate":
        PostgresMigrationRunner(configuration.postgres_dsn).apply_event_mode_kernel_v1()
        return {"migrations": [
            "0001_ingress",
            "0002_event_mode_kernel",
            "0003_kernel_projections",
            "0004_kernel_review_corrections",
            "0005_kernel_follow_up_closure",
            "0006_media_timing_evidence",
        ]}

    if command == "reconstruct":
        stop_at = (
            latest_recorded_stop(state)
            if args.stop_at is None
            else parse_aware_time(str(args.stop_at)).isoformat()
        )
        restarted_at = utc_now()
        environment = {**os.environ, "STAGEFLOW_KERNEL_CONFIG_PATH": str(args.config)}
        components = load_kernel_components_from_environment(environment=environment)
        if components is None:
            raise ValidationRunnerError("kernel_configuration_not_loaded")
        snapshot = capture_status(components, state, reason="fresh_process_reconstruction")
        result = {
            "recorded_stop_at": stop_at,
            "restart_invoked_at": restarted_at.isoformat(),
            "reconstruction_completed_at": utc_now().isoformat(),
            "status": snapshot,
        }
        required_list(
            state.setdefault("reconstructions", []), "reconstruction_state_invalid"
        ).append(result)
        return result

    components = compose_without_reconciliation(configuration)
    actor_id = EntityId.parse(str(state["actor_id"]))
    if command == "bootstrap":
        operation_id = retained_operation_id(
            state, key="bootstrap", supplied=args.operation_id
        )
        status = components.explicit_bootstrap(
            operation_id=operation_id, actor_id=actor_id
        )
        state["event"] = {
            "event_id": status.event_id.value,
            "event_key": status.event_key,
            "event_name": status.event_name,
        }
        snapshot = status_payload(status)
        required_list(
            state.setdefault("status_snapshots", []), "status_snapshot_state_invalid"
        ).append({**snapshot, "reason": "explicit_bootstrap"})
        refresh_media_blocks(components, state, status.event_id)
        return {"operation_id": operation_id.value, "status": snapshot}

    event_id = require_event(components)
    if command == "expectation":
        expectations = required_object(
            state.setdefault("expectations", {}), "expectation_state_invalid"
        )
        key = str(args.key)
        if key in expectations:
            return {"replayed_from_run_file": True, **expectations[key]}
        stage_id = stage_id_for_key(components, event_id, args.stage_key)
        expectation = components.kernel.record_program_expectation(
            event_id=event_id,
            key=key,
            title=str(args.title),
            speakers=tuple(str(value) for value in args.speaker),
            stage_id=stage_id,
            planned_start=(
                None
                if args.planned_start is None
                else parse_aware_time(str(args.planned_start))
            ),
            planned_end=(
                None if args.planned_end is None else parse_aware_time(str(args.planned_end))
            ),
            external_references=parse_key_values(args.external_reference),
        )
        result = {
            "expectation_id": expectation.id.value,
            "key": expectation.key,
            "revision": expectation.revision,
            "stage_id": None if expectation.stage_id is None else expectation.stage_id.value,
            "title": expectation.title,
            "planned_start": iso(expectation.planned_start),
            "planned_end": iso(expectation.planned_end),
        }
        expectations[key] = result
        return result

    if command == "start-session":
        label = str(args.session_label)
        operation_id = retained_operation_id(
            state, key=f"session_start:{label}", supplied=args.operation_id
        )
        stage_id = stage_id_for_key(components, event_id, args.stage_key)
        expectation_id = None
        if args.expectation_key is not None:
            expectations = required_object(
                state.get("expectations"), "expectation_state_invalid"
            )
            if args.expectation_key not in expectations:
                raise ValidationRunnerError("expectation_key_not_recorded")
            expectation = required_object(
                expectations.get(str(args.expectation_key)),
                "expectation_record_invalid",
            )
            expectation_id = EntityId.parse(
                str(expectation["expectation_id"])
            )
        authoritative_start = parse_aware_time(str(args.at))
        session = components.kernel.start_session(
            StartSessionRequest(
                operation_id=operation_id,
                event_id=event_id,
                stage_id=stage_id,
                actor_id=actor_id,
                authoritative_start=authoritative_start,
                requested_at=utc_now(),
                program_expectation_id=expectation_id,
                title=args.title,
            )
        )
        update_session(state, label, session)
        return {"operation_id": operation_id.value, "session": session_payload(session)}

    if command in {"cycle", "drive-cycles"}:
        if command == "cycle":
            entry = execute_cycle(
                components,
                state,
                scope=str(args.scope),
                sequence=len(state.get("cycles", [])) + 1,
            )
            return {"cycles": [entry], "interrupted": False}

        def run_once(_: int) -> dict[str, Any]:
            return execute_cycle(
                components,
                state,
                scope=str(args.scope),
                sequence=len(state.get("cycles", [])) + 1,
            )

        entries, interrupted = drive_bounded_cycles(
            run_once,
            maximum_cycles=int(args.max_cycles),
            cycle_every_seconds=float(args.cycle_every_seconds),
            on_cycle_completed=(
                None if checkpoint is None else lambda _: checkpoint()
            ),
        )
        return {"cycles": entries, "interrupted": interrupted}

    if command == "end-session":
        label = str(args.session_label)
        recorded = state_session(state, label)
        session_id = EntityId.parse(str(recorded["session_id"]))
        operation_id = retained_operation_id(
            state, key=f"session_end:{label}", supplied=args.operation_id
        )
        session = components.kernel.correct_session_boundary(
            operation_id=operation_id,
            session_id=session_id,
            boundary_kind="end",
            boundary_at=parse_aware_time(str(args.at)),
            actor_id=actor_id,
            reason=str(args.reason),
        )
        update_session(state, label, session)
        return {"operation_id": operation_id.value, "session": session_payload(session)}

    if command == "assign-asset":
        label = str(args.session_label)
        recorded = state_session(state, label)
        session_id = EntityId.parse(str(recorded["session_id"]))
        asset_id = EntityId.parse(str(args.asset_id))
        operation_id = retained_operation_id(
            state,
            key=f"asset_assignment:{asset_id.value}:{session_id.value}",
            supplied=args.operation_id,
        )
        association = components.kernel.assign_asset(
            operation_id=operation_id,
            asset_id=asset_id,
            session_id=session_id,
            actor_id=actor_id,
            reason=str(args.reason),
        )
        refresh_media_blocks(components, state, event_id)
        return {
            "operation_id": operation_id.value,
            "asset_id": asset_id.value,
            "session_id": session_id.value,
            "association_status": association.status.value,
            "association_revision": association.revision,
        }

    if command == "package-ready":
        label = str(args.session_label)
        recorded = state_session(state, label)
        session_id = EntityId.parse(str(recorded["session_id"]))
        current = components.repository.get_session(session_id)
        if current is None:
            raise ValidationRunnerError("session_not_found")
        if current.package_state is SessionPackageState.READY_FOR_REVIEW:
            update_session(state, label, current)
            return {"already_ready": True, "session": session_payload(current)}
        if current.package_state is not SessionPackageState.ASSEMBLING:
            raise ValidationRunnerError(
                f"package_ready_transition_not_allowed:{current.package_state.value}"
            )
        session = components.kernel.mark_package_ready(session_id)
        update_session(state, label, session)
        return {"already_ready": False, "session": session_payload(session)}

    if command == "complete-package":
        label = str(args.session_label)
        recorded = state_session(state, label)
        session_id = EntityId.parse(str(recorded["session_id"]))
        operation_id = retained_operation_id(
            state, key=f"package_completion:{label}", supplied=args.operation_id
        )
        session = components.kernel.complete_package(
            operation_id=operation_id,
            session_id=session_id,
            actor_id=actor_id,
            approved=bool(args.approve),
            reason=str(args.reason),
        )
        update_session(state, label, session)
        return {"operation_id": operation_id.value, "session": session_payload(session)}

    if command == "status":
        return capture_status(components, state, reason="operator_status")
    if command == "reconcile":
        components.reconcile_startup(event_id)
        return capture_status(components, state, reason="explicit_reconciliation")
    raise ValidationRunnerError(f"unsupported_command:{command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        files = RunFiles(args.run_file)
        with files.operation_lock(action=str(args.command)):
            configuration = load_kernel_deployment_configuration(args.config)
            if args.command == "initialize":
                if files.exists():
                    raise ValidationRunnerError("run_file_already_exists")
                state = initialize_state(
                    configuration,
                    run_id=args.run_id,
                    actor_id=args.actor_id,
                    mode=str(args.mode),
                    corpus_manifest=args.corpus_manifest,
                    corpus_item_id=args.corpus_item,
                    include_filenames=bool(args.include_filenames),
                    source_assumptions=parse_key_values(args.source_assumption),
                )
                result = record_command(
                    state,
                    name="initialize",
                    details={"mode": args.mode, "corpus_item": args.corpus_item},
                    action=lambda: {
                        "run_id": state["run_id"],
                        "actor_id": state["actor_id"],
                    },
                )
            else:
                state = files.load()
                validate_configuration_matches_state(configuration, state)
                try:
                    result = record_command(
                        state,
                        name=str(args.command),
                        details={"database_acknowledged": _confirmed(args)},
                        on_started=lambda: files.save(state),
                        action=lambda: _command_result(
                            configuration,
                            state,
                            args,
                            checkpoint=lambda: files.save(state),
                        ),
                    )
                except BaseException:
                    files.save(state)
                    raise
            files.save(state)
    except BaseException as exc:
        print(f"validation runner failed: {safe_error(exc)}", file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
