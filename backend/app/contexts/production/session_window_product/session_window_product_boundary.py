from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionWindowProductBoundary:
    """Quality signal for the verified product media boundaries."""

    start_confidence: float
    end_confidence: float
    start_note: str | None = None
    end_note: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.start_confidence <= 1.0:
            raise ValueError(
                "SessionWindowProductBoundary start_confidence must be between 0.0 and 1.0."
            )
        if not 0.0 <= self.end_confidence <= 1.0:
            raise ValueError(
                "SessionWindowProductBoundary end_confidence must be between 0.0 and 1.0."
            )
