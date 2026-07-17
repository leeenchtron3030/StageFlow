from __future__ import annotations

from abc import ABC, abstractmethod

from app.contexts.production.runtime import RuntimeHealth


class RuntimeHealthSink(ABC):
    """Narrow synchronous sink for an immutable health declaration."""

    @abstractmethod
    def publish_health(self, health: RuntimeHealth) -> None:
        """Publish supplied lifecycle-derived health without performing checks."""


__all__ = ["RuntimeHealthSink"]
