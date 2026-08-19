from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from qualification import transcription_benchmark as benchmark
from qualification.transcription_benchmark import (
    CorpusItem,
    EngineIdentity,
    EngineSegment,
    EngineTranscript,
    EngineWord,
    EvaluationError,
    QualificationExecutionPort,
)
from test_transcription_worker_substrate import (
    FakeRepository,
    claimed_operation,
    operation_input,
)

from app.contexts.transcription_evidence import (
    TranscriptionExecutionRequest,
)
from app.contexts.work_execution import (
    ClaimRequest,
    EventNetworkPolicy,
    TranscriptionWorker,
    WorkerCycleOutcome,
)

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


def _media(tmp_path: Path, *, content: bytes = b"RIFF-fixture") -> CorpusItem:
    path = tmp_path / "private-corpus" / "sample.wav"
    path.parent.mkdir()
    path.write_bytes(content)
    return CorpusItem(
        alias="web3-clean",
        media_path=path,
        media_sha256=sha256(content).hexdigest(),
        duration_seconds=4.0,
        language="en",
        reference_text="StageFlow records durable transcript evidence",
        condition="synthetic-clean",
    )


class DeterministicEngine:
    def __init__(self) -> None:
        self._identity = EngineIdentity(
            provider_id="deterministic-evaluation",
            provider_version="v1",
            model_id="fixture-model",
            model_version="fixture-v1",
            execution_tool_id="fixture-adapter",
            execution_tool_version="v1",
            execution_revision="fixture-revision-v1",
            device="cpu",
            compute_type="deterministic",
            capabilities=(
                "asset-relative-segment-timing",
                "asset-relative-word-timing",
            ),
            limitations=("synthetic-evidence",),
        )
        self.calls = 0

    @property
    def identity(self) -> EngineIdentity:
        return self._identity

    @property
    def initialization_seconds(self) -> float:
        return 0.0

    def transcribe(
        self,
        item: CorpusItem,
        renew_lease: Callable[[], None],
    ) -> EngineTranscript:
        self.calls += 1
        renew_lease()
        return EngineTranscript(
            language="en",
            segments=(
                EngineSegment(
                    text="StageFlow records durable transcript evidence",
                    start_seconds=0.25,
                    end_seconds=3.5,
                    words=(
                        EngineWord(
                            text="StageFlow",
                            start_seconds=0.25,
                            end_seconds=0.75,
                            confidence=0.9,
                            confidence_semantics="provider-probability",
                        ),
                    ),
                    limitations=("synthetic-timing",),
                ),
            ),
            produced_at=NOW,
            limitations=("synthetic-evidence",),
        )


def test_error_metrics_are_normalized_and_behavior_based() -> None:
    assert benchmark.normalize_text("  StageFlow’s, WORKER! ") == "stageflow's worker"
    assert benchmark.word_error_rate("one two three", "one too three") == 1 / 3
    assert benchmark.character_error_rate("ABC", "adc") == 1 / 3
    with pytest.raises(EvaluationError, match="WER reference"):
        benchmark.word_error_rate("...", "content")


def test_normalization_preserves_asset_relative_timing_and_is_deterministic(
    tmp_path: Path,
) -> None:
    item = _media(tmp_path)
    engine = DeterministicEngine()
    transcript = engine.transcribe(item, lambda: None)

    first = benchmark.normalize_transcript(engine.identity, item, transcript)
    second = benchmark.normalize_transcript(engine.identity, item, transcript)

    assert first.segments[0].id == second.segments[0].id
    assert first.segments[0].asset_start_microseconds == 250_000
    assert first.segments[0].asset_end_microseconds == 3_500_000
    assert first.segments[0].words[0].asset_start_microseconds == 250_000
    assert first.segments[0].words[0].confidence_semantics == "provider-probability"
    assert first.provenance.produced_at == NOW


