from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import (
    EvidenceItem,
    EvidenceSet,
)
from app.contexts.production.evidence_builder.evidence_builder_context import (
    EvidenceBuilderContext,
)
from app.contexts.production.evidence_builder.evidence_builder_result import (
    EvidenceBuilderResult,
)
from app.contexts.production.evidence_builder.evidence_builder_rule import (
    EvidenceBuilderRule,
)
from app.contexts.production.observation import Observation, ObservationType
from app.shared.ids import EntityId


class EvidenceBuilderStatus(StrEnum):
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
    EvidenceBuilderStatus.READY,
    EvidenceBuilderStatus.ACTIVE,
    EvidenceBuilderStatus.DEGRADED,
}


def default_evidence_builder_rules() -> tuple[EvidenceBuilderRule, ...]:
    """Default single-domain rules for objective Observation concerns."""

    return (
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern="recording_activity",
            supporting_observation_types=(ObservationType.RECORDING_ACTIVITY,),
            description="Groups recording activity Observations.",
        ),
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern="media_artifact_availability",
            supporting_observation_types=(ObservationType.MEDIA_ARTIFACT,),
            description="Groups media artifact availability Observations.",
        ),
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern="time_boundary",
            supporting_observation_types=(ObservationType.TIME_BOUNDARY,),
            description="Groups runtime clock time-boundary Observations.",
        ),
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern="scheduled_activity",
            supporting_observation_types=(ObservationType.SCHEDULE_ACTIVITY,),
            description="Groups planned schedule activity Observations.",
        ),
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern="transcript_activity",
            supporting_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
            description="Groups transcript availability Observations.",
        ),
        EvidenceBuilderRule(
            id=EntityId.new(),
            operational_concern="vision_activity",
            supporting_observation_types=(ObservationType.VISION_ACTIVITY,),
            description="Groups visual phenomena Observations.",
        ),
    )


