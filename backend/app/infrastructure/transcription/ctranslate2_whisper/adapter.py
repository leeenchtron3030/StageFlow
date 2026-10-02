"""StageFlow-owned adapter; identical provider-neutral normalized result boundary."""
from __future__ import annotations

import importlib.metadata
import math
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from app.contexts.transcription_evidence import (
    NormalizedTranscriptResult,
    TranscriptEvidenceStatus,
    TranscriptExecutionProvenance,
    TranscriptSegment,
    TranscriptWord,
)
from app.contexts.transcription_evidence.application import (
    TranscriptionExecutionError,
    TranscriptionExecutionRequest,
)
from app.contexts.work_execution.repository import WorkExecutionLeaseLostError
from app.core.config.deployment import LocalTranscriptionConfiguration
from app.infrastructure.transcription.media_path import (
    MediaPathResolver,
)
from app.shared.ids import EntityId
from app.shared.time import Clock

if TYPE_CHECKING:
    from .types import Segment


def _installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        raise TranscriptionExecutionError(
            "provider_runtime_unavailable", retryable=False,
            diagnostic_summary="local transcription runtime unavailable") from None


def _deterministic_id(work_key: str, kind: str, ordinal: int) -> EntityId:
    return EntityId(str(uuid5(NAMESPACE_URL, f"stageflow:{work_key}:{kind}:{ordinal}")))


def _microseconds(value: float, field: str) -> int:
    if not math.isfinite(value) or value < 0:
        raise TranscriptionExecutionError(
            "provider_timing_invalid", retryable=False,
            diagnostic_summary=f"provider {field} timing is invalid")
    return round(value * 1_000_000)


class Engine(Protocol):
    def transcribe(self, audio: Any, *, language: str | None, word_timestamps: bool,
                   renew_lease: Callable[[], None]) -> Iterable[Segment]: ...


class Decoder(Protocol):
    @property
    def identity(self) -> tuple[str, str, str, str]: ...

    def decode(self, path: Path, heartbeat: Callable[[], None]) -> Any: ...


def _provider_failure(exc: Exception) -> TranscriptionExecutionError:
    cuda = any(name in str(exc).casefold() for name in ("cuda", "cublas", "cudnn"))
    return TranscriptionExecutionError(
        "cuda_runtime_unavailable" if cuda else "provider_execution_failed",
        retryable=not cuda, diagnostic_summary="local transcription execution failed")


