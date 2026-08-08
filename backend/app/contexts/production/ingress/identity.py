from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any, cast

from app.contexts.production.production_event import ProductionEventPayload
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import normalize_utc_datetime, require_aware_datetime

FINGERPRINT_VERSION = "stageflow-ingress-v1"


class IngressIdentityKind(StrEnum):
    SOURCE_EVENT_KEY = "source_event_key"
    CANONICAL_FINGERPRINT = "canonical_fingerprint"


@dataclass(frozen=True, slots=True)
class StableSourceIdentity:
    namespace: str
    identifier: str

    def __post_init__(self) -> None:
        if not self.namespace.strip() or not self.identifier.strip():
            raise ValueError("Stable source namespace and identifier must not be empty.")


@dataclass(frozen=True, slots=True)
class IngressIdentity:
    kind: IngressIdentityKind
    value: str
    fingerprint_version: str | None = None


def canonical_ingress_document(
    *,
    source: StableSourceIdentity,
    event_type: str,
    event_source: str,
    occurred_at: datetime,
    payload: ProductionEventPayload,
    authoritative_source_facts: Mapping[str, Any],
) -> str:
    occurred_at = require_aware_datetime(occurred_at, "occurred_at")
    document = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "source": {
            "namespace": source.namespace,
            "identifier": source.identifier,
        },
        "event_type": event_type,
        "event_source": event_source,
        "occurred_at": normalize_utc_datetime(
            occurred_at, "occurred_at"
        ).isoformat().replace("+00:00", "Z"),
        "payload": _json_value(payload.data),
        "authoritative_source_facts": _json_value(
            freeze_metadata(authoritative_source_facts)
        ),
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def resolve_ingress_identity(
    source_event_key: str | None,
    canonical_document: str,
) -> IngressIdentity:
    if source_event_key is not None:
        if not source_event_key.strip():
            raise ValueError("source_event_key must not be empty when supplied.")
        return IngressIdentity(IngressIdentityKind.SOURCE_EVENT_KEY, source_event_key)
    fingerprint = hashlib.sha256(canonical_document.encode("utf-8")).hexdigest()
    return IngressIdentity(
        IngressIdentityKind.CANONICAL_FINGERPRINT,
        fingerprint,
        FINGERPRINT_VERSION,
    )


def digest_canonical_document(canonical_document: str) -> str:
    return hashlib.sha256(canonical_document.encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("Canonical ingress facts must contain finite numbers.")
        return value
    if isinstance(value, datetime):
        value = require_aware_datetime(value, "authoritative source fact")
        return normalize_utc_datetime(
            value, "authoritative source fact"
        ).isoformat().replace("+00:00", "Z")
    if isinstance(value, EntityId | CorrelationId):
        return value.to_json()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        if not all(isinstance(key, str) for key in mapping):
            raise ValueError("Canonical ingress fact keys must be strings.")
        return {key: _json_value(mapping[key]) for key in sorted(mapping)}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_value(item) for item in cast(Sequence[Any], value)]
    raise ValueError("Canonical ingress facts must be JSON-compatible StageFlow values.")