@dataclass(frozen=True, slots=True)
class ObservationEvidenceBuilder:
    """Builds explainable Evidence from objective Observations."""

    id: EntityId
    name: str
    status: EvidenceBuilderStatus = EvidenceBuilderStatus.READY
    rules: Sequence[EvidenceBuilderRule] = field(default_factory=default_evidence_builder_rules)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ObservationEvidenceBuilder name must not be empty.")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def can_build(self) -> bool:
        return self.status in _BUILDABLE_STATUSES

    def build(
        self,
        observations: Sequence[Observation],
        context: EvidenceBuilderContext,
    ) -> EvidenceBuilderResult:
        observation_tuple = tuple(observations)
        source_observation_ids = tuple(observation.id for observation in observation_tuple)
        warnings: list[str] = []

        if not observation_tuple:
            return EvidenceBuilderResult(
                source_observation_ids=(),
                evidence_sets=(),
                builder_id=self.id,
                warnings=("No Observations were provided.",),
                metadata={"correlation_id": context.correlation_id.to_json()},
            )

        if not self.can_build():
            return EvidenceBuilderResult(
                source_observation_ids=source_observation_ids,
                evidence_sets=(),
                builder_id=self.id,
                warnings=("ObservationEvidenceBuilder is not in a buildable status.",),
                metadata={"correlation_id": context.correlation_id.to_json()},
            )

        evidence_sets: list[EvidenceSet] = []
        grouped_observation_ids: set[EntityId] = set()

        for rule in self.rules:
            matching = self._matching_observations(rule, observation_tuple)
            if not matching:
                continue

            evidence_sets.append(
                self._evidence_set_for_rule(
                    rule=rule,
                    matches=matching,
                    context=context,
                )
            )
            grouped_observation_ids.update(observation.id for observation, _role in matching)

        ungrouped_ids = tuple(
            observation.id.to_json()
            for observation in observation_tuple
            if observation.id not in grouped_observation_ids
        )
        if ungrouped_ids:
            warnings.append("Some Observations did not match an EvidenceBuilderRule.")

        return EvidenceBuilderResult(
            source_observation_ids=source_observation_ids,
            evidence_sets=tuple(evidence_sets),
            builder_id=self.id,
            warnings=tuple(warnings),
            metadata={
                "correlation_id": context.correlation_id.to_json(),
                "source_observation_count": len(source_observation_ids),
                "ungrouped_observation_ids": ungrouped_ids,
            },
        )

    def _matching_observations(
        self,
        rule: EvidenceBuilderRule,
        observations: tuple[Observation, ...],
    ) -> tuple[tuple[Observation, str], ...]:
        matches: list[tuple[Observation, str]] = []
        for observation in observations:
            role = rule.role_for(observation.observation_type)
            if role is not None:
                matches.append((observation, role))
        return tuple(matches)

    def _evidence_set_for_rule(
        self,
        *,
        rule: EvidenceBuilderRule,
        matches: tuple[tuple[Observation, str], ...],
        context: EvidenceBuilderContext,
    ) -> EvidenceSet:
        items = tuple(
            self._evidence_item_for_observation(
                observation=observation,
                role=role,
                rule=rule,
            )
            for observation, role in matches
        )
        role_ids = self._role_ids(matches)
        recording_block_id = self._recording_block_id(matches, context)

        return EvidenceSet(
            id=EntityId.new(),
            recording_block_id=recording_block_id,
            purpose=rule.evidence_purpose,
            items=items,
            correlation_id=context.correlation_id,
            created_at=context.current_timestamp,
            notes=f"Evidence organized for operational concern: {rule.operational_concern}.",
            metadata={
                "evidence_builder_id": self.id.to_json(),
                "evidence_builder_rule_id": rule.id.to_json(),
                "operational_concern": rule.operational_concern,
                "supporting_observation_ids": role_ids["supporting"],
                "contradicting_observation_ids": role_ids["contradicting"],
                "contextual_observation_ids": role_ids["contextual"],
                "observation_traceability": self._observation_traceability(matches),
                "semantic_conclusion": None,
            },
        )

    def _evidence_item_for_observation(
        self,
        *,
        observation: Observation,
        role: str,
        rule: EvidenceBuilderRule,
    ) -> EvidenceItem:
        metadata: dict[str, Any] = {
            "evidence_role": role,
            "operational_concern": rule.operational_concern,
            "observation_type": observation.observation_type.value,
        }
        source_event_ids = observation.metadata.get("source_production_event_ids")
        if source_event_ids is not None:
            metadata["source_production_event_ids"] = source_event_ids

        return EvidenceItem(
            id=EntityId.new(),
            observation_id=observation.id,
            strength=rule.strength_for_role(role),
            rationale=f"Observation grouped as {role} evidence for {rule.operational_concern}.",
            metadata=metadata,
        )

    def _role_ids(
        self,
        matches: tuple[tuple[Observation, str], ...],
    ) -> dict[str, tuple[str, ...]]:
        return {
            role: tuple(
                observation.id.to_json()
                for observation, observation_role in matches
                if observation_role == role
            )
            for role in ("supporting", "contradicting", "contextual")
        }

    def _observation_traceability(
        self,
        matches: tuple[tuple[Observation, str], ...],
    ) -> Mapping[str, tuple[str, ...]]:
        traceability: dict[str, tuple[str, ...]] = {}
        for observation, _role in matches:
            raw_source_ids = observation.metadata.get("source_production_event_ids", ())
            if isinstance(raw_source_ids, str):
                source_ids = (raw_source_ids,)
            else:
                source_ids = tuple(str(source_id) for source_id in raw_source_ids)
            traceability[observation.id.to_json()] = source_ids
        return MappingProxyType(traceability)

    def _recording_block_id(
        self,
        matches: tuple[tuple[Observation, str], ...],
        context: EvidenceBuilderContext,
    ) -> EntityId | None:
        if context.recording_block_id is not None:
            return context.recording_block_id

        recording_block_ids = {
            observation.recording_block_id
            for observation, _role in matches
            if observation.recording_block_id is not None
        }
        if len(recording_block_ids) == 1:
            return next(iter(recording_block_ids))
        return None


def make_default_observation_evidence_builder(
    *,
    builder_id: EntityId | None = None,
    name: str = "Observation Evidence Builder",
) -> ObservationEvidenceBuilder:
    return ObservationEvidenceBuilder(id=builder_id or EntityId.new(), name=name)
