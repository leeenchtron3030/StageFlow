from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime


def _key(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _string_mapping(value: Mapping[str, str], field_name: str) -> Mapping[str, str]:
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized[_key(key, f"{field_name} key")] = _key(
            item, f"{field_name}[{key}]"
        )
    return MappingProxyType(dict(sorted(normalized.items())))


def _empty_string_mapping() -> Mapping[str, str]:
    return {}


class BootstrapStatus(StrEnum):
    CREATED = "created"
    RESOLVED = "resolved"
    UPDATED = "updated"
    CONFLICT = "conflict"
    STORAGE_UNAVAILABLE = "storage_unavailable"


class ProgramExpectationLifecycle(StrEnum):
    CURRENT = "current"
    WITHDRAWN = "withdrawn"


class ProgramExpectationChangeKind(StrEnum):
    ADDED = "added"
    CHANGED = "changed"
    WITHDRAWN = "withdrawn"
    RESTORED = "restored"


@dataclass(frozen=True, slots=True)
class StageBootstrapDefinition:
    key: str
    name: str
    source_bindings: Mapping[str, str]
    external_references: Mapping[str, str] = field(default_factory=_empty_string_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "Stage key"))
        object.__setattr__(self, "name", _key(self.name, "Stage name"))
        object.__setattr__(
            self,
            "source_bindings",
            _string_mapping(self.source_bindings, "source_bindings"),
        )
        object.__setattr__(
            self,
            "external_references",
            _string_mapping(self.external_references, "external_references"),
        )


@dataclass(frozen=True, slots=True)
class EventStageBootstrapRequest:
    operation_id: EntityId
    event_key: str
    event_name: str
    stages: Sequence[StageBootstrapDefinition]
    actor_id: EntityId
    requested_at: datetime
    external_references: Mapping[str, str] = field(default_factory=_empty_string_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_key", _key(self.event_key, "Event key"))
        object.__setattr__(self, "event_name", _key(self.event_name, "Event name"))
        require_aware_datetime(self.requested_at, "requested_at")
        stages = tuple(sorted(self.stages, key=lambda value: value.key))
        if not stages:
            raise ValueError("Bootstrap requires at least one Stage.")
        if len({stage.key for stage in stages}) != len(stages):
            raise ValueError("Stage bootstrap keys must be unique.")
        source_keys = [key for stage in stages for key in stage.source_bindings]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("A source binding key can belong to only one Stage.")
        object.__setattr__(self, "stages", stages)
        object.__setattr__(
            self,
            "external_references",
            _string_mapping(self.external_references, "external_references"),
        )


@dataclass(frozen=True, slots=True)
class BusinessEvent:
    id: EntityId
    key: str
    name: str
    external_references: Mapping[str, str]
    revision: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "BusinessEvent.key"))
        object.__setattr__(self, "name", _key(self.name, "BusinessEvent.name"))
        object.__setattr__(
            self,
            "external_references",
            _string_mapping(self.external_references, "external_references"),
        )
        if self.revision < 1:
            raise ValueError("BusinessEvent.revision must be positive.")
        require_aware_datetime(self.created_at, "created_at")
        require_aware_datetime(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class Stage:
    id: EntityId
    event_id: EntityId
    key: str
    name: str
    source_bindings: Mapping[str, str]
    external_references: Mapping[str, str]
    revision: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "Stage.key"))
        object.__setattr__(self, "name", _key(self.name, "Stage.name"))
        object.__setattr__(
            self,
            "source_bindings",
            _string_mapping(self.source_bindings, "source_bindings"),
        )
        object.__setattr__(
            self,
            "external_references",
            _string_mapping(self.external_references, "external_references"),
        )
        if self.revision < 1:
            raise ValueError("Stage.revision must be positive.")
        require_aware_datetime(self.created_at, "created_at")
        require_aware_datetime(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class EventStageBootstrapResult:
    status: BootstrapStatus
    event: BusinessEvent | None
    stages: Sequence[Stage]
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(sorted(self.stages, key=lambda x: x.key)))


