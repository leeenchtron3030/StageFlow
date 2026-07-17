from __future__ import annotations

from abc import ABC, abstractmethod

from app.contexts.production.software_agent_runtime import AgentRuntimeSnapshot
from app.shared.ids import EntityId


class AgentExecutionStatePort(ABC):
    """Read-only synchronous boundary for the current Agent snapshot."""

    @abstractmethod
    def get_current_snapshot(self, runtime_id: EntityId) -> AgentRuntimeSnapshot:
        """Return current immutable execution state without waiting or mutation."""


__all__ = ["AgentExecutionStatePort"]
