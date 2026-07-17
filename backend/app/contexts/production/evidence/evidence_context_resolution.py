from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId

from .evidence_context import EvidenceContext
from .evidence_context_conflict import (
    EvidenceContextConflict,
    EvidenceContextConflictResolution,
)
from .evidence_context_source import EvidenceContextSource

if TYPE_CHECKING:
    from app.contexts.production.observation import Observation

    from .evidence_set import EvidenceSet


_CONTEXT_FIELDS = (
    "stage_id",
    "recording_block_id",
    "scheduled_activity_id",
    "transcript_stream_ids",
    "media_artifact_ids",
    "correlation_ids",
    "timeline",
    "organizational_anchor",
    "organizational_anchor_seconds",
    "boundary_context_id",
    "source_context_ids",
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _empty_sources() -> Mapping[str, EvidenceContextSource]:
    return {}


def _empty_ignored_values() -> Mapping[str, Sequence[str]]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceContextResolution:
    """Resolved first-class context plus structured compatibility diagnostics."""

    context: EvidenceContext
    sources: Mapping[str, EvidenceContextSource] = field(default_factory=_empty_sources)
    conflicts: Sequence[EvidenceContextConflict] = field(default_factory=tuple)
    ignored_values: Mapping[str, Sequence[str]] = field(default_factory=_empty_ignored_values)
    unresolved_fields: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))
        conflicts_by_key: dict[tuple[object, ...], EvidenceContextConflict] = {}
        for conflict in self.conflicts:
            key = (
                conflict.field_name,
                tuple(conflict.authoritative_value),
                tuple(conflict.conflicting_value),
                conflict.authoritative_source,
                conflict.conflicting_source,
                tuple(conflict.contributing_reference_ids),
                conflict.resolution,
            )
            conflicts_by_key.setdefault(key, conflict)
        object.__setattr__(
            self,
            "conflicts",
            tuple(
                sorted(
                    conflicts_by_key.values(),
                    key=lambda conflict: (
                        conflict.field_name,
                        tuple(conflict.authoritative_value),
                        tuple(conflict.conflicting_value),
                        conflict.authoritative_source.value,
                        conflict.conflicting_source.value,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "ignored_values",
            MappingProxyType(
                {
                    key: tuple(sorted(dict.fromkeys(values)))
                    for key, values in sorted(self.ignored_values.items())
                }
            ),
        )
        object.__setattr__(
            self,
            "unresolved_fields",
            tuple(sorted(dict.fromkeys(self.unresolved_fields))),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


class EvidenceContextResolver:
    """Central deterministic resolver for first-class and compatibility context."""

    def resolve(
        self,
        *,
        first_class: EvidenceContext | None = None,
        first_class_source: EvidenceContextSource = (EvidenceContextSource.EVIDENCE_FIRST_CLASS),
        structured_legacy: EvidenceContext | None = None,
        metadata_sources: Sequence[Mapping[str, Any]] = (),
        contributing_reference_ids: Sequence[EntityId] = (),
    ) -> EvidenceContextResolution:
        authoritative = first_class or EvidenceContext.unknown()
        legacy = structured_legacy or EvidenceContext.unknown()
        fallback, ignored, metadata_conflicts = self._metadata_context(
            metadata_sources,
            contributing_reference_ids,
        )
        fields: dict[str, object] = {}
        sources: dict[str, EvidenceContextSource] = {}
        conflicts: list[EvidenceContextConflict] = list(metadata_conflicts)
        unresolved: list[str] = []

        for name in ("stage_id", "recording_block_id", "scheduled_activity_id"):
            value, source, field_conflicts, is_unresolved = self._resolve_singular(
                name,
                getattr(authoritative, name),
                first_class_source,
                getattr(legacy, name),
                getattr(fallback, name),
                contributing_reference_ids,
            )
            fields[name] = value
            if source is not EvidenceContextSource.UNKNOWN:
                sources[name] = source
            conflicts.extend(field_conflicts)
            if is_unresolved:
                unresolved.append(name)

        for name in (
            "transcript_stream_ids",
            "media_artifact_ids",
            "correlation_ids",
            "source_context_ids",
        ):
            value, source, field_conflicts = self._resolve_collection(
                name,
                getattr(authoritative, name),
                first_class_source,
                getattr(legacy, name),
                getattr(fallback, name),
                contributing_reference_ids,
            )
            fields[name] = value
            if source is not EvidenceContextSource.UNKNOWN:
                sources[name] = source
            conflicts.extend(field_conflicts)

        for name in (
            "organizational_anchor",
            "organizational_anchor_seconds",
            "boundary_context_id",
        ):
            value, source, field_conflicts, is_unresolved = self._resolve_singular(
                name,
                getattr(authoritative, name),
                first_class_source,
                getattr(legacy, name),
                getattr(fallback, name),
                contributing_reference_ids,
            )
            fields[name] = value
            if source is not EvidenceContextSource.UNKNOWN:
                sources[name] = source
            conflicts.extend(field_conflicts)
            if is_unresolved:
                unresolved.append(name)

        timeline, timeline_source, timeline_conflicts = self._resolve_timeline(
            authoritative,
            first_class_source,
            legacy,
            fallback,
            contributing_reference_ids,
        )
        fields.update(timeline)
        if timeline_source is not EvidenceContextSource.UNKNOWN:
            sources["timeline"] = timeline_source
        conflicts.extend(timeline_conflicts)
        unresolved.extend(
            conflict.field_name
            for conflict in metadata_conflicts
            if conflict.field_name in fields and fields[conflict.field_name] in (None, ())
        )

        return EvidenceContextResolution(
            context=EvidenceContext(
                stage_id=cast(EntityId | None, fields["stage_id"]),
                recording_block_id=cast(
                    EntityId | None,
                    fields["recording_block_id"],
                ),
                scheduled_activity_id=cast(
                    EntityId | None,
                    fields["scheduled_activity_id"],
                ),
                transcript_stream_ids=cast(
                    tuple[str, ...],
                    fields["transcript_stream_ids"],
                ),
                media_artifact_ids=cast(
                    tuple[str, ...],
                    fields["media_artifact_ids"],
                ),
                correlation_ids=cast(
                    tuple[CorrelationId, ...],
                    fields["correlation_ids"],
                ),
                timeline_position=cast(
                    TimelinePosition | None,
                    fields["timeline_position"],
                ),
                timeline_range=cast(
                    TimelineRange | None,
                    fields["timeline_range"],
                ),
                organizational_anchor=cast(
                    datetime | None,
                    fields["organizational_anchor"],
                ),
                organizational_anchor_seconds=cast(
                    float | None,
                    fields["organizational_anchor_seconds"],
                ),
                boundary_context_id=cast(
                    EntityId | None,
                    fields["boundary_context_id"],
                ),
                source_context_ids=cast(
                    tuple[EntityId, ...],
                    fields["source_context_ids"],
                ),
            ),
            sources=sources,
            conflicts=conflicts,
            ignored_values=ignored,
            unresolved_fields=unresolved,
            metadata={
                "metadata_fallback_used": any(
                    source is EvidenceContextSource.STRUCTURED_METADATA_FALLBACK
                    for source in sources.values()
                )
            },
        )

    def compose(
        self,
        resolutions: Sequence[EvidenceContextResolution],
        *,
        source_context_ids: Sequence[EntityId] = (),
    ) -> EvidenceContextResolution:
        ordered = tuple(
            sorted(
                resolutions,
                key=lambda resolution: self._context_key(resolution.context),
            )
        )
        conflicts = [conflict for resolution in ordered for conflict in resolution.conflicts]
        ignored: dict[str, list[str]] = {}
        for resolution in ordered:
            for key, values in resolution.ignored_values.items():
                ignored.setdefault(key, []).extend(values)

        singular_values: dict[str, object] = {}
        unresolved: list[str] = []
        for name in (
            "stage_id",
            "recording_block_id",
            "scheduled_activity_id",
            "organizational_anchor",
            "organizational_anchor_seconds",
            "boundary_context_id",
        ):
            known = tuple(
                dict.fromkeys(
                    getattr(resolution.context, name)
                    for resolution in ordered
                    if getattr(resolution.context, name) is not None
                )
            )
            if len(known) <= 1:
                singular_values[name] = known[0] if known else None
            else:
                singular_values[name] = None
                unresolved.append(name)
                conflicts.append(
                    self._conflict(
                        name,
                        (known[0],),
                        known[1:],
                        EvidenceContextSource.COMPOSED_FROM_SOURCES,
                        EvidenceContextSource.COMPOSED_FROM_SOURCES,
                        source_context_ids,
                        EvidenceContextConflictResolution.COMPOSITION_REJECTED,
                    )
                )

        collections: dict[str, tuple[object, ...]] = {}
        for name in (
            "transcript_stream_ids",
            "media_artifact_ids",
            "correlation_ids",
            "source_context_ids",
        ):
            values = tuple(
                value
                for resolution in ordered
                for value in cast(Sequence[object], getattr(resolution.context, name))
            )
            collections[name] = self._sorted_unique(values)
        collections["source_context_ids"] = self._sorted_unique(
            (*collections["source_context_ids"], *source_context_ids)
        )

        timeline_position, timeline_range = self._compose_timeline(
            tuple(resolution.context for resolution in ordered),
            cast(EntityId | None, singular_values["recording_block_id"]),
        )
        context = EvidenceContext(
            stage_id=cast(EntityId | None, singular_values["stage_id"]),
            recording_block_id=cast(
                EntityId | None,
                singular_values["recording_block_id"],
            ),
            scheduled_activity_id=cast(
                EntityId | None,
                singular_values["scheduled_activity_id"],
            ),
            transcript_stream_ids=cast(tuple[str, ...], collections["transcript_stream_ids"]),
            media_artifact_ids=cast(tuple[str, ...], collections["media_artifact_ids"]),
            correlation_ids=cast(tuple[CorrelationId, ...], collections["correlation_ids"]),
            timeline_position=timeline_position,
            timeline_range=timeline_range,
            organizational_anchor=cast(
                datetime | None,
                singular_values["organizational_anchor"],
            ),
            organizational_anchor_seconds=cast(
                float | None,
                singular_values["organizational_anchor_seconds"],
            ),
            boundary_context_id=cast(
                EntityId | None,
                singular_values["boundary_context_id"],
            ),
            source_context_ids=cast(tuple[EntityId, ...], collections["source_context_ids"]),
        )
        return EvidenceContextResolution(
            context=context,
            sources={
                name: EvidenceContextSource.COMPOSED_FROM_SOURCES
                for name in _CONTEXT_FIELDS
                if self._field_present(context, name)
            },
            conflicts=conflicts,
            ignored_values=ignored,
            unresolved_fields=unresolved,
            metadata={"source_resolution_count": len(ordered)},
        )

    def _resolve_singular(
        self,
        name: str,
        first: object | None,
        first_source: EvidenceContextSource,
        legacy: object | None,
        fallback: object | None,
        reference_ids: Sequence[EntityId],
    ) -> tuple[
        object | None,
        EvidenceContextSource,
        tuple[EvidenceContextConflict, ...],
        bool,
    ]:
        candidates = (
            (first, first_source),
            (legacy, EvidenceContextSource.STRUCTURED_LEGACY_FIELD),
            (fallback, EvidenceContextSource.STRUCTURED_METADATA_FALLBACK),
        )
        selected = next(
            ((value, source) for value, source in candidates if value is not None),
            (None, EvidenceContextSource.UNKNOWN),
        )
        conflicts = tuple(
            self._conflict(
                name,
                (selected[0],),
                (value,),
                selected[1],
                source,
                reference_ids,
                (
                    EvidenceContextConflictResolution.FIRST_CLASS_VALUE_RETAINED
                    if selected[1]
                    in {
                        EvidenceContextSource.OBSERVATION_FIRST_CLASS,
                        EvidenceContextSource.EVIDENCE_FIRST_CLASS,
                        EvidenceContextSource.EXPLICIT_BUILDER_INPUT,
                    }
                    else EvidenceContextConflictResolution.INPUT_IGNORED
                ),
            )
            for value, source in candidates
            if value is not None and selected[0] is not None and value != selected[0]
        )
        return selected[0], selected[1], conflicts, False

    def _resolve_collection(
        self,
        name: str,
        first: Sequence[object],
        first_source: EvidenceContextSource,
        legacy: Sequence[object],
        fallback: Sequence[object],
        reference_ids: Sequence[EntityId],
    ) -> tuple[tuple[object, ...], EvidenceContextSource, tuple[EvidenceContextConflict, ...]]:
        candidates = (
            (self._sorted_unique(first), first_source),
            (
                self._sorted_unique(legacy),
                EvidenceContextSource.STRUCTURED_LEGACY_FIELD,
            ),
            (
                self._sorted_unique(fallback),
                EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
            ),
        )
        selected = next(
            ((values, source) for values, source in candidates if values),
            ((), EvidenceContextSource.UNKNOWN),
        )
        conflicts = tuple(
            self._conflict(
                name,
                selected[0],
                values,
                selected[1],
                source,
                reference_ids,
                (
                    EvidenceContextConflictResolution.FIRST_CLASS_VALUE_RETAINED
                    if selected[1]
                    in {
                        EvidenceContextSource.OBSERVATION_FIRST_CLASS,
                        EvidenceContextSource.EVIDENCE_FIRST_CLASS,
                        EvidenceContextSource.EXPLICIT_BUILDER_INPUT,
                    }
                    else EvidenceContextConflictResolution.INPUT_IGNORED
                ),
            )
            for values, source in candidates
            if values and selected[0] and values != selected[0]
        )
        return selected[0], selected[1], conflicts

    def _resolve_timeline(
        self,
        first: EvidenceContext,
        first_source: EvidenceContextSource,
        legacy: EvidenceContext,
        fallback: EvidenceContext,
        reference_ids: Sequence[EntityId],
    ) -> tuple[
        dict[str, object | None], EvidenceContextSource, tuple[EvidenceContextConflict, ...]
    ]:
        candidates = (
            (self._timeline(first), first_source),
            (
                self._timeline(legacy),
                EvidenceContextSource.STRUCTURED_LEGACY_FIELD,
            ),
            (
                self._timeline(fallback),
                EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
            ),
        )
        selected = next(
            ((value, source) for value, source in candidates if value is not None),
            (None, EvidenceContextSource.UNKNOWN),
        )
        conflicts = tuple(
            self._conflict(
                "timeline",
                (selected[0],),
                (value,),
                selected[1],
                source,
                reference_ids,
                EvidenceContextConflictResolution.FIRST_CLASS_VALUE_RETAINED,
            )
            for value, source in candidates
            if value is not None and selected[0] is not None and value != selected[0]
        )
        position = selected[0] if isinstance(selected[0], TimelinePosition) else None
        timeline_range = selected[0] if isinstance(selected[0], TimelineRange) else None
        return (
            {"timeline_position": position, "timeline_range": timeline_range},
            selected[1],
            conflicts,
        )

    def _metadata_context(
        self,
        sources: Sequence[Mapping[str, Any]],
        reference_ids: Sequence[EntityId],
    ) -> tuple[
        EvidenceContext,
        Mapping[str, Sequence[str]],
        tuple[EvidenceContextConflict, ...],
    ]:
        ignored: dict[str, list[str]] = {}
        conflicts: list[EvidenceContextConflict] = []
        stage = self._one_entity(
            sources, ("stage_id",), "stage_id", ignored, conflicts, reference_ids
        )
        block = self._one_entity(
            sources,
            ("recording_block_id",),
            "recording_block_id",
            ignored,
            conflicts,
            reference_ids,
        )
        activity = self._one_entity(
            sources,
            ("scheduled_activity_id", "schedule_activity_id"),
            "scheduled_activity_id",
            ignored,
            conflicts,
            reference_ids,
        )
        boundary = self._one_entity(
            sources,
            ("boundary_context_id", "boundary_evidence_context_id"),
            "boundary_context_id",
            ignored,
            conflicts,
            reference_ids,
        )
        streams = self._text_values(
            sources,
            ("transcript_stream_ids", "transcript_stream_id", "stream_id", "transcript_source_id"),
        )
        artifacts = self._text_values(
            sources,
            ("media_artifact_ids", "media_artifact_id", "artifact_id"),
        )
        correlations = self._correlation_values(sources, ignored)
        position, timeline_range = self._metadata_timeline(sources, block, ignored)
        anchor = self._datetime_value(
            sources,
            ("organizational_anchor", "boundary_anchor_at"),
            "organizational_anchor",
            ignored,
            conflicts,
            reference_ids,
        )
        anchor_seconds = self._number_value(
            sources,
            ("organizational_anchor_seconds", "boundary_anchor_seconds"),
            "organizational_anchor_seconds",
            ignored,
            conflicts,
            reference_ids,
        )
        return (
            EvidenceContext(
                stage_id=stage,
                recording_block_id=block,
                scheduled_activity_id=activity,
                transcript_stream_ids=streams,
                media_artifact_ids=artifacts,
                correlation_ids=correlations,
                timeline_position=position,
                timeline_range=timeline_range,
                organizational_anchor=anchor,
                organizational_anchor_seconds=anchor_seconds,
                boundary_context_id=boundary,
            ),
            ignored,
            tuple(conflicts),
        )

    def _one_entity(
        self,
        sources: Sequence[Mapping[str, Any]],
        keys: Sequence[str],
        field_name: str,
        ignored: dict[str, list[str]],
        conflicts: list[EvidenceContextConflict],
        reference_ids: Sequence[EntityId],
    ) -> EntityId | None:
        values: list[EntityId] = []
        for source in sources:
            for key in keys:
                raw = source.get(key)
                if raw is None:
                    continue
                parsed = self._entity(raw)
                if parsed is None:
                    ignored.setdefault(field_name, []).append(str(raw))
                elif parsed not in values:
                    values.append(parsed)
        values.sort(key=lambda item: item.to_json())
        if len(values) > 1:
            conflicts.append(
                self._conflict(
                    field_name,
                    (values[0],),
                    values[1:],
                    EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
                    EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
                    reference_ids,
                    EvidenceContextConflictResolution.INPUT_IGNORED,
                )
            )
            return None
        return values[0] if values else None

    def _text_values(
        self,
        sources: Sequence[Mapping[str, Any]],
        keys: Sequence[str],
    ) -> tuple[str, ...]:
        values: list[str] = []
        for source in sources:
            for key in keys:
                raw = source.get(key)
                if isinstance(raw, str) and raw.strip():
                    values.append(raw.strip())
                elif isinstance(raw, Sequence) and not isinstance(raw, str | bytes):
                    values.extend(
                        value.strip()
                        for value in cast(Sequence[object], raw)
                        if isinstance(value, str) and value.strip()
                    )
        return tuple(sorted(dict.fromkeys(values)))

    def _correlation_values(
        self,
        sources: Sequence[Mapping[str, Any]],
        ignored: dict[str, list[str]],
    ) -> tuple[CorrelationId, ...]:
        raw_values = self._text_values(sources, ("correlation_ids", "correlation_id"))
        values: list[CorrelationId] = []
        for raw in raw_values:
            try:
                values.append(CorrelationId.parse(raw))
            except ValueError:
                ignored.setdefault("correlation_ids", []).append(raw)
        return tuple(sorted(dict.fromkeys(values), key=lambda item: item.to_json()))

    def _metadata_timeline(
        self,
        sources: Sequence[Mapping[str, Any]],
        block: EntityId | None,
        ignored: dict[str, list[str]],
    ) -> tuple[TimelinePosition | None, TimelineRange | None]:
        if block is None:
            return None, None
        starts = self._numbers(sources, ("timeline_range_start_seconds",))
        ends = self._numbers(sources, ("timeline_range_end_seconds",))
        points = self._numbers(sources, ("timeline_offset_seconds",))
        if starts and ends:
            start = min(starts)
            end = max(ends)
            if end > start >= 0:
                return None, TimelineRange(
                    start=TimelinePosition(block, timedelta(seconds=start)),
                    end=TimelinePosition(block, timedelta(seconds=end)),
                )
            ignored.setdefault("timeline", []).append(f"{start}:{end}")
        if points:
            point = min(points)
            if point >= 0:
                return TimelinePosition(block, timedelta(seconds=point)), None
        return None, None

    def _datetime_value(
        self,
        sources: Sequence[Mapping[str, Any]],
        keys: Sequence[str],
        field_name: str,
        ignored: dict[str, list[str]],
        conflicts: list[EvidenceContextConflict],
        reference_ids: Sequence[EntityId],
    ) -> datetime | None:
        values: list[datetime] = []
        for source in sources:
            for key in keys:
                raw = source.get(key)
                if isinstance(raw, datetime):
                    values.append(raw)
                elif isinstance(raw, str) and raw.strip():
                    try:
                        values.append(datetime.fromisoformat(raw))
                    except ValueError:
                        ignored.setdefault(field_name, []).append(raw)
        known = tuple(sorted(dict.fromkeys(values), key=lambda value: value.isoformat()))
        if len(known) > 1:
            conflicts.append(
                self._conflict(
                    field_name,
                    (known[0],),
                    known[1:],
                    EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
                    EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
                    reference_ids,
                    EvidenceContextConflictResolution.INPUT_IGNORED,
                )
            )
            return None
        return known[0] if known else None

    def _number_value(
        self,
        sources: Sequence[Mapping[str, Any]],
        keys: Sequence[str],
        field_name: str,
        ignored: dict[str, list[str]],
        conflicts: list[EvidenceContextConflict],
        reference_ids: Sequence[EntityId],
    ) -> float | None:
        values = self._numbers(sources, keys)
        if not values:
            return None
        known = tuple(sorted(dict.fromkeys(values)))
        if len(known) > 1:
            conflicts.append(
                self._conflict(
                    field_name,
                    (known[0],),
                    known[1:],
                    EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
                    EvidenceContextSource.STRUCTURED_METADATA_FALLBACK,
                    reference_ids,
                    EvidenceContextConflictResolution.INPUT_IGNORED,
                )
            )
            return None
        return known[0] if known else None

    def _numbers(
        self,
        sources: Sequence[Mapping[str, Any]],
        keys: Sequence[str],
    ) -> tuple[float, ...]:
        values: list[float] = []
        for source in sources:
            nested = source.get("observation_location")
            source_values = (source,) + (
                (cast(Mapping[str, Any], nested),) if isinstance(nested, Mapping) else ()
            )
            for current in source_values:
                for key in keys:
                    raw = current.get(key)
                    if isinstance(raw, int | float) and not isinstance(raw, bool) and isfinite(raw):
                        values.append(float(raw))
        return tuple(values)

    def _compose_timeline(
        self,
        contexts: Sequence[EvidenceContext],
        block: EntityId | None,
    ) -> tuple[TimelinePosition | None, TimelineRange | None]:
        if block is None:
            return None, None
        offsets = tuple(
            value
            for context in contexts
            for value in (
                (
                    context.timeline_position.offset.total_seconds(),
                    context.timeline_position.offset.total_seconds(),
                )
                if context.timeline_position is not None
                else (
                    (
                        context.timeline_range.start.offset.total_seconds(),
                        context.timeline_range.end.offset.total_seconds(),
                    )
                    if context.timeline_range is not None
                    else ()
                )
            )
        )
        if not offsets:
            return None, None
        start = min(offsets)
        end = max(offsets)
        if start == end:
            return TimelinePosition(block, timedelta(seconds=start)), None
        return None, TimelineRange(
            TimelinePosition(block, timedelta(seconds=start)),
            TimelinePosition(block, timedelta(seconds=end)),
        )

    def _context_key(self, context: EvidenceContext) -> tuple[str, ...]:
        return (
            context.stage_id.to_json() if context.stage_id else "",
            context.recording_block_id.to_json() if context.recording_block_id else "",
            context.scheduled_activity_id.to_json() if context.scheduled_activity_id else "",
            ",".join(context.transcript_stream_ids),
            ",".join(context.media_artifact_ids),
            ",".join(item.to_json() for item in context.correlation_ids),
            str(context.timeline_range_seconds or ""),
            context.organizational_anchor.isoformat() if context.organizational_anchor else "",
            str(context.organizational_anchor_seconds or ""),
            context.boundary_context_id.to_json() if context.boundary_context_id else "",
        )

    def _field_present(self, context: EvidenceContext, name: str) -> bool:
        if name == "timeline":
            return context.timeline_position is not None or context.timeline_range is not None
        return bool(getattr(context, name))

    def _timeline(self, context: EvidenceContext) -> TimelinePosition | TimelineRange | None:
        return context.timeline_position or context.timeline_range

    def _entity(self, raw: object) -> EntityId | None:
        if isinstance(raw, EntityId):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                return EntityId.parse(raw)
            except ValueError:
                return None
        return None

    def _sorted_unique(self, values: Sequence[object]) -> tuple[object, ...]:
        return tuple(
            sorted(
                dict.fromkeys(values),
                key=lambda value: (
                    value.to_json() if isinstance(value, EntityId | CorrelationId) else str(value)
                ),
            )
        )

    def _render(self, value: object) -> str:
        if isinstance(value, EntityId | CorrelationId):
            return value.to_json()
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, TimelinePosition):
            return f"{value.recording_block_id.to_json()}:{value.offset.total_seconds()}"
        if isinstance(value, TimelineRange):
            return (
                f"{value.recording_block_id.to_json()}:"
                f"{value.start.offset.total_seconds()}:"
                f"{value.end.offset.total_seconds()}"
            )
        return str(value)

    def _conflict(
        self,
        field_name: str,
        authoritative: Sequence[object],
        conflicting: Sequence[object],
        authoritative_source: EvidenceContextSource,
        conflicting_source: EvidenceContextSource,
        reference_ids: Sequence[EntityId],
        resolution: EvidenceContextConflictResolution,
    ) -> EvidenceContextConflict:
        return EvidenceContextConflict(
            field_name=field_name,
            authoritative_value=tuple(self._render(value) for value in authoritative),
            conflicting_value=tuple(self._render(value) for value in conflicting),
            authoritative_source=authoritative_source,
            conflicting_source=conflicting_source,
            contributing_reference_ids=reference_ids,
            resolution=resolution,
        )


def resolve_observation_evidence_context(
    observation: Observation,
) -> EvidenceContextResolution:
    context = observation.context
    first_class = EvidenceContext(
        stage_id=context.stage_id,
        recording_block_id=context.recording_block_id,
        scheduled_activity_id=context.scheduled_activity_id,
        transcript_stream_ids=(context.transcript_stream_id,)
        if context.transcript_stream_id is not None
        else (),
        media_artifact_ids=(context.media_artifact_id,)
        if context.media_artifact_id is not None
        else (),
        correlation_ids=(context.correlation_id,) if context.correlation_id is not None else (),
        timeline_position=context.timeline_position,
        timeline_range=context.timeline_range,
        source_context_ids=(observation.id,),
    )
    legacy = EvidenceContext(
        stage_id=observation.location.stage_id,
        recording_block_id=(
            observation.recording_block_id or observation.location.recording_block_id
        ),
        correlation_ids=(observation.correlation_id,),
        timeline_position=observation.location.point,
        timeline_range=observation.location.range,
        source_context_ids=(observation.id,),
    )
    return EvidenceContextResolver().resolve(
        first_class=first_class,
        first_class_source=EvidenceContextSource.OBSERVATION_FIRST_CLASS,
        structured_legacy=legacy,
        metadata_sources=(observation.metadata,),
        contributing_reference_ids=(observation.id,),
    )


def resolve_evidence_set_context(
    evidence_set: EvidenceSet,
) -> EvidenceContextResolution:
    legacy = EvidenceContext(
        recording_block_id=evidence_set.recording_block_id,
        correlation_ids=(evidence_set.correlation_id,),
        source_context_ids=(evidence_set.id,),
    )
    metadata_sources = (
        {
            "recording_block_id": (
                evidence_set.recording_block_id.to_json()
                if evidence_set.recording_block_id is not None
                else None
            ),
            "correlation_id": evidence_set.correlation_id.to_json(),
        },
        evidence_set.metadata,
        *(reference.metadata for reference in evidence_set.signals),
        *(item.metadata for item in evidence_set.items),
    )
    resolved = EvidenceContextResolver().resolve(
        first_class=evidence_set.context,
        first_class_source=EvidenceContextSource.EVIDENCE_FIRST_CLASS,
        structured_legacy=legacy,
        metadata_sources=metadata_sources,
        contributing_reference_ids=(evidence_set.id,),
    )
    if evidence_set.context_resolution is None:
        return resolved
    ignored_values = {
        key: tuple(
            sorted(
                dict.fromkeys(
                    (
                        *evidence_set.context_resolution.ignored_values.get(key, ()),
                        *resolved.ignored_values.get(key, ()),
                    )
                )
            )
        )
        for key in (
            evidence_set.context_resolution.ignored_values.keys() | resolved.ignored_values.keys()
        )
    }
    return EvidenceContextResolution(
        context=resolved.context,
        sources=resolved.sources,
        conflicts=(*evidence_set.context_resolution.conflicts, *resolved.conflicts),
        ignored_values=ignored_values,
        unresolved_fields=(
            *evidence_set.context_resolution.unresolved_fields,
            *resolved.unresolved_fields,
        ),
        metadata={"stored_resolution_preserved": True},
    )
