from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceContextResolver,
    EvidenceItem,
    EvidencePurpose,
    EvidenceSet,
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

from .recording_coverage_evidence_mapping import (
    RECORDING_COVERAGE_EVIDENCE_MAPPINGS,
    RecordingCoverageEvidenceMapping,
    mapping_for_recording_semantic_value,
)
from .recording_coverage_evidence_result import (
    RecordingCoverageEvidenceResult,
)
from .recording_coverage_evidence_rule import (
    RecordingCoverageEvidenceRule,
)


class RecordingCoverageEvidenceBuilderStatus(StrEnum):
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
    RecordingCoverageEvidenceBuilderStatus.READY,
    RecordingCoverageEvidenceBuilderStatus.ACTIVE,
    RecordingCoverageEvidenceBuilderStatus.DEGRADED,
}


def default_recording_coverage_evidence_rules() -> tuple[
    RecordingCoverageEvidenceRule,
    ...,
]:
    return tuple(
        RecordingCoverageEvidenceRule(
            id=EntityId.new(),
            recognized_observation_type=ObservationType.RECORDING_ACTIVITY,
            recognized_recording_activity=mapping.recording_activity,
            target_signal=mapping.evidence_signal,
            rationale_template=mapping.rationale,
        )
        for mapping in RECORDING_COVERAGE_EVIDENCE_MAPPINGS
    )


def default_recording_coverage_semantic_selector() -> ObservationSemanticSelector:
    return ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        semantic_keys=("recording_activity", "recording_event_kind"),
    )


