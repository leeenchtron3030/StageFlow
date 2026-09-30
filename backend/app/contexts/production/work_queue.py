"""Application composition over Kernel, Assembly and Session Suggestions reads."""
from dataclasses import dataclass

from app.contexts.assembly.session_repository import SessionAssemblyRepository
from app.shared.ids import EntityId

from .event_mode_kernel.contracts import (
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
)
from .event_mode_kernel.repository import EventModeKernelRepository
from .event_mode_kernel.work_queue import work_queue_sort_key
from .session_suggestions.work_queue import SessionSuggestionWorkQueueReader


@dataclass
class ProducerWorkQueueService:
    kernel: EventModeKernelRepository
    assemblies: SessionAssemblyRepository | None = None
    suggestions: SessionSuggestionWorkQueueReader | None = None

    def list_items(
        self, event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
        limit: int = 50,
    ) -> tuple[ProducerWorkQueueSubject, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("Work Queue page limit must be between 1 and 100.")
        kernel_items = self.kernel.list_producer_work_queue(
            event_id, after=after, limit=limit + 1,
        )
        assembly_items = (() if self.assemblies is None else
                          self.assemblies.list_pending_approvals(
                              event_id, after=after, limit=limit + 1,
                          ))
        suggestion_items = (() if self.suggestions is None else
                            self.suggestions.list_pending_confirmations(
                                event_id, after=after, limit=limit + 1,
                            ))
        return tuple(sorted((*kernel_items, *assembly_items, *suggestion_items),
                            key=work_queue_sort_key)[:limit + 1])
