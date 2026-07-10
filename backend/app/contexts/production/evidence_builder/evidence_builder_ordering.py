from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.contexts.production.observation import Observation


@dataclass(frozen=True, slots=True)
class EvidenceBuilderOrderedObservation:
    """Observation paired with its original input index for stable fallback ordering."""

    observation: Observation
    input_index: int


def timeline_order_value(observation: Observation) -> float:
    location = observation.location
    if location.point is not None:
        return location.point.offset.total_seconds()
    if location.range is not None:
        return location.range.start.offset.total_seconds()
    return float("inf")


def observation_ordering_key(
    ordered_observation: EvidenceBuilderOrderedObservation,
) -> tuple[datetime, float, str, int]:
    observation = ordered_observation.observation
    return (
        observation.observed_at,
        timeline_order_value(observation),
        observation.id.to_json(),
        ordered_observation.input_index,
    )


def order_observations(
    observations: tuple[Observation, ...],
) -> tuple[EvidenceBuilderOrderedObservation, ...]:
    indexed = tuple(
        EvidenceBuilderOrderedObservation(observation=observation, input_index=index)
        for index, observation in enumerate(observations)
    )
    return tuple(sorted(indexed, key=observation_ordering_key))
