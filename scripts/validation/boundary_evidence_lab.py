"""ED-0126 offline raw boundary separability, without fitting or production writes."""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO, cast

from boundary_evidence_common import (
    Parser,
    Refusal,
    command,
    config,
    decode,
    decode_chunks,
    digest,
    external,
    ffmpeg_tool,
    finite,
    key,
    local_path,
    np_module,
    output_collisions,
    quiet_output,
    tool,
    utc,
    write_json,
)
from boundary_evidence_features import (
    FEATURES,
    auc,
    distance,
    graphics,
    measurements,
    metadata,
    music,
    second_series,
)
from boundary_evidence_referee import MODELS, Referee, metrics

FAMILIES = (*FEATURES, "llm_referee")
FILTERS = {"audio_stats": ("aspectralstats", "ebur128", "astats", "ametadata"),
           "picture": ("scdet", "blackdetect", "metadata", "fps", "scale")}


def parse_manifest(raw: str, truth: Any = None) -> list[dict[str, Any]]:
    source = json.loads(raw)
    stages: list[dict[str, Any]] = []
    for ordinal, stage in enumerate(source["stages"]):
        spans: Any = stage.get("truth") if truth is None else (
            cast(list[Any], truth) if isinstance(truth, list)
            else truth["stages"][ordinal]["truth"])
        if spans is None:
            raise Refusal()
        if isinstance(truth, list) and len(source["stages"]) != 1:
            raise Refusal()
        spans = [(utc(s["start"]), utc(s["end"])) for s in spans]
        if any(start >= end for start, end in spans):
            raise Refusal()
        blocks = [{"path": external(b["path"]), "start": utc(b["start"])}
                  for b in stage["blocks"]]
        blocks.sort(key=lambda b: b["start"])
        if not blocks or len({b["start"] for b in blocks}) != len(blocks):
            raise Refusal()
        folder = stage.get("known_graphics")
        references = [] if not folder else [external(str(p)) for p in sorted(
            external(folder, directory=True).iterdir()) if p.suffix.lower() == ".png"]
        stages.append({"blocks": blocks, "truth": spans, "graphics": references,
                       "cues": [external(p) for p in stage.get("music_cues", [])]})
    if not stages:
        raise Refusal()
    return stages


def safe_rows(rows: Any, family: str) -> list[dict[str, Any]]:
    """Validate both new effects and cache reads; arbitrary keys never reach output."""
    allowed = {"second", "start", "end", *FEATURES[family]}
    if not isinstance(rows, list):
        raise Refusal()
    clean: list[dict[str, Any]] = []
    for raw_row in cast(list[Any], rows):
        if not isinstance(raw_row, dict):
            raise Refusal()
        row = cast(dict[str, Any], raw_row)
        if row.keys() - allowed:
            raise Refusal()
        if not ("second" in row or {"start", "end"} <= row.keys()):
            raise Refusal()
        converted = {k: finite(v) for k, v in row.items()}
        if converted.get("second", converted.get("start", 0)) < 0:
            raise Refusal()
        if "end" in converted and converted["end"] < converted["start"]:
            raise Refusal()
        clean.append(converted)
    return clean


