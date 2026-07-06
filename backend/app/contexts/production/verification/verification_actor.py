from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.shared.ids import EntityId


class VerificationActorType(StrEnum):
    HUMAN = "human"
    APPROVED_SYSTEM = "approved_system"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class VerificationActor:
    """Reference to who or what recorded a verification decision."""

    actor_id: EntityId
    actor_type: VerificationActorType
    display_name: str | None = None
    role_label: str | None = None