def test_manifest_validates_digest_and_report_excludes_paths_and_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _media(tmp_path)
    manifest = tmp_path / "corpus.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_name": benchmark.CORPUS_SCHEMA,
                "schema_version": benchmark.SCHEMA_VERSION,
                "items": [
                    {
                        "alias": item.alias,
                        "media_path": str(item.media_path),
                        "media_sha256": item.media_sha256,
                        "duration_seconds": item.duration_seconds,
                        "language": item.language,
                        "reference_text": item.reference_text,
                        "condition": item.condition,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = benchmark.load_corpus_manifest(manifest)
    monkeypatch.setattr(benchmark, "_nvidia_used_memory_mib", lambda: 123)

    report = benchmark.run_benchmark(DeterministicEngine(), loaded, repetitions=2)
    serialized = json.dumps(report, sort_keys=True)

    assert len(report["trials"]) == 2
    assert report["trials"][0]["word_error_rate"] == 0
    assert report["trials"][0]["word_timing_count"] == 1
    assert report["trials"][0]["thermal_state"] == "first_inference_model_loaded"
    assert report["trials"][1]["thermal_state"] == "warm_inference_model_loaded"
    subprocess_engine = DeterministicEngine()
    object.__setattr__(
        subprocess_engine,
        "_identity",
        EngineIdentity(
            provider_id="deterministic-subprocess",
            provider_version="v1",
            model_id="fixture-model",
            model_version="fixture-v1",
            execution_tool_id="fixture-adapter",
            execution_tool_version="v1",
            execution_revision="fixture-subprocess-v1",
            device="cpu",
            compute_type="deterministic",
            capabilities=("subprocess-isolation",),
        ),
    )
    subprocess_report = benchmark.run_benchmark(
        subprocess_engine,
        loaded,
        repetitions=2,
    )
    assert {trial["thermal_state"] for trial in subprocess_report["trials"]} == {
        "cold_subprocess_model_load_included"
    }
    assert str(item.media_path) not in serialized
    assert item.reference_text is not None
    assert item.reference_text not in serialized
    assert "StageFlow records durable transcript evidence" not in serialized
    assert report["authority_use_prohibited"] is True


def test_manifest_rejects_changed_media_and_sensitive_identifiers(tmp_path: Path) -> None:
    item = _media(tmp_path)
    item.media_path.write_bytes(b"changed")
    manifest = tmp_path / "corpus.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_name": benchmark.CORPUS_SCHEMA,
                "schema_version": benchmark.SCHEMA_VERSION,
                "items": [
                    {
                        "alias": item.alias,
                        "media_path": str(item.media_path),
                        "media_sha256": item.media_sha256,
                        "duration_seconds": item.duration_seconds,
                        "condition": item.condition,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationError, match="digest mismatch"):
        benchmark.load_corpus_manifest(manifest)
    with pytest.raises(EvaluationError, match="sanitized"):
        EngineIdentity(
            provider_id="token=private",
            provider_version="v1",
            model_id="fixture",
            model_version="v1",
            execution_tool_id="fixture",
            execution_tool_version="v1",
            execution_revision="v1",
            device="cpu",
            compute_type="float32",
        )


def test_report_publication_is_new_file_only(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    benchmark.write_report(output, {"schema_name": "safe"})
    assert output.is_file()

    with pytest.raises(EvaluationError, match="already exists"):
        benchmark.write_report(output, {"schema_name": "replacement"})


def test_qualification_port_runs_through_real_fenced_worker_cycle(
    tmp_path: Path,
) -> None:
    item = _media(tmp_path)
    engine = DeterministicEngine()
    claim = claimed_operation(operation_input())
    repository = FakeRepository(claim)
    requests: list[TranscriptionExecutionRequest] = []

    def locate(request: TranscriptionExecutionRequest) -> CorpusItem:
        requests.append(request)
        assert request.input.asset_id == claim.operation.input.asset_id
        return item

    worker = TranscriptionWorker(
        repository=repository,
        execution_port=QualificationExecutionPort(
            engine=engine,
            locate_media=locate,
        ),
    )
    result = worker.run_once(
        ClaimRequest(
            worker_id=claim.attempt.worker_id,
            network_policy=EventNetworkPolicy.LOCAL_ONLY,
            lease_duration=timedelta(seconds=30),
        )
    )

    assert result.outcome is WorkerCycleOutcome.SUCCEEDED
    assert repository.applied is not None
    assert repository.applied.result.provenance.provider_id == "deterministic-evaluation"
    assert repository.applied.result.segments[0].asset_start_microseconds == 250_000
    assert repository.renewal_count == 3
    assert requests[0].fence_generation == claim.attempt.fence_generation