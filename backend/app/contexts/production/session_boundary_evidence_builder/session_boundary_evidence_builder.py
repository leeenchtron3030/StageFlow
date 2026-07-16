from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
    EvidenceStrength,
)
from app.shared.ids import EntityId

from .session_boundary_evidence_context import SessionBoundaryEvidenceContext
from .session_boundary_evidence_mapping import (
    SESSION_BOUNDARY_EVIDENCE_MAPPINGS,
    SUPPORTED_SESSION_BOUNDARY_SOURCE_CONCERNS,
    SessionBoundaryEvidenceMapping,
)
from .session_boundary_evidence_result import SessionBoundaryEvidenceResult
from .session_boundary_evidence_rule import SessionBoundaryEvidenceRule

DEFAULT_BOUNDARY_COMPOSITION_WINDOW = timedelta(minutes=5)


class SessionBoundaryEvidenceBuilderStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    ARCHIVED = "archived"


_BUILDABLE_STATUSES = {
    SessionBoundaryEvidenceBuilderStatus.READY,
    SessionBoundaryEvidenceBuilderStatus.ACTIVE,
    SessionBoundaryEvidenceBuilderStatus.DEGRADED,
}


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _stable_entity_id(name: str) -> EntityId:
    return EntityId.parse(str(uuid5(NAMESPACE_URL, f"stageflow:session-boundary:{name}")))


def default_session_boundary_evidence_rules() -> tuple[SessionBoundaryEvidenceRule, ...]:
    return tuple(
        SessionBoundaryEvidenceRule(
            id=_stable_entity_id(
                "rule:"
                f"{mapping.source_concern.value}:{mapping.source_signal.value}:"
                f"{mapping.target_concern.value}:{mapping.target_role.value}"
            ),
            accepted_source_concerns=(mapping.source_concern,),
            accepted_signal=mapping.source_signal,
            target_boundary_concern=mapping.target_concern,
            target_role=mapping.target_role,
            rationale_template=mapping.rationale,
            strength_treatment=mapping.strength_treatment,
        )
        for mapping in SESSION_BOUNDARY_EVIDENCE_MAPPINGS
    )


@dataclass(frozen=True, slots=True)
class _MergedSourceSignal:
    signal: EvidenceSignal
    evidence_item_ids: tuple[EntityId, ...]
    observation_ids: tuple[EntityId, ...]
    references: tuple[EvidenceSignalReference, ...]


@dataclass(frozen=True, slots=True)
class _Contribution:
    source_set: EvidenceSet
    source_signal: _MergedSourceSignal
    mapping: SessionBoundaryEvidenceMapping
    rule: SessionBoundaryEvidenceRule
    source_items: tuple[EvidenceItem, ...]
    recording_block_id: EntityId | None
    stage_id: EntityId | None
    scheduled_activity_id: EntityId | None
    transcript_stream_ids: tuple[str, ...]
    media_artifact_ids: tuple[str, ...]
    timeline_start_seconds: float | None
    timeline_end_seconds: float | None
    anchor_seconds: float | None
    anchor_at: datetime
    input_index: int


