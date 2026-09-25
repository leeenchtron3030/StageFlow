from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.shared.ids import EntityId
from app.shared.time.validation import require_aware_datetime

MAX_INTEGER = 2**63 - 1


class PackagingAssetRole(StrEnum):
    OPENING_BUMPER = "opening_bumper"
    TITLE_CARD = "title_card"
    SPONSOR_CARD = "sponsor_card"
    OUTRO = "outro"


class ApprovalAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REVOKE = "revoke"


class ApprovalState(StrEnum):
    UNREVIEWED = "unreviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


def bounded_text(value: str, name: str, maximum: int) -> None:
    if "\x00" in value:
        raise ValueError(f"{name} must not contain a NUL character")
    if not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must contain 1..{maximum} characters")


def nonnegative(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_INTEGER:
        raise ValueError(f"{name} must be an integer between 0 and {MAX_INTEGER}")


@dataclass(frozen=True, slots=True)
class ExternalContent:
    content_key: str
    sha256: str
    byte_size: int
    media_type: str

    def __post_init__(self) -> None:
        # Opaque tokens only: no separators, drive/scheme syntax, dots or escapes.
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}", self.content_key) is None:
            raise ValueError("content_key must be an opaque token, never a filesystem path")
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        nonnegative(self.byte_size, "byte_size")
        if re.fullmatch(r"[A-Za-z0-9!#$&^_+.-]+/[A-Za-z0-9!#$&^_+.-]+", self.media_type) is None:
            raise ValueError("media_type must be a declared type/subtype")
        bounded_text(self.media_type, "media_type", 127)


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetContent:
    asset_id: EntityId


type ContentReference = ExternalContent | CompletedMediaAssetContent


def require_content_reference(value: object) -> None:
    if not isinstance(value, (ExternalContent, CompletedMediaAssetContent)):
        raise ValueError("exactly one supported content reference is required")


@dataclass(frozen=True, slots=True)
class RevisionContent:
    reference: ContentReference
    measured_duration_microseconds: int | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    def __post_init__(self) -> None:
        require_content_reference(self.reference)
        if self.measured_duration_microseconds is not None:
            nonnegative(self.measured_duration_microseconds, "measured_duration_microseconds")
        for name in ("effective_from", "effective_until"):
            value = getattr(self, name)
            if value is not None:
                require_aware_datetime(value, name)
        if (self.effective_from is not None and self.effective_until is not None
                and self.effective_until <= self.effective_from):
            raise ValueError("effective_until must follow effective_from")


@dataclass(frozen=True, slots=True)
class PackagingAsset:
    id: EntityId
    event_id: EntityId
    stage_id: EntityId | None
    name: str
    role: PackagingAssetRole
    created_at: datetime

    def __post_init__(self) -> None:
        bounded_text(self.name, "name", 200)
        object.__setattr__(self, "role", PackagingAssetRole(self.role))
        require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class PackagingAssetRevision:
    id: EntityId
    packaging_asset_id: EntityId
    revision_number: int
    content: RevisionContent
    created_at: datetime

    def __post_init__(self) -> None:
        nonnegative(self.revision_number, "revision_number")
        if self.revision_number == 0:
            raise ValueError("revision_number must be positive")
        require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class PackagingAssetApprovalDecision:
    id: EntityId
    packaging_asset_id: EntityId
    revision_number: int
    sequence: int
    actor_id: EntityId
    decided_at: datetime
    action: ApprovalAction
    reason: str

    def __post_init__(self) -> None:
        nonnegative(self.revision_number, "revision_number")
        nonnegative(self.sequence, "sequence")
        if self.revision_number == 0 or self.sequence == 0:
            raise ValueError("revision_number and sequence must be positive")
        object.__setattr__(self, "action", ApprovalAction(self.action))
        require_aware_datetime(self.decided_at, "decided_at")
        bounded_text(self.reason, "reason", 500)

    @property
    def approval_state(self) -> ApprovalState:
        return {
            ApprovalAction.APPROVE: ApprovalState.APPROVED,
            ApprovalAction.REJECT: ApprovalState.REJECTED,
            ApprovalAction.REVOKE: ApprovalState.REVOKED,
        }[self.action]


@dataclass(frozen=True, slots=True)
class CommandIdentity:
    operation_id: EntityId
    actor_id: EntityId
    request_digest: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_aware_datetime(self.recorded_at, "recorded_at")
        if re.fullmatch(r"[0-9a-f]{64}", self.request_digest) is None:
            raise ValueError("invalid request digest")


@dataclass(frozen=True, slots=True)
class AssetSummary:
    asset: PackagingAsset
    current_revision_number: int
    decision_count: int


@dataclass(frozen=True, slots=True)
class RevisionSummary:
    revision: PackagingAssetRevision
    approval_state: ApprovalState
    decision_count: int
    latest_decision: PackagingAssetApprovalDecision | None


@dataclass(frozen=True, slots=True)
class AssetPage:
    items: tuple[AssetSummary, ...]
    total_count: int
    next_after: EntityId | None


@dataclass(frozen=True, slots=True)
class RevisionPage:
    items: tuple[RevisionSummary, ...]
    total_count: int
    next_after: int | None


def validate_page(limit: int) -> None:
    nonnegative(limit, "limit")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
