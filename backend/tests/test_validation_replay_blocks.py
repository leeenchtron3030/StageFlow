"""Live replay contracts tested without a database, network, ffmpeg or media."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from argparse import Namespace
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validation" / "replay_blocks.py"
spec = importlib.util.spec_from_file_location("validation_replay_blocks", SCRIPT)
assert spec is not None and spec.loader is not None
replay: Any = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = replay
spec.loader.exec_module(replay)

BASE = datetime(2026, 1, 1, tzinfo=UTC)
EVENT = str(UUID(int=1))
STAGE = str(UUID(int=2))
ACTOR = str(UUID(int=3))


def span(start: float, end: float) -> Any:
    return replay.Span(BASE + timedelta(seconds=start), BASE + timedelta(seconds=end))


def settings(count: int = 5, every: int = 2, pace: float = 2) -> Any:
    return replay.Settings(
        tuple(Path(f"private-block-{i}.mp4") for i in range(count)), Path("private-source"),
        (10.0,) * count, pace, every, ACTOR, "private-event", "private-deployment", "private-node",
        (), 20, 1,
    )


class FakeEffects:
    def __init__(self) -> None:
        self.clock = 0.0
        self.copied = 0
        self.copy_times: list[float] = []
        self.requests: list[tuple[str, str, Any]] = []
        self.workers: list[str] = []
        self.done: dict[str, int] = {"media_timing": 0, "media_segmentation": 0}
        self.runs: list[int] = []
        self.discovery_timeout_at = 0
        self.worker_failure = False
        self.terminal_failure = False
        self.empty_operations = False
        self.stale_run = False
        self.work_seconds = 0.0

    def now(self) -> float:
        return self.clock

    def sleep(self, seconds: float) -> None:
        assert 0 < seconds <= 60
        self.clock += seconds

    def copy(self, block: Path, source: Path, ordinal: int) -> None:
        self.copied = ordinal
        self.copy_times.append(self.clock)

    def worker(self, kind: str, timeout: float) -> None:
        assert 0 < timeout <= 20
        self.workers.append(kind)
        if self.worker_failure:
            raise RuntimeError("private-secret path timestamp")
        self.clock += self.work_seconds
        self.done[kind] = self.copied

    def request(self, method: str, path: str, body: dict[str, Any] | None,
                timeout: float) -> dict[str, Any]:
        assert timeout > 0
        self.requests.append((method, path, body))
        if path == "/api/v1/kernel/status":
            registered = self.copied - int(self.copied == self.discovery_timeout_at > 0)
            return {
                "event_id": EVENT, "event_key": "private-event",
                "deployment_id": "private-deployment", "node_id": "private-node",
                "ready": True, "database_available": True, "automation": {"enabled": True},
                "stages": [{"stage_id": STAGE, "key": "main", "discovered": registered,
                            "stabilizing": 0, "ready": 0,
                            "registered": registered, "associated": 0}],
                "recent_media": [{"stage_id": STAGE, "asset_id": str(UUID(int=100 + i))}
                                 for i in range(1, registered + 1)],
            }
        if "/media-timing/assets/" in path:
            return {"evidence": {"candidate_interval": {
                "started_at": BASE.isoformat(),
                "ended_at": (BASE + timedelta(seconds=10)).isoformat(),
            }}}
        if path.endswith("/runs"):
            assert body == {"actor_id": ACTOR}
            self.runs.append(self.copied)
            return {"run_id": str(UUID(int=200 + len(self.runs)))}
        if path.endswith("/runs/latest"):
            return {"run_id": str(UUID(int=200 + len(self.runs) + int(self.stale_run))),
                    "blocks": [], "skips": dict.fromkeys(replay.SKIPS, 0),
                    "private-title": "private-secret"}
        if "/suggestions?" in path:
            return {"items": [{"run_id": str(UUID(int=200 + len(self.runs))),
                               "suggested_start": BASE.isoformat(),
                               "suggested_end": (BASE + timedelta(seconds=10)).isoformat(),
                               "title": "private-secret"}], "next_after": None}
        kind = "media_timing" if "/media-timing/" in path else "media_segmentation"
        if method == "POST":
            assert body == {"actor_id": ACTOR, "confirmed": "confirmed", "limit": 100}
        state = "succeeded" if self.done[kind] == self.copied else "pending"
        if self.terminal_failure:
            state = "terminal_failed"
        return {"items": [] if self.empty_operations and method == "GET" else [
            {"asset_id": str(UUID(int=100 + self.copied)), "state": state}], "next_after": None}


@pytest.mark.parametrize(("pace", "expected"), [(1, (10, 30, 35)), (5, (2, 6, 7))])
def test_pacing_math(pace: float, expected: tuple[int, ...]) -> None:
    assert replay.schedule((10, 20, 5), pace) == expected


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_pacing(value: float) -> None:
    with pytest.raises(replay.Refusal):
        replay.schedule((10,), value)
    with pytest.raises(replay.Refusal):
        replay.schedule((value,), 1)


@pytest.mark.parametrize(("count", "every", "expected"), [
    (5, 2, [2, 4, 5]), (4, 2, [2, 4]), (2, 7, [2]), (1, 1, [1]),
])
def test_run_every_including_final_and_api_worker_contracts(
    count: int, every: int, expected: list[int],
) -> None:
    effects, progress = FakeEffects(), replay.Progress()
    replay.drive(settings(count, every), effects, progress)
    assert effects.runs == expected
    assert [run.copied for run in progress.observations] == expected
    assert effects.copy_times == [5 * i for i in range(1, count + 1)]
    assert effects.workers == ["media_timing", "media_segmentation"] * count
    assert progress.copied == progress.registered == progress.settled == count


def test_slow_pipeline_does_not_add_another_duration_sleep() -> None:
    effects = FakeEffects()
    effects.work_seconds = 6
    progress = replay.Progress()
    replay.drive(settings(2, 1), effects, progress)
    assert effects.copy_times == [5, 19]
    assert progress.observations[1].media_seconds == 66


@pytest.mark.parametrize("problem", ["nonempty", "inside", "secret", "truth_inside"])
def test_refusal_locations_and_secret(problem: str) -> None:
    root = Path("/repository").absolute()
    external = Path("/external").absolute()
    with pytest.raises(replay.Refusal):
        replay.validate_locations(
            root / "source" if problem == "inside" else external / "source", external / "blocks",
            root / "truth.json" if problem == "truth_inside" else None, root,
            source_empty=problem != "nonempty", secret="" if problem == "secret" else "fake-secret",
        )


@pytest.mark.parametrize("raw", [
    "broken-json", "{}", "[]", '[{"start":"2026-01-01","end":"2026-01-02"}]',
    '[{"start":"2026-01-01T00:00:00Z","end":"2026-01-01T00:01:00"}]',
    '[{"start":"2026-01-01T00:01:00Z","end":"2026-01-01T00:00:00Z"}]',
    '[{"start":"2026-01-01T00:00:00Z","end":"2026-01-01T00:01:00Z","title":"x"}]',
])
def test_bad_truth_and_naive_timestamps_refused(raw: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        replay.parse_truth(raw)


def test_truth_normalizes_aware_offsets_and_sorts() -> None:
    truth = replay.parse_truth(json.dumps([
        {"start": "2026-01-01T01:01:00+01:00", "end": "2026-01-01T01:02:00+01:00"},
        {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:01:00Z"},
    ]))
    assert truth == (span(0, 60), span(60, 120))


def test_atomic_copy_uses_excluded_suffix_and_renames_only_after_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations: list[Any] = []

    class Buffer(io.BytesIO):
        def fileno(self) -> int:
            return 42

        def close(self) -> None:
            operations.append("closed")
            super().close()

    target = Buffer()

    def opened(path: Path, mode: str) -> io.BytesIO:
        operations.append((path, mode))
        return target if mode == "xb" else io.BytesIO(b"synthetic bytes")

    def renamed(path: Path, destination: Path) -> None:
        assert target.closed
        operations.append((path, destination))

    def absent(path: Path) -> bool:
        return False

    def synced(fd: int) -> None:
        operations.append(fd)

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(Path, "exists", absent)
    monkeypatch.setattr(Path, "rename", renamed)
    monkeypatch.setattr(replay.os, "fsync", synced)
    replay.atomic_copy(Path("private.MP4"), Path("source"), 1)
    assert operations == [
        (Path("source/block-000001.mp4.partial"), "xb"), (Path("private.MP4"), "rb"), 42,
        "closed", (Path("source/block-000001.mp4.partial"), Path("source/block-000001.mp4")),
    ]


def test_atomic_copy_refuses_overwrite(monkeypatch: pytest.MonkeyPatch) -> None:
    def exists(path: Path) -> bool:
        return True

    monkeypatch.setattr(Path, "exists", exists)
    with pytest.raises(replay.PipelineFailure):
        replay.atomic_copy(Path("private.mp4"), Path("source"), 1)


def test_pagination_requests_and_operations_follow_cursor() -> None:
    class Paged(FakeEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            self.requests.append((method, path, body))
            after = body.get("after") if body else parse_qs(urlsplit(path).query).get("after")
            return {"items": [{"ordinal": 2 if after else 1}],
                    "next_after": None if after else ACTOR}

    for method, body in (("POST", {"actor_id": ACTOR}), ("GET", None)):
        effects = Paged()
        assert replay.page_items(effects, method, "/page", 20, body) == [
            {"ordinal": 1}, {"ordinal": 2},
        ]
        assert len(effects.requests) == 2


@pytest.mark.parametrize("failure", ["terminal_failure", "empty_operations", "stale_run"])
def test_pipeline_failure_modes_are_bounded(failure: str) -> None:
    effects = FakeEffects()
    setattr(effects, failure, True)
    progress = replay.Progress()
    with pytest.raises(replay.PipelineFailure):
        replay.drive(settings(1, 1), effects, progress)
    assert effects.clock <= 25
    assert progress.copied == 1
    assert not progress.observations


def test_mismatched_config_is_refused_before_copy() -> None:
    effects = FakeEffects()
    with pytest.raises(replay.Refusal):
        replay.drive(replace(settings(), event_key="other-event"), effects, replay.Progress())
    assert not effects.copy_times


def test_existing_discovered_asset_is_refused_before_copy() -> None:
    class ExistingMedia(FakeEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            value = super().request(method, path, body, timeout)
            if path == "/api/v1/kernel/status":
                value["stages"][0]["discovered"] = 1
            return value

    effects, progress = ExistingMedia(), replay.Progress()
    with pytest.raises(replay.Refusal):
        replay.drive(settings(), effects, progress)
    assert effects.copy_times == []
    assert effects.copied == progress.copied == 0
    assert effects.workers == effects.runs == []
    assert effects.requests == [("GET", "/api/v1/kernel/status", None)]


def test_truth_origin_comes_from_first_registered_asset_timing() -> None:
    effects, progress = FakeEffects(), replay.Progress()
    replay.drive(replace(settings(1, 1), truth=(span(0, 10),)), effects, progress)
    assert progress.origin == BASE


def test_timeout_retains_completed_runs_and_sanitizes_partial_report() -> None:
    effects = FakeEffects()
    effects.discovery_timeout_at = 3
    code, document = replay.execute(settings(4, 2), effects)
    assert code == 3
    assert document["error_count"] == 1
    assert document["blocks_copied"] == 3
    assert document["blocks_registered"] == document["blocks_settled"] == 2
    assert [run["blocks_copied"] for run in document["runs"]] == [2]
    serialized = json.dumps(document)
    for private in ("private", "mp4", EVENT, STAGE, ACTOR, "2026-", "source", "path"):
        assert private not in serialized


def test_worker_failure_has_no_exception_or_child_output() -> None:
    effects = FakeEffects()
    effects.worker_failure = True
    code, document = replay.execute(settings(), effects)
    assert code == 3
    assert document["blocks_copied"] == document["blocks_registered"] == 1
    assert document["blocks_settled"] == 0
    assert "private" not in json.dumps(document)


def test_cli_parser_never_echoes_invalid_argument(capsys: pytest.CaptureFixture[str]) -> None:
    assert replay.main(["--secret", "private-secret"]) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n'
    assert output.err == ""


def fake_inputs(monkeypatch: pytest.MonkeyPatch) -> tuple[Namespace, dict[str, str]]:
    root = Path("/anonymous-external").absolute()
    source, blocks, config = root / "source", root / "blocks", root / "config.toml"
    config_text = f'''
deployment_id = "private-deployment"
node_id = "private-node"
[event]
key = "private-event"
[[event.stages]]
key = "main"
[[event.stages.sources]]
path = '{source.as_posix()}'
allowed_extensions = [".mp4"]
[autonomous_event_node]
enabled = true
[local_media_timing]
enabled = true
ffprobe_path = '/operator/ffprobe'
[local_media_segmentation]
enabled = true
'''

    def resolve(path: Path, strict: bool = False) -> Path:
        return path

    def is_dir(path: Path) -> bool:
        return path in (source, blocks)

    def is_file(path: Path) -> bool:
        return not is_dir(path)

    def is_symlink(path: Path) -> bool:
        return False

    def iterdir(path: Path) -> Iterator[Path]:
        return iter((blocks / "02.mp4", blocks / "01.mp4") if path == blocks else ())

    def opened(path: Path, mode: str) -> io.BytesIO:
        assert path == config and mode == "rb"
        return io.BytesIO(config_text.encode())

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "is_dir", is_dir)
    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(Path, "is_symlink", is_symlink)
    monkeypatch.setattr(Path, "iterdir", iterdir)
    monkeypatch.setattr(Path, "open", opened)
    return Namespace(source=source, blocks=blocks, truth=None, actor_id=ACTOR, pace="real",
                     run_every=1, api_base_url="http://127.0.0.1:8000", timeout_seconds=20,
                     poll_seconds=1, duration_seconds=10), {
        "STAGEFLOW_API_SHARED_SECRET": "private-secret",
        "STAGEFLOW_KERNEL_CONFIG_PATH": str(config),
    }


def test_prepare_orders_blocks_and_supplied_duration_skips_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, environment = fake_inputs(monkeypatch)

    def unexpected_probe(path: Path, executable: Path) -> float:
        pytest.fail("supplied duration must bypass ffprobe")

    result = replay.prepare(args, environment, unexpected_probe)
    assert [block.name for block in result.blocks] == ["01.mp4", "02.mp4"]
    assert result.durations == (10, 10)
    assert result.pace == 1


@pytest.mark.parametrize("problem", [
    "nonempty_source", "source_inside_repository", "mismatched_binding",
    "local_media_timing", "local_media_segmentation", "unsupported_block",
    "hidden_block", "symlinked_block",
])
def test_prepare_operator_safety_refusals_and_sanitized_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], problem: str,
) -> None:
    args, environment = fake_inputs(monkeypatch)
    original_source = args.source
    original_open, original_iterdir, original_is_dir = Path.open, Path.iterdir, Path.is_dir
    if problem == "source_inside_repository":
        args.source = replay.REPOSITORY / "synthetic-source"

    def is_dir(path: Path) -> bool:
        return path == args.source or original_is_dir(path)

    def iterdir(path: Path) -> Iterator[Path]:
        if path == args.source:
            return iter((path / "existing.mp4",) if problem == "nonempty_source" else ())
        extra = {"unsupported_block": "03.txt", "hidden_block": ".03.mp4"}.get(problem)
        return iter((*original_iterdir(path), path / extra)) if extra else original_iterdir(path)

    def opened(path: Path, mode: str) -> io.BytesIO:
        with original_open(path, mode) as handle:
            config_text = handle.read().decode()
        binding = (original_source.parent / "other-source"
                   if problem == "mismatched_binding" else args.source)
        config_text = config_text.replace(original_source.as_posix(), binding.as_posix())
        if problem in {"local_media_timing", "local_media_segmentation"}:
            config_text = config_text.replace(f"[{problem}]\nenabled = true",
                                              f"[{problem}]\nenabled = false")
        return io.BytesIO(config_text.encode())

    def is_symlink(path: Path) -> bool:
        return problem == "symlinked_block" and path == args.blocks / "01.mp4"

    def unexpected_effects(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("refused inputs must not create pipeline effects")

    monkeypatch.setattr(Path, "is_dir", is_dir)
    monkeypatch.setattr(Path, "iterdir", iterdir)
    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(Path, "is_symlink", is_symlink)
    with pytest.raises(replay.Refusal):
        replay.prepare(args, environment)
    assert replay.main([
        "--source", str(args.source), "--blocks", str(args.blocks),
        "--api-base-url", args.api_base_url, "--actor-id", args.actor_id,
        "--duration-seconds", str(args.duration_seconds),
    ], environment=environment, factory=unexpected_effects) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n'
    assert output.err == ""


def test_prepare_uses_each_probe_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    args, environment = fake_inputs(monkeypatch)
    args.duration_seconds = None
    args.pace = "4"

    def probe(path: Path, executable: Path) -> float:
        assert executable == Path("/operator/ffprobe")
        return 10 if path.name == "01.mp4" else 20

    result = replay.prepare(args, environment, probe)
    assert result.durations == (10, 20)
    assert replay.schedule(result.durations, result.pace) == (2.5, 7.5)


@pytest.mark.parametrize(("key", "value"), [
    ("pace", "nan"), ("pace", "0.5"), ("run_every", 0), ("duration_seconds", -1),
    ("actor_id", "not-a-uuid"), ("api_base_url", "http://user:secret@localhost"),
    ("api_base_url", "http://localhost/api/v1"),
])
def test_prepare_invalid_arguments_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, key: str, value: Any,
) -> None:
    args, environment = fake_inputs(monkeypatch)
    setattr(args, key, value)
    with pytest.raises(ValueError):
        replay.prepare(args, environment)


def test_missing_secret_is_refused_before_reading_config(monkeypatch: pytest.MonkeyPatch) -> None:
    args, environment = fake_inputs(monkeypatch)
    del environment["STAGEFLOW_API_SHARED_SECRET"]

    def unopened(*args: Any, **kwargs: Any) -> None:
        pytest.fail("configuration must not be read")

    monkeypatch.setattr(Path, "open", unopened)
    with pytest.raises(replay.Refusal):
        replay.prepare(args, environment)


def test_worker_adapter_suppresses_output_and_preserves_operator_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[list[str], dict[str, Any]]] = []

    def run(command: list[str], **kwargs: Any) -> None:
        commands.append((command, kwargs))

    monkeypatch.setattr(replay.subprocess, "run", run)
    environment = {"STAGEFLOW_API_SHARED_SECRET": "private-secret",
                   "STAGEFLOW_KERNEL_CONFIG_PATH": "private-config"}
    replay.LocalEffects("http://localhost:8000", environment).worker("media_timing", 19)
    command, kwargs = commands[0]
    assert command == [sys.executable, "-m", "app.demo.media_timing_worker", "--once"]
    assert kwargs["timeout"] == 19 and kwargs["check"] is True
    assert kwargs["stdout"] == kwargs["stderr"] == replay.subprocess.DEVNULL
    assert kwargs["env"] == environment
    assert "private-secret" not in " ".join(command)


def test_http_adapter_uses_header_and_refuses_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[Any] = []

    class Opener:
        def open(self, request: Any, timeout: float) -> io.BytesIO:
            requests.append(request)
            assert timeout == 20
            return io.BytesIO(b'{"items": []}')

    effects = replay.LocalEffects("http://localhost:8000", {
        "STAGEFLOW_API_SHARED_SECRET": "private-secret",
    })
    effects.opener = Opener()
    assert effects.request("GET", "/api/v1/kernel/status", None, 20) == {"items": []}
    assert requests[0].get_header("X-stageflow-api-secret") == "private-secret"
    assert "private-secret" not in requests[0].full_url
    with pytest.raises(replay.PipelineFailure):
        replay.NoRedirect().redirect_request(None, None, 302, "", None, "http://elsewhere")


def observation(media: float, *suggestions: Any) -> Any:
    return replay.Observation(1, media / 2, media, tuple(suggestions), (0,) * len(replay.SKIPS))


def test_per_talk_latency_stability_threshold_and_absent_runs() -> None:
    progress = replay.Progress(origin=BASE, observations=[
        observation(90, span(0, 100)),  # Early suggestions have zero latency.
        observation(110, span(1, 99)),  # Exactly one second is stable.
        observation(120),
        observation(130, span(3, 97), span(200, 300)),
        observation(320, span(3.5, 96.5), span(202, 302)),
        observation(350, span(5, 95), span(205, 306)),
    ])
    document = replay.report(progress, (span(0, 100), span(200, 300), span(400, 500)), 0)
    assert document["talks"] == [
        {"ordinal": 1, "time_to_first_suggestion_seconds": 0,
         "stability_change_count": 2, "maximum_edge_move_seconds": 2},
        {"ordinal": 2, "time_to_first_suggestion_seconds": 0,
         "stability_change_count": 2, "maximum_edge_move_seconds": 4},
        {"ordinal": 3, "time_to_first_suggestion_seconds": None,
         "stability_change_count": 0, "maximum_edge_move_seconds": 0},
    ]
    assert document["final_accuracy"] == {
        "truth_count": 3, "suggestion_count": 2, "matched_count": 2, "recall": 2 / 3,
        "median_start_error_seconds": 5, "median_end_error_seconds": 5.5,
    }


def test_latency_uses_media_clock_and_recording_origin_not_first_truth_start() -> None:
    progress = replay.Progress(origin=BASE, observations=[
        observation(150), observation(240, span(60, 180)),
    ])
    talk = replay.report(progress, (span(60, 180),), 0)["talks"][0]
    assert talk["time_to_first_suggestion_seconds"] == 60
    assert talk["stability_change_count"] == 0
    assert talk["maximum_edge_move_seconds"] == 0


def test_per_talk_matching_is_global_one_to_one_and_retains_duplicate_truth() -> None:
    progress = replay.Progress(origin=BASE, observations=[
        observation(200, span(75, 175), span(25, 125)),
    ])
    talks = replay.report(progress, (span(0, 100), span(50, 150)), 0)["talks"]
    assert [talk["time_to_first_suggestion_seconds"] for talk in talks] == [100, 50]
    progress.observations = [observation(200, span(0, 100))]
    talks = replay.report(progress, (span(0, 100), span(0, 100)), 0)["talks"]
    assert [talk["time_to_first_suggestion_seconds"] for talk in talks] == [100, None]


def test_no_truth_omits_metrics_and_no_runs_reports_unmatched_truth() -> None:
    assert "talks" not in replay.report(replay.Progress(), (), 0)
    document = replay.report(replay.Progress(), (span(0, 10),), 1)
    assert document["talks"][0]["time_to_first_suggestion_seconds"] is None
    assert document["talks"][0]["stability_change_count"] == 0
    assert document["final_accuracy"]["matched_count"] == 0
    assert document["final_accuracy"]["median_start_error_seconds"] is None


def test_completed_and_partial_reports_include_sanitized_truth_metrics() -> None:
    for fail_at in (0, 3):
        effects = FakeEffects()
        effects.discovery_timeout_at = fail_at
        code, document = replay.execute(replace(settings(4, 2), truth=(span(0, 10),)), effects)
        assert code == (3 if fail_at else 0)
        assert document["talks"][0]["time_to_first_suggestion_seconds"] == 14
        assert document["final_accuracy"]["recall"] == 1
        assert document["talks"][0]["stability_change_count"] == 0
        serialized = json.dumps(document)
        for private in ("private", "mp4", EVENT, STAGE, ACTOR, "2026-", "source", "path"):
            assert private not in serialized


def test_running_reconciliation_at_startup_and_during_discovery_is_tolerated() -> None:
    class Reconciling(FakeEffects):
        status_reads = 0

        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            value = super().request(method, path, body, timeout)
            if path == "/api/v1/kernel/status":
                self.status_reads += 1
                value["ready"] = self.status_reads == 2
            return value

    effects = Reconciling()
    code, document = replay.execute(settings(2, 1), effects)
    assert code == 0
    assert document["blocks_settled"] == 2
    assert effects.copy_times[0] == 6


def test_permanently_not_ready_times_out_before_copy() -> None:
    class Unready(FakeEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            value = super().request(method, path, body, timeout)
            value["ready"] = False
            return value

    effects = Unready()
    code, document = replay.execute(settings(), effects)
    assert code == 3
    assert document["blocks_copied"] == 0
    assert document["runs"] == []
    assert effects.clock == 20


def test_registration_uses_paginated_requests_beyond_recent_media_projection() -> None:
    class Truncated(FakeEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            if method == "POST" and "/media-timing/" in path:
                assert body is not None
                assert body["actor_id"] == ACTOR and body["confirmed"] == "confirmed"
                assert body["limit"] == 100
                self.requests.append((method, path, body))
                start = 100 if body.get("after") else 0
                stop = min(start + 100, self.copied)
                return {"items": [{"asset_id": str(UUID(int=101 + i)), "state": "pending"}
                                  for i in range(start, stop)],
                        "next_after": str(UUID(int=200)) if stop < self.copied else None}
            value = super().request(method, path, body, timeout)
            if path == "/api/v1/kernel/status":
                value["recent_media"] = value["recent_media"][:100]
            return value

    effects = Truncated()
    code, document = replay.execute(settings(102, 100), effects)
    assert code == 0
    assert document["blocks_registered"] == document["blocks_settled"] == 102
    assert [run["blocks_copied"] for run in document["runs"]] == [100, 102]


def test_enqueue_failure_retains_registration_already_observed() -> None:
    class EnqueueFailure(FakeEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            if method == "POST" and "/media-timing/" in path:
                raise OSError("private diagnostic")
            return super().request(method, path, body, timeout)

    code, document = replay.execute(settings(), EnqueueFailure())
    assert code == 3
    assert document["blocks_copied"] == document["blocks_registered"] == 1
    assert document["blocks_settled"] == 0
    assert "private" not in json.dumps(document)


class UpgradedEffects(FakeEffects):
    def __init__(self) -> None:
        super().__init__()
        self.transcription_state = "succeeded"
        self.complete = True
        self.partial = False
        self.existing_cues = False
        self.enqueued = 7
        self.enqueue_reads = 0
        self.transcribed = 0
        self.status_reads = 0

    def worker(self, kind: str, timeout: float) -> Any:
        if kind != "transcription":
            return super().worker(kind, timeout)
        self.workers.append(kind)
        self.transcribed = self.copied
        self.clock += self.work_seconds
        return "terminal_failed" if self.transcription_state == "terminal_failed" else "succeeded"

    def request(self, method: str, path: str, body: dict[str, Any] | None,
                timeout: float) -> dict[str, Any]:
        if path.endswith("/boundary-cues"):
            self.requests.append((method, path, body))
            return {"current": {} if self.existing_cues else None}
        if path.endswith("/boundary-cue-catalog"):
            return {"version": 9, "profiles": [{"name": "Conference stage", "key": "conference-9",
                                                 "group_keys": ["group-a", "group-b"]}]}
        if "/transcription/assets/" in path:
            self.status_reads += 1
            done = self.transcribed == self.copied
            return {"operation": {"state": self.transcription_state if done else "pending"},
                    "complete_evidence": self.complete and done,
                    "partial_evidence": self.partial and done, "text": "private transcript"}
        value = super().request(method, path, body, timeout)
        if path == "/api/v1/kernel/status":
            self.enqueue_reads += 1
            value["automation"]["transcription_operations_enqueued"] = (
                self.enqueued + max(0, self.copied - int(self.enqueue_reads % 2 == 0)))
        return value


def test_default_report_shape_is_byte_identical() -> None:
    code, document = replay.execute(settings(1, 1), FakeEffects())
    assert code == 0
    expected = {"error_count": 0, "blocks_copied": 1, "blocks_registered": 1,
                "blocks_settled": 1, "runs": [{"ordinal": 1, "blocks_copied": 1,
                "wall_seconds": 7.0, "media_seconds": 14.0, "suggestion_count": 1,
                "skips": dict.fromkeys(replay.SKIPS, 0)}]}
    assert json.dumps(document, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_transcription_prepare_requires_table(monkeypatch: pytest.MonkeyPatch) -> None:
    args, env = fake_inputs(monkeypatch)
    args.transcription = True
    with pytest.raises(replay.Refusal):
        replay.prepare(args, env)
    original = Path.open
    def opened(path: Path, mode: str) -> io.BytesIO:
        with original(path, mode) as f:
            return io.BytesIO(f.read() + b"\n[local_transcription]\n")
    monkeypatch.setattr(Path, "open", opened)
    assert replay.prepare(args, env).transcription


@pytest.mark.parametrize("label", ["", "A", "a b", "a/secret", "-a", "a" * 65, "a\n"])
def test_profile_label_refused(monkeypatch: pytest.MonkeyPatch, label: str) -> None:
    args, env = fake_inputs(monkeypatch)
    args.profile_label = label
    with pytest.raises(replay.Refusal):
        replay.prepare(args, env)


def test_profile_label_allowed_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    args, env = fake_inputs(monkeypatch)
    args.profile_label = "appliance.v1_gpu-0"
    assert replay.prepare(args, env).profile_label == args.profile_label
    code, doc = replay.execute(
        replace(settings(1), profile_label=args.profile_label), FakeEffects())
    assert code == 0 and doc["profile_label"] == args.profile_label


def test_transcription_cues_counter_worker_and_timeline() -> None:
    effects = UpgradedEffects()
    code, doc = replay.execute(replace(settings(2, 1), transcription=True), effects)
    assert code == 0 and doc["transcription_unavailable_count"] == 0
    assert effects.workers.count("transcription") == 2
    assert effects.status_reads == 4
    compositions = [body for method, path, body in effects.requests
                    if method == "POST" and path.endswith("/boundary-cues")]
    assert len(compositions) == 1
    body = compositions[0]
    assert UUID(body["command_id"])
    assert {k: v for k, v in body.items() if k != "command_id"} == {
        "catalog_version": 9, "profile_key": "conference-9",
        "group_keys": ["group-a", "group-b"],
        "actor_id": ACTOR, "authority_kind": "human",
    }
    assert doc["evidence_timeline"]["runs"][-1]["transcription"] == 2
    assert doc["evidence_timeline"]["runs"][-1]["segmentation"] == 2
    assert doc["evidence_timeline"]["blocks"][0]["transcription"] >= 14
    assert "private" not in json.dumps(doc)


def test_transcription_refuses_existing_composition_before_arrival() -> None:
    effects = UpgradedEffects()
    effects.existing_cues = True
    assert replay.execute(replace(settings(), transcription=True), effects) == (
        1, {"error_count": 1})
    assert not effects.copy_times


@pytest.mark.parametrize("state,complete,partial", [
    ("terminal_failed", False, False), ("succeeded", False, True), ("pending", False, False),
    ("terminal_failed", True, False), ("pending", True, False),
])
def test_transcription_unavailable_degrades_and_retains_runs(
    state: str, complete: bool, partial: bool,
) -> None:
    effects = UpgradedEffects()
    effects.transcription_state, effects.complete, effects.partial = state, complete, partial
    code, doc = replay.execute(replace(settings(2, 1), transcription=True), effects)
    assert code == 0 and len(doc["runs"]) == 2
    assert doc["transcription_unavailable_count"] == 2
    assert doc["transcription_partial_count"] == (2 if partial else 0)
    assert all(b["transcription"] is None for b in doc["evidence_timeline"]["blocks"])
    assert doc["stage_summary"]["transcription"] == {"median": None, "p95": None}


def test_transcription_worker_timeout_degrades() -> None:
    class Timeout(UpgradedEffects):
        def worker(self, kind: str, timeout: float) -> Any:
            if kind == "transcription":
                raise replay.subprocess.TimeoutExpired("private", timeout)
            return super().worker(kind, timeout)
    code, doc = replay.execute(replace(settings(1), transcription=True), Timeout())
    assert code == 0 and doc["transcription_unavailable_count"] == 1


def test_transcription_enqueue_timeout_degrades_without_worker() -> None:
    class NeverEnqueued(UpgradedEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            value = super().request(method, path, body, timeout)
            if path == "/api/v1/kernel/status":
                value["automation"]["transcription_operations_enqueued"] = 7
            return value
    effects = NeverEnqueued()
    code, doc = replay.execute(replace(settings(1), transcription=True), effects)
    assert code == 0 and doc["transcription_unavailable_count"] == 1
    assert "transcription" not in effects.workers


def test_transcription_protocol_failure_retains_observations() -> None:
    class Broken(UpgradedEffects):
        def worker(self, kind: str, timeout: float) -> Any:
            if kind == "transcription" and self.copied == 2:
                raise replay.PipelineFailure("private")
            return super().worker(kind, timeout)
    code, doc = replay.execute(replace(settings(2, 1), transcription=True), Broken())
    assert code == 3 and len(doc["runs"]) == 1 and "private" not in json.dumps(doc)


def test_worker_startup_line_outcome_only_and_cap() -> None:
    startup = b'{"state":"available","worker_id":"private"}\n'
    assert replay.worker_outcome(startup) is None
    for outcome in ("succeeded", "retry_scheduled", "terminal_failed"):
        assert replay.worker_outcome(startup + json.dumps(
            {"outcome": outcome, "text": "private"}).encode()) == outcome
    for raw in (b"x" * 16385, startup + b'{"outcome":"private"}', b'{}',
                startup + b'{}\n{}'):
        with pytest.raises(replay.PipelineFailure):
            replay.worker_outcome(raw)


def test_time_of_use_accuracy_cutoffs_first_nulls_and_final_unchanged() -> None:
    progress = replay.Progress(upgraded=True, origin=BASE, observations=[
        observation(90, span(1, 99)), observation(400, span(2, 98)),
        observation(401, span(3, 97)), observation(1000, span(4, 96)),
        observation(1001, span(5, 95)),
    ])
    truth = (span(0, 100), span(200, 300))
    doc = replay.report(progress, truth, 0)
    talk = doc["talks"][0]
    for prefix, error in (("first", 1), ("plus_300", 2), ("plus_900", 4)):
        assert talk[prefix + "_start_error_seconds"] == error
        assert talk[prefix + "_end_error_seconds"] == error
        assert doc["talks"][1][prefix + "_start_error_seconds"] is None
    progress.upgraded = False
    assert replay.report(progress, truth, 0)["final_accuracy"] == doc["final_accuracy"]


def test_stage_summary_nearest_rank_p95_and_timeline() -> None:
    progress = replay.Progress(upgraded=True, transcription=True,
        blocks=[replay.BlockObservation(i, i * 10, i * 10 + i, i * 10 + 2 * i,
                                        i * 10 + 3 * i, None, i * 10 + 4 * i)
                for i in range(1, 21)], observations=[observation(130), observation(260)])
    doc = replay.report(progress, (), 0)
    assert doc["stage_summary"]["registered"] == {"median": 10.5, "p95": 19}
    assert doc["stage_summary"]["segmentation"] == {"median": 31.5, "p95": 57}
    assert doc["stage_timings"][0] == {"ordinal": 1, "registered": 1, "timing": 2,
                                      "segmentation": 3, "transcription": None, "suggestion": 4}
    assert doc["evidence_timeline"]["runs"] == [
        {"ordinal": 1, "media_seconds": 130, "segmentation": 10, "transcription": 0},
        {"ordinal": 2, "media_seconds": 260, "segmentation": 20, "transcription": 0},
    ]


def test_growing_chunks_deadline_exclusive_flush_fsync(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    effects = FakeEffects()
    writes: list[tuple[float, bytes]] = []
    events: list[Any] = []
    class Buffer(io.BytesIO):
        def write(self, data: Any) -> int:
            writes.append((effects.now(), bytes(data)))
            return super().write(data)
        def flush(self) -> None:
            events.append("flush")
        def fileno(self) -> int:
            return 42
    def opened(path: Path, mode: str) -> io.BytesIO:
        events.append((path, mode))
        return Buffer() if mode == "xb" else io.BytesIO(b"abcdefgh")
    monkeypatch.setattr(Path, "open", opened)
    def stat(path: Path) -> SimpleNamespace:
        return SimpleNamespace(st_size=8)
    def sync(fd: int) -> None:
        events.append(fd)
    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(replay.os, "fsync", sync)
    replay.growing_copy(Path("input.mp4"), Path("output"), 1, 0, 4, effects.now, effects.sleep)
    assert writes == [(1, b"ab"), (2, b"cd"), (3, b"ef"), (4, b"gh")]
    assert events[0] == (Path("output/block-000001.mp4"), "xb")
    assert events[-2:] == ["flush", 42]
    def exists(path: Path, mode: str) -> Any:
        raise FileExistsError("private")
    monkeypatch.setattr(Path, "open", exists)
    with pytest.raises(FileExistsError):
        replay.growing_copy(Path("input.mp4"), Path("output"), 1, 0, 4, effects.now, effects.sleep)


class GrowingEffects(FakeEffects):
    def __init__(self, count: int = 2, failure: bool = False) -> None:
        super().__init__()
        self.count, self.failure = count, failure
        self.stopped = False
        self.work_seconds = 6

    def writer(self, settings: Any, started: float) -> Any:
        return self

    def closed(self, ordinal: int) -> float | None:
        if self.failure and self.clock >= 10:
            raise replay.PipelineFailure("private writer")
        return ordinal * 5 if self.clock >= ordinal * 5 else None

    def stop(self) -> None:
        self.stopped = True

    def copy(self, block: Path, source: Path, ordinal: int) -> None:
        pytest.fail("growing arrival must use the writer")

    def request(self, method: str, path: str, body: dict[str, Any] | None,
                timeout: float) -> dict[str, Any]:
        self.copied = min(self.count, int(self.clock // 5))
        if "/media-timing/assets/" in path:
            ordinal = UUID(path.split("/")[-2]).int - 100
            return {"evidence": {"candidate_interval": {
                "started_at": (BASE + timedelta(seconds=(ordinal - 1) * 10)).isoformat(),
                "ended_at": (BASE + timedelta(seconds=ordinal * 10)).isoformat(),
            }}}
        if "/media-timing/events/" in path or "/media-segmentation/events/" in path:
            kind = "media_timing" if "/media-timing/" in path else "media_segmentation"
            return {"items": [{"asset_id": str(UUID(int=100 + i)),
                               "state": "succeeded" if i <= self.done[kind] else "pending"}
                              for i in range(1, self.copied + 1)], "next_after": None}
        result = super().request(method, path, body, timeout)
        if path == "/api/v1/kernel/status":
            # Scan timestamp ties and a capped projection must not determine order.
            result["recent_media"] = []
        return result


def test_growing_writer_seam_overlap_timeline_and_failure() -> None:
    for failure in (False, True):
        effects = GrowingEffects(failure=failure)
        code, doc = replay.execute(replace(settings(2, 1), arrival="growing"), effects)
        assert code == (3 if failure else 0)
        assert effects.stopped
        assert "private" not in json.dumps(doc)
        if not failure:
            assert doc["evidence_timeline"]["runs"][0]["segmentation"] == 2
            assert doc["evidence_timeline"]["blocks"][1]["segmentation"] <= doc["runs"][0][
                "media_seconds"]
            # Both registered assets were included in the first suggestion run.
            assert [b["suggestion"] + i * 10 for i, b in enumerate(doc["stage_timings"], 1)] == [
                doc["runs"][0]["media_seconds"]] * 2
            assert doc["stage_timings"][1]["timing"] < doc["stage_timings"][1]["suggestion"]


@pytest.mark.parametrize("phase", ["enqueue", "status", "http"])
def test_transcription_timeout_during_poll_degrades(phase: str) -> None:
    class SlowPoll(UpgradedEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            value = super().request(method, path, body, timeout)
            if (self.copied and self.done["media_segmentation"] == self.copied
                    and ((phase == "enqueue" and path == "/api/v1/kernel/status")
                         or (phase != "enqueue" and "/transcription/assets/" in path))):
                self.clock = float(self.clock) + timeout
                if phase == "http":
                    raise TimeoutError("private timeout")
            return value
    code, doc = replay.execute(replace(settings(1), transcription=True), SlowPoll())
    assert code == 0 and doc["transcription_unavailable_count"] == 1



def test_growing_transcription_sampling_timeout_is_degradable() -> None:
    class Transcribing(GrowingEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            if path.endswith("/boundary-cues"):
                return {"current": None}
            if path.endswith("/boundary-cue-catalog"):
                return {"version": 1, "profiles": [
                    {"key": "conference", "name": "Conference stage",
                     "group_keys": ["group-a"]}]}
            if "/transcription/assets/" in path:
                if UUID(path.split("/")[-2]).int == 102:
                    raise TimeoutError("private")
                return {"complete_evidence": True, "partial_evidence": False,
                        "operation": {"state": "succeeded"}}
            result = super().request(method, path, body, timeout)
            if path == "/api/v1/kernel/status":
                result["automation"]["transcription_operations_enqueued"] = self.copied
            return result
    code, doc = replay.execute(replace(settings(2, 1), arrival="growing", transcription=True),
                               Transcribing())
    assert code == 0 and doc["transcription_unavailable_count"] == 1
    assert doc["runs"][0]["blocks_copied"] == 2
    assert doc["evidence_timeline"]["runs"][0]["transcription"] == 1


def test_http_wrapped_timeout_is_normalized() -> None:
    from urllib.error import URLError
    class Opener:
        def open(self, request: Any, timeout: float) -> Any:
            raise URLError(TimeoutError("private"))
    effects = replay.LocalEffects("http://localhost:8000", {
        "STAGEFLOW_API_SHARED_SECRET": "private-secret"})
    effects.opener = Opener()
    with pytest.raises(TimeoutError):
        effects.request("GET", "/test", None, 2)


@pytest.mark.parametrize("overflow,timeout", [(False, False), (True, False), (False, True)])
def test_transcription_subprocess_bounded_pipe_and_timeout(
    monkeypatch: pytest.MonkeyPatch, overflow: bool, timeout: bool,
) -> None:
    commands: list[Any] = []
    class Child:
        def __init__(self, command: list[str], **kwargs: Any) -> None:
            commands.append((command, kwargs))
            self.stdout = io.BytesIO(b"x" * 16385 if overflow else
                b'{"state":"available","worker_id":"private"}\n'
                b'{"outcome":"succeeded","text":"private"}\n')
            self.returncode = 0
            self.killed = False
        def __enter__(self) -> Any:
            return self
        def __exit__(self, *args: Any) -> None:
            self.stdout.close()
        def wait(self, timeout: float | None = None) -> int:
            if timeout is not None and timeout_case:
                raise replay.subprocess.TimeoutExpired("private", timeout)
            return self.returncode
        def kill(self) -> None:
            self.killed = True
            self.returncode = -1
    timeout_case = timeout
    monkeypatch.setattr(replay.subprocess, "Popen", Child)
    effects = replay.LocalEffects("http://localhost:8000", {
        "STAGEFLOW_API_SHARED_SECRET": "private-secret"})
    if overflow or timeout:
        with pytest.raises((replay.PipelineFailure, replay.subprocess.TimeoutExpired)):
            effects.worker("transcription", 2)
    else:
        assert effects.worker("transcription", 2) == "succeeded"
    assert commands[0][0] == [sys.executable, "-m", "app.demo.worker", "--once"]
    assert commands[0][1]["stderr"] == replay.subprocess.DEVNULL


def test_growing_backlog_beyond_recent_media_cap_and_tied_scans() -> None:
    class Backlog(GrowingEffects):
        def worker(self, kind: str, timeout: float) -> None:
            self.workers.append(kind)
            self.clock += 600
            self.done[kind] = self.copied
    effects = Backlog(count=102)
    code, doc = replay.execute(
        replace(settings(102, 102), arrival="growing", timeout=3000), effects)
    assert code == 0 and doc["blocks_registered"] == 102
    assert doc["evidence_timeline"]["runs"][0]["segmentation"] == 102



def test_transcription_counter_reset_is_a_pipeline_failure() -> None:
    class Reset(UpgradedEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            value = super().request(method, path, body, timeout)
            if path == "/api/v1/kernel/status" and self.copied == 2:
                value["automation"]["transcription_operations_enqueued"] = 0
            return value
    code, doc = replay.execute(replace(settings(2, 1), transcription=True), Reset())
    assert code == 3 and len(doc["runs"]) == 1
    assert doc["transcription_enqueue_baseline"] == 7


def test_background_writer_retains_schedule_and_propagates_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, float, float]] = []
    class Thread:
        def __init__(self, target: Any, args: Any, daemon: bool) -> None:
            self.target, self.args = target, args
        def start(self) -> None:
            self.target(*self.args)
        def join(self) -> None:
            pass
    def copy(block: Path, source: Path, ordinal: int, start: float, end: float,
             now: Any, sleep: Any) -> None:
        calls.append((ordinal, start, end))
        if fail and ordinal == 2:
            raise OSError("private")
    monkeypatch.setattr(replay.threading, "Thread", Thread)
    monkeypatch.setattr(replay, "growing_copy", copy)
    for fail in (False, True):
        calls.clear()
        writer = replay.GrowingWriter(settings(2), 100)
        assert calls == [(1, 100, 105), (2, 105, 110)]
        if fail:
            with pytest.raises(replay.PipelineFailure):
                writer.closed(2)
        else:
            assert writer.closed(1) is not None and writer.closed(2) is not None
        writer.stop()



def test_run_availability_snapshot_survives_later_block_timeout() -> None:
    progress = replay.Progress(upgraded=True, transcription=True,
        blocks=[replay.BlockObservation(1, 10, 12, 14, 16, None, 20)],
        observations=[replay.Observation(1, 10, 20, (), (0,) * len(replay.SKIPS), 1, 1)])
    # A subsequent phase timeout clears this block's final availability but cannot
    # change what was observed available at an earlier suggestion run.
    doc = replay.report(progress, (), 0)
    assert doc["evidence_timeline"]["blocks"][0]["transcription"] is None
    assert doc["evidence_timeline"]["runs"][0]["transcription"] == 1


def test_transcription_refuses_conference_profile_without_groups() -> None:
    class NoGroups(UpgradedEffects):
        def request(self, method: str, path: str, body: dict[str, Any] | None,
                    timeout: float) -> dict[str, Any]:
            if path.endswith("/boundary-cue-catalog"):
                return {"version": 9, "profiles": [
                    {"name": "Conference stage", "key": "conference-9", "group_keys": []}]}
            return super().request(method, path, body, timeout)
    effects = NoGroups()
    assert replay.execute(replace(settings(), transcription=True), effects) == (
        1, {"error_count": 1})
    assert not [1 for method, path, _ in effects.requests
                if method == "POST" and path.endswith("/boundary-cues")]
