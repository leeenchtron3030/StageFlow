from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObservationConfidence:
    """Confidence value for an observation, from 0.0 to 1.0 inclusive."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("ObservationConfidence value must be between 0.0 and 1.0.")

    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("ObservationConfidence threshold must be between 0.0 and 1.0.")
        return self.value >= threshold
