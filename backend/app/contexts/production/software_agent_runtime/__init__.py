"""Synchronous in-process Software Agent Runtime lifecycle contracts."""

from .agent_runtime_dependencies import AgentRuntimeDependencies
from .agent_runtime_lifecycle import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeNotificationPortKind,
    AgentRuntimeOperation,
    AgentRuntimeOperationOutcome,
    AgentRuntimeTransitionReasonCode,
)
from .agent_runtime_requests import (
    AgentRuntimeCancellation,
    AgentRuntimeFailure,
    AgentRuntimePrepareRequest,
    AgentRuntimePressureDeclaration,
    AgentRuntimePressureUpdate,
    AgentRuntimeResumeRequest,
    AgentRuntimeStartRequest,
    AgentRuntimeStopRequest,
)
from .agent_runtime_snapshot import (
    AgentRuntimeNotificationFailure,
    AgentRuntimeOperationResult,
    AgentRuntimeSnapshot,
    AgentRuntimeSummary,
    AgentRuntimeTransition,
)
from .ports import LifecycleEventSink, RuntimeAvailabilitySink, RuntimeHealthSink
from .software_agent_runtime import SoftwareAgentRuntime

__all__ = [
    "AgentRuntimeCancellation",
    "AgentRuntimeDependencies",
    "AgentRuntimeExecutionPermission",
    "AgentRuntimeFailure",
    "AgentRuntimeLifecycleState",
    "AgentRuntimeNotificationFailure",
    "AgentRuntimeNotificationPortKind",
    "AgentRuntimeOperation",
    "AgentRuntimeOperationOutcome",
    "AgentRuntimeOperationResult",
    "AgentRuntimePrepareRequest",
    "AgentRuntimePressureDeclaration",
    "AgentRuntimePressureUpdate",
    "AgentRuntimeResumeRequest",
    "AgentRuntimeSnapshot",
    "AgentRuntimeStartRequest",
    "AgentRuntimeStopRequest",
    "AgentRuntimeSummary",
    "AgentRuntimeTransition",
    "AgentRuntimeTransitionReasonCode",
    "LifecycleEventSink",
    "RuntimeAvailabilitySink",
    "RuntimeHealthSink",
    "SoftwareAgentRuntime",
]
