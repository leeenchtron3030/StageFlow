"""Synthetic numeric and fake-native inference tests; no downloads or model weights."""
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

np = pytest.importorskip("numpy")
tokenizers = pytest.importorskip("tokenizers")

from app.infrastructure.transcription.ctranslate2_whisper.alignment import Alignment  # noqa: E402
from app.infrastructure.transcription.ctranslate2_whisper.engine import WhisperEngine  # noqa: E402
from app.infrastructure.transcription.ctranslate2_whisper.features import (  # noqa: E402
    FeatureExtractor,
)
from app.infrastructure.transcription.ctranslate2_whisper.tokenizer import Tokenizer  # noqa: E402


@pytest.mark.parametrize("size", [80, 128])
@pytest.mark.parametrize("signal", ["silence", "tone", "impulse"])
def test_features_match_fixed_reference(signal: str, size: int) -> None:
    audio = np.zeros(800, dtype=np.float32)
    if signal == "tone":
        audio = (0.2 * np.sin(2 * np.pi * 440 * np.arange(800) / 16000)).astype(np.float32)
    elif signal == "impulse":
        audio[400] = 1
    expected = np.load(Path(__file__).parent / "fixtures/ctranslate2_whisper" /
                       f"{signal}_{size}.npy")
    actual = FeatureExtractor(size)(audio)
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)
    assert actual.dtype == np.float32


def real_tokenizer() -> Tokenizer:
    vocab = {"hello": 0, "world": 1, "!": 2, "[UNK]": 3}
    special = ("<|endoftext|>", "<|startoftranscript|>", "<|en|>", "<|transcribe|>",
               "<|translate|>", "<|startoflm|>", "<|startofprev|>", "<|nospeech|>",
               "<|notimestamps|>", "<|0.00|>")
    vocab.update({s: i + 4 for i, s in enumerate(special)})
    raw = tokenizers.Tokenizer(tokenizers.models.WordLevel(vocab, unk_token="[UNK]"))
    raw.pre_tokenizer = tokenizers.pre_tokenizers.Whitespace()
    raw.add_special_tokens(list(special))
    return Tokenizer(raw, multilingual=True, language="en", task="transcribe")


def test_tokenizer_special_tokens_and_text_filtering() -> None:
    tokenizer = real_tokenizer()
    assert tokenizer.sot_sequence == [5, 6, 7]
    assert tokenizer.eot == 4 and tokenizer.timestamp_begin == 13
    assert tokenizer.no_speech == 11
    assert tokenizer.encode("hello world") == [0, 1]
    assert tokenizer.decode([13, 0, 1, 4]) == "hello world"
    assert tokenizer.decode_with_timestamps([13, 0, 18]) == "<|0.00|>hello<|0.10|>"
    assert isinstance(tokenizer.non_speech_tokens, tuple)
    with pytest.raises(ValueError):
        Tokenizer(tokenizer.tokenizer, True, language="fr")


class FakeTokenizer:
    timestamp_begin = 100
    eot = 50
    sot = 51
    sot_prev = 52
    sot_lm = 53
    transcribe = 54
    translate = 55
    no_speech = 56
    sot_sequence = [51, 57, 54]
    non_speech_tokens = (30, 31)

    def decode(self, tokens: list[int]) -> str:
        return "".join({1: " Hello", 2: " world", 3: "!"}.get(t, "") for t in tokens)

    def split_to_word_tokens(self, tokens: list[int]) -> tuple[list[str], list[list[int]]]:
        return ([{1: " Hello", 2: " world", 3: "!", 50: ""}[t] for t in tokens],
                [[t] for t in tokens])


def result(score: float = -.1, speech: float = .1,
           tokens: list[int] | None = None) -> Any:
    return SimpleNamespace(sequences_ids=[tokens if tokens is not None else [100, 1, 150]],
                           scores=[score], no_speech_prob=speech)


