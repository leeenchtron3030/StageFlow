from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import EntityId


class ObservationLocationKind(StrEnum):
    TIMELINE_POSITION = "timeline_position"
    TIMELINE_RANGE = "timeline_range"
    RECORDING_BLOCK = "recording_block"
    WALL_CLOCK = "wall_clock"
    STAGE = "stage"
    COMPOSITE = "composite"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ObservationLocation:
    """The explicit place or time anchor for an objective observation."""

    kind: ObservationLocationKind | None = None
    point: TimelinePosition | None = None
    range: TimelineRange | None = None
    recording_block: EntityId | None = None
    wall_clock_at: datetime | None = None
    stage_id: EntityId | None = None

    def __post_init__(self) -> None:
        kind = self.kind or self._infer_kind()
        object.__setattr__(self, "kind", kind)

        self._validate_kind(kind)
        self._validate_recording_block_consistency()

    @classmethod
    def at_point(cls, point: TimelinePosition) -> ObservationLocation:
        return cls(kind=ObservationLocationKind.TIMELINE_POSITION, point=point)

    @classmethod
    def over_range(cls, time_range: TimelineRange) -> ObservationLocation:
        return cls(kind=ObservationLocationKind.TIMELINE_RANGE, range=time_range)

    @classmethod
    def for_recording_block(cls, recording_block_id: EntityId) -> ObservationLocation:
        return cls(
            kind=ObservationLocationKind.RECORDING_BLOCK,
            recording_block=recording_block_id,
        )

    @classmethod
    def at_wall_clock(cls, timestamp: datetime) -> ObservationLocation:
        return cls(kind=ObservationLocationKind.WALL_CLOCK, wall_clock_at=timestamp)

    @classmethod
    def for_stage(cls, stage_id: EntityId) -> ObservationLocation:
        return cls(kind=ObservationLocationKind.STAGE, stage_id=stage_id)

    @classmethod
    def composite(
        cls,
        *,
        point: TimelinePosition | None = None,
        range: TimelineRange | None = None,
        recording_block: EntityId | None = None,
        wall_clock_at: datetime | None = None,
        stage_id: EntityId | None = None,
    ) -> ObservationLocation:
        return cls(
            kind=ObservationLocationKind.COMPOSITE,
            point=point,
            range=range,
            recording_block=recording_block,
            wall_clock_at=wall_clock_at,
            stage_id=stage_id,
        )

    @classmethod
    def unknown(cls) -> ObservationLocation:
        return cls(kind=ObservationLocationKind.UNKNOWN)

    @property
    def is_point(self) -> bool:
        return self.kind is ObservationLocationKind.TIMELINE_POSITION

    @property
    def is_range(self) -> bool:
        return self.kind is ObservationLocationKind.TIMELINE_RANGE

    @property
    def is_recording_block(self) -> bool:
        return self.kind is ObservationLocationKind.RECORDING_BLOCK

    @property
    def is_wall_clock(self) -> bool:
        return self.kind is ObservationLocationKind.WALL_CLOCK

    @property
    def is_stage(self) -> bool:
        return self.kind is ObservationLocationKind.STAGE

    @property
    def is_composite(self) -> bool:
        return self.kind is ObservationLocationKind.COMPOSITE

    @property
    def is_unknown(self) -> bool:
        return self.kind is ObservationLocationKind.UNKNOWN

    @property
    def recording_block_id(self) -> EntityId | None:
        if self.point is not None:
            return self.point.recording_block_id
        if self.range is not None:
            return self.range.recording_block_id
        return self.recording_block

    def _infer_kind(self) -> ObservationLocationKind:
        if self._anchor_count() != 1:
            raise ValueError(
                "ObservationLocation requires an explicit location kind when no single "
                "anchor is provided."
            )
        if self.point is not None:
            return ObservationLocationKind.TIMELINE_POSITION
        if self.range is not None:
            return ObservationLocationKind.TIMELINE_RANGE
        if self.recording_block is not None:
            return ObservationLocationKind.RECORDING_BLOCK
        if self.wall_clock_at is not None:
            return ObservationLocationKind.WALL_CLOCK
        if self.stage_id is not None:
            return ObservationLocationKind.STAGE
        raise ValueError("ObservationLocation requires an explicit location kind.")

    def _validate_kind(self, kind: ObservationLocationKind) -> None:
        match kind:
            case ObservationLocationKind.TIMELINE_POSITION:
                self._require_only(point=True)
            case ObservationLocationKind.TIMELINE_RANGE:
                self._require_only(range=True)
            case ObservationLocationKind.RECORDING_BLOCK:
                self._require_only(recording_block=True)
            case ObservationLocationKind.WALL_CLOCK:
                self._require_only(wall_clock_at=True)
            case ObservationLocationKind.STAGE:
                self._require_only(stage_id=True)
            case ObservationLocationKind.COMPOSITE:
                if self._anchor_count() < 2:
                    raise ValueError(
                        "Composite ObservationLocation requires at least two anchors."
                    )
            case ObservationLocationKind.UNKNOWN:
                if self._anchor_count() != 0:
                    raise ValueError("Unknown ObservationLocation must not include anchors.")

    def _anchor_count(self) -> int:
        return sum(
            anchor is not None
            for anchor in (
                self.point,
                self.range,
                self.recording_block,
                self.wall_clock_at,
                self.stage_id,
            )
        )

    def _require_only(
        self,
        *,
        point: bool = False,
        range: bool = False,
        recording_block: bool = False,
        wall_clock_at: bool = False,
        stage_id: bool = False,
    ) -> None:
        expected = {
            "point": point,
            "range": range,
            "recording_block": recording_block,
            "wall_clock_at": wall_clock_at,
            "stage_id": stage_id,
        }
        actual = {
            "point": self.point is not None,
            "range": self.range is not None,
            "recording_block": self.recording_block is not None,
            "wall_clock_at": self.wall_clock_at is not None,
            "stage_id": self.stage_id is not None,
        }
        if actual != expected:
            kind = self.kind or ObservationLocationKind.UNKNOWN
            raise ValueError(
                f"{kind.value} ObservationLocation requires exactly its matching anchor."
            )

    def _validate_recording_block_consistency(self) -> None:
        recording_block_ids = {
            recording_block_id
            for recording_block_id in (
                self.point.recording_block_id if self.point is not None else None,
                self.range.recording_block_id if self.range is not None else None,
                self.recording_block,
            )
            if recording_block_id is not None
        }
        if len(recording_block_ids) > 1:
            raise ValueError(
                "ObservationLocation recording block anchors must reference the same ID."
            )
