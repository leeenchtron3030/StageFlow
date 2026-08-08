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


__all__ = [
    "BootstrapStatus",
    "BusinessEvent",
    "EventStageBootstrapRequest",
    "EventStageBootstrapResult",
    "ProgramExpectation",
    "Stage",
    "StageBootstrapDefinition",
]
