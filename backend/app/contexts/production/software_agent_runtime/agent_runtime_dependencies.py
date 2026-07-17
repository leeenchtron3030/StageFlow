from __future__ import annotations

from dataclasses import dataclass

from .ports import LifecycleEventSink, RuntimeAvailabilitySink, RuntimeHealthSink


@dataclass(frozen=True, slots=True)
class AgentRuntimeDependencies:
    lifecycle_event_sink: LifecycleEventSink | None
    runtime_health_sink: RuntimeHealthSink | None
    runtime_availability_sink: RuntimeAvailabilitySink | None

    @property
    def missing_required_ports(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.lifecycle_event_sink is None:
            missing.append("lifecycle_event_sink")
        if self.runtime_health_sink is None:
            missing.append("runtime_health_sink")
        if self.runtime_availability_sink is None:
            missing.append("runtime_availability_sink")
        return tuple(missing)


__all__ = ["AgentRuntimeDependencies"]
