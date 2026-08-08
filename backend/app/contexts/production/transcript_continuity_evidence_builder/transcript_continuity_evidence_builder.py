from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceContextResolver,
    EvidenceItem,
    EvidencePurpose,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
    resolve_observation_evidence_context,
)
from app.contexts.production.evidence_builder import (
    EvidenceBuilderContextKey,
    EvidenceBuilderInputReport,
    ObservationSemanticSelection,
    ObservationSemanticSelectionStatus,
    ObservationSemanticSelector,
    deduplicate_observations,
)
from app.contexts.production.observation import (
    Observation,
    ObservationType,
    observation_recording_block_id,
    observation_stage_id,
    observation_traceability_metadata,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .transcript_continuity_evidence_mapping import (
    TRANSCRIPT_CONTINUITY_EVIDENCE_MAPPINGS,
    TranscriptContinuityEvidenceMapping,
    mapping_for_transcript_lifecycle,
)
from .transcript_continuity_evidence_result import TranscriptContinuityEvidenceResult
from .transcript_continuity_evidence_rule import TranscriptContinuityEvidenceRule


class TranscriptContinuityEvidenceBuilderStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    ARCHIVED = "archived"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_BUILDABLE_STATUSES = {
    TranscriptContinuityEvidenceBuilderStatus.READY,
    TranscriptContinuityEvidenceBuilderStatus.ACTIVE,
    TranscriptContinuityEvidenceBuilderStatus.DEGRADED,
}


def default_transcript_continuity_evidence_rules() -> tuple[
    TranscriptContinuityEvidenceRule,
    ...,
]:
    rules: list[TranscriptContinuityEvidenceRule] = []
    for mapping in TRANSCRIPT_CONTINUITY_EVIDENCE_MAPPINGS:
        signals = (mapping.evidence_signal,)
        if mapping.continuation_signal is not None:
            signals = signals + (mapping.continuation_signal,)
        for signal in signals:
            rules.append(
                TranscriptContinuityEvidenceRule(
                    id=EntityId.new(),
                    recognized_observation_type=ObservationType.TRANSCRIPT_ACTIVITY,
                    recognized_transcript_lifecycle=mapping.transcript_lifecycle,
                    target_signal=signal,
                    rationale_template=mapping.rationale,
                )
            )
    return tuple(rules)


def default_transcript_continuity_semantic_selector() -> ObservationSemanticSelector:
    return ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
        semantic_keys=(
            "transcript_lifecycle",
            "transcript_activity",
            "transcript_event_kind",
            "status",
        ),
    )


