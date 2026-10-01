"""Ported from faster-whisper 1.2.1; bounded English inference subset.

MIT License

Copyright (c) 2023 SYSTRAN

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import importlib
import json
import zlib
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from app.contexts.transcription_evidence import TranscriptionExecutionError

from .alignment import Alignment
from .features import FeatureExtractor, FloatArray, np, pad_or_trim
from .runtime import inference_runtime
from .tokenizer import Tokenizer
from .types import Segment, Word


def compression_ratio(text: str) -> float:
    encoded = text.encode("utf-8")
    return len(encoded) / len(zlib.compress(encoded))


class WhisperEngine:
    def __init__(self, model: Any, tokenizer: Tokenizer, features: FeatureExtractor,
                 storage: Callable[[FloatArray], Any]) -> None:
        self.model, self.tokenizer = model, tokenizer
        self.features, self.storage = features, storage
        self.alignment = Alignment(model)

    def fallback(self, encoded: Any, prompt: list[int]) -> tuple[Any, float, float]:
        tokenizer = self.tokenizer
        suppressed = sorted(set((*tokenizer.non_speech_tokens, tokenizer.transcribe,
                                 tokenizer.translate, tokenizer.sot, tokenizer.sot_prev,
                                 tokenizer.sot_lm, tokenizer.no_speech)))
        results: list[tuple[Any, float, float]] = []
        below_ratio: list[tuple[Any, float, float]] = []
        for temperature in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            kwargs: dict[str, Any] = (
                {"beam_size": 1, "num_hypotheses": 5, "sampling_topk": 0,
                 "sampling_temperature": temperature} if temperature else
                {"beam_size": 5, "patience": 1})
            result = self.model.generate(
                encoded, [prompt], length_penalty=1, repetition_penalty=1,
                no_repeat_ngram_size=0, max_length=448, return_scores=True,
                return_no_speech_prob=True, suppress_blank=True, suppress_tokens=suppressed,
                max_initial_timestamp_index=50, **kwargs)[0]
            tokens = result.sequences_ids[0]
            avg = float(result.scores[0]) * len(tokens) / (len(tokens) + 1)
            ratio = compression_ratio(tokenizer.decode(tokens).strip())
            choice = (result, avg, temperature)
            results.append(choice)
            if ratio <= 2.4:
                below_ratio.append(choice)
            if ((ratio <= 2.4 and avg >= -1.0)
                    or (result.no_speech_prob > 0.6 and avg < -1.0)):
                return choice
        result, avg, _ = max(below_ratio or results, key=lambda item: item[1])
        return result, avg, 1.0

    def split(self, tokens: list[int], offset: float, size: int,
              seek: int) -> tuple[list[Any], int, bool]:
        begin = self.tokenizer.timestamp_begin
        single = len(tokens) >= 2 and tokens[-2] < begin <= tokens[-1]
        consecutive = [i for i in range(1, len(tokens))
                       if tokens[i] >= begin and tokens[i - 1] >= begin]
        segments: list[Any] = []
        if consecutive:
            if single:
                consecutive.append(len(tokens))
            last = 0
            for end in consecutive:
                sliced = tokens[last:end]
                segments.append(dict(seek=seek, start=offset + (sliced[0] - begin) * .02,
                                     end=offset + (sliced[-1] - begin) * .02, tokens=sliced))
                last = end
            seek += size if single else (tokens[last - 1] - begin) * 2
        else:
            timestamps = [t for t in tokens if t >= begin]
            duration = ((timestamps[-1] - begin) * .02
                        if timestamps and timestamps[-1] != begin else size * .01)
            segments.append(dict(seek=seek, start=offset, end=offset + duration, tokens=tokens))
            seek += size
        return segments, seek, single

    def transcribe(self, audio: FloatArray, *, language: str | None,
                   word_timestamps: bool, renew_lease: Callable[[], None]) -> Iterable[Segment]:
        if language not in (None, "en"):
            raise ValueError("only fixed English transcription is supported")
        features = self.features(audio)
        content_frames = features.shape[-1] - 1
        seek = 0
        all_tokens: list[int] = []
        reset = 0
        last_speech = 0.0
        while seek < content_frames:
            renew_lease()
            previous_seek = seek
            offset = seek * .01
            size = min(3000, content_frames - seek)
            window = pad_or_trim(features[:, seek:seek + size])
            encoded = self.model.encode(self.storage(np.ascontiguousarray(window[None])),
                                        to_cpu=False)
            previous = all_tokens[reset:]
            prompt = ([self.tokenizer.sot_prev, *previous[-223:]] if previous else [])
            prompt.extend(self.tokenizer.sot_sequence)
            result, avg, temperature = self.fallback(encoded, prompt)
            if result.no_speech_prob > .6 and avg <= -1.0:
                seek += size
                continue
            segments, seek, single = self.split(result.sequences_ids[0], offset, size, seek)
            if word_timestamps:
                self.alignment.add_word_timestamps(
                    [segments], self.tokenizer, encoded, size,
                    "\"'“¿([{-", "\"'.。,，!！?？:：”)]}、", last_speech)
                end = next((s["words"][-1]["end"] for s in reversed(segments) if s["words"]),
                           segments[-1]["end"] if segments else None)
                if end is not None:
                    if not single and end > offset:
                        seek = round(end * 100)
                    last_speech = end
            # Malformed native output must not spin forever on the same window.
            if seek <= previous_seek:
                raise RuntimeError("provider window did not advance")
            for segment in segments:
                text = self.tokenizer.decode(segment["tokens"])
                if segment["start"] == segment["end"] or not text.strip():
                    continue
                all_tokens.extend(segment["tokens"])
                yield Segment(text, segment["start"], segment["end"],
                              [Word(**w) for w in segment["words"]] if word_timestamps else None)
            if temperature > .5:
                reset = len(all_tokens)


def load_engine(path: str, *, device: str, compute_type: str) -> WhisperEngine:
    if not all((Path(path) / name).is_file() for name in ("model.bin", "config.json")):
        raise TranscriptionExecutionError(
            "provider_model_unavailable", retryable=False,
            diagnostic_summary="configured local model is unavailable")
    try:
        runtime = inference_runtime()
    except (ImportError, OSError) as exc:
        raise TranscriptionExecutionError(
            "provider_runtime_unavailable", retryable=False,
            diagnostic_summary="local transcription runtime unavailable") from exc
    model = runtime.Whisper(path, device=device, device_index=0, compute_type=compute_type,
                            intra_threads=0, inter_threads=1)
    tokenizers = importlib.import_module("tokenizers")
    try:
        tokenizer = Tokenizer(
            tokenizers.Tokenizer.from_file(str(Path(path) / "tokenizer.json")),
            model.is_multilingual, task="transcribe", language="en")
    except Exception as exc:
        # The Rust binding raises plain Exception for malformed tokenizer JSON.
        raise TranscriptionExecutionError(
            "provider_model_unavailable", retryable=False,
            diagnostic_summary="configured local tokenizer is unavailable") from exc
    config: dict[str, Any] = {}
    preprocessor = Path(path) / "preprocessor_config.json"
    if preprocessor.is_file():
        try:
            config = json.loads(preprocessor.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass  # Reference falls back to defaults for invalid JSON.
    keys = {"feature_size", "sampling_rate", "hop_length", "chunk_length", "n_fft"}
    features = FeatureExtractor(**{k: v for k, v in config.items() if k in keys})
    return WhisperEngine(model, tokenizer, features, runtime.StorageView.from_array)