class Effects:
    def __init__(self, settings: dict[str, Any], join_tolerance: float = 2.0) -> None:
        self.join_tolerance = finite(join_tolerance)
        if self.join_tolerance < 0:
            raise Refusal()
        self.settings = settings
        ffmpeg_path = (settings.get("local_transcription", {}).get("ffmpeg_path")
                       or settings.get("local_media_segmentation", {}).get("ffmpeg_path"))
        self.ffmpeg = ffmpeg_tool(ffmpeg_path)
        self.filters = (command([str(self.ffmpeg), "-hide_banner", "-filters"])
                        .decode("utf-8", "replace") if self.ffmpeg else "")
        self.engine: Any = None
        self.engine_identity: str | None = None
        self.binary_digest = digest(self.ffmpeg) if self.ffmpeg else None
        self.previous_embedding: Any = None
        self.previous_end: float | None = None

    def available(self, family: str) -> bool:
        if self.ffmpeg is None:
            return False
        if family in FILTERS and any(re.search(r"\b" + f + r"\b", self.filters) is None
                                     for f in FILTERS[family]):
            return False
        if family != "audio_stats":
            try:
                np_module()
            except ImportError:
                return False
        if family in {"whisper", "voice_continuity", "llm_referee"}:
            try:
                self.load_engine()
            except Exception:
                return False
        return True

    def load_engine(self) -> Any:
        if self.engine is None:
            options = self.settings["local_transcription"]
            path = local_path(options["model_path"], directory=True)
            module = importlib.import_module(
                "app.infrastructure.transcription.ctranslate2_whisper.engine")
            device = options.get("device", "cuda")
            if device not in {"cpu", "cuda"}:
                raise Refusal()
            self.engine = module.load_engine(str(path), device=device,
                                             compute_type="int8" if device == "cpu" else "float16")
            files = sorted(p for p in path.iterdir() if p.is_file())
            self.engine_identity = key([digest(p) for p in files], device)
        return self.engine

    def identity(self, family: str, stage: dict[str, Any]) -> str:
        model_identity = self.engine_identity if family in {"whisper", "voice_continuity"} else None
        return key(family, self.binary_digest, model_identity,
                   [digest(p) for p in stage["graphics"]] if family == "picture" else [],
                   [digest(p) for p in stage["cues"]] if family == "music_cue" else [], .8,
                   self.join_tolerance if family == "voice_continuity" else None)

    def frames(self, path: Path, *, reference: bool = False) -> Any:
        assert self.ffmpeg
        args = [str(self.ffmpeg), "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                "-i", str(path), "-an", "-vf",
                ("" if reference else "fps=1,") + "scale=64:36,format=gray"]
        if reference:
            args += ["-frames:v", "1"]
        raw = command([*args, "-f", "rawvideo", "pipe:1"])
        return np_module().frombuffer(raw, dtype="uint8").reshape(-1, 36, 64)

    def extract(self, family: str, path: Path, stage: dict[str, Any]) -> list[dict[str, Any]]:
        assert self.ffmpeg
        if family in {"audio_stats", "picture"}:
            audio = family == "audio_stats"
            filters = ("aformat=channel_layouts=mono,aspectralstats,ebur128=metadata=1,"
                       "astats=metadata=1:reset=1,ametadata=mode=print:file=-" if audio else
                       "scdet,blackdetect=d=0,metadata=mode=print:file=-")
            raw = command([str(self.ffmpeg), "-nostdin", "-v", "error", "-protocol_whitelist",
                           "file,pipe", "-i", str(path), "-map", "0:a:0" if audio else "0:v:0",
                           "-vn" if audio else "-an", "-af" if audio else "-vf", filters,
                           "-f", "null", "-"])
            rows = metadata(raw.decode("utf-8", "replace"), family)
            if not audio and stage["graphics"]:
                refs = [self.frames(p, reference=True)[0] for p in stage["graphics"]]
                similarities = graphics(self.frames(path), refs)
                indexed = {r["second"]: r for r in rows}
                for row in similarities:
                    indexed.setdefault(row["second"], {"second": row["second"]}).update(row)
                rows = [indexed[s] for s in sorted(indexed)]
            return rows
        if family == "music_cue":
            references = [decode(self.ffmpeg, p) for p in stage["cues"]]
            overlap = max((len(r) for r in references), default=0)
            rows: list[dict[str, Any]] = []
            for start, audio in decode_chunks(self.ffmpeg, path, overlap):
                rows.extend({**r, "second": r["second"] + start / 8000}
                            for r in music(audio, references) if r["second"] < 60)
            return rows
        raise Refusal()

    def whisper(self, path: Path, start: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                                            list[dict[str, Any]]]:
        assert self.ffmpeg
        engine, audio = self.load_engine(), decode(self.ffmpeg, path, 16000)
        rows: list[dict[str, Any]] = []
        continuity: list[dict[str, Any]] = []
        words: list[dict[str, Any]] = []
        previous = (self.previous_embedding if self.previous_end is not None
                    and abs(start - self.previous_end) <= self.join_tolerance else None)
        for offset in range(0, len(audio), 160000):
            window = audio[offset:offset + 160000]
            observation = engine.inspect_window(window)
            at = offset / 16000
            if previous is not None:
                value = distance(previous, observation["embedding"])
                if value is not None:
                    continuity.append({"second": at, "cosine_distance": value})
            previous = observation["embedding"]
            for segment in observation["segments"]:
                segment_start = at + max(0, finite(segment["start"]))
                end = min(at + len(window) / 16000, at + finite(segment["end"]))
                if segment_start < end:
                    rows.append({"start": segment_start, "end": end,
                                 **{f: segment[f] for f in FEATURES["whisper"]}})
                for word in segment["words"]:
                    if 0 <= word.start <= word.end <= len(window) / 16000:
                        words.append({"start": at + word.start, "end": at + word.end,
                                      "text": word.word})
        self.previous_embedding, self.previous_end = previous, start + len(audio) / 16000
        return rows, continuity, words


