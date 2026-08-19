from __future__ import annotations

import importlib
import importlib.metadata
import math
import stat
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Protocol, cast
from uuid import NAMESPACE_URL, uuid5

from app.contexts.production.event_mode_kernel.contracts import MediaRegistrationState
from app.contexts.production.event_mode_kernel.repository import EventModeKernelRepository
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
from app.contexts.work_execution.contracts import TranscriptionOperationInput
from app.core.config.deployment import LocalTranscriptionConfiguration
from app.shared.ids import EntityId
from app.shared.time import Clock


class FasterWhisperWord(Protocol):
    word: str
    start: float
    end: float
    probability: float


class FasterWhisperSegment(Protocol):
    text: str
    start: float
    end: float
    words: Iterable[FasterWhisperWord] | None


class FasterWhisperInfo(Protocol):
    language: str


class FasterWhisperModel(Protocol):
    def transcribe(
        self,
        audio: str,
        *,
        language: str | None,
        beam_size: int,
        word_timestamps: bool,
        vad_filter: bool,
        condition_on_previous_text: bool,
    ) -> tuple[Iterable[FasterWhisperSegment], FasterWhisperInfo]: ...


class FasterWhisperModelFactory(Protocol):
    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
    ) -> FasterWhisperModel: ...


class MediaPathResolver(Protocol):
    def resolve(self, input: TranscriptionOperationInput) -> Path: ...


class KernelMediaPathResolver:
    def __init__(
        self,
        repository: EventModeKernelRepository,
        *,
        source_roots: Mapping[str, str],
    ) -> None:
        self._repository = repository
        self._source_roots = dict(source_roots)

    def resolve(self, input: TranscriptionOperationInput) -> Path:
        asset = self._repository.get_asset(input.asset_id)
        if asset is None:
            raise TranscriptionExecutionError(
                "media_asset_not_found",
                retryable=False,
                diagnostic_summary="registered media asset is unavailable",
            )
        if asset.manifest_id != input.manifest_id:
            raise TranscriptionExecutionError(
                "media_manifest_conflict",
                retryable=False,
                diagnostic_summary="operation manifest does not match registered media",
            )
        candidate = self._repository.get_candidate(asset.candidate_id)
        if candidate is None or candidate.state is not MediaRegistrationState.REGISTERED:
            raise TranscriptionExecutionError(
                "media_candidate_not_registered",
                retryable=False,
                diagnostic_summary="media candidate is not registered",
            )
        configured_root = self._source_roots.get(candidate.source_binding_key)
        if configured_root is None:
            raise TranscriptionExecutionError(
                "media_source_not_configured",
                retryable=False,
                diagnostic_summary="registered media source is not configured",
            )
        try:
            root = Path(configured_root).resolve(strict=True)
            unresolved = Path(candidate.source_reference)
            details = unresolved.lstat()
            if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
                raise OSError("not_regular")
            resolved = unresolved.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise OSError("outside_source")
        except OSError as exc:
            raise TranscriptionExecutionError(
                "media_resource_unavailable",
                retryable=True,
                diagnostic_summary="registered media resource is not safely readable",
            ) from exc
        return resolved


def _default_model_factory() -> FasterWhisperModelFactory:
    try:
        module = importlib.import_module("faster_whisper")
        value = module.WhisperModel
    except (ImportError, AttributeError, OSError) as exc:
        raise TranscriptionExecutionError(
            "provider_runtime_unavailable",
            retryable=False,
            diagnostic_summary="faster-whisper runtime is unavailable",
        ) from exc
    return cast(FasterWhisperModelFactory, value)


def _installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise TranscriptionExecutionError(
            "provider_runtime_unavailable",
            retryable=False,
            diagnostic_summary="configured transcription runtime is unavailable",
        ) from exc


def _deterministic_id(work_key: str, kind: str, ordinal: int) -> EntityId:
    return EntityId(
        str(uuid5(NAMESPACE_URL, f"stageflow:{work_key}:{kind}:{ordinal}"))
    )


