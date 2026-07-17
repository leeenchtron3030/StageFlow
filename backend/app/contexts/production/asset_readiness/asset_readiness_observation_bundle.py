from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .asset_finalization_observation import AssetFinalizationObservation
from .asset_read_access_observation import AssetReadAccessObservation
from .asset_readiness_validation import (
    freeze_readiness_metadata,
    normalize_entity_ids,
    require_aware,
)
from .asset_resource_presence_observation import AssetResourcePresenceObservation
from .asset_resource_snapshot import AssetResourceSnapshot
from .asset_write_state_observation import AssetWriteStateObservation

type AssetReadinessObservation = (
    AssetResourceSnapshot
    | AssetFinalizationObservation
    | AssetWriteStateObservation
    | AssetReadAccessObservation
    | AssetResourcePresenceObservation
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AssetReadinessObservationBundle:
    """Deterministically normalized supplied resource facts for one candidate."""

    id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    created_at: datetime
    resource_snapshots: Sequence[AssetResourceSnapshot] = field(default_factory=tuple)
    finalization_observations: Sequence[AssetFinalizationObservation] = field(
        default_factory=tuple
    )
    write_state_observations: Sequence[AssetWriteStateObservation] = field(
        default_factory=tuple
    )
    read_access_observations: Sequence[AssetReadAccessObservation] = field(
        default_factory=tuple
    )
    presence_observations: Sequence[AssetResourcePresenceObservation] = field(
        default_factory=tuple
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    conflicting_observation_ids: tuple[EntityId, ...] = field(
        init=False,
        default_factory=tuple,
    )

    def __post_init__(self) -> None:
        require_aware(self.created_at, "AssetReadinessObservationBundle.created_at")
        normalized, conflicts = _normalize_observations(
            (
                *self.resource_snapshots,
                *self.finalization_observations,
                *self.write_state_observations,
                *self.read_access_observations,
                *self.presence_observations,
            )
        )
        for observation in normalized:
            if observation.candidate_id != self.candidate_id:
                raise ValueError("Bundle observation candidate ID must match the bundle.")
            if observation.resource_id != self.resource_id:
                raise ValueError("Bundle observation resource ID must match the bundle.")
            if observation.observed_at > self.created_at:
                raise ValueError("Bundle observation must not occur after bundle creation.")
        object.__setattr__(
            self,
            "resource_snapshots",
            tuple(
                observation
                for observation in normalized
                if isinstance(observation, AssetResourceSnapshot)
            ),
        )
        object.__setattr__(
            self,
            "finalization_observations",
            tuple(
                observation
                for observation in normalized
                if isinstance(observation, AssetFinalizationObservation)
            ),
        )
        object.__setattr__(
            self,
            "write_state_observations",
            tuple(
                observation
                for observation in normalized
                if isinstance(observation, AssetWriteStateObservation)
            ),
        )
        object.__setattr__(
            self,
            "read_access_observations",
            tuple(
                observation
                for observation in normalized
                if isinstance(observation, AssetReadAccessObservation)
            ),
        )
        object.__setattr__(
            self,
            "presence_observations",
            tuple(
                observation
                for observation in normalized
                if isinstance(observation, AssetResourcePresenceObservation)
            ),
        )
        object.__setattr__(
            self,
            "conflicting_observation_ids",
            normalize_entity_ids(conflicts, "conflicting observation IDs"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "AssetReadinessObservationBundle.metadata",
            ),
        )

    @property
    def all_observations(self) -> tuple[AssetReadinessObservation, ...]:
        return tuple(
            sorted(
                (
                    *self.resource_snapshots,
                    *self.finalization_observations,
                    *self.write_state_observations,
                    *self.read_access_observations,
                    *self.presence_observations,
                ),
                key=_observation_sort_key,
            )
        )

    @property
    def observation_ids(self) -> tuple[EntityId, ...]:
        return tuple(observation.id for observation in self.all_observations)


def _normalize_observations(
    observations: Sequence[AssetReadinessObservation],
) -> tuple[tuple[AssetReadinessObservation, ...], tuple[EntityId, ...]]:
    grouped: dict[str, list[AssetReadinessObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.id.value, []).append(observation)
    normalized: list[AssetReadinessObservation] = []
    conflicts: list[EntityId] = []
    for observation_id in sorted(grouped):
        choices = sorted(grouped[observation_id], key=_observation_semantic_key)
        semantic_keys = {_observation_semantic_key(choice) for choice in choices}
        if len(semantic_keys) > 1:
            conflicts.append(choices[0].id)
        normalized.append(choices[0])
    return tuple(sorted(normalized, key=_observation_sort_key)), tuple(conflicts)


def _observation_sort_key(
    observation: AssetReadinessObservation,
) -> tuple[str, str, tuple[str, ...]]:
    return (
        observation.observed_at.isoformat(),
        observation.id.value,
        _observation_semantic_key(observation),
    )


def _observation_semantic_key(
    observation: AssetReadinessObservation,
) -> tuple[str, ...]:
    common = (
        type(observation).__name__,
        observation.candidate_id.value,
        observation.resource_id.value,
        observation.observed_at.isoformat(),
        observation.observer_id.value,
        observation.source_runtime_id.value if observation.source_runtime_id else "",
        *observation.limitations,
    )
    if isinstance(observation, AssetResourceSnapshot):
        return (
            *common,
            str(observation.size_bytes),
            observation.filesystem_modified_at.isoformat()
            if observation.filesystem_modified_at
            else "",
            observation.stable_resource_identity_token or "",
            observation.source_volume_id.value if observation.source_volume_id else "",
            observation.source_host_id.value if observation.source_host_id else "",
        )
    if isinstance(observation, AssetFinalizationObservation):
        return (
            *common,
            observation.completion_method.value,
            observation.declaring_entity_id.value,
            observation.completion_marker_resource_id.value
            if observation.completion_marker_resource_id
            else "",
            observation.source_event_id.value if observation.source_event_id else "",
        )
    if isinstance(observation, AssetWriteStateObservation):
        return (
            *common,
            observation.status.value,
            observation.assessment_mechanism_id,
            observation.writer_id.value if observation.writer_id else "",
        )
    if isinstance(observation, AssetReadAccessObservation):
        return (
            *common,
            observation.status.value,
            observation.assessment_method_id,
            observation.access_scope,
        )
    return (
        *common,
        observation.status.value,
        observation.observed_resource_identity_token or "",
        observation.replacement_resource_id.value
        if observation.replacement_resource_id
        else "",
    )
