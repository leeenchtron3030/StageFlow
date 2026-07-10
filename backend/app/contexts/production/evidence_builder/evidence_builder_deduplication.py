from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.contexts.production.observation import Observation
from app.shared.ids import EntityId

from .evidence_builder_ordering import (
    EvidenceBuilderOrderedObservation,
    order_observations,
)
from .observation_semantic_selection import (
    ObservationSemanticSelection,
    ObservationSemanticSelectionStatus,
)


@dataclass(frozen=True, slots=True)
class EvidenceBuilderDeduplicationResult:
    """Generic deterministic Observation-ID deduplication result."""

    retained_observations: tuple[Observation, ...]
    duplicate_observation_ids: tuple[EntityId, ...]
    duplicate_selections: tuple[ObservationSemanticSelection, ...]
    ordered_observations: tuple[EvidenceBuilderOrderedObservation, ...]


def deduplicate_observations(
    observations: Sequence[Observation],
) -> EvidenceBuilderDeduplicationResult:
    ordered = order_observations(tuple(observations))
    seen_ids: set[EntityId] = set()
    retained: list[Observation] = []
    duplicate_ids: list[EntityId] = []
    duplicate_selections: list[ObservationSemanticSelection] = []

    for ordered_observation in ordered:
        observation = ordered_observation.observation
        if observation.id in seen_ids:
            duplicate_ids.append(observation.id)
            duplicate_selections.append(
                ObservationSemanticSelection(
                    observation_id=observation.id,
                    status=ObservationSemanticSelectionStatus.DUPLICATE,
                    matched_observation_type=observation.observation_type,
                    rationale="Observation ID already processed in this build invocation.",
                    metadata={"input_index": ordered_observation.input_index},
                )
            )
            continue
        seen_ids.add(observation.id)
        retained.append(observation)

    return EvidenceBuilderDeduplicationResult(
        retained_observations=tuple(retained),
        duplicate_observation_ids=tuple(duplicate_ids),
        duplicate_selections=tuple(duplicate_selections),
        ordered_observations=ordered,
    )
