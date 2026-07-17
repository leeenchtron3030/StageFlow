from __future__ import annotations

from abc import ABC, abstractmethod

from ..agent_runtime_snapshot import AgentRuntimeTransition


class LifecycleEventSink(ABC):
    """Narrow synchronous sink for immutable Agent lifecycle transitions."""

    @abstractmethod
    def publish_transition(self, transition: AgentRuntimeTransition) -> None:
        """Publish one already-committed transition without controlling lifecycle."""


__all__ = ["LifecycleEventSink"]
