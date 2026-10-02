"""Align private edited exports to advisory UTC recorder intervals, entirely offline."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from boundary_evidence_common import (
    Parser,
    Refusal,
    config,
    correlate,
    decode,
    external,
    ffmpeg_tool,
    finite,
    iso,
    np_module,
    output_collisions,
    probe,
    quiet_output,
    utc,
    write_json,
)
from transcription_engine_spike import EXTENSIONS


@dataclass
class Run:
    start: float
    audio: Any


def recording_runs(blocks: list[tuple[float, float, Any]], rate: int,
                   join_tolerance: float = 2.0) -> list[Run]:
    """Join recorder-clock rounding jitter, anchored sample-contiguously to run start."""
    if finite(join_tolerance) < 0:
        raise Refusal()
    np = np_module()
    runs: list[Run] = []
    previous_end: float | None = None
    for start, duration, audio in sorted(blocks, key=lambda b: b[0]):
        if abs(len(audio) / rate - duration) > .1:
            raise Refusal()
        if previous_end is not None and start < previous_end - join_tolerance:
            raise Refusal()
        if runs and previous_end is not None and abs(start - previous_end) <= join_tolerance:
            runs[-1].audio = np.concatenate((runs[-1].audio, audio))
        else:
            runs.append(Run(start, audio))
        previous_end = start + duration
    return runs


def locate(audio: Any, runs: list[Run], rate: int, *,
           predicted: tuple[float, int] | None = None) -> tuple[float, float, int]:
    best = (0.0, -1.0, -1)
    for ordinal, run in enumerate(runs):
        left, right = 0, len(run.audio)
        if predicted is not None:
            if ordinal != predicted[1]:
                continue
            center = round((predicted[0] - run.start) * rate)
            left = min(len(run.audio), max(0, center - 60 * rate))
            right = max(0, min(right, center + 60 * rate + len(audio)))
        if right - left < len(audio):
            continue
        scores = correlate(run.audio[left:right], audio)
        if len(scores):
            index = int(scores.argmax())
            if float(scores[index]) > best[1]:
                best = (run.start + (left + index) / rate, float(scores[index]), ordinal)
    return best


def align_export(audio: Any, runs: list[Run], *, ordinal: int, rate: int = 8000,
                 intro_skip: float = 0, outro_skip: float = 0,
                 threshold: float = .8, acceptance_fraction: float = .9) -> dict[str, Any]:
    """Five global anchors, then local tracking; quarter-second support per segment."""
    if (not 0 < threshold <= 1 or not 0 < acceptance_fraction <= 1
            or min(intro_skip, outro_skip) < 0):
        raise Refusal()
    start, end = round(intro_skip * rate), len(audio) - round(outro_skip * rate)
    if end - start < 10 * rate:
        raise Refusal()
    anchors: list[tuple[int, float, float, int]] = []
    for fraction in (0, .15, .5, .85, 1):
        position = start + round((end - start - 10 * rate) * fraction)
        at, score, run = locate(audio[position:position + 10 * rate], runs, rate)
        anchors.append((position, at, score, run))
    snippet_scores = [a[2] for a in anchors]
    accepted = [a for a in anchors if a[2] >= threshold]
    pieces: list[tuple[int, int, float, float, int]] = []
    last = accepted[0] if accepted else None

    def visit(left: int, right: int, *, sub_tile: bool = False,
              parent_match: tuple[int, float, int] | None = None) -> None:
        nonlocal last
        assert last is not None
        prediction = (last[1] + (left - last[0]) / rate, last[3])
        at, score, run = locate(audio[left:right], runs, rate, predicted=prediction)
        if sub_tile and parent_match is not None:
            parent_prediction = (parent_match[1] + (left - parent_match[0]) / rate,
                                 parent_match[2])
            alternative = locate(audio[left:right], runs, rate, predicted=parent_prediction)
            if alternative[1] > score:
                at, score, run = alternative
        if score < threshold and not sub_tile and right - left > max(1, rate // 4):
            at, score, run = locate(audio[left:right], runs, rate)
            # Even a below-threshold parent match can locate the far side of a cut.
            if run >= 0:
                parent_match = (left, at, run)
        if score >= threshold:
            source = round((at - runs[run].start) * rate)
            checks: list[float] = []
            for offset in range(0, right - left, max(1, rate // 4)):
                size = min(max(1, rate // 4), right - left - offset)
                scores = correlate(runs[run].audio[source + offset:source + offset + size],
                                   audio[left + offset:left + offset + size])
                checks.append(float(scores[0]) if len(scores) else -1.0)
            if min(checks) >= threshold or right - left <= max(1, rate // 4):
                last = (left, at, score, run)
                # Keep quarter-second evidence so the fraction is independent of search tiling.
                for offset, check in zip(range(0, right - left, max(1, rate // 4)),
                                         checks, strict=True):
                    pieces.append((left + offset, min(right, left + offset + max(1, rate // 4)),
                                   at + offset / rate, check, run))
                return
        if right - left > max(1, rate // 4):
            for position in range(left, right, max(1, rate // 4)):
                visit(position, min(right, position + max(1, rate // 4)),
                      sub_tile=True, parent_match=parent_match)
        else:
            # Quiet/processed tiles may lack waveform support. Retain their predicted
            # placement, but never let them update tracking or count as accepted evidence.
            pieces.append((left, right, prediction[0], min(score, threshold - 1e-9), prediction[1]))

    if last is not None:
        for position in range(start, end, 10 * rate):
            visit(position, min(end, position + 10 * rate))
    groups: list[list[tuple[int, int, float, float, int]]] = []
    for piece in pieces:
        if groups:
            prior = groups[-1][-1]
            same = (piece[0] == prior[1] and piece[4] == prior[4]
                    and abs(piece[2] - prior[2] - (piece[0] - prior[0]) / rate) <= .05)
        else:
            same = False
        if same:
            groups[-1].append(piece)
        else:
            groups.append([piece])
    fractions = [sum(p[3] >= threshold for p in g) / len(g) for g in groups]
    supported = [g for g, fraction in zip(groups, fractions, strict=True)
                 if fraction >= acceptance_fraction
                 and g[0][2] >= runs[g[0][4]].start
                 and g[-1][2] + (g[-1][1] - g[-1][0]) / rate
                 <= runs[g[-1][4]].start + len(runs[g[-1][4]].audio) / rate + 1 / rate]
    segments = [{"start": iso(g[0][2]),
                 "end": iso(g[-1][2] + (g[-1][1] - g[-1][0]) / rate),
                 "accepted_fraction": sum(p[3] >= threshold for p in g) / len(g)}
                for g in supported]
    aligned = bool(segments) and len(supported) == len(groups)
    return {"ordinal": ordinal, "start": segments[0]["start"] if aligned else None,
            "end": segments[-1]["end"] if aligned else None, "segments": segments,
            "min_score": min(p[3] for p in pieces) if aligned else min(snippet_scores),
            "acceptance_fraction": acceptance_fraction,
            "accepted_fraction": sum(p[3] >= threshold for p in pieces) / len(pieces)
            if pieces else 0.0,
            "consistent": aligned and len(groups) == 1,
            "status": "aligned" if aligned else "unaligned", "snippet_scores": snippet_scores,
            "snippet_aligned": [s >= threshold for s in snippet_scores]}


def media(folder: str) -> list[Path]:
    entries = sorted(external(folder, directory=True).iterdir(),
                     key=lambda p: (p.name.casefold(), p.name))
    if not entries or any(p.suffix.lower() not in EXTENSIONS for p in entries):
        raise Refusal()
    return [external(str(p)) for p in entries]


def main(argv: list[str] | None = None, *, output: TextIO | None = None,
         native_quiet: bool = False) -> int:
    output = output or sys.stdout
    rows: list[dict[str, Any]] = []
    with quiet_output(native=native_quiet):
        try:
            parser = Parser(description=__doc__)
            for name in ("blocks", "exports", "out"):
                parser.add_argument("--" + name, required=True)
            parser.add_argument("--intro-skip", type=float, default=0)
            parser.add_argument("--outro-skip", type=float, default=0)
            parser.add_argument("--threshold", type=float, default=.8)
            parser.add_argument("--join-tolerance", type=float, default=2.0)
            parser.add_argument("--acceptance-fraction", type=float, default=.9)
            args = parser.parse_args(argv)
            target = external(args.out, output=True)
            settings = config(os.environ.get("STAGEFLOW_KERNEL_CONFIG_PATH", ""))
            ffmpeg = ffmpeg_tool(settings.get("local_transcription", {}).get("ffmpeg_path")
                                 or settings.get("local_media_segmentation", {}).get("ffmpeg_path"))
            ffprobe = ffmpeg_tool(settings.get("local_media_timing", {}).get("ffprobe_path"))
            if ffmpeg is None or ffprobe is None:
                raise Refusal()
            block_paths, export_paths = media(args.blocks), media(args.exports)
            output_collisions([target], [*block_paths, *export_paths, ffmpeg, ffprobe,
                                         Path(os.environ["STAGEFLOW_KERNEL_CONFIG_PATH"])])
            blocks: list[tuple[float, float, Any]] = []
            for path in block_paths:
                metadata = probe(ffprobe, path)["format"]
                blocks.append((utc(metadata["tags"]["creation_time"]),
                               finite(metadata["duration"]), decode(ffmpeg, path)))
            runs = recording_runs(blocks, 8000, finite(args.join_tolerance))
            for ordinal, path in enumerate(export_paths):
                rows.append(align_export(decode(ffmpeg, path), runs, ordinal=ordinal,
                                         intro_skip=finite(args.intro_skip),
                                         outro_skip=finite(args.outro_skip),
                                         threshold=finite(args.threshold),
                                         acceptance_fraction=finite(args.acceptance_fraction)))
            write_json(target, rows)
        except Exception:
            rows = []
    # Times are permitted in the external truth artifact only, never on stdout.
    print(json.dumps([{"ordinal": r["ordinal"], "min_score": r["min_score"],
                       "consistent": r["consistent"], "aligned": r["status"] == "aligned",
                       "snippet_scores": r["snippet_scores"],
                       "accepted_fraction": r["accepted_fraction"],
                       "acceptance_fraction": r["acceptance_fraction"]} for r in rows]
                     if rows else {"error_count": 1}, allow_nan=False), file=output)
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main(native_quiet=True))
