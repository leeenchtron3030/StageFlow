from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contexts.production.dispatcher.dispatch_result import interpreter_status_semantics
from app.contexts.production.interpreter import (
    InterpreterContext,
    InterpreterResult,
    InterpreterStatus,
)
from app.contexts.production.observation import Observation
from app.contexts.production.observation_interpreter import (
    ObservationInterpreterContext,
    ObservationInterpreterResult,
    ObservationInterpreterStatus,
)
from app.contexts.production.observation_interpreter.event_observation_lineage import (
    event_observation_lineage_from_event,
    observation_context_from_event,
    observation_provenance_from_event,
)
from app.contexts.production.production_event import ProductionEvent
from app.shared.ids import EntityId


class CompatibleObservationInterpreter(Protocol):
    @property
    def id(self) -> EntityId: ...

    @property
    def status(self) -> ObservationInterpreterStatus: ...

    def can_interpret_event(self, event: ProductionEvent) -> bool: ...

    def interpret(
        self,
        events: ProductionEvent | Sequence[ProductionEvent],
        context: ObservationInterpreterContext,
    ) -> ObservationInterpreterResult: ...


_STATUS_MAPPING: Mapping[ObservationInterpreterStatus, InterpreterStatus] = {
    ObservationInterpreterStatus.UNKNOWN: InterpreterStatus.UNKNOWN,
    ObservationInterpreterStatus.CONFIGURED: InterpreterStatus.CONFIGURED,
    ObservationInterpreterStatus.READY: InterpreterStatus.READY,
    ObservationInterpreterStatus.ACTIVE: InterpreterStatus.ACTIVE,
    ObservationInterpreterStatus.DEGRADED: InterpreterStatus.DEGRADED,
    ObservationInterpreterStatus.FAILED: InterpreterStatus.FAILED,
    ObservationInterpreterStatus.DISABLED: InterpreterStatus.DISABLED,
    ObservationInterpreterStatus.ARCHIVED: InterpreterStatus.ARCHIVED,
}


def map_observation_interpreter_status(
    status: ObservationInterpreterStatus,
) -> InterpreterStatus:
    """Map every concrete lifecycle status without value-based casting."""

    try:
        return _STATUS_MAPPING[status]
    except KeyError as error:
        raise ValueError("Unsupported Observation Interpreter status.") from error


def observation_interpreter_context_from(
    context: InterpreterContext,
) -> ObservationInterpreterContext:
    """Translate all five context fields without deriving authoritative facts."""

    return ObservationInterpreterContext(
        correlation_id=context.correlation_id,
        current_timestamp=context.current_timestamp,
        recording_block_id=context.recording_block_id,
        stage_id=context.stage_id,
        metadata=context.metadata,
    )


@dataclass(frozen=True, slots=True)
class ObservationInterpreterAdapter:
    """Dispatcher-owned bridge for a concrete Observation Interpreter."""

    interpreter: CompatibleObservationInterpreter

    @property
    def id(self) -> EntityId:
        return self.interpreter.id

    def can_interpret(self, event: ProductionEvent) -> bool:
        return self.interpreter.can_interpret_event(event)

    def interpret(
        self,
        event: ProductionEvent,
        context: InterpreterContext,
    ) -> InterpreterResult:
        concrete_context = observation_interpreter_context_from(context)
        event_lineage = event_observation_lineage_from_event(event)
        if event_lineage.failure_code is not None:
            return self._failure(event, event_lineage.failure_code)
        try:
            concrete_result = self.interpreter.interpret(
                event,
                concrete_context,
            )
        except Exception as error:
            return self._failure(event, f"interpreter_exception:{type(error).__name__}")

        failure_code = self._lineage_failure(event, concrete_context, concrete_result)
        if failure_code is not None:
            return self._failure(event, failure_code)

        status = map_observation_interpreter_status(self.interpreter.status)
        if not interpreter_status_semantics(status).observations_survive:
            return self._failure(event, f"non_interpretable_status:{status.value}")

        return InterpreterResult(
            source_production_event_id=event.id,
            observations=concrete_result.observations,
            interpreter_status=status,
            warnings=concrete_result.warnings,
            metadata=concrete_result.metadata,
        )

    def _lineage_failure(
        self,
        event: ProductionEvent,
        context: ObservationInterpreterContext,
        result: ObservationInterpreterResult,
    ) -> str | None:
        if tuple(result.source_production_event_ids) != (event.id,):
            return "invalid_source_production_event_lineage"
        if result.interpreter_id != self.id:
            return "invalid_interpreter_identity"
        for observation in result.observations:
            failure = self._observation_lineage_failure(event, context, observation)
            if failure is not None:
                return failure
        return None

    def _observation_lineage_failure(
        self,
        event: ProductionEvent,
        context: ObservationInterpreterContext,
        observation: Observation,
    ) -> str | None:
        provenance = observation.provenance
        if provenance is None or provenance.source_event_id != event.id:
            return "invalid_observation_source_lineage"
        if provenance.source_event_type is not event.event_type:
            return "invalid_observation_source_event_type"
        if provenance.source_event_occurred_at != event.occurred_at:
            return "invalid_observation_source_event_occurred_at"
        if provenance.interpreter_id != self.id:
            return "invalid_observation_interpreter_lineage"
        if observation.correlation_id != event.correlation_id:
            return "invalid_observation_correlation_lineage"
        if observation.context.correlation_id != event.correlation_id:
            return "invalid_observation_context_lineage"
        expected_context = observation_context_from_event(event, context)
        for field_name in (
            "stage_id",
            "recording_block_id",
            "scheduled_activity_id",
            "transcript_stream_id",
            "media_artifact_id",
            "timeline_reference",
        ):
            expected = getattr(expected_context, field_name)
            source = expected_context.metadata.get(f"{field_name}_source")
            is_event_derived = isinstance(source, str) and source.startswith("event")
            if (
                expected is not None
                and is_event_derived
                and getattr(observation.context, field_name) != expected
            ):
                return f"invalid_observation_context_{field_name}"
        expected_producer = observation_provenance_from_event(
            event,
            interpreter_id=self.id,
            interpreter_kind=provenance.interpreter_kind,
            interpretation_rule_id=provenance.interpretation_rule_id,
        ).producer_identifier
        if provenance.producer_identifier != expected_producer:
            return "invalid_observation_source_producer_identifier"
        return None

    def _failure(self, event: ProductionEvent, failure_code: str) -> InterpreterResult:
        warning = f"Observation Interpreter compatibility failure: {failure_code}."
        return InterpreterResult(
            source_production_event_id=event.id,
            observations=(),
            interpreter_status=InterpreterStatus.FAILED,
            warnings=(warning,),
            metadata={"failure_code": failure_code},
        )
