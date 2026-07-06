from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

type Timestamp = datetime


class Clock(Protocol):
    """Clock contract for replaceable time sources."""

    def now(self) -> Timestamp:
        """Return the current UTC timestamp."""
        ...


@dataclass(frozen=True, slots=True)
class SystemClock:
    """Production clock backed by the system clock."""

    def now(self) -> Timestamp:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Deterministic clock for tests and future simulation mode."""

    fixed_at: Timestamp

    def now(self) -> Timestamp:
        return self.fixed_at