class CTranslate2WhisperExecutionAdapter:
    provider_id = "stageflow-ctranslate2-whisper"
    provider_version = "1.0"
    required_runtime_version = "4.8.1"
    execution_tool_id = "ctranslate2"
    execution_revision = "stageflow-ctranslate2-whisper-adapter-1.0"

    def __init__(self, configuration: LocalTranscriptionConfiguration, *,
                 resolver: MediaPathResolver, clock: Clock,
                 model_factory: Callable[..., Engine] | None = None,
                 decoder_factory: Callable[[Path], Decoder] | None = None,
                 version_lookup: Callable[[str], str] = _installed_version) -> None:
        if configuration.provider != self.provider_id or (
                configuration.device, configuration.compute_type) not in {
                    ("cuda", "float16"), ("cpu", "int8")}:
            raise ValueError("local transcription requires CUDA float16 or CPU int8")
        model_path = Path(configuration.model_path)
        if not model_path.is_dir() or not (model_path / "tokenizer.json").is_file():
            raise TranscriptionExecutionError(
                "provider_model_unavailable", retryable=False,
                diagnostic_summary="configured local model or tokenizer is unavailable")
        if configuration.ffmpeg_path is None:
            raise ValueError("local transcription requires an explicit FFmpeg path")
        self.runtime_version = version_lookup("ctranslate2")
        if self.runtime_version != self.required_runtime_version:
            raise TranscriptionExecutionError(
                "runtime_version_mismatch", retryable=False,
                diagnostic_summary="CTranslate2 version does not match qualification")
        try:
            if decoder_factory is None:
                from .decode import FFmpegDecoder
                decoder_factory = FFmpegDecoder
            self._decoder = decoder_factory(Path(configuration.ffmpeg_path))
            if model_factory is None:
                from .engine import load_engine
                model_factory = load_engine
            self._model = model_factory(str(model_path), device=configuration.device,
                                        compute_type=configuration.compute_type)
        except (TranscriptionExecutionError, WorkExecutionLeaseLostError):
            raise
        except ImportError as exc:
            raise TranscriptionExecutionError(
                "provider_runtime_unavailable", retryable=False,
                diagnostic_summary="local transcription runtime unavailable") from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise _provider_failure(exc) from exc
        (self.decode_tool_version, self.decode_tool_sha256,
         self.probe_tool_version, self.probe_tool_sha256) = self._decoder.identity
        self._configuration, self._resolver, self._clock = configuration, resolver, clock

    def _provenance(self) -> TranscriptExecutionProvenance:
        return TranscriptExecutionProvenance(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            model_id=self._configuration.model_id,
            model_version=self._configuration.model_version,
            execution_tool_id=self.execution_tool_id,
            execution_tool_version=self.runtime_version,
            execution_revision=self.execution_revision,
            produced_at=self._clock.now(),
        )

    def execute(
        self,
        request: TranscriptionExecutionRequest,
        renew_lease: Callable[[], None],
    ) -> NormalizedTranscriptResult:
        media_path = self._resolver.resolve(request.input)
        renew_lease()
        audio = self._decoder.decode(media_path, renew_lease)
        try:
            raw_segments = self._model.transcribe(
                audio,
                language=request.input.requested_language,
                word_timestamps=request.input.request_word_timing,
                renew_lease=renew_lease,
            )
        except (TranscriptionExecutionError, WorkExecutionLeaseLostError):
            raise
        except (IndexError, OSError, RuntimeError, ValueError) as exc:
            raise _provider_failure(exc) from exc

        segments: list[TranscriptSegment] = []
        try:
            for segment_ordinal, raw_segment in enumerate(raw_segments):
                renew_lease()
                text = str(raw_segment.text).strip()
                if not text:
                    continue
                words: list[TranscriptWord] = []
                for word_ordinal, raw_word in enumerate(raw_segment.words or ()):
                    word_text = str(raw_word.word).strip()
                    if not word_text:
                        continue
                    confidence = float(raw_word.probability)
                    confidence_valid = math.isfinite(confidence) and 0 <= confidence <= 1
                    words.append(
                        TranscriptWord(
                            id=_deterministic_id(
                                request.work_key,
                                f"segment-{segment_ordinal}-word",
                                word_ordinal,
                            ),
                            ordinal=word_ordinal,
                            text=word_text,
                            asset_start_microseconds=_microseconds(
                                float(raw_word.start), "word_start"
                            ),
                            asset_end_microseconds=_microseconds(
                                float(raw_word.end), "word_end"
                            ),
                            confidence=confidence if confidence_valid else None,
                            confidence_semantics=(
                                "provider_probability" if confidence_valid else None
                            ),
                            limitations=(
                                ()
                                if confidence_valid
                                else ("provider word probability was invalid and omitted",)
                            ),
                        )
                    )
                raw_start = _microseconds(float(raw_segment.start), "segment_start")
                raw_end = _microseconds(float(raw_segment.end), "segment_end")
                segment_start = min(
                    (raw_start, *(word.asset_start_microseconds for word in words))
                )
                segment_end = max(
                    (raw_end, *(word.asset_end_microseconds for word in words))
                )
                limitations = ["segment confidence is not normalized"]
                if segment_start != raw_start or segment_end != raw_end:
                    limitations.append("segment boundary expanded to provider word timing")
                segments.append(
                    TranscriptSegment(
                        id=_deterministic_id(
                            request.work_key, "segment", segment_ordinal
                        ),
                        ordinal=segment_ordinal,
                        text=text,
                        asset_start_microseconds=segment_start,
                        asset_end_microseconds=segment_end,
                        words=tuple(words),
                        limitations=tuple(limitations),
                    )
                )
        except (TranscriptionExecutionError, WorkExecutionLeaseLostError):
            raise
        except IndexError as exc:
            raise _provider_failure(exc) from exc
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            if not segments:
                raise _provider_failure(exc) from exc
            return NormalizedTranscriptResult(
                status=TranscriptEvidenceStatus.PARTIAL,
                provenance=self._provenance(),
                language="en",
                segments=tuple(segments),
                limitations=(
                    "speaker labels unavailable",
                    "provider language probability not persisted",
                ),
                partial_reason="provider_iteration_failed",
            )

        if not segments:
            raise TranscriptionExecutionError(
                "provider_no_speech_segments",
                retryable=False,
                diagnostic_summary="local transcription engine returned no speech segments",
            )
        return NormalizedTranscriptResult(
            status=TranscriptEvidenceStatus.COMPLETE,
            provenance=self._provenance(),
            language="en",
            segments=tuple(segments),
            limitations=(
                "speaker labels unavailable",
                "provider language probability not persisted",
            ),
        )