@dataclass(frozen=True, slots=True)
class ProgramExpectation:
    id: EntityId
    event_id: EntityId
    key: str
    stage_id: EntityId | None
    title: str
    speakers: Sequence[str]
    planned_start: datetime | None
    planned_end: datetime | None
    external_references: Mapping[str, str]
    revision: int
    recorded_at: datetime
    lifecycle_state: ProgramExpectationLifecycle = ProgramExpectationLifecycle.CURRENT
    synchronization_scope: str | None = None
    last_observed_at: datetime | None = None
    lifecycle_changed_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "ProgramExpectation.key"))
        object.__setattr__(self, "title", _key(self.title, "ProgramExpectation.title"))
        speakers = tuple(sorted({_key(value, "speaker") for value in self.speakers}))
        object.__setattr__(self, "speakers", speakers)
        for value, name in (
            (self.planned_start, "planned_start"),
            (self.planned_end, "planned_end"),
        ):
            if value is not None:
                require_aware_datetime(value, name)
        if (
            self.planned_start is not None
            and self.planned_end is not None
            and self.planned_end < self.planned_start
        ):
            raise ValueError("Program expectation end cannot precede start.")
        object.__setattr__(
            self,
            "external_references",
            _string_mapping(self.external_references, "external_references"),
        )
        if self.revision < 1:
            raise ValueError("ProgramExpectation.revision must be positive.")
        require_aware_datetime(self.recorded_at, "recorded_at")
        if self.synchronization_scope is not None:
            object.__setattr__(
                self,
                "synchronization_scope",
                _key(self.synchronization_scope, "synchronization_scope"),
            )
        if self.last_observed_at is None:
            object.__setattr__(self, "last_observed_at", self.recorded_at)
        if self.lifecycle_changed_at is None:
            object.__setattr__(self, "lifecycle_changed_at", self.recorded_at)
        assert self.last_observed_at is not None
        assert self.lifecycle_changed_at is not None
        require_aware_datetime(self.last_observed_at, "last_observed_at")
        require_aware_datetime(self.lifecycle_changed_at, "lifecycle_changed_at")


@dataclass(frozen=True, slots=True)
class ProgramExpectationFieldChange:
    field: str
    previous: str | None
    current: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", _key(self.field, "field"))


@dataclass(frozen=True, slots=True)
class ProgramExpectationChange:
    kind: ProgramExpectationChangeKind
    expectation_id: EntityId
    expectation_key: str
    title: str
    external_session_id: str | None
    fields: Sequence[ProgramExpectationFieldChange] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "expectation_key", _key(self.expectation_key, "expectation_key")
        )
        object.__setattr__(self, "title", _key(self.title, "title"))
        object.__setattr__(self, "fields", tuple(self.fields))


@dataclass(frozen=True, slots=True)
class ProgramExpectationSnapshot:
    event_id: EntityId
    stage_id: EntityId
    provider: str
    synchronization_scope: str
    observed_at: datetime
    expectations: Sequence[ProgramExpectation]

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _key(self.provider, "provider"))
        object.__setattr__(
            self,
            "synchronization_scope",
            _key(self.synchronization_scope, "synchronization_scope"),
        )
        require_aware_datetime(self.observed_at, "observed_at")
        expectations = tuple(self.expectations)
        if len({item.key for item in expectations}) != len(expectations):
            raise ValueError("Program snapshot expectation keys must be unique.")
        for item in expectations:
            if item.event_id != self.event_id or item.stage_id != self.stage_id:
                raise ValueError("Program snapshot expectation scope mismatch.")
            if item.synchronization_scope != self.synchronization_scope:
                raise ValueError("Program snapshot synchronization scope mismatch.")
            if item.lifecycle_state is not ProgramExpectationLifecycle.CURRENT:
                raise ValueError("Program snapshot items must be current.")
        object.__setattr__(self, "expectations", expectations)


@dataclass(frozen=True, slots=True)
class ProgramExpectationReconciliation:
    event_id: EntityId
    stage_id: EntityId
    provider: str
    synchronization_scope: str
    synchronized_at: datetime
    observed: int
    added: int
    changed: int
    unchanged: int
    withdrawn: int
    restored: int
    expectations: Sequence[ProgramExpectation]
    changes: Sequence[ProgramExpectationChange]
    changes_truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _key(self.provider, "provider"))
        object.__setattr__(
            self,
            "synchronization_scope",
            _key(self.synchronization_scope, "synchronization_scope"),
        )
        require_aware_datetime(self.synchronized_at, "synchronized_at")
        for field_name in (
            "observed",
            "added",
            "changed",
            "unchanged",
            "withdrawn",
            "restored",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must not be negative.")
        if self.added + self.changed + self.unchanged + self.restored != self.observed:
            raise ValueError("Observed Program reconciliation counts are inconsistent.")
        object.__setattr__(self, "expectations", tuple(self.expectations))
        object.__setattr__(self, "changes", tuple(self.changes))


__all__ = [
    "BootstrapStatus",
    "BusinessEvent",
    "EventStageBootstrapRequest",
    "EventStageBootstrapResult",
    "ProgramExpectation",
    "ProgramExpectationChange",
    "ProgramExpectationChangeKind",
    "ProgramExpectationFieldChange",
    "ProgramExpectationLifecycle",
    "ProgramExpectationReconciliation",
    "ProgramExpectationSnapshot",
    "Stage",
    "StageBootstrapDefinition",
]
