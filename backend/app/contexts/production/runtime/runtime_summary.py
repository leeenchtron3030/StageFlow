from __future__ import annotations

from dataclasses import dataclass

from app.shared.ids import EntityId

from .runtime_availability import RuntimeAvailabilityStatus
from .runtime_contract_validation import normalize_entity_ids, normalize_strings
from .runtime_event_mode import RuntimeEventModeKind
from .runtime_health import RuntimeHealthStatus
from .runtime_limitation import RuntimeLimitationSeverity
from .runtime_profile import RuntimeProfile
from .runtime_readiness_policy_selection import RuntimeReadinessRoute
from .runtime_resource_policy import RuntimeResourcePriorityClass
from .runtime_source_capability import RuntimeSourceLocationScheme
from .runtime_validation import RuntimeValidationOutcome, RuntimeValidationResult
from .stageflow_runtime import StageFlowRuntime


@dataclass(frozen=True, slots=True)
class RuntimeSummary:
    runtime_id: EntityId
    logical_runtime_name: str
    runtime_profile: RuntimeProfile
    runtime_version: str
    host_id: EntityId
    event_mode: RuntimeEventModeKind
    availability: RuntimeAvailabilityStatus
    health: RuntimeHealthStatus
    validation_outcome: RuntimeValidationOutcome
    enabled_collection_plan_count: int
    supported_readiness_routes: tuple[RuntimeReadinessRoute, ...]
    supported_source_schemes: tuple[RuntimeSourceLocationScheme, ...]
    resource_priority_class: RuntimeResourcePriorityClass
    limitation_count: int
    blocking_limitation_count: int
    configured_stage_ids: tuple[EntityId, ...]
    warning_codes: tuple[str, ...]

    @classmethod
    def from_runtime(
        cls,
        runtime: StageFlowRuntime,
        validation: RuntimeValidationResult,
    ) -> RuntimeSummary:
        if validation.runtime_id != runtime.identity.runtime_id:
            raise ValueError("Runtime summary validation must match the Runtime.")
        routes = tuple(
            sorted(
                {
                    selection.selected_route
                    for selection in runtime.readiness_policy_selections
                    if selection.selected_route is not RuntimeReadinessRoute.DISABLED
                },
                key=lambda value: value.value,
            )
        )
        source_schemes = tuple(
            sorted(
                {
                    scheme
                    for capability in runtime.capability_set.source_capabilities
                    for scheme in capability.supported_location_schemes
                },
                key=lambda value: value.value,
            )
        )
        warnings = tuple(
            reason.code.value
            for reason in validation.reasons
            if reason.code.value != "configuration_valid"
        )
        return cls(
            runtime_id=runtime.identity.runtime_id,
            logical_runtime_name=runtime.identity.logical_name,
            runtime_profile=runtime.profile,
            runtime_version=runtime.software_version.semantic_version,
            host_id=runtime.host.host_id,
            event_mode=runtime.event_mode.mode,
            availability=runtime.availability.status,
            health=runtime.health.status,
            validation_outcome=validation.outcome,
            enabled_collection_plan_count=sum(
                plan.enabled for plan in runtime.collection_plans
            ),
            supported_readiness_routes=routes,
            supported_source_schemes=source_schemes,
            resource_priority_class=runtime.resource_policy.priority_class,
            limitation_count=len(runtime.limitations),
            blocking_limitation_count=sum(
                limitation.severity is RuntimeLimitationSeverity.BLOCKING
                for limitation in runtime.limitations
            ),
            configured_stage_ids=normalize_entity_ids(
                runtime.identity.configured_stage_ids,
                "RuntimeSummary.configured_stage_ids",
            ),
            warning_codes=normalize_strings(warnings, "RuntimeSummary.warning_codes"),
        )
