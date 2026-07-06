from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FindingConfidence:
    """Confidence in a human-reviewable reasoning product."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("FindingConfidence value must be between 0.0 and 1.0.")