def _microseconds(value: float, field: str) -> int:
    if not math.isfinite(value) or value < 0:
        raise TranscriptionExecutionError(
            "provider_timing_invalid",
            retryable=False,
            diagnostic_summary=f"provider {field} timing is invalid",
        )
    return round(value * 1_000_000)


def _provider_failure(exc: Exception) -> TranscriptionExecutionError:
    diagnostic = str(exc).casefold()
    if any(
        library in diagnostic
        for library in ("cublas64_12.dll", "cudnn64_9.dll", "cuda")
    ):
        return TranscriptionExecutionError(
            "cuda_runtime_unavailable",
            retryable=False,
            diagnostic_summary="configured CUDA runtime is unavailable",
        )
    return TranscriptionExecutionError(
        "provider_execution_failed",
        retryable=True,
        diagnostic_summary="faster-whisper execution failed",
    )


class FasterWhisperExecutionAdapter:
    provider_id = "faster-whisper"
    required_provider_version = "1.2.1"
    required_runtime_version = "4.8.1"
    execution_tool_id = "ctranslate2"
    execution_revision = "stageflow-faster-whisper-adapter-1.0"

    def __init__(
        self,
        configuration: LocalTranscriptionConfiguration,
        *,
        resolver: MediaPathResolver,
        clock: Clock,
        model_factory: FasterWhisperModelFactory | None = None,
        version_lookup: Callable[[str], str] = _installed_version,
    ) -> None:
        if configuration.device != "cuda" or configuration.compute_type != "float16":
            raise ValueError("faster-whisper Demo adapter requires CUDA float16")
        model_path = Path(configuration.model_path)
        if not model_path.is_dir():
            raise TranscriptionExecutionError(
                "provider_model_unavailable",
                retryable=False,
                diagnostic_summary="configured local transcription model is unavailable",
            )
        provider_version = version_lookup("faster-whisper")
        runtime_version = version_lookup("ctranslate2")
        if provider_version != self.required_provider_version:
            raise TranscriptionExecutionError(
                "provider_version_mismatch",
                retryable=False,
                diagnostic_summary="faster-whisper version does not match Demo qualification",
            )
        if runtime_version != self.required_runtime_version:
            raise TranscriptionExecutionError(
                "runtime_version_mismatch",
                retryable=False,
                diagnostic_summary="CTranslate2 version does not match Demo qualification",
            )
        factory = model_factory or _default_model_factory()
        try:
            self._model = factory(
                str(model_path),
                device=configuration.device,
                compute_type=configuration.compute_type,
            )
        except TranscriptionExecutionError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise _provider_failure(exc) from exc
        self._configuration = configuration
        self._resolver = resolver
        self._clock = clock
        self.provider_version = provider_version
        self.runtime_version = runtime_version

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
        try:
            raw_segments, info = self._model.transcribe(
                str(media_path),
                language=request.input.requested_language,
                beam_size=5,
                word_timestamps=request.input.request_word_timing,
                vad_filter=False,
                condition_on_previous_text=True,
            )
        except (OSError, RuntimeError, ValueError) as exc:
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
        except TranscriptionExecutionError:
            raise
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            if not segments:
                raise _provider_failure(exc) from exc
            return NormalizedTranscriptResult(
                status=TranscriptEvidenceStatus.PARTIAL,
                provenance=self._provenance(),
                language=str(getattr(info, "language", "")).strip() or None,
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
                diagnostic_summary="faster-whisper returned no speech segments",
            )
        return NormalizedTranscriptResult(
            status=TranscriptEvidenceStatus.COMPLETE,
            provenance=self._provenance(),
            language=str(getattr(info, "language", "")).strip() or None,
            segments=tuple(segments),
            limitations=(
                "speaker labels unavailable",
                "provider language probability not persisted",
            ),
        )


__all__ = [
    "FasterWhisperExecutionAdapter",
    "FasterWhisperModel",
    "FasterWhisperModelFactory",
    "KernelMediaPathResolver",
    "MediaPathResolver",
]