def evaluate_groups(records: list[dict[str, Any]],
                    stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """UTC calendar-day splits, anonymous ordinal identifiers; pooled raw observations."""
    buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for stage_id, stage in enumerate(stages):
        days = stage_days(stage, [r for r in records if r["stage_ordinal"] == stage_id])
        for day_id, day in enumerate(days):
            beginning = utc(day + "T00:00:00Z")
            buckets[stage_id, day] = {"stage_ordinal": stage_id, "day_ordinal": day_id,
                                      "origin": beginning, "series": defaultdict(list),
                                      "start": [a - beginning for a, _ in stage["truth"]
                                                if beginning <= a < beginning + 86400],
                                      "end": [b - beginning for _, b in stage["truth"]
                                              if beginning <= b < beginning + 86400],
                                      "start_labels": [a - beginning for a, _ in stage["truth"]
                                                       if -120 <= a - beginning <= 86520],
                                      "end_labels": [b - beginning for _, b in stage["truth"]
                                                     if -120 <= b - beginning <= 86520],
                                      "all_edges": [t - beginning for span in stage["truth"]
                                                    for t in span
                                                    if -120 <= t - beginning <= 86520]}
    for record in records:
        if record["status"] != "ok" or record["family"] not in FEATURES:
            continue
        for feature in FEATURES[record["family"]]:
            if feature.endswith("ordinal"):
                continue
            for offset, value in second_series(record["rows"], feature):
                at = record["start"] + offset
                day = datetime.fromtimestamp(at, UTC).date().isoformat()
                bucket = buckets.get((record["stage_ordinal"], day))
                if bucket is not None:
                    bucket["series"][record["family"], feature].append(
                        (at - bucket["origin"], value))
    reports: list[dict[str, Any]] = []
    samples: dict[tuple[str, str, str], dict[tuple[int, int],
                 tuple[list[float], list[float]]]] = defaultdict(dict)
    pooled: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    pooled_peaks: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    pooled_edges: dict[str, list[float]] = {"start": [], "end": [], "all_edges": [],
                                          "start_labels": [], "end_labels": []}
    for group_id, bucket in enumerate(buckets.values()):
        shift = group_id * 1000000
        for role in pooled_edges:
            pooled_edges[role].extend(t + shift for t in bucket[role])
        feature_keys = {pair for other in buckets.values()
                        if other["stage_ordinal"] == bucket["stage_ordinal"]
                        for pair in other["series"]}
        for family, feature in sorted(feature_keys):
            series = bucket["series"].get((family, feature), [])
            by_second: dict[float, list[float]] = defaultdict(list)
            for at, value in series:
                by_second[at].append(value)
            series = [(at, sum(values) / len(values)) for at, values in sorted(by_second.items())]
            # A calendar split must not clip an edge's +/-120 s peak neighborhood.
            halo: dict[float, list[float]] = defaultdict(list)
            for neighbor in buckets.values():
                if neighbor["stage_ordinal"] != bucket["stage_ordinal"]:
                    continue
                delta = neighbor["origin"] - bucket["origin"]
                for at, value in neighbor["series"].get((family, feature), []):
                    if -120 <= at + delta <= 86520:
                        halo[at + delta].append(value)
            peaks = [(at, sum(values) / len(values)) for at, values in sorted(halo.items())]
            pooled[family, feature].extend((t + shift, v) for t, v in series)
            pooled_peaks[family, feature].extend((t + shift, v) for t, v in peaks)
            for role in ("start", "end"):
                samples[family, feature, role][bucket["stage_ordinal"], bucket["day_ordinal"]] = (
                    [v for t, v in series
                     if any(abs(t - e) <= 15 for e in bucket[role + "_labels"])],
                    [v for t, v in series
                     if all(abs(t - e) > 120 for e in bucket["all_edges"])])
                reports.append({"scope": "stage_day", "stage_ordinal": bucket["stage_ordinal"],
                                "day_ordinal": bucket["day_ordinal"], "family": family,
                                "feature": feature, "role": role, "direction_scope": "stage_day",
                                **measurements(series, bucket[role], bucket["all_edges"],
                                               peak_series=peaks,
                                               label_edges=bucket[role + "_labels"])})
    for report in reports:
        others = [values for group, values in samples[
            report["family"], report["feature"], report["role"]].items()
            if group != (report["stage_ordinal"], report["day_ordinal"])]
        training_auc = auc([v for positive, _ in others for v in positive],
                           [v for _, negative in others for v in negative])
        direction = (None if training_auc is None else
                     "lower" if training_auc < .5 else "higher")
        score = report["auc"]
        report["held_out_direction"] = direction
        report["held_out_separability"] = (None if direction is None or score is None else
                                           1 - score if direction == "lower" else score)
    for (family, feature), series in sorted(pooled.items()):
        for role in ("start", "end"):
            reports.append({"scope": "pooled", "family": family, "feature": feature, "role": role,
                            "direction_scope": "all_stage_days",
                            **measurements(series, pooled_edges[role], pooled_edges["all_edges"],
                                           peak_series=pooled_peaks[family, feature],
                                           label_edges=pooled_edges[role + "_labels"])})
    return reports


def stage_days(stage: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    dates = {datetime.fromtimestamp(t, UTC).date().isoformat()
             for span in stage["truth"] for t in span}
    dates.update(datetime.fromtimestamp(b["start"], UTC).date().isoformat()
                 for b in stage["blocks"])
    for record in records:
        for row in record["rows"]:
            for offset in (row.get("second", row.get("start", 0)),
                           row.get("end", row.get("second", 0))):
                dates.add(datetime.fromtimestamp(record["start"] + offset, UTC).date().isoformat())
    return sorted(dates)


def negative_points(records: list[dict[str, Any]], stage_id: int,
                    edges: list[float], count: int) -> list[float]:
    # Rank within each raw feature so unlike units do not dominate. No fitting.
    if count <= 0:
        return []
    candidates: dict[float, float] = {}
    for record in records:
        if record["stage_ordinal"] != stage_id or record["status"] != "ok":
            continue
        for feature in FEATURES.get(record["family"], ()):
            if feature.endswith("ordinal"):
                continue
            series = [(record["start"] + t, v) for t, v in second_series(record["rows"], feature)]
            ordered = sorted(series, key=lambda p: (p[1], -p[0]))
            for rank, (at, _) in enumerate(ordered):
                if all(abs(at - edge) > 120 for edge in edges):
                    candidates[at] = max(candidates.get(at, 0), (rank + 1) / len(ordered))
    selected: list[float] = []
    for at in sorted(candidates, key=lambda t: (-candidates[t], t)):
        if all(abs(at - prior) > 30 for prior in selected):
            selected.append(at)
            if len(selected) == count:
                break
    return selected


def run(stages: list[dict[str, Any]], families: list[str], cache: Path,
        effects: Any, referee: Any = None) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    private_words: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for stage_id, stage in enumerate(stages):
        effects.previous_embedding, effects.previous_end = None, None
        previous_block: tuple[str, float] | None = None
        for block_id, block in enumerate(stage["blocks"]):
            block_digest = digest(block["path"])
            whisper_result = None
            whisper_seconds = 0.0
            for family in families:
                if family == "llm_referee":
                    continue
                began = time.perf_counter()
                record: dict[str, Any] = {"stage_ordinal": stage_id, "block_ordinal": block_id,
                                          "family": family, "start": block["start"], "rows": []}
                try:
                    if not effects.available(family) or family == "music_cue" and not stage["cues"]:
                        record["status"] = "skipped"
                    else:
                        cache_key = key(block_digest, effects.identity(family, stage))
                        if family == "voice_continuity":
                            cache_key = key(cache_key, previous_block, block["start"])
                        target = external(str(cache / (cache_key + ".json")), output=True)
                        # Never cache embeddings or transcript. Whisper runs again when words are
                        # needed, and continuity can only be derived from adjacent live vectors.
                        if family in {"whisper", "voice_continuity"}:
                            if whisper_result is None:
                                whisper_began = time.perf_counter()
                                whisper_result = effects.whisper(block["path"], block["start"])
                                whisper_seconds = time.perf_counter() - whisper_began
                                private_words[stage_id].extend(
                                    {**w, "start": w["start"] + block["start"],
                                     "end": w["end"] + block["start"]} for w in whisper_result[2])
                            raw = whisper_result[0 if family == "whisper" else 1]
                            record["cache_hit"] = False
                            record["shared_extraction_seconds"] = whisper_seconds
                        elif target.exists():
                            raw = json.loads(target.read_text(encoding="utf-8"))
                            record["cache_hit"] = True
                        else:
                            raw = effects.extract(family, block["path"], stage)
                            record["cache_hit"] = False
                        record["rows"] = safe_rows(raw, family)
                        record["status"] = "ok" if record["rows"] else "skipped"
                        if record["status"] == "ok" and not record["cache_hit"]:
                            write_json(target, record["rows"])
                except Exception:
                    record["status"] = "failed"
                    record["rows"] = []
                record["runtime_seconds"] = time.perf_counter() - began
                records.append(record)
            if "llm_referee" in families and whisper_result is None:
                began = time.perf_counter()
                try:
                    if not effects.available("llm_referee"):
                        raise Refusal()
                    _, _, words = effects.whisper(block["path"], block["start"])
                    private_words[stage_id].extend({**w, "start": w["start"] + block["start"],
                                                   "end": w["end"] + block["start"]} for w in words)
                    status = "ok"
                except Exception:
                    status = "skipped"
                records.append({"stage_ordinal": stage_id, "block_ordinal": block_id,
                                "family": "llm_referee", "status": status, "rows": [],
                                "start": block["start"],
                                "runtime_seconds": time.perf_counter() - began})
            previous_block = (block_digest, block["start"])
        effects.previous_embedding, effects.previous_end = None, None
    referee_rows: list[dict[str, Any]] = []
    if "llm_referee" in families:
        for stage_id, stage in enumerate(stages):
            edges = [t for span in stage["truth"] for t in span]
            days = stage_days(stage, [r for r in records if r["stage_ordinal"] == stage_id])
            negatives = negative_points(records, stage_id, edges, len(edges))
            points = [(at, role, False) for span in stage["truth"]
                      for at, role in zip(span, ("start", "end"), strict=True)]
            points += [(at, "start" if i % 2 == 0 else "end", True)
                       for i, at in enumerate(negatives)]
            # Missing negatives are explicit skipped slots, not a smaller perfect sample.
            points += [(0.0, "start" if i % 2 == 0 else "end", True)
                       for i in range(len(negatives), len(edges))]
            for ordinal, (at, role, negative) in enumerate(points):
                began = time.perf_counter()
                block_id = max((i for i, b in enumerate(stage["blocks"]) if b["start"] <= at),
                               default=0)
                stamp = at or stage["blocks"][0]["start"]
                day = datetime.fromtimestamp(stamp, UTC).date().isoformat()
                row: dict[str, Any] = {"stage_ordinal": stage_id, "ordinal": ordinal, "role": role,
                       "day_ordinal": days.index(day), "block_ordinal": block_id,
                       "negative": negative, "absolute_error": None, "no_edge": False}
                try:
                    if referee is None or at == 0 or not private_words[stage_id]:
                        row["status"] = "skipped"
                    else:
                        selected = referee.evaluate(private_words[stage_id], at, role, ordinal)
                        row.update(status="ok", no_edge=selected is None,
                                   absolute_error=abs(selected - at)
                                   if selected is not None and not negative else None)
                except Exception:
                    row["status"] = "failed"
                row["runtime_seconds"] = time.perf_counter() - began
                referee_rows.append(row)
                runtime_record: dict[str, Any] | None = next(
                    (r for r in records if r["stage_ordinal"] == stage_id
                     and r["block_ordinal"] == block_id and r["family"] == "llm_referee"), None)
                if runtime_record is None:
                    runtime_record = {"stage_ordinal": stage_id, "block_ordinal": block_id,
                                      "family": "llm_referee", "rows": [],
                                      "start": stage["blocks"][block_id]["start"],
                                      "runtime_seconds": 0, "status": row["status"]}
                    records.append(runtime_record)
                runtime_record["runtime_seconds"] += row["runtime_seconds"]
                if row["status"] != "ok":
                    runtime_record["status"] = row["status"]
    separability = evaluate_groups(records, stages)
    for record in records:
        del record["start"]  # Public series use block-relative offsets only.
    referee_metrics = [{"scope": "pooled", "role": role,
                        **metrics([r for r in referee_rows if r["role"] == role])}
                       for role in ("start", "end")]
    for stage_id, day_id in sorted({(r["stage_ordinal"], r["day_ordinal"]) for r in referee_rows}):
        for role in ("start", "end"):
            referee_metrics.append({"scope": "stage_day", "stage_ordinal": stage_id,
                                    "day_ordinal": day_id, "role": role,
                                    **metrics([r for r in referee_rows if r["role"] == role
                                               and r["stage_ordinal"] == stage_id
                                               and r["day_ordinal"] == day_id])})
    return {"version": 1, "peak_radius_seconds": 120, "positive_radius_seconds": 15,
            "negative_exclusion_seconds": 120, "records": records, "separability": separability,
            "llm_referee": {"status": "ok" if referee else "skipped",
                            "model_sha256": referee.checksum if referee else None,
                            "runtime_version": referee.version if referee else None,
                            "rows": referee_rows,
                            "metrics": referee_metrics}}


def markdown(report: dict[str, Any]) -> str:
    lines = ["# Boundary evidence lab", "", "Raw scores only; no fitting or tuning.", "",
             "Peak search: +/-120 s; earliest timestamp wins ties. Positive: +/-15 s; "
             "negative: more than 120 s from any edge. UTC calendar-day splits.", "",
             "Rank families by held-out separability; pooled direction uses all stage-days.", "",
             "| Scope | Stage | Day | Family | Feature | Role | AUC | Direction | "
             "Direction scope | "
             "Separability | Held-out direction | Held-out separability | "
             "Hit 10 | Hit 30 | Lag |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | "
             "--- | --- | --- |"]
    for r in report["separability"]:
        lines.append("| " + " | ".join(str(r.get(k, "")) for k in (
            "scope", "stage_ordinal", "day_ordinal", "family", "feature", "role", "auc",
            "direction", "direction_scope", "separability", "held_out_direction",
            "held_out_separability", "hit_10", "hit_30", "median_lag")) + " |")
    lines += ["", "| Stage | Block | Family | Status | Runtime seconds |",
              "| --- | --- | --- | --- | --- |"]
    for r in report["records"]:
        lines.append("| " + " | ".join(str(r[k]) for k in (
            "stage_ordinal", "block_ordinal", "family", "status", "runtime_seconds")) + " |")
    lines += ["", "## Referee", "", "```json", json.dumps(report["llm_referee"], indent=2), "```"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, output: TextIO | None = None,
         native_quiet: bool = False) -> int:
    output = output or sys.stdout
    report: dict[str, Any] = {"error_count": 1}
    with quiet_output(native=native_quiet):
        try:
            parser = Parser(description=__doc__)
            for name in ("manifest", "cache", "out", "markdown-out"):
                parser.add_argument("--" + name, required=True)
            parser.add_argument("--truth")
            parser.add_argument("--join-tolerance", type=float, default=2.0)
            for family in FAMILIES:
                parser.add_argument("--" + family.replace("_", "-"), action="store_true")
            parser.add_argument("--llm-binary")
            parser.add_argument("--llm-model")
            parser.add_argument("--llm-sha256")
            parser.add_argument("--llm-model-family", choices=MODELS)
            args = parser.parse_args(argv)
            manifest = external(args.manifest)
            cache = external(args.cache, directory=True)
            target = external(args.out, output=True)
            md_target = external(args.markdown_out, output=True)
            if target == md_target or manifest in {target, md_target}:
                raise Refusal()
            truth = (json.loads(external(args.truth).read_text(encoding="utf-8"))
                     if args.truth else None)
            stages = parse_manifest(manifest.read_text(encoding="utf-8"), truth)
            families = [f for f in FAMILIES if getattr(args, f)]
            if not families:
                raise Refusal()
            settings = config(os.environ.get("STAGEFLOW_KERNEL_CONFIG_PATH", ""))
            inputs = [manifest, Path(os.environ["STAGEFLOW_KERNEL_CONFIG_PATH"])]
            if args.truth:
                inputs.append(external(args.truth))
            for stage in stages:
                inputs.extend(b["path"] for b in stage["blocks"])
                inputs.extend([*stage["graphics"], *stage["cues"]])
            for value in (args.llm_binary, args.llm_model):
                if value:
                    inputs.append(Path(value))
            for section, name in (("local_transcription", "ffmpeg_path"),
                                  ("local_media_segmentation", "ffmpeg_path"),
                                  ("local_media_timing", "ffprobe_path")):
                if settings.get(section, {}).get(name):
                    inputs.append(Path(settings[section][name]))
            model_path = settings.get("local_transcription", {}).get("model_path")
            if model_path:
                model_root = Path(model_path).resolve()
                if any(p.is_relative_to(model_root) for p in (target, md_target, cache)):
                    raise Refusal()
            output_collisions([target, md_target], inputs)
            referee = None
            if args.llm_referee and args.llm_binary:
                binary = tool(args.llm_binary)
                if binary is not None:
                    referee = Referee(binary, external(args.llm_model), args.llm_sha256,
                                      args.llm_model_family, cache)
            try:
                effects = Effects(settings, finite(args.join_tolerance))
                report = run(stages, families, cache, effects, referee)
            finally:
                if referee is not None:
                    referee.close()
            write_json(target, report)
            md_target.write_text(markdown(report), encoding="utf-8")
        except Exception:
            report = {"error_count": 1}
    print(json.dumps(report, allow_nan=False), file=output)
    return 1 if "error_count" in report else 0


if __name__ == "__main__":
    raise SystemExit(main(native_quiet=True))
