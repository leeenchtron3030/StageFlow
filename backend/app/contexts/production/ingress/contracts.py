from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from app.contexts.production.ingress.identity import (
    IngressIdentity,
    StableSourceIdentity,
    canonical_ingress_document,
    digest_canonical_document,
    resolve_ingress_identity,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_facts() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class IngressRegistrationRequest:
    source_identity: StableSourceIdentity
    event_type: ProductionEventType
    event_source: ProductionEventSource
    payload: ProductionEventPayload
    correlation_id: CorrelationId
    occurred_at: datetime
    received_at: datetime
    source_event_key: str | None = None
    authoritative_source_facts: Mapping[str, Any] = field(default_factory=_empty_facts)

    def __post_init__(self) -> None:
        require_aware_datetime(self.occurred_at, "occurred_at")
        require_aware_datetime(self.received_at, "received_at")
        if self.received_at < self.occurred_at:
            raise ValueError("Ingress received_at must not be earlier than occurred_at.")
        object.__setattr__(
            self,
            "authoritative_source_facts",
            freeze_metadata(self.authoritative_source_facts),
        )
        if self.source_event_key is not None and not self.source_event_key.strip():
            raise ValueError("source_event_key must not be empty when supplied.")

    @property
    def canonical_document(self) -> str:
        return canonical_ingress_document(
            source=self.source_identity,
            event_type=self.event_type.value,
            event_source=self.event_source.value,
            occurred_at=self.occurred_at,
            payload=self.payload,
            authoritative_source_facts=self.authoritative_source_facts,
        )

    @property
    def identity(self) -> IngressIdentity:
        return resolve_ingress_identity(self.source_event_key, self.canonical_document)

    @property
    def facts_digest(self) -> str:
        return digest_canonical_document(self.canonical_document)


@dataclass(frozen=True, slots=True)
class DurableIngressRecord:
    ingress_id: EntityId
    production_event_id: EntityId
    request: IngressRegistrationRequest
    identity: IngressIdentity
    canonical_document: str
    facts_digest: str
    first_received_at: datetime
    last_received_at: datetime
    delivery_count: int

    def __post_init__(self) -> None:
        require_aware_datetime(self.first_received_at, "first_received_at")
        require_aware_datetime(self.last_received_at, "last_received_at")
        if self.delivery_count < 1:
            raise ValueError("Durable ingress delivery_count must be positive.")

    def with_replay(self, received_at: datetime) -> DurableIngressRecord:
        return replace(
            self,
            last_received_at=require_aware_datetime(received_at, "received_at"),
            delivery_count=self.delivery_count + 1,
        )

    def to_production_event(self) -> ProductionEvent:
        return ProductionEvent(
            id=self.production_event_id,
            event_type=self.request.event_type,
            source=self.request.event_source,
            payload=self.request.payload,
            correlation_id=self.request.correlation_id,
            occurred_at=self.request.occurred_at,
            received_at=self.first_received_at,
            metadata={
                "ingress_id": self.ingress_id,
                "ingress_identity_kind": self.identity.kind,
                "ingress_identity_value": self.identity.value,
            },
        )


class IngressRegistrationStatus(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    CONFLICT = "conflict"
    STORAGE_UNAVAILABLE = "storage_unavailable"


@dataclass(frozen=True, slots=True)
class IngressRegistrationResult:
    status: IngressRegistrationStatus
    record: DurableIngressRecord | None = None
    failure_code: str | None = None

    @property
    def should_dispatch(self) -> bool:
        return self.status is IngressRegistrationStatus.CREATED


class IngressRepository(Protocol):
    def register(self, request: IngressRegistrationRequest) -> IngressRegistrationResult: ...
