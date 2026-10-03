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

SILENCE_LEVEL = 1e-3


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


def trim_padding(audio: Any, rate: int) -> tuple[Any, float]:
    np = np_module()
    end = len(audio)
    while end:
        left = max(0, end - 65536)
        audible = np.flatnonzero(np.abs(audio[left:end]) > SILENCE_LEVEL)
        if len(audible):
            end = left + int(audible[-1]) + 1
            break
        end = left
    return audio[:end], (len(audio) - end) / rate


def endpoint_anchor(audio: Any, runs: list[Run], rate: int, start: int, end: int,
                    threshold: float, *, from_end: bool,
                    initial: tuple[float, float, int] | None = None,
                    ) -> tuple[float, float, int] | None:
    """Search globally inward; keep the first passing snippet, otherwise the best."""
    best: tuple[float, float, int] | None = None
    for step in range(9):
        offset = step * 15 * rate
        position = end - offset - 10 * rate if from_end else start + offset
        if position < start or position + 10 * rate > end:
            break
        at, score, run = (initial if step == 0 and initial is not None else
                          locate(audio[position:position + 10 * rate], runs, rate))
        if run < 0:
            continue
        mapped = at + (end - position) / rate if from_end else at - offset / rate
        if best is None or score > best[1]:
            best = (mapped, score, run)
        if score >= threshold:
            break
    return best


def align_export(audio: Any, runs: list[Run], *, ordinal: int, rate: int = 8000,
                 intro_skip: float = 0, outro_skip: float = 0,
                 threshold: float = .8, acceptance_fraction: float = .9,
                 min_segment_seconds: float = 2.0, min_span_ratio: float = .85,
                 max_span_ratio: float = 1.10, anchor_cut_score: float = .9,
                 anchor_max_cut_ratio: float = 1.5, anchor_length_score: float = .4,
                 anchor_length_tolerance: float = .01) -> dict[str, Any]:
    """Five global anchors, then local tracking; quarter-second support per segment."""
    if (not 0 < threshold <= 1 or not 0 < acceptance_fraction <= 1
            or min(intro_skip, outro_skip) < 0
            or finite(min_segment_seconds) <= 0
            or not 0 < finite(min_span_ratio) <= finite(max_span_ratio)
            or not 0 < finite(anchor_cut_score) <= 1
            or not 0 < finite(anchor_length_score) <= 1
            or finite(anchor_max_cut_ratio) <= 0
            or finite(anchor_length_tolerance) < 0):
        raise Refusal()
    audio, padding_seconds = trim_padding(audio, rate)
    start, end = round(intro_skip * rate), len(audio) - round(outro_skip * rate)
    if end - start < 10 * rate:
        raise Refusal()
    anchors: list[tuple[int, float, float, int]] = []
    for fraction in (0, .15, .5, .85, 1):
        position = start + round((end - start - 10 * rate) * fraction)
        at, score, run = locate(audio[position:position + 10 * rate], runs, rate)
        anchors.append((position, at, score, run))
    start_anchor = endpoint_anchor(audio, runs, rate, start, end, threshold, from_end=False,
                                   initial=anchors[0][1:])
    end_anchor = endpoint_anchor(audio, runs, rate, start, end, threshold, from_end=True,
                                 initial=anchors[-1][1:])
    anchor_ratio = None
    if (start_anchor is not None and end_anchor is not None and start_anchor[2] == end_anchor[2]
            and runs[start_anchor[2]].start <= start_anchor[0] < end_anchor[0]
            <= runs[start_anchor[2]].start + len(runs[start_anchor[2]].audio) / rate + 1 / rate):
        anchor_ratio = (end_anchor[0] - start_anchor[0]) / ((end - start) / rate)
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
    merged: list[list[tuple[int, int, float, float, int]]] = []
    noise: set[int] = set()
    pending_noise: list[tuple[int, int, float, float, int]] = []
    for group in groups:
        if (group[-1][1] - group[0][0]) / rate < min_segment_seconds:
            noise.update(p[0] for p in group)
            pending_noise.extend(group)
            continue
        first = group[0]
        prior = merged[-1][-1] if merged else None
        if (prior is not None and first[4] == prior[4]
                and abs(first[2] - prior[2] - (first[0] - prior[0]) / rate) <= .05):
            merged[-1].extend(pending_noise)
            merged[-1].extend(group)
        else:
            merged.append(group.copy())
        pending_noise = []

    def accepted_piece(piece: tuple[int, int, float, float, int]) -> bool:
        # Even high-scoring mislocations are unsupported once filtered as noise.
        return piece[0] not in noise and piece[3] >= threshold

    # Include intervening noise in the denominator, never in the accepted evidence.
    fractions = [sum(accepted_piece(p) for p in g) / len(g) for g in merged]
    supported = [g for g, fraction in zip(merged, fractions, strict=True)
                 if fraction >= acceptance_fraction
                 and g[0][2] >= runs[g[0][4]].start
                 and g[-1][2] + (g[-1][1] - g[-1][0]) / rate
                 <= runs[g[-1][4]].start + len(runs[g[-1][4]].audio) / rate + 1 / rate]
    segments = [{"start": iso(g[0][2]),
                 "end": iso(g[-1][2] + (g[-1][1] - g[-1][0]) / rate),
                 "accepted_fraction": sum(accepted_piece(p) for p in g) / len(g)}
                for g in supported]
    coverage = (sum(p[0] not in noise for g in supported for p in g) / len(pieces)
                if pieces else 0.0)
    span_ratio = ((supported[-1][-1][2]
                   + (supported[-1][-1][1] - supported[-1][-1][0]) / rate
                   - supported[0][0][2]) / ((end - start) / rate) if supported else None)
    aligned = (coverage >= acceptance_fraction and span_ratio is not None
               and min_span_ratio <= span_ratio <= max_span_ratio)
    row = {"ordinal": ordinal, "start": segments[0]["start"] if aligned else None,
            "end": segments[-1]["end"] if aligned else None, "segments": segments,
            "span_start": segments[0]["start"] if segments else None,
            "span_end": segments[-1]["end"] if segments else None,
            "coverage": coverage, "span_ratio": span_ratio,
            "min_score": min(p[3] for p in pieces) if aligned else min(snippet_scores),
            "acceptance_fraction": acceptance_fraction,
            "accepted_fraction": sum(accepted_piece(p) for p in pieces) / len(pieces)
            if pieces else 0.0,
            "consistent": aligned and len(supported) == 1,
            "status": "aligned" if aligned else "unaligned", "snippet_scores": snippet_scores,
            "snippet_aligned": [s >= threshold for s in snippet_scores],
            "padding_seconds": padding_seconds,
            "anchor_start": iso(start_anchor[0]) if start_anchor is not None else None,
            "anchor_end": iso(end_anchor[0]) if end_anchor is not None else None,
            "anchor_start_score": start_anchor[1] if start_anchor is not None else None,
            "anchor_end_score": end_anchor[1] if end_anchor is not None else None,
            "anchor_span_ratio": anchor_ratio, "anchor_rule": None, "duplicate_of": None}
    rule = None
    if (not aligned and anchor_ratio is not None
            and start_anchor is not None and end_anchor is not None):
        low = min(start_anchor[1], end_anchor[1])
        if low >= threshold and min_span_ratio <= anchor_ratio <= max_span_ratio:
            rule = "fit"
        elif low >= anchor_cut_score and max_span_ratio < anchor_ratio <= anchor_max_cut_ratio:
            rule = "cut"
        elif low >= anchor_length_score and abs(anchor_ratio - 1) <= anchor_length_tolerance:
            rule = "length"
    if rule is not None:
        row.update(status="anchored", start=row["anchor_start"], end=row["anchor_end"],
                   anchor_rule=rule)
    return row


