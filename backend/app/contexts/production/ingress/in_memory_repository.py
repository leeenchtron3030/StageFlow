from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from app.contexts.production.ingress.contracts import (
    DurableIngressRecord,
    IngressRegistrationRequest,
    IngressRegistrationResult,
    IngressRegistrationStatus,
)
from app.contexts.production.ingress.identity import IngressIdentityKind
from app.shared.ids import EntityId

type _IdentityKey = tuple[str, str, IngressIdentityKind, str]


def _empty_records() -> dict[_IdentityKey, DurableIngressRecord]:
    return {}


@dataclass(slots=True)
class InMemoryIngressRepository:
    """Concurrency-safe process-local test double; never an authority fallback."""

    _records: dict[_IdentityKey, DurableIngressRecord] = field(
        default_factory=_empty_records
    )
    _lock: Lock = field(default_factory=Lock)

    def register(self, request: IngressRegistrationRequest) -> IngressRegistrationResult:
        identity = request.identity
        key = (
            request.source_identity.namespace,
            request.source_identity.identifier,
            identity.kind,
            identity.value,
        )
        with self._lock:
            current = self._records.get(key)
            if current is None:
                record = DurableIngressRecord(
                    ingress_id=EntityId.new(),
                    production_event_id=EntityId.new(),
                    request=request,
                    identity=identity,
                    canonical_document=request.canonical_document,
                    facts_digest=request.facts_digest,
                    first_received_at=request.received_at,
                    last_received_at=request.received_at,
                    delivery_count=1,
                )
                self._records[key] = record
                return IngressRegistrationResult(
                    IngressRegistrationStatus.CREATED, record
                )
            if (
                current.facts_digest != request.facts_digest
                or current.canonical_document != request.canonical_document
            ):
                return IngressRegistrationResult(
                    IngressRegistrationStatus.CONFLICT,
                    current,
                    "ingress_identity_conflict",
                )
            replayed = current.with_replay(request.received_at)
            self._records[key] = replayed
            return IngressRegistrationResult(
                IngressRegistrationStatus.REPLAYED, replayed
            )
