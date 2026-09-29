"""Explicit sanitized lineage serialization shared by persistence and API adapters."""
from dataclasses import asdict
from datetime import datetime
from typing import Any

from app.contexts.editorial.derivation_contracts import TimingQualification
from app.contexts.production.media_segmentation_evidence.contracts import SegmentationInterval
from app.shared.ids import EntityId

from .contracts import (
    AssetInput,
    Candidate,
    EdgeKind,
    Reference,
    Span,
    Strength,
)
from .service import reference_document


def reference(value: dict[str, Any] | None) -> Reference | None:
    return None if value is None else Reference(EntityId(value["id"]), value["revision"])


def references(values: list[dict[str, Any]]) -> tuple[Reference, ...]:
    return tuple(Reference(EntityId(x["id"]), x["revision"]) for x in values)


def asset_document(x: AssetInput) -> dict[str, object]:
    return {
        "asset_id": x.asset_id.value, "timing": reference_document(x.timing),
        "coverage": None if x.coverage is None else [
            x.coverage.start.isoformat(), x.coverage.end.isoformat()],
        "qualification": x.qualification, "segmentation_ids": [i.value for i in x.segmentation_ids],
        "intervals": [asdict(i) for i in x.intervals],
        "transcript": reference_document(x.transcript),
        "start_cues": [t.isoformat() for t in x.start_cues],
        "end_cues": [t.isoformat() for t in x.end_cues],
    }


def asset(value: dict[str, Any]) -> AssetInput:
    span = value["coverage"]
    return AssetInput(EntityId(value["asset_id"]), reference(value["timing"]),
                      None if span is None else Span(
                          datetime.fromisoformat(span[0]), datetime.fromisoformat(span[1])),
                      None if value["qualification"] is None
                      else TimingQualification(value["qualification"]),
                      tuple(EntityId(i) for i in value["segmentation_ids"]),
                      tuple(SegmentationInterval(**i) for i in value["intervals"]),
                      reference(value["transcript"]),
                      tuple(datetime.fromisoformat(t) for t in value["start_cues"]),
                      tuple(datetime.fromisoformat(t) for t in value["end_cues"]))


def candidate_document(x: Candidate) -> dict[str, Any]:
    return {
        "expectation_id": None if x.expectation is None else x.expectation.id.value,
        "expectation_revision": None if x.expectation is None else x.expectation.revision,
        "suggested_start": x.span.start, "suggested_end": x.span.end,
        "start_edge_kind": x.start_edge_kind.value, "end_edge_kind": x.end_edge_kind.value,
        "start_plan_offset_seconds": x.start_plan_offset_seconds,
        "end_plan_offset_seconds": x.end_plan_offset_seconds,
        "start_silence_support": x.start_silence_support,
        "end_silence_support": x.end_silence_support,
        "start_cue_support": x.start_cue_support, "end_cue_support": x.end_cue_support,
        "overlap": x.overlap, "strength": x.strength.value,
        "timing_qualifications": [q.value for q in x.timing_qualifications],
        "timing_references": [reference_document(r) for r in x.timing_references],
        "segmentation_ids": [i.value for i in x.segmentation_ids],
        "transcript_references": [reference_document(r) for r in x.transcript_references],
    }


def candidate(x: dict[str, Any]) -> Candidate:
    return Candidate(
        None if x["expectation_id"] is None else Reference(
            EntityId(str(x["expectation_id"])), x["expectation_revision"]),
        Span(x["suggested_start"], x["suggested_end"]),
        EdgeKind(x["start_edge_kind"]), EdgeKind(x["end_edge_kind"]),
        x["start_plan_offset_seconds"], x["end_plan_offset_seconds"], x["start_silence_support"],
        x["end_silence_support"], x["start_cue_support"], x["end_cue_support"],
        x["overlap"], Strength(x["strength"]),
        tuple(TimingQualification(q) for q in x["timing_qualifications"]),
        references(x["timing_references"]), tuple(EntityId(str(i)) for i in x["segmentation_ids"]),
        references(x["transcript_references"]),
    )
