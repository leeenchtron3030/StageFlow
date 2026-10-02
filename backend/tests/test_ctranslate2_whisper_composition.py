import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from app.contexts.transcription_evidence import TranscriptionExecutionError
from app.core.config.deployment import RuntimeProfile
from app.demo import cli, worker
from app.shared.ids import EntityId
from tests.test_ctranslate2_whisper_adapter import configuration


def test_worker_selects_provider_and_registers_exact_profile(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    provider = "stageflow-ctranslate2-whisper"
    config = configuration(Path.cwd(), provider=provider, device="cuda", compute_type="float16",
                           execution_profile_id=f"synthetic-{provider}")
    deployment = SimpleNamespace(local_transcription=config, deployment_id="synthetic-deployment",
        node_id="synthetic-node", event=SimpleNamespace(stages=[SimpleNamespace(sources=[
            SimpleNamespace(allowed_extensions=(".wav",))])]))
    components = SimpleNamespace(configuration=SimpleNamespace(deployment=deployment,
        postgres_dsn="unused", sources={}), repository=Mock(), event_key="synthetic")
    components.repository.get_event_by_key.return_value = SimpleNamespace(id=EntityId.new())
    monkeypatch.setattr(worker, "load_kernel_components_from_environment", lambda: components)
    repository = Mock()
    def unchanged(item: Any) -> Any:
        return item
    repository.register_worker.side_effect = unchanged
    repository.register_capability.side_effect = unchanged
    monkeypatch.setattr(worker, "PostgresWorkExecutionRepository", Mock(return_value=repository))
    selected: list[str] = []

    def factory(name: str) -> Any:
        def build(*args: Any, **kwargs: Any) -> Any:
            selected.append(name)
            return SimpleNamespace(provider_id=name, provider_version="1.0",
                                   decode_tool_version="8.1", decode_tool_sha256="a" * 64,
                                   probe_tool_version="8.1", probe_tool_sha256="b" * 64,
                                   execution_tool_id="ctranslate2", runtime_version="4.8.1")
        return build

    monkeypatch.setattr(worker, "CTranslate2WhisperExecutionAdapter",
                        factory("stageflow-ctranslate2-whisper"))
    service = Mock()
    service.run_once.return_value = SimpleNamespace(operation_id=None)
    monkeypatch.setattr(worker, "TranscriptionWorker", Mock(return_value=service))
    assert worker.main(["--once"]) == 0
    assert selected == [provider]
    capability = repository.register_capability.call_args.args[0]
    assert capability.provider_id == provider
    assert capability.execution_profile_id == config.execution_profile_id
    assert capability.execution_profile_version == config.execution_profile_version
    payload = json.loads(capsys.readouterr().out)
    assert payload["execution_profile"] == config.execution_profile_id
    assert payload["device"] == config.device
    assert payload["compute_type"] == config.compute_type
    assert payload["decode_tool"] == "ffmpeg"
    assert payload["decode_tool_version"] == "8.1"
    assert payload["decode_tool_sha256"] == "a" * 64
    assert payload["probe_tool"] == "ffprobe"
    assert payload["probe_tool_version"] == "8.1"
    assert payload["probe_tool_sha256"] == "b" * 64


def test_preflight_selects_stageflow_adapter(monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    config = configuration(Path.cwd())
    deployment = SimpleNamespace(local_transcription=config,
        runtime_profile=RuntimeProfile.DEMO_SINGLE_STAGE, deployment_id="synthetic",
        event=SimpleNamespace(stages=[SimpleNamespace(sources=[SimpleNamespace(path=str(Path.cwd()))])]))
    components = SimpleNamespace(configuration=SimpleNamespace(deployment=deployment),
                                  program_source=SimpleNamespace(probe=lambda: 1))
    monkeypatch.setattr(cli, "_components", lambda: components)
    monkeypatch.setattr(cli.subprocess, "run", Mock(return_value=SimpleNamespace(
        returncode=0, stdout="synthetic GPU")))
    execution = Mock(provider_id=config.provider, provider_version="1.0")
    execution.execute.side_effect = TranscriptionExecutionError(
        "provider_no_speech_segments", retryable=False, diagnostic_summary="synthetic silence")
    factory = Mock(return_value=execution)
    monkeypatch.setattr(cli, "CTranslate2WhisperExecutionAdapter", factory)
    monkeypatch.setattr(cli, "verify_transcription_prerequisites", Mock())

    class Scratch:
        def __enter__(self) -> str:
            return str(Path.cwd())

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr(cli.tempfile, "TemporaryDirectory", Mock(return_value=Scratch()))
    monkeypatch.setattr(cli, "write_silent_transcription_probe", Mock())
    assert cli.main(["preflight"]) == 0
    factory.assert_called_once()
    request = execution.execute.call_args.args[0]
    assert request.input.execution_profile_id == config.execution_profile_id
    assert json.loads(capsys.readouterr().out)["transcription_provider"] == config.provider
