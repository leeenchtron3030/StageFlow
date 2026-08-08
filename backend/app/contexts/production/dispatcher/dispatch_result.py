from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.dispatcher.dispatch_status import DispatchStatus
from app.contexts.production.dispatcher.interpreter_support_failure import (
    InterpreterSupportFailure,
)
from app.contexts.production.interpreter.interpreter_result import InterpreterResult
from app.contexts.production.interpreter.interpreter_status import InterpreterStatus
from app.contexts.production.observation.observation import Observation
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class _InterpreterStatusSemantics:
    supported: bool
    observations_survive: bool
    successful: bool
    warning: bool
    failure: bool


_STATUS_SEMANTICS: Mapping[InterpreterStatus, _InterpreterStatusSemantics] = {
    InterpreterStatus.UNKNOWN: _InterpreterStatusSemantics(True, False, False, False, True),
    InterpreterStatus.CONFIGURED: _InterpreterStatusSemantics(
        True, False, False, False, True
    ),
    InterpreterStatus.READY: _InterpreterStatusSemantics(True, True, True, False, False),
    InterpreterStatus.ACTIVE: _InterpreterStatusSemantics(True, True, True, False, False),
    InterpreterStatus.DEGRADED: _InterpreterStatusSemantics(True, True, True, True, False),
    InterpreterStatus.FAILED: _InterpreterStatusSemantics(True, False, False, False, True),
    InterpreterStatus.DISABLED: _InterpreterStatusSemantics(True, False, False, False, True),
    InterpreterStatus.ARCHIVED: _InterpreterStatusSemantics(True, False, False, False, True),
    InterpreterStatus.EXPERIMENTAL: _InterpreterStatusSemantics(
        True, True, True, True, False
    ),
}

_UNSUPPORTED_STATUS_SEMANTICS = _InterpreterStatusSemantics(
    supported=False,
    observations_survive=False,
    successful=False,
    warning=False,
    failure=True,
)


def interpreter_status_semantics(
    status: InterpreterStatus,
) -> _InterpreterStatusSemantics:
    """Return one fail-closed classification for supported and future statuses."""

    try:
        return _STATUS_SEMANTICS[status]
    except (KeyError, TypeError):
        return _UNSUPPORTED_STATUS_SEMANTICS


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """Outcome of routing one Production Event to available interpreters."""

    source_production_event_id: EntityId
    interpreter_count: int
    invoked_interpreter_ids: Sequence[EntityId]
    interpreter_results: Sequence[InterpreterResult]
    warnings: Sequence[str] = field(default_factory=tuple)
    declined_interpreter_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    support_failures: Sequence[InterpreterSupportFailure] = field(default_factory=tuple)
    status: DispatchStatus = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "invoked_interpreter_ids", tuple(self.invoked_interpreter_ids))
        object.__setattr__(self, "interpreter_results", tuple(self.interpreter_results))
        object.__setattr__(self, "support_failures", tuple(self.support_failures))
        explicit_warnings = tuple(self.warnings)
        derived_warnings = tuple(
            warning
            for result in self.interpreter_results
            for warning in result.warnings
        ) + tuple(failure.warning for failure in self.support_failures)
        object.__setattr__(
            self,
            "warnings",
            _merge_warning_occurrences(explicit_warnings, derived_warnings),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

        if self.interpreter_count < 0:
            raise ValueError("DispatchResult interpreter_count must not be negative.")
        if self.declined_interpreter_count < 0:
            raise ValueError("DispatchResult declined_interpreter_count must not be negative.")
        if len(self.invoked_interpreter_ids) != len(self.interpreter_results):
            raise ValueError(
                "DispatchResult invoked_interpreter_ids must match interpreter_results."
            )
        object.__setattr__(self, "status", self._aggregate_status())

    @property
    def observations(self) -> tuple[Observation, ...]:
        return tuple(
            observation
            for result in self.interpreter_results
            if interpreter_status_semantics(
                result.interpreter_status
            ).observations_survive
            for observation in result.observations
        )

    def _aggregate_status(self) -> DispatchStatus:
        if not self.interpreter_results and not self.support_failures:
            return DispatchStatus.NO_MATCH
        semantics = tuple(
            interpreter_status_semantics(result.interpreter_status)
            for result in self.interpreter_results
        )
        failures = sum(item.failure for item in semantics) + len(self.support_failures)
        successes = sum(item.successful for item in semantics)
        if failures and not successes:
            return DispatchStatus.TOTAL_FAILURE
        if failures:
            return DispatchStatus.PARTIAL_FAILURE
        if self.warnings or any(item.warning for item in semantics):
            return DispatchStatus.SUCCESS_WITH_WARNINGS
        return DispatchStatus.SUCCESS


def _merge_warning_occurrences(
    explicit: tuple[str, ...],
    derived: tuple[str, ...],
) -> tuple[str, ...]:
    """Preserve explicit order and append only derived occurrences not already present."""

    remaining = list(explicit)
    missing: list[str] = []
    for warning in derived:
        try:
            index = remaining.index(warning)
        except ValueError:
            missing.append(warning)
        else:
            remaining.pop(index)
    return (*explicit, *missing)
