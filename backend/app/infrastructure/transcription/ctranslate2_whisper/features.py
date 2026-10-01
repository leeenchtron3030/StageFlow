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
from typing import Any

# Optional native buffers stay inside infrastructure. Dynamic imports keep the
# default (no transcription runtime) installation and its static checks usable.
np: Any = importlib.import_module("numpy")
type FloatArray = Any


class FeatureExtractor:
    def __init__(self, feature_size: int = 80, sampling_rate: int = 16000,
                 hop_length: int = 160, chunk_length: int = 30, n_fft: int = 400) -> None:
        if (sampling_rate, hop_length, chunk_length, n_fft) != (16000, 160, 30, 400):
            raise ValueError("unsupported feature configuration")
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.nb_max_frames = 3000
        self.time_per_frame = 0.01
        fftfreqs = np.fft.rfftfreq(n=n_fft, d=1.0 / sampling_rate)
        mels = np.linspace(0.0, 45.245640471924965, feature_size + 2)
        freqs = (200.0 / 3) * mels
        log_t = mels >= 15.0
        freqs[log_t] = 1000.0 * np.exp(np.log(6.4) / 27.0 * (mels[log_t] - 15.0))
        fdiff = np.diff(freqs)
        ramps = freqs.reshape(-1, 1) - fftfreqs.reshape(1, -1)
        lower = -ramps[:-2] / np.expand_dims(fdiff[:-1], axis=1)
        upper = ramps[2:] / np.expand_dims(fdiff[1:], axis=1)
        weights = np.maximum(np.zeros_like(lower), np.minimum(lower, upper))
        weights *= np.expand_dims(2.0 / (freqs[2:feature_size + 2] - freqs[:feature_size]), 1)
        self.mel_filters = weights.astype(np.float32)

    def __call__(self, waveform: FloatArray) -> FloatArray:
        waveform = np.pad(waveform.astype(np.float32), (0, 160))
        waveform = np.pad(waveform, (200, 200), mode="reflect")
        frames = np.lib.stride_tricks.sliding_window_view(waveform, 400)[::160]
        window = np.hanning(401)[:-1].astype(np.float32)
        spectrum = np.fft.rfft(frames * window, n=400, axis=-1).T.astype(np.complex64)
        magnitudes = np.abs(spectrum[..., :-1]) ** 2
        mel_spec = self.mel_filters @ magnitudes
        log_spec = np.log10(np.clip(mel_spec, a_min=1e-10, a_max=None))
        log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
        return ((log_spec + 4.0) / 4.0).astype(np.float32)


def pad_or_trim(features: FloatArray) -> FloatArray:
    return np.pad(features[:, :3000], ((0, 0), (0, max(0, 3000 - features.shape[-1]))))
