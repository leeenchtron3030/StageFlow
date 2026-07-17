from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, cast

from app.shared.ids import EntityId

from .runtime_capability import RuntimeCapability
from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_limitations,
    require_aware,
    require_non_empty,
)
from .runtime_observation_capability import RuntimeObservationCapability
from .runtime_readiness_capability import RuntimeReadinessCapability
from .runtime_source_capability import RuntimeSourceCapability


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class _HasEntityId(Protocol):
    @property
    def id(self) -> EntityId: ...


@dataclass(frozen=True, slots=True)
class RuntimeCapabilitySet:
    id: EntityId
    runtime_id: EntityId
    capability_schema_version: str
    capabilities: Sequence[RuntimeCapability]
    source_capabilities: Sequence[RuntimeSourceCapability]
    observation_capabilities: Sequence[RuntimeObservationCapability]
    readiness_capabilities: Sequence[RuntimeReadinessCapability]
    declared_at: datetime
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    conflicting_capability_ids: tuple[EntityId, ...] = field(
        init=False,
        default_factory=tuple,
    )
    conflicting_capability_keys: tuple[str, ...] = field(
        init=False,
        default_factory=tuple,
    )

    def __post_init__(self) -> None:
        require_aware(self.declared_at, "RuntimeCapabilitySet.declared_at")
        object.__setattr__(
            self,
            "capability_schema_version",
            require_non_empty(
                self.capability_schema_version,
                "RuntimeCapabilitySet.capability_schema_version",
            ),
        )
        normalized, conflicting_ids, conflicting_keys = _normalize_capabilities(
            self.capabilities
        )
        object.__setattr__(self, "capabilities", normalized)
        object.__setattr__(self, "conflicting_capability_keys", conflicting_keys)
        sources, source_conflicts = _normalize_by_id(self.source_capabilities)
        observations, observation_conflicts = _normalize_by_id(
            self.observation_capabilities
        )
        readiness, readiness_conflicts = _normalize_by_id(
            self.readiness_capabilities
        )
        category_ids = (
            {value.id for value in normalized},
            {value.id for value in sources},
            {value.id for value in observations},
            {value.id for value in readiness},
        )
        cross_category_conflicts = {
            capability_id
            for ids in category_ids
            for capability_id in ids
            if sum(capability_id in other_ids for other_ids in category_ids) > 1
        }
        object.__setattr__(
            self,
            "conflicting_capability_ids",
            tuple(
                sorted(
                    {
                        *conflicting_ids,
                        *source_conflicts,
                        *observation_conflicts,
                        *readiness_conflicts,
                        *cross_category_conflicts,
                    },
                    key=lambda value: value.value,
                )
            ),
        )
        object.__setattr__(
            self,
            "source_capabilities",
            sources,
        )
        object.__setattr__(
            self,
            "observation_capabilities",
            observations,
        )
        object.__setattr__(
            self,
            "readiness_capabilities",
            readiness,
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeCapabilitySet.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeCapabilitySet.metadata"),
        )


def _normalize_capabilities(
    capabilities: Sequence[RuntimeCapability],
) -> tuple[tuple[RuntimeCapability, ...], tuple[EntityId, ...], tuple[str, ...]]:
    by_id: dict[str, list[RuntimeCapability]] = {}
    for capability in capabilities:
        by_id.setdefault(capability.id.value, []).append(capability)
    normalized: list[RuntimeCapability] = []
    conflicting_ids: list[EntityId] = []
    for capability_id in sorted(by_id):
        choices = sorted(by_id[capability_id], key=_capability_semantic_key)
        if len({_capability_semantic_key(choice) for choice in choices}) > 1:
            conflicting_ids.append(choices[0].id)
        normalized.append(choices[0])
    by_key: dict[str, list[RuntimeCapability]] = {}
    for capability in normalized:
        key = f"{capability.kind.value}:{capability.scope}"
        by_key.setdefault(key, []).append(capability)
    conflicting_keys = tuple(
        key
        for key, values in sorted(by_key.items())
        if len(values) > 1
    )
    return (
        tuple(
            sorted(
                normalized,
                key=lambda value: (value.kind.value, value.scope, value.id.value),
            )
        ),
        tuple(sorted(conflicting_ids, key=lambda value: value.value)),
        conflicting_keys,
    )


def _capability_semantic_key(capability: RuntimeCapability) -> tuple[str, ...]:
    return (
        capability.runtime_id.value,
        capability.kind.value,
        capability.support_status.value,
        capability.capability_version,
        capability.scope,
        capability.provider_or_adapter_id.value
        if capability.provider_or_adapter_id
        else "",
        *capability.limitations,
        _canonical_mapping(capability.parameters),
        _canonical_mapping(capability.metadata),
    )


def _canonical_mapping(value: Mapping[str, Any]) -> str:
    return "{" + ",".join(
        f"{key!r}:{_canonical_value(item)}" for key, item in sorted(value.items())
    ) + "}"


def _canonical_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return _canonical_mapping(cast(Mapping[str, Any], value))
    if isinstance(value, tuple):
        items = cast(tuple[Any, ...], value)
        return "[" + ",".join(_canonical_value(item) for item in items) + "]"
    return f"{type(value).__name__}:{value!r}"


def _normalize_by_id[T: _HasEntityId](
    values: Sequence[T],
) -> tuple[tuple[T, ...], tuple[EntityId, ...]]:
    by_id: dict[str, list[T]] = {}
    for value in values:
        by_id.setdefault(value.id.value, []).append(value)
    normalized: list[T] = []
    conflicts: list[EntityId] = []
    for value_id in sorted(by_id):
        choices = sorted(by_id[value_id], key=repr)
        selected = choices[0]
        if any(choice != selected for choice in choices[1:]):
            conflicts.append(selected.id)
        normalized.append(selected)
    return tuple(normalized), tuple(conflicts)