def failed_row(ordinal: int, acceptance_fraction: float,
               padding_seconds: float = 0.0) -> dict[str, Any]:
    return {"ordinal": ordinal, "status": "error", "start": None, "end": None,
            "span_start": None, "span_end": None, "coverage": 0.0, "span_ratio": None,
            "segments": [], "min_score": 0.0, "consistent": False, "snippet_scores": [],
            "accepted_fraction": 0.0, "acceptance_fraction": acceptance_fraction,
            "snippet_aligned": [], "padding_seconds": padding_seconds,
            "anchor_start": None, "anchor_end": None, "anchor_start_score": None,
            "anchor_end_score": None, "anchor_span_ratio": None, "anchor_rule": None,
            "duplicate_of": None}


def row_start(row: dict[str, Any]) -> float:
    return utc(row["start"])


def collapse_sessions(rows: list[dict[str, Any]], seconds: float = 5.0) -> None:
    if finite(seconds) < 0:
        raise Refusal()
    groups: list[list[dict[str, Any]]] = []
    for row in rows:
        row["duplicate_of"] = None
    accepted = sorted((r for r in rows if r["status"] in ("aligned", "anchored")), key=row_start)
    for row in accepted:
        if not groups or row_start(row) - row_start(groups[-1][0]) > seconds:
            groups.append([])
        groups[-1].append(row)

    def rank(row: dict[str, Any]) -> tuple[float, int]:
        ratio = row["span_ratio"] if row["status"] == "aligned" else row["anchor_span_ratio"]
        return abs(ratio - 1), row["ordinal"]

    for group in groups:
        kept = min(group, key=rank)
        for row in group:
            if row is not kept:
                row["duplicate_of"] = kept["ordinal"]


def media(folder: str) -> list[Path]:
    entries = sorted(external(folder, directory=True).iterdir(),
                     key=lambda p: (p.name.casefold(), p.name))
    if not entries or any(p.suffix.lower() not in EXTENSIONS for p in entries):
        raise Refusal()
    return [external(str(p)) for p in entries]


def rows_with_spans(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r["status"] in ("aligned", "anchored")
            and r["duplicate_of"] is None]


