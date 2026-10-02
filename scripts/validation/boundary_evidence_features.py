"""Raw feature parsing and measurement; no fitting, text retention, or identity."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from statistics import median
from typing import Any

from boundary_evidence_common import Refusal, correlate, finite, np_module

FEATURES = {
    "audio_stats": ("flatness", "centroid", "flux", "entropy", "rolloff", "momentary", "rms"),
    "picture": ("scene", "black", "graphic_similarity", "graphic_ordinal"),
    "music_cue": ("correlation", "detected", "cue_ordinal"),
    "whisper": ("no_speech_probability", "average_log_probability", "compression_ratio"),
    "voice_continuity": ("cosine_distance",),
}


def metadata(payload: str, family: str) -> list[dict[str, float]]:
    """Average audio metadata frames per second; picture scene uses the maximum.

    Parse ametadata/metadata print records only. Unknown keys and all log text
    disappear. -inf dB (digital silence) is explicitly floored to -120 dB.
    Black intervals use black_start/end timestamps, not the end frame's timestamp.
    """
    samples: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    second: int | None = None
    black_start: float | None = None
    last_time = 0.0
    for line in payload.splitlines():
        frame = re.search(r"\bpts_time:([0-9.eE+-]+)", line)
        if frame:
            last_time = finite(frame[1])
            second = math.floor(last_time)
        pair = re.search(r"(lavfi\.[A-Za-z0-9_.]+)=(-?inf|[-+0-9.eE]+)\s*$", line)
        if pair is None or second is None:
            continue
        name, raw = pair.groups()
        value = -120.0 if raw == "-inf" else finite(raw)
        feature = None
        if family == "audio_stats":
            suffix = name.rsplit(".", 1)[-1]
            if name.startswith("lavfi.aspectralstats.") and suffix in FEATURES[family][:5]:
                feature = suffix
            elif name == "lavfi.r128.M":
                feature = "momentary"
            elif name == "lavfi.astats.Overall.RMS_level":
                feature = "rms"
        elif family == "picture":
            samples[second]["black"].append(0.0)
            if name == "lavfi.scd.score":
                feature = "scene"
            elif name == "lavfi.black_start":
                black_start = value
            elif name == "lavfi.black_end" and black_start is not None:
                for at in range(math.floor(black_start), math.ceil(value)):
                    samples[at]["black"].append(1.0)
                black_start = None
        if feature:
            samples[second][feature].append(value)
    if black_start is not None:
        for at in range(math.floor(black_start), math.floor(last_time) + 1):
            samples[at]["black"].append(1.0)
    return [{"second": float(s), **{k: (max(v) if family == "picture" else sum(v) / len(v))
                                   for k, v in values.items()}}
            for s, values in sorted(samples.items())]


def graphics(frames: Any, references: list[Any]) -> list[dict[str, float]]:
    np = np_module()
    result: list[dict[str, float]] = []
    for second, frame in enumerate(frames):
        x = np.asarray(frame, dtype=float).ravel()
        x -= x.mean()
        scores: list[float] = []
        for reference in references:
            y = np.asarray(reference, dtype=float).ravel()
            y = y - y.mean()
            norm = float(np.linalg.norm(x) * np.linalg.norm(y))
            # Uniform frames are not evidence of a graphic, even two black frames.
            scores.append(float(np.clip(x @ y / norm, -1, 1)) if norm > 1e-12 else 0.0)
        if scores:
            best = max(range(len(scores)), key=lambda i: scores[i])
            result.append({"second": float(second), "graphic_similarity": scores[best],
                           "graphic_ordinal": float(best)})
    return result


def music(audio: Any, references: list[Any], rate: int = 8000,
          threshold: float = .8) -> list[dict[str, float]]:
    if not 0 < threshold <= 1:
        raise Refusal()
    result: list[dict[str, float]] = []
    overlap = max((len(r) for r in references), default=0)
    for start in range(0, len(audio), 60 * rate):
        rows = _music_chunk(audio[start:start + 60 * rate + overlap], references, rate, threshold)
        result.extend({**r, "second": r["second"] + start / rate}
                      for r in rows if r["second"] < 60)
    return result


def _music_chunk(audio: Any, references: list[Any], rate: int,
                 threshold: float) -> list[dict[str, float]]:
    scores = [correlate(audio, reference) for reference in references]
    result: list[dict[str, float]] = []
    for second in range(math.ceil(len(audio) / rate)):
        values = [(float(s[second * rate:min(len(s), (second + 1) * rate)].max()), i)
                  for i, s in enumerate(scores) if second * rate < len(s)]
        if values:
            value, best = max(values, key=lambda pair: (pair[0], -pair[1]))
            result.append({"second": float(second), "correlation": value,
                           "detected": float(value >= threshold), "cue_ordinal": float(best)})
    return result


def distance(left: Any, right: Any) -> float | None:
    np = np_module()
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if a.shape != b.shape or a.ndim != 1 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise Refusal()
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.clip(1 - a @ b / norm, 0, 2)) if norm > 1e-12 else None


def auc(positive: list[float], negative: list[float]) -> float | None:
    """Mann-Whitney AUC, with half credit for ties; O(n log n)."""
    if not positive or not negative:
        return None
    ranked = sorted([(v, 1) for v in positive] + [(v, 0) for v in negative])
    total = 0.0
    negatives = 0
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        p = sum(label for _, label in ranked[index:end])
        n = end - index - p
        total += p * (negatives + n / 2)
        negatives += n
        index = end
    return total / (len(positive) * len(negative))


def measurements(series: list[tuple[float, float]], edges: list[float],
                 all_edges: list[float], *, peak_series: list[tuple[float, float]] | None = None,
                 label_edges: list[float] | None = None) -> dict[str, Any]:
    labels = edges if label_edges is None else label_edges
    positives = [v for t, v in series if any(abs(t - e) <= 15 for e in labels)]
    negatives = [v for t, v in series if all(abs(t - e) > 120 for e in all_edges)]
    score = auc(positives, negatives)
    direction = "lower" if score is not None and score < .5 else "higher"
    lags: list[float] = []
    for edge in edges:
        window = [(t, v) for t, v in (series if peak_series is None else peak_series)
                  if abs(t - edge) <= 120]
        if window:
            # Earliest timestamp wins ties; truth proximity never breaks ties.
            peak = min(window, key=lambda pair: (pair[1] if direction == "lower" else -pair[1],
                                                  pair[0]))
            lags.append(peak[0] - edge)
    return {"auc": score, "direction": direction,
            "separability": max(score, 1 - score) if score is not None else None,
            "positive_seconds": len(positives),
            "negative_seconds": len(negatives), "edge_count": len(edges),
            "covered_edge_count": len(lags),
            "hit_10": sum(abs(v) <= 10 for v in lags) / len(edges) if edges else None,
            "hit_30": sum(abs(v) <= 30 for v in lags) / len(edges) if edges else None,
            "median_lag": median(lags) if lags else None}


def second_series(rows: list[dict[str, Any]], feature: str) -> list[tuple[float, float]]:
    """Expand segment statistics only over their own covered seconds, not gaps."""
    values: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        if feature not in row:
            continue
        start = float(row.get("second", row.get("start", 0)))
        end = float(row.get("end", start + 1))
        for second in range(math.floor(start), math.ceil(end)):
            values[second].append(finite(row[feature]))
    return [(float(t), sum(v) / len(v)) for t, v in sorted(values.items())]
