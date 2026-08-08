"""Production event dispatcher contracts."""

from app.contexts.production.dispatcher.compatibility import ObservationInterpreterAdapter
from app.contexts.production.dispatcher.dispatch_context import DispatchContext
from app.contexts.production.dispatcher.dispatch_result import DispatchResult
from app.contexts.production.dispatcher.dispatch_rule import DispatchRule
from app.contexts.production.dispatcher.dispatch_status import DispatchStatus
from app.contexts.production.dispatcher.dispatch_summary import DispatchSummary
from app.contexts.production.dispatcher.dispatcher_interpreter import DispatcherInterpreter
from app.contexts.production.dispatcher.interpreter_support_failure import (
    InterpreterSupportFailure,
)
from app.contexts.production.dispatcher.production_event_dispatcher import (
    ProductionEventDispatcher,
)

__all__ = [
    "DispatchContext",
    "DispatchResult",
    "DispatchRule",
    "DispatchSummary",
    "DispatchStatus",
    "DispatcherInterpreter",
    "InterpreterSupportFailure",
    "ObservationInterpreterAdapter",
    "ProductionEventDispatcher",
]