def main(argv: list[str] | None = None, *, output: TextIO | None = None,
         native_quiet: bool = False) -> int:
    output = output or sys.stdout
    rows: list[dict[str, Any]] = []
    with quiet_output(native=native_quiet):
        try:
            parser = Parser(description=__doc__)
            for name in ("blocks", "exports", "out"):
                parser.add_argument("--" + name, required=True)
            parser.add_argument("--spans-out")
            parser.add_argument("--intro-skip", type=float, default=0)
            parser.add_argument("--outro-skip", type=float, default=0)
            parser.add_argument("--threshold", type=float, default=.8)
            parser.add_argument("--join-tolerance", type=float, default=2.0)
            parser.add_argument("--acceptance-fraction", type=float, default=.9)
            parser.add_argument("--min-segment-seconds", type=float, default=2.0)
            parser.add_argument("--min-span-ratio", type=float, default=.85)
            parser.add_argument("--max-span-ratio", type=float, default=1.10)
            parser.add_argument("--anchor-cut-score", type=float, default=.9)
            parser.add_argument("--anchor-max-cut-ratio", type=float, default=1.5)
            parser.add_argument("--anchor-length-score", type=float, default=.4)
            parser.add_argument("--anchor-length-tolerance", type=float, default=.01)
            parser.add_argument("--collapse-seconds", type=float, default=5.0)
            args = parser.parse_args(argv)
            target = external(args.out, output=True)
            spans_target = (external(args.spans_out, output=True)
                            if args.spans_out is not None else None)
            collapse_seconds = finite(args.collapse_seconds)
            if collapse_seconds < 0:
                raise Refusal()
            settings = config(os.environ.get("STAGEFLOW_KERNEL_CONFIG_PATH", ""))
            ffmpeg = ffmpeg_tool(settings.get("local_transcription", {}).get("ffmpeg_path")
                                 or settings.get("local_media_segmentation", {}).get("ffmpeg_path"))
            ffprobe = ffmpeg_tool(settings.get("local_media_timing", {}).get("ffprobe_path"))
            if ffmpeg is None or ffprobe is None:
                raise Refusal()
            block_paths, export_paths = media(args.blocks), media(args.exports)
            output_collisions([target, spans_target] if spans_target is not None else [target],
                              [*block_paths, *export_paths, ffmpeg, ffprobe,
                               Path(os.environ["STAGEFLOW_KERNEL_CONFIG_PATH"])])
            blocks: list[tuple[float, float, Any]] = []
            for path in block_paths:
                metadata = probe(ffprobe, path)["format"]
                blocks.append((utc(metadata["tags"]["creation_time"]),
                               finite(metadata["duration"]), decode(ffmpeg, path)))
            runs = recording_runs(blocks, 8000, finite(args.join_tolerance))
            for ordinal, path in enumerate(export_paths):
                # One failing export (decode error, malformed media) must not discard the
                # day's other alignments; it is recorded as a closed error status instead.
                padding_seconds = 0.0
                try:
                    audio, padding_seconds = trim_padding(decode(ffmpeg, path), 8000)
                    row = align_export(
                        audio, runs, ordinal=ordinal,
                        intro_skip=finite(args.intro_skip), outro_skip=finite(args.outro_skip),
                        threshold=finite(args.threshold),
                        acceptance_fraction=finite(args.acceptance_fraction),
                        min_segment_seconds=finite(args.min_segment_seconds),
                        min_span_ratio=finite(args.min_span_ratio),
                        max_span_ratio=finite(args.max_span_ratio),
                        anchor_cut_score=finite(args.anchor_cut_score),
                        anchor_max_cut_ratio=finite(args.anchor_max_cut_ratio),
                        anchor_length_score=finite(args.anchor_length_score),
                        anchor_length_tolerance=finite(args.anchor_length_tolerance))
                    row["padding_seconds"] = padding_seconds
                    rows.append(row)
                except Exception:
                    rows.append(failed_row(ordinal, finite(args.acceptance_fraction),
                                           padding_seconds))
            collapse_sessions(rows, collapse_seconds)
            write_json(target, rows)
            if spans_target is not None:
                write_json(spans_target, [{"start": r["start"], "end": r["end"]}
                                         for r in sorted(rows_with_spans(rows), key=row_start)])
        except Exception:
            rows = []
    # Times are permitted in the external truth artifact only, never on stdout.
    print(json.dumps([{"ordinal": r["ordinal"], "min_score": r["min_score"],
                       "consistent": r["consistent"], "aligned": r["status"] == "aligned",
                       "anchored": r["status"] == "anchored",
                       "padding_seconds": r["padding_seconds"],
                       "anchor_start_score": r["anchor_start_score"] or 0.0,
                       "anchor_end_score": r["anchor_end_score"] or 0.0,
                       "anchor_span_ratio": r["anchor_span_ratio"] or 0.0,
                       "duplicate": r["duplicate_of"] is not None,
                       "snippet_scores": r["snippet_scores"],
                       "accepted_fraction": r["accepted_fraction"],
                       "acceptance_fraction": r["acceptance_fraction"]} for r in rows]
                     if rows else {"error_count": 1}, allow_nan=False), file=output)
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main(native_quiet=True))