class Model:
    def __init__(self, results: list[Any]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []
        self.prompts: list[list[int]] = []
        self.windows: list[Any] = []

    def encode(self, window: Any, *, to_cpu: bool) -> Any:
        assert not to_cpu
        self.windows.append(window)
        return window

    def generate(self, encoded: Any, prompts: list[list[int]], **kwargs: Any) -> list[Any]:
        self.calls.append(kwargs)
        self.prompts.extend(prompts)
        return [self.results.pop(0)]


def engine(model: Model) -> WhisperEngine:
    return WhisperEngine(model, cast(Tokenizer, FakeTokenizer()), FeatureExtractor(), lambda x: x)


def test_window_defaults_previous_text_and_lease_per_window() -> None:
    model = Model([result(), result()])
    renewals: list[None] = []
    segments = list(engine(model).transcribe(
        np.zeros(31 * 16000, dtype=np.float32), language="en", word_timestamps=False,
        renew_lease=lambda: renewals.append(None)))
    assert len(segments) == 2 and len(renewals) == 2
    assert segments[1].start == 30
    assert [w.shape for w in model.windows] == [(1, 80, 3000)] * 2
    assert model.prompts == [[51, 57, 54], [52, 100, 1, 150, 51, 57, 54]]
    assert model.calls[0] == dict(length_penalty=1, repetition_penalty=1,
        no_repeat_ngram_size=0, max_length=448, return_scores=True, return_no_speech_prob=True,
        suppress_blank=True, suppress_tokens=[30, 31, 51, 52, 53, 54, 55, 56],
        max_initial_timestamp_index=50, beam_size=5, patience=1)


def test_window_that_does_not_advance_is_refused() -> None:
    model = Model([result(tokens=[100, 1, 100, 100, 2])])
    renewals: list[None] = []
    with pytest.raises(RuntimeError, match="provider window did not advance"):
        list(engine(model).transcribe(np.zeros(16000, dtype=np.float32), language="en",
             word_timestamps=False, renew_lease=lambda: renewals.append(None)))
    assert len(model.calls) == 1 and len(renewals) == 1


def test_non_english_language_is_refused_before_inference() -> None:
    model = Model([])
    renewals: list[None] = []
    with pytest.raises(ValueError, match="only fixed English"):
        list(engine(model).transcribe(np.zeros(16000, dtype=np.float32), language="fr",
             word_timestamps=False, renew_lease=lambda: renewals.append(None)))
    assert not model.calls and not model.windows and not renewals


@pytest.mark.parametrize("language", [None, "en"])
def test_unspecified_language_and_english_use_fixed_english_prompt(language: str | None) -> None:
    model = Model([result()])
    port = WhisperEngine(model, real_tokenizer(), FeatureExtractor(), lambda x: x)
    list(port.transcribe(np.zeros(16000, dtype=np.float32), language=language,
                         word_timestamps=False, renew_lease=lambda: None))
    assert model.prompts == [[5, 6, 7]]


def test_temperature_fallback_and_prompt_reset() -> None:
    model = Model([result(-3), result(-3), result(-3), result(), result()])
    segments = list(engine(model).transcribe(np.zeros(31 * 16000, dtype=np.float32),
                    language="en", word_timestamps=False, renew_lease=lambda: None))
    assert len(segments) == 2
    assert model.calls[3]["sampling_temperature"] == .6
    assert model.calls[3]["num_hypotheses"] == 5
    assert model.calls[3]["sampling_topk"] == 0
    assert model.prompts[-1] == [51, 57, 54]


@pytest.mark.parametrize("score,speech,count", [(-3, .9, 0), (-.1, .9, 1), (-.1, .6, 1)])
def test_no_speech_threshold_and_logprob_override(score: float, speech: float, count: int) -> None:
    model = Model([result(score, speech)])
    segments = list(engine(model).transcribe(np.zeros(16000, dtype=np.float32),
                    language="en", word_timestamps=False, renew_lease=lambda: None))
    assert len(segments) == count and len(model.calls) == 1


def test_compression_fallback_selects_best_below_ratio_and_final_temperature() -> None:
    repeated = result(-.01, tokens=[1] * 300)
    best = result(-1.5)
    model = Model([repeated, best, result(-2), result(-3), result(-3), result(-3)])
    chosen, _, temperature = engine(model).fallback(None, [51])
    assert chosen is best and temperature == 1
    assert len(model.calls) == 6


def test_timestamp_splits_and_unfinished_tail() -> None:
    port = engine(Model([]))
    segments, seek, single = port.split([100, 1, 150, 150, 2, 200], 30, 3000, 3000)
    assert [(s["start"], s["end"]) for s in segments] == [(30, 31), (31, 32)]
    assert seek == 6000 and single
    segments, seek, single = port.split([100, 1, 150, 150, 2], 30, 3000, 3000)
    assert len(segments) == 1 and seek == 3100 and not single


def test_alignment_maps_native_steps_probabilities_and_merges_punctuation() -> None:
    def align(encoded: Any, prompt: list[int], tokens: list[list[int]], frames: int,
              *, median_filter_width: int) -> list[Any]:
        assert prompt == [51, 57, 54] and tokens == [[1, 2, 3]]
        assert frames == 300 and median_filter_width == 7
        return [SimpleNamespace(text_token_probs=[.9, .8, .7],
                                alignments=[(0, 0), (0, 5), (1, 20), (2, 40), (3, 45)])]
    alignment = Alignment(SimpleNamespace(align=align))
    segments: list[Any] = [dict(seek=100, start=1., end=2., tokens=[100, 1, 2, 3, 150])]
    alignment.add_word_timestamps([segments], cast(Tokenizer, FakeTokenizer()), None, 300,
                                  "\"'([", "!?.,", 0.)
    assert [w["word"] for w in segments[0]["words"]] == [" Hello", " world!"]
    assert segments[0]["words"][0] == dict(word=" Hello", start=1., end=1.4, probability=.9)
    assert segments[0]["words"][1]["end"] == 1.8  # punctuation preserves word's timing


def test_word_timing_changes_next_window_seek() -> None:
    model = Model([result(tokens=[1]), result()])
    port = engine(model)

    def timing(groups: list[Any], *args: Any, **kwargs: Any) -> None:
        for s in groups[0]:
            s["words"] = [dict(word=" Hello", start=s["start"], end=s["start"] + 1,
                               probability=.9)]
    port.alignment.add_word_timestamps = cast(Callable[..., Any], timing)
    segments = list(port.transcribe(np.zeros(2 * 16000, dtype=np.float32), language="en",
                                    word_timestamps=True, renew_lease=lambda: None))
    assert [s.start for s in segments] == [0, 1]


def test_loader_maps_missing_model_malformed_tokenizer_and_native_load_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.contexts.transcription_evidence import TranscriptionExecutionError
    from app.infrastructure.transcription.ctranslate2_whisper import engine as module

    with pytest.raises(TranscriptionExecutionError, match="provider_model_unavailable"):
        module.load_engine(str(tmp_path), device="cpu", compute_type="int8")
    for name in ("model.bin", "config.json", "tokenizer.json"):
        (tmp_path / name).write_text("invalid synthetic data")

    def unavailable() -> Any:
        raise OSError("private native path")

    monkeypatch.setattr(module, "inference_runtime", unavailable)
    with pytest.raises(TranscriptionExecutionError) as caught:
        module.load_engine(str(tmp_path), device="cpu", compute_type="int8")
    assert caught.value.reason_code == "provider_runtime_unavailable" and not caught.value.retryable

    def whisper(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(is_multilingual=True)

    monkeypatch.setattr(module, "inference_runtime", lambda: SimpleNamespace(Whisper=whisper))
    with pytest.raises(TranscriptionExecutionError) as caught:
        module.load_engine(str(tmp_path), device="cpu", compute_type="int8")
    assert caught.value.reason_code == "provider_model_unavailable" and not caught.value.retryable
    assert "private" not in caught.value.diagnostic_summary


@pytest.mark.parametrize("preprocessor,mel_bins", [
    (None, 80), ("invalid JSON", 80),
    ('{"feature_size": 128, "sampling_rate": 16000, "hop_length": 160, '
     '"chunk_length": 30, "n_fft": 400, "ignored": true}', 128),
])
def test_loader_reads_preprocessor_and_preserves_native_thread_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preprocessor: str | None, mel_bins: int,
) -> None:
    from app.infrastructure.transcription.ctranslate2_whisper import engine as module

    for name in ("model.bin", "config.json"):
        (tmp_path / name).write_text("synthetic model")
    cast(Any, real_tokenizer().tokenizer).save(str(tmp_path / "tokenizer.json"))
    if preprocessor is not None:
        (tmp_path / "preprocessor_config.json").write_text(preprocessor, encoding="utf-8")
    calls: list[dict[str, Any]] = []
    model = SimpleNamespace(is_multilingual=True)

    def loader(path: str, **kwargs: Any) -> Any:
        assert path == str(tmp_path)
        calls.append(kwargs)
        return model

    def storage(array: Any) -> Any:
        return array

    monkeypatch.setattr(module, "inference_runtime", lambda: SimpleNamespace(
        Whisper=loader, StorageView=SimpleNamespace(from_array=storage)))
    loaded = module.load_engine(str(tmp_path), device="cpu", compute_type="int8")
    assert loaded.model is model
    assert calls == [dict(device="cpu", device_index=0, compute_type="int8",
                          intra_threads=0, inter_threads=1)]
    assert loaded.tokenizer.sot_sequence == [5, 6, 7]
    features = loaded.features(np.zeros(16000, dtype=np.float32))
    assert features.shape == (mel_bins, 101)
    assert loaded.storage(features) is features
