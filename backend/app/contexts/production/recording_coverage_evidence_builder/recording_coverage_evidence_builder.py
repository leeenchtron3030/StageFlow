from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidencePurpose,
    EvidenceSet,
    EvidenceSignalReference,
)
from app.contexts.production.observation import Observation, ObservationType
from app.shared.ids import EntityId

from .recording_coverage_evidence_mapping import (
    RECORDING_COVERAGE_EVIDENCE_MAPPINGS,
    RecordingCoverageEvidenceMapping,
    mapping_for_recording_observation,
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


@dataclass(frozen=True, slots=True)
class RecordingCoverageEvidenceBuilder:
    """Builds recording coverage Evidence from objective recording Observations."""

    id: EntityId
    name: str = "Recording Coverage Evidence Builder"
    status: RecordingCoverageEvidenceBuilderStatus = (
        RecordingCoverageEvidenceBuilderStatus.READY
    )
    rules: Sequence[RecordingCoverageEvidenceRule] = field(
        default_factory=default_recording_coverage_evidence_rules
    )
    mappings: Sequence[RecordingCoverageEvidenceMapping] = field(
        default_factory=lambda: RECORDING_COVERAGE_EVIDENCE_MAPPINGS
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
                metadata={
                    "builder_id": self.id.to_json(),
                    "input_observation_count": len(observation_tuple),
                    "builder_status": self.status.value,
                },
            )

        ordered_unique, duplicate_ids = self._ordered_unique_observations(
            observation_tuple
        )
        ignored_ids: list[EntityId] = []
        unsupported_ids: list[EntityId] = []
        recognized: list[tuple[Observation, RecordingCoverageEvidenceMapping]] = []

        for observation in ordered_unique:
            if observation.observation_type is not ObservationType.RECORDING_ACTIVITY:
                ignored_ids.append(observation.id)
                continue

            mapping = self._mapping_for_observation(observation)
            if mapping is None:
                unsupported_ids.append(observation.id)
                continue

            recognized.append((observation, mapping))

        evidence_sets, applied_rule_ids = self._evidence_sets_for_recognized(
            tuple(recognized)
        )

        return RecordingCoverageEvidenceResult(
            evidence_sets=evidence_sets,
            consumed_observation_ids=tuple(observation.id for observation, _ in recognized),
            ignored_observation_ids=tuple(ignored_ids),
            unsupported_observation_ids=tuple(unsupported_ids),
            duplicate_observation_ids=duplicate_ids,
            applied_rule_ids=applied_rule_ids,
            metadata={
                "builder_id": self.id.to_json(),
                "input_observation_count": len(observation_tuple),
                "grouping_behavior": "recording_block_and_stage_context",
                "ordering_behavior": "observed_at_then_timeline_then_observation_id",
                "duplicate_behavior": "first_deterministic_observation_kept",
            },
        )

    def _mapping_for_observation(
        self,
        observation: Observation,
    ) -> RecordingCoverageEvidenceMapping | None:
        mapping = mapping_for_recording_observation(observation)
        if mapping is None:
            return None
        if mapping not in self.mappings:
            return None
        return mapping

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

    def _ordered_unique_observations(
        self,
        observations: tuple[Observation, ...],
    ) -> tuple[tuple[Observation, ...], tuple[EntityId, ...]]:
        sorted_observations = tuple(sorted(observations, key=self._ordering_key))
        seen_ids: set[EntityId] = set()
        unique: list[Observation] = []
        duplicate_ids: list[EntityId] = []

        for observation in sorted_observations:
            if observation.id in seen_ids:
                duplicate_ids.append(observation.id)
                continue
            seen_ids.add(observation.id)
            unique.append(observation)

        return tuple(unique), tuple(duplicate_ids)

    def _ordering_key(
        self,
        observation: Observation,
    ) -> tuple[datetime, float, str]:
        return (
            observation.observed_at,
            self._timeline_order_value(observation),
            observation.id.to_json(),
        )

    def _timeline_order_value(self, observation: Observation) -> float:
        location = observation.location
        if location.point is not None:
            return location.point.offset.total_seconds()
        if location.range is not None:
            return location.range.start.offset.total_seconds()
        return float("inf")

    def _evidence_sets_for_recognized(
        self,
        recognized: tuple[tuple[Observation, RecordingCoverageEvidenceMapping], ...],
    ) -> tuple[tuple[EvidenceSet, ...], tuple[EntityId, ...]]:
        grouped: dict[
            tuple[str | None, str | None],
            list[tuple[Observation, RecordingCoverageEvidenceMapping]],
        ] = {}
        for observation, mapping in recognized:
            grouped.setdefault(self._group_key(observation), []).append(
                (observation, mapping)
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
    ) -> tuple[str | None, str | None]:
        recording_block_id = observation.recording_block_id
        stage_id = observation.location.stage_id
        return (
            recording_block_id.to_json() if recording_block_id is not None else None,
            stage_id.to_json() if stage_id is not None else None,
        )

    def _evidence_set_for_group(
        self,
        group: tuple[tuple[Observation, RecordingCoverageEvidenceMapping], ...],
    ) -> tuple[EvidenceSet | None, tuple[EntityId, ...]]:
        items: list[EvidenceItem] = []
        signals: list[EvidenceSignalReference] = []
        applied_rule_ids: list[EntityId] = []

        for observation, mapping in group:
            rule = self._rule_for_mapping(mapping)
            if rule is None:
                continue
            item = self._evidence_item_for_observation(observation, mapping, rule)
            items.append(item)
            signals.append(
                self._signal_reference_for_observation(
                    observation=observation,
                    mapping=mapping,
                    rule=rule,
                    item=item,
                )
            )
            applied_rule_ids.append(rule.id)

        if not items:
            return None, ()

        first_observation = group[0][0]
        return (
            EvidenceSet(
                id=EntityId.new(),
                recording_block_id=first_observation.recording_block_id,
                concern=EvidenceConcern.RECORDING_COVERAGE,
                purpose=EvidencePurpose.TRANSITION_SUPPORT,
                items=tuple(items),
                signals=tuple(signals),
                correlation_id=first_observation.correlation_id,
                created_at=first_observation.observed_at,
                notes="Evidence organized for recording coverage.",
                metadata={
                    "recording_coverage_evidence_builder_id": self.id.to_json(),
                    "source_observation_ids": tuple(
                        observation.id.to_json() for observation, _ in group
                    ),
                    "recording_block_id": (
                        first_observation.recording_block_id.to_json()
                        if first_observation.recording_block_id is not None
                        else None
                    ),
                    "stage_id": (
                        first_observation.location.stage_id.to_json()
                        if first_observation.location.stage_id is not None
                        else None
                    ),
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
    ) -> EvidenceItem:
        return EvidenceItem(
            id=EntityId.new(),
            observation_id=observation.id,
            role=rule.evidence_role,
            strength=rule.evidence_strength,
            rationale=rule.rationale(),
            metadata={
                "recording_activity": mapping.recording_activity,
                "recording_event_kind": mapping.recording_event_kind,
                "evidence_builder_rule_id": rule.id.to_json(),
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
    ) -> EvidenceSignalReference:
        return EvidenceSignalReference(
            signal=mapping.evidence_signal,
            evidence_item_ids=(item.id,),
            observation_ids=(observation.id,),
            rationale=mapping.rationale,
            metadata={
                "evidence_builder_rule_id": rule.id.to_json(),
                "recording_activity": mapping.recording_activity,
                "recording_block_id": (
                    observation.recording_block_id.to_json()
                    if observation.recording_block_id is not None
                    else None
                ),
                "stage_id": (
                    observation.location.stage_id.to_json()
                    if observation.location.stage_id is not None
                    else None
                ),
                "observation_location": self._location_metadata(observation),
            },
        )

    def _location_metadata(self, observation: Observation) -> Mapping[str, Any]:
        location = observation.location
        metadata: dict[str, Any] = {
            "kind": location.kind.value if location.kind is not None else None,
            "recording_block_id": (
                observation.recording_block_id.to_json()
                if observation.recording_block_id is not None
                else None
            ),
            "stage_id": location.stage_id.to_json() if location.stage_id is not None else None,
        }
        if location.point is not None:
            metadata["timeline_offset_seconds"] = self._seconds(location.point.offset)
        if location.range is not None:
            metadata["timeline_range_start_seconds"] = self._seconds(
                location.range.start.offset
            )
            metadata["timeline_range_end_seconds"] = self._seconds(
                location.range.end.offset
            )
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
