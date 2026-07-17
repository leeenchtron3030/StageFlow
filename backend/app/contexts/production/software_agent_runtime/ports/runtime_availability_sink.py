from __future__ import annotations

from abc import ABC, abstractmethod

from app.contexts.production.runtime import RuntimeAvailability


class RuntimeAvailabilitySink(ABC):
    """Narrow synchronous sink for an immutable availability declaration."""

    @abstractmethod
    def publish_availability(self, availability: RuntimeAvailability) -> None:
        """Publish supplied availability without performing liveness monitoring."""


__all__ = ["RuntimeAvailabilitySink"]