@dataclass(frozen=True, slots=True)
class TranscriptContinuityEvidenceBuilder:
    """Builds transcript continuity Evidence from objective transcript Observations."""

    id: EntityId
    name: str = "Transcript Continuity Evidence Builder"
    status: TranscriptContinuityEvidenceBuilderStatus = (
        TranscriptContinuityEvidenceBuilderStatus.READY
    )
    rules: Sequence[TranscriptContinuityEvidenceRule] = field(
        default_factory=default_transcript_continuity_evidence_rules
    )
    mappings: Sequence[TranscriptContinuityEvidenceMapping] = field(
        default_factory=lambda: TRANSCRIPT_CONTINUITY_EVIDENCE_MAPPINGS
    )
    semantic_selector: ObservationSemanticSelector = field(
        default_factory=default_transcript_continuity_semantic_selector
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("TranscriptContinuityEvidenceBuilder name must not be empty.")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def can_build(self) -> bool:
        return self.status in _BUILDABLE_STATUSES

    def build(
        self,
        observations: Sequence[Observation],
    ) -> TranscriptContinuityEvidenceResult:
        observation_tuple = tuple(observations)
        if not self.can_build():
            return TranscriptContinuityEvidenceResult(
                evidence_sets=(),
                consumed_observation_ids=(),
                ignored_observation_ids=tuple(observation.id for observation in observation_tuple),
                unsupported_observation_ids=(),
                duplicate_observation_ids=(),
                applied_rule_ids=(),
                input_report=EvidenceBuilderInputReport(
                    recognized_observation_ids=(),
                    ignored_observation_ids=tuple(
                        observation.id for observation in observation_tuple
                    ),
                    unsupported_observation_ids=(),
                    duplicate_observation_ids=(),
                    metadata={"builder_status": self.status.value},
                ),
                metadata={
                    "builder_id": self.id.to_json(),
                    "input_observation_count": len(observation_tuple),
                    "builder_status": self.status.value,
                },
            )

        deduplication = deduplicate_observations(observation_tuple)
        ignored_ids: list[EntityId] = []
        unsupported_ids: list[EntityId] = []
        selections: list[ObservationSemanticSelection] = list(deduplication.duplicate_selections)
        recognized: list[
            tuple[
                Observation,
                TranscriptContinuityEvidenceMapping,
                ObservationSemanticSelection,
            ]
        ] = []

        for observation in deduplication.retained_observations:
            selection = self.semantic_selector.select(
                observation,
                supported_values=self._supported_semantic_values(),
            )
            selections.append(selection)
            if selection.status is ObservationSemanticSelectionStatus.IGNORED_OBSERVATION_TYPE:
                ignored_ids.append(observation.id)
                continue
            if selection.status is not ObservationSemanticSelectionStatus.SELECTED:
                unsupported_ids.append(observation.id)
                continue

            mapping = self._mapping_for_selection(selection)
            if mapping is None:
                unsupported_ids.append(observation.id)
                continue

            recognized.append((observation, mapping, selection))

        evidence_sets, applied_rule_ids = self._evidence_sets_for_recognized(tuple(recognized))
        input_report = EvidenceBuilderInputReport.from_selections(
            selections,
            applied_rule_ids=applied_rule_ids,
            metadata={"selector_keys": self.semantic_selector.semantic_keys},
        )

        return TranscriptContinuityEvidenceResult(
            evidence_sets=evidence_sets,
            consumed_observation_ids=tuple(
                observation.id for observation, _mapping, _selection in recognized
            ),
            ignored_observation_ids=tuple(ignored_ids),
            unsupported_observation_ids=tuple(unsupported_ids),
            duplicate_observation_ids=deduplication.duplicate_observation_ids,
            applied_rule_ids=applied_rule_ids,
            input_report=input_report,
            metadata={
                "builder_id": self.id.to_json(),
                "input_observation_count": len(observation_tuple),
                "grouping_behavior": "recording_block_stage_transcript_stream",
                "ordering_behavior": "observed_at_then_timeline_then_observation_id",
                "duplicate_behavior": "first_deterministic_observation_kept",
                "interruption_behavior": "explicit_observation_required",
                "timeline_span_seconds": self._timeline_span_seconds(evidence_sets),
            },
        )

    def _mapping_for_selection(
        self,
        selection: ObservationSemanticSelection,
    ) -> TranscriptContinuityEvidenceMapping | None:
        if selection.normalized_semantic_value is None:
            return None
        mapping = mapping_for_transcript_lifecycle(selection.normalized_semantic_value)
        if mapping is None:
            return None
        if mapping not in self.mappings:
            return None
        return mapping

    def _supported_semantic_values(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(mapping.transcript_lifecycle for mapping in self.mappings))

    def _rule_for_mapping_signal(
        self,
        mapping: TranscriptContinuityEvidenceMapping,
        signal: EvidenceSignal,
    ) -> TranscriptContinuityEvidenceRule | None:
        for rule in self.rules:
            if (
                rule.recognized_transcript_lifecycle == mapping.transcript_lifecycle
                and rule.target_signal is signal
            ):
                return rule
        return None

    def _evidence_sets_for_recognized(
        self,
        recognized: tuple[
            tuple[
                Observation,
                TranscriptContinuityEvidenceMapping,
                ObservationSemanticSelection,
            ],
            ...,
        ],
    ) -> tuple[tuple[EvidenceSet, ...], tuple[EntityId, ...]]:
        grouped: dict[
            EvidenceBuilderContextKey,
            list[
                tuple[
                    Observation,
                    TranscriptContinuityEvidenceMapping,
                    ObservationSemanticSelection,
                ]
            ],
        ] = {}
        for observation, mapping, selection in recognized:
            grouped.setdefault(self._group_key(observation), []).append(
                (observation, mapping, selection)
            )

        evidence_sets: list[EvidenceSet] = []
        applied_rule_ids: list[EntityId] = []
        for group in grouped.values():
            evidence_set, rule_ids = self._evidence_set_for_group(tuple(group))
            if evidence_set is not None:
                evidence_sets.append(evidence_set)
                applied_rule_ids.extend(rule_ids)

        evidence_sets.sort(
            key=lambda evidence_set: (
                min(
                    str(item.metadata.get("observation_observed_at", ""))
                    for item in evidence_set.items
                ),
                evidence_set.id.to_json(),
            )
        )
        return tuple(evidence_sets), tuple(applied_rule_ids)

    def _group_key(self, observation: Observation) -> EvidenceBuilderContextKey:
        context = resolve_observation_evidence_context(observation).context
        transcript_stream_id = self._transcript_stream_id(observation)
        return EvidenceBuilderContextKey.from_components(
            recording_block_id=(
                context.recording_block_id.to_json()
                if context.recording_block_id is not None
                else None
            ),
            stage_id=context.stage_id.to_json() if context.stage_id is not None else None,
            transcript_stream_id=transcript_stream_id,
        )

    def _transcript_stream_id(self, observation: Observation) -> str | None:
        streams = resolve_observation_evidence_context(observation).context.transcript_stream_ids
        return streams[0] if len(streams) == 1 else None

    def _evidence_set_for_group(
        self,
        group: tuple[
            tuple[
                Observation,
                TranscriptContinuityEvidenceMapping,
                ObservationSemanticSelection,
            ],
            ...,
        ],
    ) -> tuple[EvidenceSet | None, tuple[EntityId, ...]]:
        items: list[EvidenceItem] = []
        signals: list[EvidenceSignalReference] = []
        applied_rule_ids: list[EntityId] = []
        transcript_activity_seen = False

        for observation, mapping, selection in group:
            signal = self._signal_for_mapping(mapping, transcript_activity_seen)
            rule = self._rule_for_mapping_signal(mapping, signal)
            if rule is None:
                continue
            item = self._evidence_item_for_observation(
                observation,
                mapping,
                rule,
                signal,
                selection,
            )
            items.append(item)
            signals.append(
                self._signal_reference_for_observation(
                    observation=observation,
                    mapping=mapping,
                    rule=rule,
                    item=item,
                    signal=signal,
                    selection=selection,
                )
            )
            applied_rule_ids.append(rule.id)
            if signal in {
                EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
                EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
            }:
                transcript_activity_seen = True

        if not items:
            return None, ()

        first_observation = group[0][0]
        context_resolution = EvidenceContextResolver().compose(
            tuple(
                resolve_observation_evidence_context(observation)
                for observation, _mapping, _selection in group
            ),
            source_context_ids=tuple(observation.id for observation, _mapping, _selection in group),
        )
        first_recording_block_id = context_resolution.context.recording_block_id
        first_stage_id = context_resolution.context.stage_id
        return (
            EvidenceSet(
                id=EntityId.new(),
                recording_block_id=first_recording_block_id,
                concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
                purpose=EvidencePurpose.TRANSITION_SUPPORT,
                items=tuple(items),
                signals=tuple(signals),
                correlation_id=first_observation.correlation_id,
                created_at=first_observation.observed_at,
                notes="Evidence organized for transcript continuity.",
                context=context_resolution.context,
                context_resolution=context_resolution,
                metadata={
                    "transcript_continuity_evidence_builder_id": self.id.to_json(),
                    "source_observation_ids": tuple(
                        observation.id.to_json() for observation, _mapping, _selection in group
                    ),
                    "source_production_event_ids": self._lineage_values(
                        group,
                        "source_production_event_id",
                    ),
                    "source_production_event_types": self._lineage_values(
                        group,
                        "source_production_event_type",
                    ),
                    "source_interpreter_ids": self._lineage_values(
                        group,
                        "observation_interpreter_id",
                    ),
                    "source_interpretation_rule_ids": self._lineage_values(
                        group,
                        "interpretation_rule_id",
                    ),
                    "recording_block_id": (
                        first_recording_block_id.to_json()
                        if first_recording_block_id is not None
                        else None
                    ),
                    "stage_id": (first_stage_id.to_json() if first_stage_id is not None else None),
                    "transcript_stream_id": self._transcript_stream_id(first_observation),
                    "semantic_conclusion": None,
                },
            ),
            tuple(applied_rule_ids),
        )

    def _signal_for_mapping(
        self,
        mapping: TranscriptContinuityEvidenceMapping,
        transcript_activity_seen: bool,
    ) -> EvidenceSignal:
        if transcript_activity_seen and mapping.continuation_signal is not None:
            return mapping.continuation_signal
        return mapping.evidence_signal

    def _evidence_item_for_observation(
        self,
        observation: Observation,
        mapping: TranscriptContinuityEvidenceMapping,
        rule: TranscriptContinuityEvidenceRule,
        signal: EvidenceSignal,
        selection: ObservationSemanticSelection,
    ) -> EvidenceItem:
        return EvidenceItem(
            id=EntityId.new(),
            observation_id=observation.id,
            role=rule.evidence_role,
            strength=rule.evidence_strength,
            rationale=rule.rationale(),
            metadata={
                **observation_traceability_metadata(observation),
                "transcript_lifecycle": mapping.transcript_lifecycle,
                "evidence_signal": signal.value,
                "evidence_builder_rule_id": rule.id.to_json(),
                "matched_semantic_key": selection.matched_semantic_key,
                "normalized_semantic_value": selection.normalized_semantic_value,
                "observation_observed_at": observation.observed_at.isoformat(),
                "transcript_stream_id": self._transcript_stream_id(observation),
                "transcript_segment_id": observation.metadata.get("transcript_segment_id"),
                "timeline_range_reference": observation.metadata.get("timeline_range_reference"),
                "observation_location": self._location_metadata(observation),
            },
        )

    def _signal_reference_for_observation(
        self,
        *,
        observation: Observation,
        mapping: TranscriptContinuityEvidenceMapping,
        rule: TranscriptContinuityEvidenceRule,
        item: EvidenceItem,
        signal: EvidenceSignal,
        selection: ObservationSemanticSelection,
    ) -> EvidenceSignalReference:
        return EvidenceSignalReference(
            signal=signal,
            evidence_item_ids=(item.id,),
            observation_ids=(observation.id,),
            rationale=mapping.rationale,
            metadata={
                **observation_traceability_metadata(observation),
                "evidence_builder_rule_id": rule.id.to_json(),
                "transcript_lifecycle": mapping.transcript_lifecycle,
                "matched_semantic_key": selection.matched_semantic_key,
                "normalized_semantic_value": selection.normalized_semantic_value,
                "transcript_stream_id": self._transcript_stream_id(observation),
                "timeline_range_reference": observation.metadata.get("timeline_range_reference"),
                "observation_location": self._location_metadata(observation),
            },
        )

    def _lineage_values(
        self,
        group: tuple[
            tuple[
                Observation,
                TranscriptContinuityEvidenceMapping,
                ObservationSemanticSelection,
            ],
            ...,
        ],
        key: str,
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                value
                for observation, _mapping, _selection in group
                for value in (observation_traceability_metadata(observation).get(key),)
                if isinstance(value, str) and value
            )
        )

    def _location_metadata(self, observation: Observation) -> Mapping[str, Any]:
        location = observation.location
        recording_block_id = observation_recording_block_id(observation)
        stage_id = observation_stage_id(observation)
        metadata: dict[str, Any] = {
            "kind": location.kind.value if location.kind is not None else None,
            "recording_block_id": (
                recording_block_id.to_json() if recording_block_id is not None else None
            ),
            "stage_id": (stage_id.to_json() if stage_id is not None else None),
        }
        if location.point is not None:
            metadata["timeline_offset_seconds"] = self._seconds(location.point.offset)
        if location.range is not None:
            metadata["timeline_range_start_seconds"] = self._seconds(location.range.start.offset)
            metadata["timeline_range_end_seconds"] = self._seconds(location.range.end.offset)
        if location.wall_clock_at is not None:
            metadata["wall_clock_at"] = location.wall_clock_at.isoformat()
        return MappingProxyType(metadata)

    def _timeline_span_seconds(
        self,
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[float, float] | None:
        offsets: list[float] = []
        for evidence_set in evidence_sets:
            for item in evidence_set.items:
                location_raw = item.metadata.get("observation_location", {})
                if not isinstance(location_raw, Mapping):
                    continue
                location = cast(Mapping[str, object], location_raw)
                point_offset = location.get("timeline_offset_seconds")
                range_start = location.get("timeline_range_start_seconds")
                range_end = location.get("timeline_range_end_seconds")
                for value in (point_offset, range_start, range_end):
                    if isinstance(value, int | float):
                        offsets.append(float(value))
        if not offsets:
            return None
        return min(offsets), max(offsets)

    def _seconds(self, value: timedelta) -> float:
        return value.total_seconds()


def make_transcript_continuity_evidence_builder(
    *,
    builder_id: EntityId | None = None,
    name: str = "Transcript Continuity Evidence Builder",
) -> TranscriptContinuityEvidenceBuilder:
    return TranscriptContinuityEvidenceBuilder(id=builder_id or EntityId.new(), name=name)
