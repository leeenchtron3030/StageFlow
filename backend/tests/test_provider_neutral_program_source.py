from __future__ import annotations

import json
import socket
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import ValidationError

from app.api.v1.demo import router as demo_router
from app.api.v1.kernel_status import router as status_router
from app.bootstrap.event_mode_kernel import KernelComponents, build_kernel_components
from app.contexts.events import (
    EventStageBootstrapRequest,
    ProgramExpectationSnapshot,
    StageBootstrapDefinition,
)
from app.contexts.integration.devcon import DevconProgramSync, ExternalProgramItem
from app.contexts.integration.local_schedule import (
    LocalScheduleContractError,
    LocalScheduleFileSource,
    LocalScheduleReadError,
)
from app.contexts.integration.program_source import (
    ProgramScheduleSource,
    ProgramSourceUnavailableError,
)
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
)
from app.contexts.production.event_mode_kernel.contracts import StartSessionRequest
from app.core.config.deployment import (
    DevconReadConfiguration,
    EffectiveKernelConfiguration,
    KernelDeploymentConfiguration,
    LocalScheduleConfiguration,
    load_kernel_deployment_configuration,
)
from app.demo import cli
from app.infrastructure.devcon import DevconReadError
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 9, 24, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("program source test attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    monkeypatch.setattr("app.infrastructure.devcon.public_api.urlopen", forbidden)


def _session(key: str = "opening") -> dict[str, object]:
    return {
        "session_key": key,
        "title": "Opening discussion",
        "speakers": ["Example Speaker"],
        "stage_key": "main",
        "planned_start": "2026-09-24T14:00:00+02:00",
        "planned_end": "2026-09-24T14:30:00+02:00",
    }


def _schedule(*sessions: dict[str, object]) -> dict[str, object]:
    return {"schema_version": "1.0", "event_key": "example-event", "sessions": sessions}


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _configuration(path: Path) -> EffectiveKernelConfiguration:
    deployment = KernelDeploymentConfiguration.model_validate({
        "schema_version": "1.0",
        "deployment_id": "example-deployment",
        "node_id": "example-node",
        "runtime_profile": "demo-single-stage",
        "node_role": "node",
        "network_policy": "offline",
        "postgres_dsn_secret_ref": "EXAMPLE_DATABASE",
        "local_schedule": {"path": str(path)},
        "local_transcription": {"model_version": "example", "model_path": "C:/models/example"},
        "event": {
            "key": "example-event", "name": "Example Event",
            "stages": [{"key": "main", "name": "Main", "sources": [
                {"key": "recording", "path": "C:/example/media"},
            ]}],
        },
    })
    return EffectiveKernelConfiguration(
        deployment=deployment, postgres_dsn="postgresql://unused",
        sources={"recording": "C:/example/media"}, field_sources={},
    )


def _components(path: Path) -> KernelComponents:
    repository = InMemoryEventModeKernelRepository()
    clock = FixedClock(NOW)
    repository.bootstrap(EventStageBootstrapRequest(
        operation_id=EntityId.new(), event_key="example-event", event_name="Example Event",
        stages=(StageBootstrapDefinition(
            key="main", name="Main", source_bindings={"recording": "C:/example/media"},
        ),), actor_id=EntityId.new(), requested_at=NOW,
    ))
    return KernelComponents(
        configuration=_configuration(path), repository=repository,
        kernel=DurableEventModeKernel(repository=repository, clock=clock),
        program_source=LocalScheduleFileSource(
            path=path, event_key="example-event", stage_keys=("main",),
            repository=repository, clock=clock,
        ),
    )


class _HttpClient(Protocol):
    def get(self, url: str) -> Response: ...

    def post(self, url: str, *, json: object) -> Response: ...


@contextmanager
def _client(components: KernelComponents) -> Generator[_HttpClient]:
    app = FastAPI()
    app.include_router(demo_router)
    app.include_router(status_router)
    app.state.kernel = components
    with TestClient(app) as client:
        yield cast(_HttpClient, client)


def test_offline_import_replay_ordering_status_and_immutable_references(tmp_path: Path) -> None:
    path = tmp_path / "schedule.json"
    later = _session("later") | {
        "planned_start": "2026-09-24T15:00:00+02:00",
        "planned_end": "2026-09-24T15:30:00+02:00",
    }
    _write(path, _schedule(later, _session()))
    components = _components(path)
    source = components.program_source
    assert source is not None and isinstance(source, ProgramScheduleSource)
    assert source.probe() == 2
    initial = components.sync_program()
    repeated = components.sync_program()
    assert initial.provider == "local_file"
    assert (initial.added, repeated.unchanged) == (2, 2)
    assert [item.id for item in initial.expectations] == [item.id for item in repeated.expectations]
    first = initial.expectations[0]
    assert first.external_references["external_session_id"] == "opening"
    assert first.planned_start == NOW
    assert first.speakers == ("Example Speaker",)
    with pytest.raises(TypeError):
        cast(dict[str, str], first.external_references)["provider"] = "changed"
    assert components.repository.list_sessions_for_stage(initial.stage_id) == ()
    with _client(components) as client:
        response = client.get("/kernel/status")
        assert response.status_code == 200
        body = response.json()
        assert body["program_synchronization"]["provider"] == "local_file"
        item = body["program_expectations"][0]
        assert item["provider"] == "local_file"
        assert item["external_session_id"] == "opening"
        assert item["external_event_id"] == "example-event"
        assert item["external_room_id"] == "main"
        assert str(path) not in response.text


@pytest.mark.parametrize("payload", [
    {"schema_version": "2.0", "event_key": "example-event", "sessions": []},
    _schedule(_session()) | {"unknown": True},
    _schedule(_session() | {"unknown": True}),
    _schedule(_session() | {"planned_start": "2026-09-24T12:00:00"}),
    _schedule(_session() | {"planned_end": "2026-09-24T12:30:00"}),
    _schedule(_session() | {"planned_start": 12345}),
    _schedule(_session() | {"planned_end": "2026-09-23T12:30:00Z"}),
    _schedule(_session() | {"stage_key": "unknown"}),
    _schedule(_session(), _session()),
    _schedule(_session(), _session(" opening ")),
    _schedule(_session()) | {"event_key": "wrong-event"},
    _schedule(_session() | {"session_key": " "}),
    _schedule(_session() | {"title": 42}),
    _schedule(_session() | {"speakers": [{"name": "Example Speaker"}]}),
    _schedule(_session() | {"speakers": [""]}),
    {"event_key": "example-event", "sessions": []},
    _schedule({key: value for key, value in _session().items() if key != "stage_key"}),
    [],
])
def test_strict_rejection_preserves_cached_snapshot(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "schedule.json"
    _write(path, _schedule(_session()))
    components = _components(path)
    result = components.sync_program()
    _write(path, payload)
    source = components.program_source
    assert source is not None
    for operation in (source.probe, components.sync_program):
        with pytest.raises(LocalScheduleContractError):
            operation()
    assert source.cached_program(event_id=result.event_id) == tuple(result.expectations)
    assert components.repository.get_latest_program_reconciliation(
        result.event_id, result.stage_id
    ) == result


@pytest.mark.parametrize("content", [
    b'{"schema_version":"1.0","schema_version":"1.0","event_key":"example-event",'
    b'"sessions":[]}',
    b'{"schema_version":"1.0","event_key":"example-event","sessions":'
    b'[{"session_key":"one","session_key":"two"}]}',
    b"{broken", b"\xff", b"[" * 2000,
], ids=["duplicate-root", "duplicate-session", "invalid-json", "invalid-utf8", "depth"])
def test_malformed_json_is_typed(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "schedule.json"
    path.write_bytes(content)
    with pytest.raises(LocalScheduleContractError):
        _components(path).sync_program()


@pytest.mark.parametrize("failure", ["missing", "directory", "oversized"])
def test_unreadable_file_and_bounds_preserve_cache(tmp_path: Path, failure: str) -> None:
    path = tmp_path / "schedule.json"
    _write(path, _schedule(_session()))
    components = _components(path)
    result = components.sync_program()
    if failure == "missing":
        path.unlink()
    elif failure == "directory":
        path.unlink()
        path.mkdir()
    else:
        path.write_bytes(b" " * (4 * 1024 * 1024 + 1))
    with pytest.raises(LocalScheduleReadError) as exc:
        components.sync_program()
    assert str(path) not in str(exc.value)
    assert components.program_source is not None
    assert components.program_source.cached_program(event_id=result.event_id) == tuple(
        result.expectations
    )
    with _client(components) as client:
        response = client.post("/demo/program/refresh", json={})
        assert response.status_code == 503
        assert response.json()["detail"] == "program_refresh_failed_using_last_successful_snapshot"


def test_revisions_withdrawal_restoration_and_session_authority(tmp_path: Path) -> None:
    path = tmp_path / "schedule.json"
    _write(path, _schedule(_session()))
    components = _components(path)
    initial = components.sync_program()
    session = components.repository.start_session(StartSessionRequest(
        operation_id=EntityId.new(), event_id=initial.event_id, stage_id=initial.stage_id,
        program_expectation_id=initial.expectations[0].id, actor_id=EntityId.new(),
        authoritative_start=NOW, requested_at=NOW,
    ))
    _write(path, _schedule(_session() | {"title": "Revised title"}))
    changed = components.sync_program()
    assert (changed.changed, changed.expectations[0].revision) == (1, 2)
    _write(path, _schedule())
    assert components.sync_program().withdrawn == 1
    _write(path, _schedule(_session()))
    restored = components.sync_program()
    assert restored.restored == 1
    assert restored.expectations[0].id == initial.expectations[0].id
    assert restored.expectations[0].revision == 4
    assert components.repository.get_session(session.id) == session


def test_reconstructed_source_reorders_and_relocates_without_new_identity(tmp_path: Path) -> None:
    original = tmp_path / "schedule.json"
    _write(original, _schedule(_session("b"), _session("a")))
    components = _components(original)
    result = components.sync_program()
    relocated = tmp_path / "relocated.json"
    _write(relocated, _schedule(_session("a"), _session("b")))
    source = LocalScheduleFileSource(
        path=relocated, event_key="example-event", stage_keys=("main",),
        repository=components.repository, clock=FixedClock(NOW),
    )
    assert source.cached_program(event_id=result.event_id) == tuple(result.expectations)
    repeated = source.synchronize(event_id=result.event_id, stage_id=result.stage_id)
    assert repeated.unchanged == 2
    assert [item.id for item in repeated.expectations] == [item.id for item in result.expectations]


def test_session_count_bound_and_scope_rejections_do_not_mutate_cache(tmp_path: Path) -> None:
    path = tmp_path / "schedule.json"
    _write(path, _schedule(_session()))
    components = _components(path)
    result = components.sync_program()
    source = components.program_source
    assert source is not None
    with pytest.raises(LocalScheduleContractError, match="event_scope_mismatch"):
        source.synchronize(event_id=EntityId.new(), stage_id=result.stage_id)
    with pytest.raises(LocalScheduleContractError, match="stage_scope_mismatch"):
        source.synchronize(event_id=result.event_id, stage_id=EntityId.new())
    _write(path, _schedule(*(_session(str(index)) for index in range(10_001))))
    with pytest.raises(LocalScheduleContractError):
        components.sync_program()
    assert source.cached_program(event_id=result.event_id) == tuple(result.expectations)


@pytest.mark.parametrize("choice", ["local", "legacy", "both", "neither"])
def test_exactly_one_source_and_legacy_configuration(tmp_path: Path, choice: str) -> None:
    data = _configuration(tmp_path / "schedule.json").deployment.model_dump()
    if choice != "local":
        data["network_policy"] = "optional"
    if choice in {"legacy", "both"}:
        data["devcon_read"] = {"event_id": "example-event", "room_id": "main"}
    if choice in {"legacy", "neither"}:
        data["local_schedule"] = None
    if choice in {"both", "neither"}:
        with pytest.raises(ValidationError, match="exactly one"):
            KernelDeploymentConfiguration.model_validate(data)
    else:
        configured = KernelDeploymentConfiguration.model_validate(data)
        assert (configured.local_schedule is not None) == (choice == "local")
        if choice == "legacy":
            assert configured.devcon_read == DevconReadConfiguration(
                event_id="example-event", room_id="main",
            )


@pytest.mark.parametrize("path", ["relative.json", "../schedule.json", "https://example/file",
                                  "//host/share/file", "\\\\host\\share\\file"])
def test_local_configuration_rejects_nonlocal_or_relative_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        LocalScheduleConfiguration(path=path)


def test_local_configuration_forbids_provider_fields() -> None:
    with pytest.raises(ValidationError):
        LocalScheduleConfiguration.model_validate({"path": "C:/schedule.json", "provider": "x"})


def test_composition_uses_local_source(tmp_path: Path) -> None:
    path = tmp_path / "schedule.json"
    _write(path, _schedule(_session()))
    composed = build_kernel_components(_configuration(path), clock=FixedClock(NOW))
    assert isinstance(composed.program_source, LocalScheduleFileSource)
    assert composed.program_source.probe() == 1
    components = _components(path)
    assert components.sync_program().added == 1
    assert components.sync_program().unchanged == 1
    assert replace(components).program_source is components.program_source


class _ExternalSource:
    provider = "devcon"
    event_id = "example-event"
    room_id = "main"

    def fetch_program(self) -> tuple[ExternalProgramItem, ...]:
        return (ExternalProgramItem(
            event_id=self.event_id, room_id=self.room_id, room_name="Main", session_id="opening",
            title="Opening discussion", speakers=("Example Speaker",),
            planned_start=NOW, planned_end=NOW,
        ),)


def test_optional_adapter_conforms_and_writes_neutral_references(tmp_path: Path) -> None:
    components = _components(tmp_path / "unused.json")
    source: ProgramScheduleSource = DevconProgramSync(
        repository=components.repository, source=_ExternalSource(), clock=FixedClock(NOW),
    )
    assert isinstance(source, ProgramScheduleSource)
    assert source.probe() == 1
    components.program_source = source
    initial = components.sync_program()
    assert initial.provider == "devcon"
    assert components.sync_program().unchanged == 1
    references = initial.expectations[0].external_references
    assert references["external_session_id"] == "opening"
    assert references["external_event_id"] == "example-event"
    assert references["external_room_id"] == "main"
    assert "devcon_session_id" not in references
    assert source.cached_program(event_id=initial.event_id) == tuple(initial.expectations)
    assert isinstance(DevconReadError("unavailable"), ProgramSourceUnavailableError)


@pytest.mark.parametrize("mode", ["neutral", "legacy", "both"])
def test_reference_reads_in_reconciliation_and_status(tmp_path: Path, mode: str) -> None:
    path = tmp_path / "schedule.json"
    _write(path, _schedule(_session()))
    components = _components(path)
    initial = components.sync_program()
    references = {"provider": "devcon"}
    for kind in ("event", "session", "room"):
        if mode in {"legacy", "both"}:
            references[f"devcon_{kind}_id"] = f"legacy-{kind}"
        if mode in {"neutral", "both"}:
            references[f"external_{kind}_id"] = f"neutral-{kind}"
    expectation = replace(initial.expectations[0], external_references=references)
    result = components.repository.reconcile_program_expectations(ProgramExpectationSnapshot(
        event_id=initial.event_id, stage_id=initial.stage_id, provider="devcon",
        synchronization_scope=initial.synchronization_scope, observed_at=NOW,
        expectations=(expectation,),
    ))
    prefix = "legacy" if mode == "legacy" else "neutral"
    assert result.changes[0].external_session_id == f"{prefix}-session"
    with _client(components) as client:
        response = client.get("/kernel/status")
        assert response.status_code == 200
        item = response.json()["program_expectations"][0]
        for kind in ("event", "session", "room"):
            assert item[f"external_{kind}_id"] == f"{prefix}-{kind}"
            assert f"devcon_{kind}_id" not in item


def test_api_and_cli_propagate_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                       capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "schedule.json"
    _write(path, _schedule(_session()))
    components = _components(path)
    with _client(components) as client:
        response = client.post("/demo/program/refresh", json={})
        assert response.status_code == 200
        assert response.json()["provider"] == "local_file"
    monkeypatch.setattr(cli, "_components", lambda: components)
    assert cli.main(["sync-program"]) == 0
    assert json.loads(capsys.readouterr().out)["provider"] == "local_file"
    path.write_text("broken", encoding="utf-8")
    assert cli.main(["sync-program"]) == 1
    assert "local_schedule_invalid_format" in capsys.readouterr().err


def test_example_schedule_imports_offline(tmp_path: Path) -> None:
    example = Path(__file__).parents[2] / "examples/local-schedule.example.json"
    path = tmp_path / "schedule.json"
    path.write_bytes(example.read_bytes())
    assert _components(path).sync_program().provider == "local_file"


def test_toml_loader_accepts_local_section(tmp_path: Path) -> None:
    # Exercise the actual file loader, including its secret-reference resolution.
    config = tmp_path / "deployment.toml"
    config.write_text('''schema_version = "1.0"
deployment_id = "example-deployment"
node_id = "example-node"
node_role = "node"
postgres_dsn_secret_ref = "EXAMPLE_DATABASE"
[local_schedule]
path = 'C:/example/schedule.json'
[event]
key = "example-event"
name = "Example Event"
[[event.stages]]
key = "main"
name = "Main"
[[event.stages.sources]]
key = "recording"
path = 'C:/example/media'
''', encoding="utf-8")
    configured = load_kernel_deployment_configuration(
        config, environment={"EXAMPLE_DATABASE": "postgresql://unused"},
    )
    assert configured.deployment.local_schedule == LocalScheduleConfiguration(
        path="C:/example/schedule.json",
    )


@pytest.mark.parametrize(
    ("references", "expected"),
    [
        ({"external_session_id": "neutral"}, "neutral"),
        ({"devcon_session_id": "legacy"}, "legacy"),
        ({"external_session_id": "neutral", "devcon_session_id": "legacy"}, "neutral"),
        ({}, None),
    ],
)
def test_program_reference_reads_neutral_key_then_legacy_fallback(
    references: dict[str, str], expected: str | None
) -> None:
    """Persisted pre-ADR-0031 records carry only devcon_* keys and must stay readable."""
    from app.contexts.events.program_references import program_reference

    assert program_reference(references, "external_session_id") == expected


@pytest.mark.parametrize(
    ("neutral", "legacy"),
    [
        ("external_event_id", "devcon_event_id"),
        ("external_room_id", "devcon_room_id"),
    ],
)
def test_program_reference_fallback_covers_event_and_room_keys(
    neutral: str, legacy: str
) -> None:
    from app.contexts.events.program_references import program_reference

    assert program_reference({legacy: "persisted"}, neutral) == "persisted"  # type: ignore[arg-type]