@dataclass(frozen=True, slots=True)
class SessionBoundaryEvidenceBuilder:
    """Composes structured domain Evidence into possible-boundary Evidence only."""

    id: EntityId
    name: str = "Session Boundary Evidence Builder"
    status: SessionBoundaryEvidenceBuilderStatus = SessionBoundaryEvidenceBuilderStatus.READY
    rules: Sequence[SessionBoundaryEvidenceRule] = field(
        default_factory=default_session_boundary_evidence_rules
    )
    mappings: Sequence[SessionBoundaryEvidenceMapping] = field(
        default_factory=lambda: SESSION_BOUNDARY_EVIDENCE_MAPPINGS
    )
    composition_window: timedelta = DEFAULT_BOUNDARY_COMPOSITION_WINDOW
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("SessionBoundaryEvidenceBuilder name must not be empty.")
        if self.composition_window <= timedelta(0):
            raise ValueError("Boundary composition window must be greater than zero.")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def can_build(self) -> bool:
        return self.status in _BUILDABLE_STATUSES

    def build(self, evidence_sets: Sequence[EvidenceSet]) -> SessionBoundaryEvidenceResult:
        inputs = tuple(evidence_sets)
        if not self.can_build():
            return SessionBoundaryEvidenceResult(
                start_boundary_evidence_sets=(),
                end_boundary_evidence_sets=(),
                consumed_source_evidence_set_ids=(),
                ignored_source_evidence_set_ids=tuple(item.id for item in inputs),
                unsupported_source_evidence_set_ids=(),
                duplicate_source_evidence_set_ids=(),
                applied_rule_ids=(),
                generated_boundary_contexts=(),
                metadata={
                    "builder_id": self.id.to_json(),
                    "builder_status": self.status.value,
                    "input_evidence_set_count": len(inputs),
                },
            )

        ordered = self._order_inputs(inputs)
        retained: list[tuple[EvidenceSet, int]] = []
        duplicate_ids: list[EntityId] = []
        seen_ids: set[EntityId] = set()
        for evidence_set, input_index in ordered:
            if evidence_set.id in seen_ids:
                duplicate_ids.append(evidence_set.id)
                continue
            seen_ids.add(evidence_set.id)
            retained.append((evidence_set, input_index))

        consumed_ids: list[EntityId] = []
        ignored_ids: list[EntityId] = []
        unsupported_ids: list[EntityId] = []
        contributions: list[_Contribution] = []
        unsupported_combinations: list[str] = []

        for evidence_set, input_index in retained:
            source_contributions, unsupported_signals = self._contributions_for_set(
                evidence_set,
                input_index,
            )
            if source_contributions:
                consumed_ids.append(evidence_set.id)
                contributions.extend(source_contributions)
                unsupported_combinations.extend(unsupported_signals)
            elif (
                evidence_set.concern in SUPPORTED_SESSION_BOUNDARY_SOURCE_CONCERNS
                or evidence_set.concern
                in {
                    EvidenceConcern.POSSIBLE_SESSION_START,
                    EvidenceConcern.POSSIBLE_SESSION_END,
                }
            ):
                unsupported_ids.append(evidence_set.id)
                unsupported_combinations.extend(unsupported_signals)
            else:
                ignored_ids.append(evidence_set.id)

        groups = self._group_contributions(tuple(contributions))
        outputs: list[EvidenceSet] = []
        contexts: list[SessionBoundaryEvidenceContext] = []
        applied_rule_ids: list[EntityId] = []
        for group in groups:
            evidence_set, context, rule_ids = self._build_group(group)
            outputs.append(evidence_set)
            contexts.append(context)
            applied_rule_ids.extend(rule_ids)

        paired = sorted(
            zip(outputs, contexts, strict=True),
            key=lambda pair: self._output_ordering_key(pair[0], pair[1]),
        )
        ordered_outputs = tuple(pair[0] for pair in paired)
        ordered_contexts = tuple(pair[1] for pair in paired)
        start_outputs = tuple(
            output
            for output in ordered_outputs
            if output.concern is EvidenceConcern.POSSIBLE_SESSION_START
        )
        end_outputs = tuple(
            output
            for output in ordered_outputs
            if output.concern is EvidenceConcern.POSSIBLE_SESSION_END
        )

        return SessionBoundaryEvidenceResult(
            start_boundary_evidence_sets=start_outputs,
            end_boundary_evidence_sets=end_outputs,
            consumed_source_evidence_set_ids=tuple(consumed_ids),
            ignored_source_evidence_set_ids=tuple(ignored_ids),
            unsupported_source_evidence_set_ids=tuple(unsupported_ids),
            duplicate_source_evidence_set_ids=tuple(duplicate_ids),
            applied_rule_ids=tuple(dict.fromkeys(applied_rule_ids)),
            generated_boundary_contexts=ordered_contexts,
            metadata={
                "builder_id": self.id.to_json(),
                "builder_status": self.status.value,
                "input_evidence_set_count": len(inputs),
                "composition_window_seconds": self.composition_window.total_seconds(),
                "grouping_behavior": (
                    "boundary_concern_recording_block_stage_scheduled_activity_"
                    "correlation_and_bounded_temporal_neighborhood"
                ),
                "ordering_behavior": (
                    "source_created_at_then_timeline_then_evidence_set_id_then_input_index"
                ),
                "duplicate_behavior": "first_deterministic_evidence_set_kept",
                "anchor_behavior": (
                    "earliest_contributing_anchor_for_start_latest_for_end"
                ),
                "unsupported_combinations": tuple(unsupported_combinations),
                "semantic_conclusion": None,
                "possible_boundary_only": True,
            },
        )

    def _order_inputs(
        self,
        evidence_sets: tuple[EvidenceSet, ...],
    ) -> tuple[tuple[EvidenceSet, int], ...]:
        indexed = tuple((evidence_set, index) for index, evidence_set in enumerate(evidence_sets))
        return tuple(
            sorted(
                indexed,
                key=lambda pair: (
                    pair[0].created_at,
                    self._set_timeline_start(pair[0]),
                    pair[0].id.to_json(),
                    pair[1],
                ),
            )
        )

    def _contributions_for_set(
        self,
        evidence_set: EvidenceSet,
        input_index: int,
    ) -> tuple[tuple[_Contribution, ...], tuple[str, ...]]:
        contributions: list[_Contribution] = []
        unsupported: list[str] = []
        for source_signal in self._merged_signals(evidence_set):
            mappings = tuple(
                mapping
                for mapping in self.mappings
                if mapping.source_concern is evidence_set.concern
                and mapping.source_signal is source_signal.signal
            )
            if not mappings:
                unsupported.append(
                    f"{evidence_set.id.to_json()}:{evidence_set.concern.value}:"
                    f"{source_signal.signal.value}"
                )
                continue
            source_items = self._source_items(evidence_set, source_signal)
            if not source_items:
                unsupported.append(
                    f"{evidence_set.id.to_json()}:{source_signal.signal.value}:"
                    "missing_evidence_item_linkage"
                )
                continue
            for mapping in mappings:
                rule = self._rule_for_mapping(mapping)
                if rule is None:
                    unsupported.append(
                        f"{evidence_set.id.to_json()}:{source_signal.signal.value}:"
                        "missing_declarative_rule"
                    )
                    continue
                contributions.append(
                    self._make_contribution(
                        evidence_set,
                        source_signal,
                        source_items,
                        mapping,
                        rule,
                        input_index,
                    )
                )
        return tuple(contributions), tuple(unsupported)

    def _merged_signals(self, evidence_set: EvidenceSet) -> tuple[_MergedSourceSignal, ...]:
        grouped: dict[EvidenceSignal, list[EvidenceSignalReference]] = {}
        signal_order: list[EvidenceSignal] = []
        for reference in evidence_set.signals:
            if reference.signal not in grouped:
                grouped[reference.signal] = []
                signal_order.append(reference.signal)
            grouped[reference.signal].append(reference)

        merged: list[_MergedSourceSignal] = []
        for signal in signal_order:
            references = tuple(grouped[signal])
            merged.append(
                _MergedSourceSignal(
                    signal=signal,
                    evidence_item_ids=tuple(
                        dict.fromkeys(
                            item_id
                            for reference in references
                            for item_id in reference.evidence_item_ids
                        )
                    ),
                    observation_ids=tuple(
                        dict.fromkeys(
                            observation_id
                            for reference in references
                            for observation_id in reference.observation_ids
                        )
                    ),
                    references=references,
                )
            )
        return tuple(merged)

    def _source_items(
        self,
        evidence_set: EvidenceSet,
        source_signal: _MergedSourceSignal,
    ) -> tuple[EvidenceItem, ...]:
        linked_ids = set(source_signal.evidence_item_ids)
        linked_observations = set(source_signal.observation_ids)
        if linked_ids:
            return tuple(item for item in evidence_set.items if item.id in linked_ids)
        if linked_observations:
            return tuple(
                item for item in evidence_set.items if item.observation_id in linked_observations
            )
        if len(evidence_set.items) == 1:
            return tuple(evidence_set.items)
        return ()

    def _rule_for_mapping(
        self,
        mapping: SessionBoundaryEvidenceMapping,
    ) -> SessionBoundaryEvidenceRule | None:
        for rule in self.rules:
            if (
                rule.accepts(mapping.source_concern, mapping.source_signal)
                and rule.target_boundary_concern is mapping.target_concern
                and rule.target_role is mapping.target_role
            ):
                return rule
        return None

    def _make_contribution(
        self,
        evidence_set: EvidenceSet,
        source_signal: _MergedSourceSignal,
        source_items: tuple[EvidenceItem, ...],
        mapping: SessionBoundaryEvidenceMapping,
        rule: SessionBoundaryEvidenceRule,
        input_index: int,
    ) -> _Contribution:
        metadata_sources = self._metadata_sources(evidence_set, source_signal, source_items)
        timeline_starts, timeline_ends = self._timeline_values(metadata_sources)
        anchor_seconds: float | None = None
        if mapping.target_concern is EvidenceConcern.POSSIBLE_SESSION_START:
            if timeline_starts:
                anchor_seconds = min(timeline_starts)
        elif timeline_ends:
            anchor_seconds = max(timeline_ends)
        timestamps = tuple(
            timestamp
            for timestamp in (
                self._timestamp_from_metadata(source.metadata)
                for source in source_items
            )
            if timestamp is not None
        )
        if mapping.target_concern is EvidenceConcern.POSSIBLE_SESSION_START:
            anchor_at = min(timestamps) if timestamps else evidence_set.created_at
        else:
            anchor_at = max(timestamps) if timestamps else evidence_set.created_at

        return _Contribution(
            source_set=evidence_set,
            source_signal=source_signal,
            mapping=mapping,
            rule=rule,
            source_items=source_items,
            recording_block_id=evidence_set.recording_block_id
            or self._entity_from_sources(metadata_sources, ("recording_block_id",)),
            stage_id=self._entity_from_sources(metadata_sources, ("stage_id",)),
            scheduled_activity_id=self._entity_from_sources(
                metadata_sources,
                ("scheduled_activity_id", "schedule_activity_id"),
            ),
            transcript_stream_ids=self._identifiers_from_sources(
                metadata_sources,
                ("transcript_stream_ids", "transcript_stream_id", "stream_id"),
            ),
            media_artifact_ids=self._identifiers_from_sources(
                metadata_sources,
                ("media_artifact_ids", "media_artifact_id", "artifact_id"),
            ),
            timeline_start_seconds=min(timeline_starts) if timeline_starts else None,
            timeline_end_seconds=max(timeline_ends) if timeline_ends else None,
            anchor_seconds=anchor_seconds,
            anchor_at=anchor_at,
            input_index=input_index,
        )

    def _metadata_sources(
        self,
        evidence_set: EvidenceSet,
        source_signal: _MergedSourceSignal,
        source_items: tuple[EvidenceItem, ...],
    ) -> tuple[Mapping[str, Any], ...]:
        sources: list[Mapping[str, Any]] = []
        for reference in source_signal.references:
            sources.append(reference.metadata)
            location = reference.metadata.get("observation_location")
            if isinstance(location, Mapping):
                sources.append(cast(Mapping[str, Any], location))
        for item in source_items:
            sources.append(item.metadata)
            location = item.metadata.get("observation_location")
            if isinstance(location, Mapping):
                sources.append(cast(Mapping[str, Any], location))
        sources.append(evidence_set.metadata)
        return tuple(sources)

    def _group_contributions(
        self,
        contributions: tuple[_Contribution, ...],
    ) -> tuple[tuple[_Contribution, ...], ...]:
        base_groups: dict[tuple[str, ...], list[_Contribution]] = {}
        for contribution in contributions:
            unknown_discriminator = ""
            if (
                contribution.recording_block_id is None
                and contribution.stage_id is None
                and contribution.scheduled_activity_id is None
            ):
                unknown_discriminator = contribution.source_set.id.to_json()
            key = (
                contribution.mapping.target_concern.value,
                contribution.source_set.correlation_id.to_json(),
                self._id_value(contribution.recording_block_id),
                self._id_value(contribution.stage_id),
                self._id_value(contribution.scheduled_activity_id),
                unknown_discriminator,
            )
            base_groups.setdefault(key, []).append(contribution)

        groups: list[tuple[_Contribution, ...]] = []
        for key in sorted(base_groups):
            ordered = sorted(base_groups[key], key=self._contribution_ordering_key)
            current: list[_Contribution] = []
            cluster_coordinate: tuple[str, float] | None = None
            for contribution in ordered:
                coordinate = self._coordinate(contribution)
                if not current:
                    current = [contribution]
                    cluster_coordinate = coordinate
                    continue
                if (
                    cluster_coordinate is not None
                    and coordinate[0] == cluster_coordinate[0]
                    and coordinate[1] - cluster_coordinate[1]
                    <= self.composition_window.total_seconds()
                ):
                    current.append(contribution)
                else:
                    groups.append(tuple(current))
                    current = [contribution]
                    cluster_coordinate = coordinate
            if current:
                groups.append(tuple(current))
        return tuple(groups)

    def _build_group(
        self,
        group: tuple[_Contribution, ...],
    ) -> tuple[EvidenceSet, SessionBoundaryEvidenceContext, tuple[EntityId, ...]]:
        concern = group[0].mapping.target_concern
        ordered = tuple(sorted(group, key=self._contribution_ordering_key))
        source_set_ids = tuple(
            dict.fromkeys(contribution.source_set.id for contribution in ordered)
        )
        rule_ids = tuple(dict.fromkeys(contribution.rule.id for contribution in ordered))
        context = self._context_for_group(ordered)
        items: list[EvidenceItem] = []
        signals: list[EvidenceSignalReference] = []
        for contribution in ordered:
            contribution_items: list[EvidenceItem] = []
            for source_item in contribution.source_items:
                output_item = self._output_item(contribution, source_item, context.id)
                items.append(output_item)
                contribution_items.append(output_item)
            signals.append(
                EvidenceSignalReference(
                    signal=contribution.source_signal.signal,
                    evidence_item_ids=tuple(item.id for item in contribution_items),
                    observation_ids=tuple(
                        dict.fromkeys(
                            contribution.source_signal.observation_ids
                            + tuple(
                                item.observation_id
                                for item in contribution.source_items
                            )
                        )
                    ),
                    rationale=contribution.rule.rationale(),
                    metadata={
                        "source_evidence_set_ids": (
                            contribution.source_set.id.to_json(),
                        ),
                        "source_evidence_item_ids": tuple(
                            item.id.to_json() for item in contribution.source_items
                        ),
                        "source_observation_ids": tuple(
                            observation_id.to_json()
                            for observation_id in dict.fromkeys(
                                contribution.source_signal.observation_ids
                                + tuple(
                                    item.observation_id
                                    for item in contribution.source_items
                                )
                            )
                        ),
                        "source_concern": contribution.source_set.concern.value,
                        "source_signal": contribution.source_signal.signal.value,
                        "assigned_boundary_role": self._target_role(contribution).value,
                        "session_boundary_rule_id": contribution.rule.id.to_json(),
                        "boundary_context_id": context.id.to_json(),
                        "possible_boundary_only": True,
                    },
                )
            )

        output_id = _stable_entity_id(
            "evidence-set:"
            f"{concern.value}:{context.id.to_json()}:"
            + ":".join(source_id.to_json() for source_id in source_set_ids)
        )
        anchor_at = context.boundary_anchor_at or ordered[0].source_set.created_at
        return (
            EvidenceSet(
                id=output_id,
                recording_block_id=context.recording_block_id,
                concern=concern,
                purpose=EvidencePurpose.TRANSITION_SUPPORT,
                items=tuple(items),
                signals=tuple(signals),
                correlation_id=ordered[0].source_set.correlation_id,
                created_at=anchor_at,
                notes=(
                    "Evidence organized for a possible session boundary; no boundary, "
                    "transition, or Session State is concluded."
                ),
                metadata={
                    "session_boundary_evidence_builder_id": self.id.to_json(),
                    "boundary_context_id": context.id.to_json(),
                    "source_evidence_set_ids": tuple(
                        source_id.to_json() for source_id in source_set_ids
                    ),
                    "source_evidence_item_ids": tuple(
                        dict.fromkeys(
                            item.id.to_json()
                            for contribution in ordered
                            for item in contribution.source_items
                        )
                    ),
                    "source_observation_ids": tuple(
                        dict.fromkeys(
                            observation_id.to_json()
                            for contribution in ordered
                            for observation_id in (
                                contribution.source_signal.observation_ids
                                + tuple(
                                    item.observation_id
                                    for item in contribution.source_items
                                )
                            )
                        )
                    ),
                    "source_concerns": tuple(
                        dict.fromkeys(
                            contribution.source_set.concern.value
                            for contribution in ordered
                        )
                    ),
                    "source_signals": tuple(
                        contribution.source_signal.signal.value
                        for contribution in ordered
                    ),
                    "applied_rule_ids": tuple(rule_id.to_json() for rule_id in rule_ids),
                    "recording_block_id": self._optional_json(context.recording_block_id),
                    "stage_id": self._optional_json(context.stage_id),
                    "scheduled_activity_id": self._optional_json(
                        context.scheduled_activity_id
                    ),
                    "transcript_stream_ids": tuple(
                        context.transcript_stream_ids
                    ),
                    "media_artifact_ids": tuple(
                        context.media_artifact_ids
                    ),
                    "timeline_start_seconds": context.timeline_start_seconds,
                    "timeline_end_seconds": context.timeline_end_seconds,
                    "boundary_anchor_seconds": context.boundary_anchor_seconds,
                    "boundary_anchor_at": (
                        context.boundary_anchor_at.isoformat()
                        if context.boundary_anchor_at is not None
                        else None
                    ),
                    "boundary_anchor_policy": (
                        "earliest_contributing_anchor"
                        if concern is EvidenceConcern.POSSIBLE_SESSION_START
                        else "latest_contributing_anchor"
                    ),
                    "grouping_rationale": (
                        "Compatible source Evidence shares boundary orientation, correlation, "
                        "recording block, stage, known scheduled activity, and the configured "
                        "composition window."
                    ),
                    "composition_window_seconds": self.composition_window.total_seconds(),
                    "semantic_conclusion": None,
                    "final_boundary_timestamp": None,
                    "possible_boundary_only": True,
                },
            ),
            context,
            rule_ids,
        )

    def _output_item(
        self,
        contribution: _Contribution,
        source_item: EvidenceItem,
        context_id: EntityId,
    ) -> EvidenceItem:
        role = self._target_role(contribution, source_item)
        strength = contribution.rule.strength_treatment or source_item.strength
        output_id = _stable_entity_id(
            "evidence-item:"
            f"{contribution.mapping.target_concern.value}:"
            f"{contribution.source_set.id.to_json()}:{source_item.id.to_json()}:"
            f"{contribution.source_signal.signal.value}:{contribution.rule.id.to_json()}"
        )
        return EvidenceItem(
            id=output_id,
            observation_id=source_item.observation_id,
            role=role,
            strength=strength,
            rationale=contribution.rule.rationale(),
            metadata={
                "source_evidence_set_id": contribution.source_set.id.to_json(),
                "source_evidence_item_id": source_item.id.to_json(),
                "source_observation_id": source_item.observation_id.to_json(),
                "source_concern": contribution.source_set.concern.value,
                "source_signal": contribution.source_signal.signal.value,
                "source_role": source_item.role.value,
                "source_strength": source_item.strength.value,
                "session_boundary_rule_id": contribution.rule.id.to_json(),
                "boundary_context_id": context_id.to_json(),
                "strength_treatment": (
                    "preserved"
                    if contribution.rule.strength_treatment is None
                    else "declarative_override"
                ),
                "possible_boundary_only": True,
            },
        )

    def _target_role(
        self,
        contribution: _Contribution,
        source_item: EvidenceItem | None = None,
    ) -> EvidenceRole:
        if source_item is None and any(
            item.role is EvidenceRole.CONTRADICTS
            or item.strength is EvidenceStrength.CONTRADICTORY
            for item in contribution.source_items
        ):
            return EvidenceRole.CONTRADICTS
        if source_item is not None and (
            source_item.role is EvidenceRole.CONTRADICTS
            or source_item.strength is EvidenceStrength.CONTRADICTORY
        ):
            return EvidenceRole.CONTRADICTS
        return contribution.rule.target_role

    def _context_for_group(
        self,
        group: tuple[_Contribution, ...],
    ) -> SessionBoundaryEvidenceContext:
        concern = group[0].mapping.target_concern
        recording_block_id = group[0].recording_block_id
        stage_id = group[0].stage_id
        scheduled_activity_id = group[0].scheduled_activity_id
        starts = tuple(
            value
            for contribution in group
            for value in (contribution.timeline_start_seconds,)
            if value is not None
        )
        ends = tuple(
            value
            for contribution in group
            for value in (contribution.timeline_end_seconds,)
            if value is not None
        )
        anchor_seconds_values = tuple(
            contribution.anchor_seconds
            for contribution in group
            if contribution.anchor_seconds is not None
        )
        anchor_at_values = tuple(contribution.anchor_at for contribution in group)
        anchor_seconds = None
        if concern is EvidenceConcern.POSSIBLE_SESSION_START:
            if anchor_seconds_values:
                anchor_seconds = min(anchor_seconds_values)
            anchor_at = min(anchor_at_values)
        else:
            if anchor_seconds_values:
                anchor_seconds = max(anchor_seconds_values)
            anchor_at = max(anchor_at_values)
        source_set_ids = tuple(
            dict.fromkeys(contribution.source_set.id for contribution in group)
        )
        context_id = _stable_entity_id(
            "context:"
            f"{concern.value}:{self._id_value(recording_block_id)}:"
            f"{self._id_value(stage_id)}:{self._id_value(scheduled_activity_id)}:"
            f"{anchor_seconds if anchor_seconds is not None else anchor_at.isoformat()}:"
            + ":".join(source_id.to_json() for source_id in source_set_ids)
        )
        return SessionBoundaryEvidenceContext(
            id=context_id,
            boundary_concern=concern,
            recording_block_id=recording_block_id,
            stage_id=stage_id,
            scheduled_activity_id=scheduled_activity_id,
            transcript_stream_ids=tuple(
                dict.fromkeys(
                    stream_id
                    for contribution in group
                    for stream_id in contribution.transcript_stream_ids
                )
            ),
            media_artifact_ids=tuple(
                dict.fromkeys(
                    artifact_id
                    for contribution in group
                    for artifact_id in contribution.media_artifact_ids
                )
            ),
            timeline_start_seconds=min(starts) if starts else None,
            timeline_end_seconds=max(ends) if ends else None,
            boundary_anchor_seconds=anchor_seconds,
            boundary_anchor_at=anchor_at,
            context_label=self._context_label(group),
            metadata={
                "source_evidence_set_ids": tuple(
                    source_id.to_json() for source_id in source_set_ids
                ),
                "composition_window_seconds": self.composition_window.total_seconds(),
                "anchor_is_organizational_only": True,
                "session_id": None,
            },
        )

    def _context_label(self, group: tuple[_Contribution, ...]) -> str | None:
        for contribution in group:
            value = contribution.source_set.metadata.get("context_label")
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _contribution_ordering_key(
        self,
        contribution: _Contribution,
    ) -> tuple[str, float, datetime, str, str, int]:
        coordinate_kind, coordinate_value = self._coordinate(contribution)
        return (
            coordinate_kind,
            coordinate_value,
            contribution.anchor_at,
            contribution.source_set.id.to_json(),
            contribution.source_signal.signal.value,
            contribution.input_index,
        )

    def _coordinate(self, contribution: _Contribution) -> tuple[str, float]:
        if contribution.anchor_seconds is not None:
            return "timeline", contribution.anchor_seconds
        return "wall_clock", contribution.anchor_at.timestamp()

    def _output_ordering_key(
        self,
        evidence_set: EvidenceSet,
        context: SessionBoundaryEvidenceContext,
    ) -> tuple[datetime, float, str, str]:
        return (
            context.boundary_anchor_at or evidence_set.created_at,
            context.boundary_anchor_seconds
            if context.boundary_anchor_seconds is not None
            else float("inf"),
            evidence_set.concern.value,
            evidence_set.id.to_json(),
        )

    def _set_timeline_start(self, evidence_set: EvidenceSet) -> float:
        values: list[float] = []
        for item in evidence_set.items:
            sources: list[Mapping[str, Any]] = [item.metadata]
            location = item.metadata.get("observation_location")
            if isinstance(location, Mapping):
                sources.append(cast(Mapping[str, Any], location))
            starts, _ends = self._timeline_values(tuple(sources))
            values.extend(starts)
        return min(values) if values else float("inf")

    def _timeline_values(
        self,
        sources: tuple[Mapping[str, Any], ...],
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        starts: list[float] = []
        ends: list[float] = []
        for source in sources:
            point = self._number(source.get("timeline_offset_seconds"))
            start = self._number(source.get("timeline_range_start_seconds"))
            end = self._number(source.get("timeline_range_end_seconds"))
            if point is not None:
                starts.append(point)
                ends.append(point)
            if start is not None:
                starts.append(start)
            if end is not None:
                ends.append(end)
        return tuple(starts), tuple(ends)

    def _timestamp_from_metadata(self, metadata: Mapping[str, Any]) -> datetime | None:
        for key in ("observation_observed_at", "wall_clock_at", "evidence_timestamp"):
            parsed = self._datetime(metadata.get(key))
            if parsed is not None:
                return parsed
        location = metadata.get("observation_location")
        if isinstance(location, Mapping):
            typed_location = cast(Mapping[str, object], location)
            return self._datetime(typed_location.get("wall_clock_at"))
        return None

    def _entity_from_sources(
        self,
        sources: tuple[Mapping[str, Any], ...],
        keys: tuple[str, ...],
    ) -> EntityId | None:
        entities = self._entities_from_sources(sources, keys)
        return entities[0] if entities else None

    def _entities_from_sources(
        self,
        sources: tuple[Mapping[str, Any], ...],
        keys: tuple[str, ...],
    ) -> tuple[EntityId, ...]:
        entities: list[EntityId] = []
        for source in sources:
            for key in keys:
                raw = source.get(key)
                values: Sequence[object]
                if isinstance(raw, tuple | list):
                    values = cast(Sequence[object], raw)
                else:
                    values = (raw,)
                for value in values:
                    entity = self._entity(value)
                    if entity is not None and entity not in entities:
                        entities.append(entity)
        return tuple(entities)

    def _entity(self, value: object) -> EntityId | None:
        if isinstance(value, EntityId):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return EntityId.parse(value)
        except ValueError:
            return None

    def _identifiers_from_sources(
        self,
        sources: tuple[Mapping[str, Any], ...],
        keys: tuple[str, ...],
    ) -> tuple[str, ...]:
        identifiers: list[str] = []
        for source in sources:
            for key in keys:
                raw = source.get(key)
                values: Sequence[object]
                if isinstance(raw, tuple | list):
                    values = cast(Sequence[object], raw)
                else:
                    values = (raw,)
                for value in values:
                    identifier: str | None = None
                    if isinstance(value, EntityId):
                        identifier = value.to_json()
                    elif isinstance(value, str) and value.strip():
                        identifier = value
                    if identifier is not None and identifier not in identifiers:
                        identifiers.append(identifier)
        return tuple(identifiers)

    def _datetime(self, value: object) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def _number(self, value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        return None

    def _id_value(self, value: EntityId | None) -> str:
        return value.to_json() if value is not None else ""

    def _optional_json(self, value: EntityId | None) -> str | None:
        return value.to_json() if value is not None else None


def make_session_boundary_evidence_builder(
    *,
    builder_id: EntityId | None = None,
    name: str = "Session Boundary Evidence Builder",
    composition_window: timedelta = DEFAULT_BOUNDARY_COMPOSITION_WINDOW,
) -> SessionBoundaryEvidenceBuilder:
    return SessionBoundaryEvidenceBuilder(
        id=builder_id or EntityId.new(),
        name=name,
        composition_window=composition_window,
    )
