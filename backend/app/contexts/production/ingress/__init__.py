"""Stable, replay-safe Production Event ingress contracts."""

from app.contexts.production.ingress.contracts import (
    DurableIngressRecord,
    IngressRegistrationRequest,
    IngressRegistrationResult,
    IngressRegistrationStatus,
    IngressRepository,
)
from app.contexts.production.ingress.dispatch import (
    DurableIngressDispatcher,
    IngressDispatchResult,
)
from app.contexts.production.ingress.identity import (
    FINGERPRINT_VERSION,
    IngressIdentity,
    IngressIdentityKind,
    StableSourceIdentity,
)
from app.contexts.production.ingress.in_memory_repository import InMemoryIngressRepository

__all__ = [
    "DurableIngressDispatcher",
    "DurableIngressRecord",
    "FINGERPRINT_VERSION",
    "IngressDispatchResult",
    "IngressIdentity",
    "IngressIdentityKind",
    "IngressRegistrationRequest",
    "IngressRegistrationResult",
    "IngressRegistrationStatus",
    "IngressRepository",
    "InMemoryIngressRepository",
    "StableSourceIdentity",
]
