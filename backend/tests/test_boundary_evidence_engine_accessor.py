"""Read-only diagnostic accessor, synthetic native effects; adapter outputs unchanged."""
import math
from typing import Any, cast

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("tokenizers")

from test_ctranslate2_whisper_engine import Model, engine, result  # noqa: E402


class DiagnosticModel(Model):
    def encode(self, window: Any, *, to_cpu: bool) -> Any:
        self.windows.append(window)
        assert to_cpu
        states = np.ones((1, 1500, 4), dtype=np.float32)
        states[:, 500:] = 999  # Padding must not affect the pooled 10 s vector.
        return states


def test_inspect_window_statistics_words_and_padding_exclusion() -> None:
    model = DiagnosticModel([result(tokens=[100, 1, 150])])
    port = engine(model)

    def align(groups: list[Any], *_args: Any) -> None:
        groups[0][0]["words"] = [dict(word="Synthetic.", start=.1, end=.5, probability=.9)]

    port.alignment.add_word_timestamps = cast(Any, align)
    observed = port.inspect_window(np.zeros(160000, dtype=np.float32))
    assert observed["embedding"].tolist() == [1, 1, 1, 1]
    row = observed["segments"][0]
    assert row["no_speech_probability"] == .1
    assert math.isclose(row["average_log_probability"], -.075)
    assert row["compression_ratio"] > 0 and "non_speech" not in row
    assert set(port.tokenizer.non_speech_tokens) <= set(model.calls[0]["suppress_tokens"])
    assert row["words"][0].start == .1
    assert model.prompts == [[51, 57, 54]]


def test_inspect_window_rejects_unbounded_audio_before_inference() -> None:
    model = DiagnosticModel([])
    port = engine(model)
    for size in (0, 160001):
        with pytest.raises(ValueError, match="invalid_window"):
            port.inspect_window(np.zeros(size, dtype=np.float32))
    assert not model.windows


def test_accessor_is_additive_normal_transcription_still_uses_native_states() -> None:
    model = Model([result()])
    port = engine(model)
    rows = list(port.transcribe(np.zeros(16000, dtype=np.float32), language="en",
                                word_timestamps=False, renew_lease=lambda: None))
    assert len(rows) == 1
    assert vars(rows[0]) == {"text": " Hello", "start": 0, "end": 1, "words": None}
