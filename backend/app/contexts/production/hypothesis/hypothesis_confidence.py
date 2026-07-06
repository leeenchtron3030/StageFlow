from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HypothesisConfidence:
    """Confidence in a possible interpretation, from 0.0 to 1.0 inclusive."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("HypothesisConfidence value must be between 0.0 and 1.0.")
