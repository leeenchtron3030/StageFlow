from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.production.ingress import (
    DurableIngressRecord,
    IngressIdentity,
    IngressIdentityKind,
    IngressRegistrationRequest,
    IngressRegistrationResult,
    IngressRegistrationStatus,
    StableSourceIdentity,
)
from app.contexts.production.production_event import (
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId

_INSERT = """
INSERT INTO stageflow.production_event_ingress (
    ingress_id, production_event_id, source_namespace, source_identifier,
    identity_kind, identity_value, fingerprint_version, source_event_key,
    canonical_document, facts_digest, event_type, event_source, payload,
    authoritative_source_facts, correlation_id, occurred_at,
    first_received_at, last_received_at, delivery_count
) VALUES (
    %(ingress_id)s, %(production_event_id)s, %(source_namespace)s,
    %(source_identifier)s, %(identity_kind)s, %(identity_value)s,
    %(fingerprint_version)s, %(source_event_key)s, %(canonical_document)s,
    %(facts_digest)s, %(event_type)s, %(event_source)s, %(payload)s,
    %(authoritative_source_facts)s, %(correlation_id)s, %(occurred_at)s,
    %(received_at)s, %(received_at)s, 1
)
ON CONFLICT (source_namespace, source_identifier, identity_kind, identity_value)
DO NOTHING
RETURNING *
"""

_SELECT_FOR_UPDATE = """
SELECT * FROM stageflow.production_event_ingress
WHERE source_namespace = %(source_namespace)s
  AND source_identifier = %(source_identifier)s
  AND identity_kind = %(identity_kind)s
  AND identity_value = %(identity_value)s
FOR UPDATE
"""

_REPLAY_UPDATE = """
UPDATE stageflow.production_event_ingress
SET last_received_at = %(received_at)s,
    delivery_count = delivery_count + 1
WHERE ingress_id = %(ingress_id)s
RETURNING *
"""


@dataclass(frozen=True, slots=True)
class PostgresIngressRepository:
    """PostgreSQL authority for replay-safe Production Event ingress."""

    dsn: str

    def register(self, request: IngressRegistrationRequest) -> IngressRegistrationResult:
        identity = request.identity
        parameters = self._parameters(request, identity)
        try:
            with psycopg.Connection[dict[str, Any]].connect(
                self.dsn, row_factory=dict_row
            ) as connection:
                inserted = connection.execute(_INSERT, parameters).fetchone()
                if inserted is not None:
                    return IngressRegistrationResult(
                        IngressRegistrationStatus.CREATED,
                        self._record(inserted),
                    )
                current = connection.execute(
                    _SELECT_FOR_UPDATE, parameters
                ).fetchone()
                if current is None:
                    raise RuntimeError("Ingress uniqueness row disappeared in transaction.")
                if (
                    current["facts_digest"] != request.facts_digest
                    or current["canonical_document"] != request.canonical_document
                ):
                    return IngressRegistrationResult(
                        IngressRegistrationStatus.CONFLICT,
                        self._record(current),
                        "ingress_identity_conflict",
                    )
                replayed = connection.execute(
                    _REPLAY_UPDATE,
                    {
                        "ingress_id": current["ingress_id"],
                        "received_at": request.received_at,
                    },
                ).fetchone()
                if replayed is None:
                    raise RuntimeError("Ingress replay update returned no authoritative row.")
                return IngressRegistrationResult(
                    IngressRegistrationStatus.REPLAYED,
                    self._record(replayed),
                )
        except (psycopg.OperationalError, psycopg.InterfaceError):
            return IngressRegistrationResult(
                IngressRegistrationStatus.STORAGE_UNAVAILABLE,
                failure_code="postgresql_ingress_unavailable",
            )

    @staticmethod
    def _parameters(
        request: IngressRegistrationRequest,
        identity: IngressIdentity,
    ) -> dict[str, Any]:
        canonical_document = json.loads(request.canonical_document)
        return {
            "ingress_id": EntityId.new().to_json(),
            "production_event_id": EntityId.new().to_json(),
            "source_namespace": request.source_identity.namespace,
            "source_identifier": request.source_identity.identifier,
            "identity_kind": identity.kind.value,
            "identity_value": identity.value,
            "fingerprint_version": identity.fingerprint_version,
            "source_event_key": request.source_event_key,
            "canonical_document": request.canonical_document,
            "facts_digest": request.facts_digest,
            "event_type": request.event_type.value,
            "event_source": request.event_source.value,
            "payload": Jsonb(canonical_document["payload"]),
            "authoritative_source_facts": Jsonb(
                canonical_document["authoritative_source_facts"]
            ),
            "correlation_id": request.correlation_id.to_json(),
            "occurred_at": request.occurred_at,
            "received_at": request.received_at,
        }

    @staticmethod
    def _record(row: Mapping[str, Any]) -> DurableIngressRecord:
        source_event_key = cast(str | None, row["source_event_key"])
        request = IngressRegistrationRequest(
            source_identity=StableSourceIdentity(
                cast(str, row["source_namespace"]),
                cast(str, row["source_identifier"]),
            ),
            event_type=ProductionEventType(cast(str, row["event_type"])),
            event_source=ProductionEventSource(cast(str, row["event_source"])),
            payload=ProductionEventPayload(cast(Mapping[str, Any], row["payload"])),
            correlation_id=CorrelationId.parse(str(row["correlation_id"])),
            occurred_at=cast(datetime, row["occurred_at"]),
            received_at=cast(datetime, row["first_received_at"]),
            source_event_key=source_event_key,
            authoritative_source_facts=cast(
                Mapping[str, Any], row["authoritative_source_facts"]
            ),
        )
        return DurableIngressRecord(
            ingress_id=EntityId.parse(str(row["ingress_id"])),
            production_event_id=EntityId.parse(str(row["production_event_id"])),
            request=request,
            identity=IngressIdentity(
                IngressIdentityKind(cast(str, row["identity_kind"])),
                cast(str, row["identity_value"]),
                cast(str | None, row["fingerprint_version"]),
            ),
            canonical_document=cast(str, row["canonical_document"]),
            facts_digest=cast(str, row["facts_digest"]),
            first_received_at=cast(datetime, row["first_received_at"]),
            last_received_at=cast(datetime, row["last_received_at"]),
            delivery_count=cast(int, row["delivery_count"]),
        )