@dataclass(frozen=True, slots=True)
class RecordingCoverageEvidenceBuilder:
    """Builds recording coverage Evidence from objective recording Observations."""

    id: EntityId
    name: str = "Recording Coverage Evidence Builder"
    status: RecordingCoverageEvidenceBuilderStatus = RecordingCoverageEvidenceBuilderStatus.READY
    rules: Sequence[RecordingCoverageEvidenceRule] = field(
        default_factory=default_recording_coverage_evidence_rules
    )
    mappings: Sequence[RecordingCoverageEvidenceMapping] = field(
        default_factory=lambda: RECORDING_COVERAGE_EVIDENCE_MAPPINGS
    )
    semantic_selector: ObservationSemanticSelector = field(
        default_factory=default_recording_coverage_semantic_selector
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("RecordingCoverageEvidenceBuilder name must not be empty.")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def can_build(self) -> bool:
        return self.status in _BUILDABLE_STATUSES

    def build(
        self,
        observations: Sequence[Observation],
    ) -> RecordingCoverageEvidenceResult:
        observation_tuple = tuple(observations)
        if not self.can_build():
            return RecordingCoverageEvidenceResult(
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
                RecordingCoverageEvidenceMapping,
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

        return RecordingCoverageEvidenceResult(
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
                "grouping_behavior": "recording_block_and_stage_context",
                "ordering_behavior": "observed_at_then_timeline_then_observation_id",
                "duplicate_behavior": "first_deterministic_observation_kept",
            },
        )

    def _mapping_for_selection(
        self,
        selection: ObservationSemanticSelection,
    ) -> RecordingCoverageEvidenceMapping | None:
        if selection.normalized_semantic_value is None:
            return None
        mapping = mapping_for_recording_semantic_value(selection.normalized_semantic_value)
        if mapping is None:
            return None
        if mapping not in self.mappings:
            return None
        return mapping

    def _supported_semantic_values(self) -> tuple[str, ...]:
        values: list[str] = []
        for mapping in self.mappings:
            values.append(mapping.recording_activity)
            values.append(mapping.recording_event_kind)
        return tuple(dict.fromkeys(values))

    def _rule_for_mapping(
        self,
        mapping: RecordingCoverageEvidenceMapping,
    ) -> RecordingCoverageEvidenceRule | None:
        for rule in self.rules:
            if (
                rule.recognized_recording_activity == mapping.recording_activity
                and rule.target_signal is mapping.evidence_signal
            ):
                return rule
        return None

    def _evidence_sets_for_recognized(
        self,
        recognized: tuple[
            tuple[
                Observation,
                RecordingCoverageEvidenceMapping,
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
                    RecordingCoverageEvidenceMapping,
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

    def _group_key(
        self,
        observation: Observation,
    ) -> EvidenceBuilderContextKey:
        context = resolve_observation_evidence_context(observation).context
        return EvidenceBuilderContextKey.from_components(
            recording_block_id=(
                context.recording_block_id.to_json()
                if context.recording_block_id is not None
                else None
            ),
            stage_id=context.stage_id.to_json() if context.stage_id is not None else None,
        )

    def _evidence_set_for_group(
        self,
        group: tuple[
            tuple[
                Observation,
                RecordingCoverageEvidenceMapping,
                ObservationSemanticSelection,
            ],
            ...,
        ],
    ) -> tuple[EvidenceSet | None, tuple[EntityId, ...]]:
        items: list[EvidenceItem] = []
        signals: list[EvidenceSignalReference] = []
        applied_rule_ids: list[EntityId] = []

        for observation, mapping, selection in group:
            rule = self._rule_for_mapping(mapping)
            if rule is None:
                continue
            item = self._evidence_item_for_observation(
                observation,
                mapping,
                rule,
                selection,
            )
            items.append(item)
            signals.append(
                self._signal_reference_for_observation(
                    observation=observation,
                    mapping=mapping,
                    rule=rule,
                    item=item,
                    selection=selection,
                )
            )
            applied_rule_ids.append(rule.id)

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
                concern=EvidenceConcern.RECORDING_COVERAGE,
                purpose=EvidencePurpose.TRANSITION_SUPPORT,
                items=tuple(items),
                signals=tuple(signals),
                correlation_id=first_observation.correlation_id,
                created_at=first_observation.observed_at,
                notes="Evidence organized for recording coverage.",
                context=context_resolution.context,
                context_resolution=context_resolution,
                metadata={
                    "recording_coverage_evidence_builder_id": self.id.to_json(),
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
                    "semantic_conclusion": None,
                },
            ),
            tuple(applied_rule_ids),
        )

    def _evidence_item_for_observation(
        self,
        observation: Observation,
        mapping: RecordingCoverageEvidenceMapping,
        rule: RecordingCoverageEvidenceRule,
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
                "recording_activity": mapping.recording_activity,
                "recording_event_kind": mapping.recording_event_kind,
                "evidence_builder_rule_id": rule.id.to_json(),
                "matched_semantic_key": selection.matched_semantic_key,
                "normalized_semantic_value": selection.normalized_semantic_value,
                "observation_observed_at": observation.observed_at.isoformat(),
                "observation_location": self._location_metadata(observation),
            },
        )

    def _signal_reference_for_observation(
        self,
        *,
        observation: Observation,
        mapping: RecordingCoverageEvidenceMapping,
        rule: RecordingCoverageEvidenceRule,
        item: EvidenceItem,
        selection: ObservationSemanticSelection,
    ) -> EvidenceSignalReference:
        return EvidenceSignalReference(
            signal=mapping.evidence_signal,
            evidence_item_ids=(item.id,),
            observation_ids=(observation.id,),
            rationale=mapping.rationale,
            metadata={
                **observation_traceability_metadata(observation),
                "evidence_builder_rule_id": rule.id.to_json(),
                "recording_activity": mapping.recording_activity,
                "matched_semantic_key": selection.matched_semantic_key,
                "normalized_semantic_value": selection.normalized_semantic_value,
                "observation_location": self._location_metadata(observation),
            },
        )

    def _lineage_values(
        self,
        group: tuple[
            tuple[
                Observation,
                RecordingCoverageEvidenceMapping,
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

    def _seconds(self, value: timedelta) -> float:
        return value.total_seconds()


def make_recording_coverage_evidence_builder(
    *,
    builder_id: EntityId | None = None,
    name: str = "Recording Coverage Evidence Builder",
) -> RecordingCoverageEvidenceBuilder:
    return RecordingCoverageEvidenceBuilder(id=builder_id or EntityId.new(), name=name)
