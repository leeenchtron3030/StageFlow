"""Immutable Session Assembly facts; no media execution or Kernel authority."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

from app.shared.ids import EntityId
from app.shared.time.validation import require_aware_datetime

from .contracts import (
    ApprovalState,
    PackagingAsset,
    PackagingAssetRevision,
    bounded_text,
    nonnegative,
)


def positive(value: int, name: str) -> None:
    nonnegative(value, name)
    if value == 0:
        raise ValueError(f"{name} must be positive")


class PlacementRole(StrEnum):
    OPENING_BUMPER = "opening_bumper"
    TITLE_CARD = "title_card"
    SESSION_MEDIA = "session_media"
    SPONSOR_CARD = "sponsor_card"
    OUTRO = "outro"


class MetadataField(StrEnum):
    SESSION_TITLE = "session_title"
    PARTICIPANT_NAMES = "participant_names"


class MetadataOverrideAction(StrEnum):
    SET = "set"
    CLEAR = "clear"


@dataclass(frozen=True, slots=True)
class AssemblyMetadataOverride:
    id: EntityId
    session_id: EntityId
    field: MetadataField
    action: MetadataOverrideAction
    values: tuple[str, ...]
    sequence: int
    actor_id: EntityId
    recorded_at: datetime
    reason: str
    authority_kind: Literal["human"] = "human"

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", MetadataField(self.field))
        object.__setattr__(self, "action", MetadataOverrideAction(self.action))
        if isinstance(self.values, str):
            raise ValueError("values must be a sequence of display strings")
        object.__setattr__(self, "values", tuple(self.values))
        if self.action == MetadataOverrideAction.SET:
            if not 1 <= len(self.values) <= 100:
                raise ValueError("set requires 1..100 values")
            for value in self.values:
                if type(value) is not str:
                    raise ValueError("values must contain display strings")
                bounded_text(value, "value", 1000)
        elif self.values:
            raise ValueError("clear must not contain values")
        positive(self.sequence, "sequence")
        bounded_text(self.reason, "reason", 500)
        require_aware_datetime(self.recorded_at, "recorded_at")
        if self.authority_kind != "human":
            raise ValueError("assembly authority must be human")


@dataclass(frozen=True, slots=True)
class MetadataOverridePage:
    items: tuple[AssemblyMetadataOverride, ...]
    total_count: int
    next_after: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


class ValidationReason(StrEnum):
    INELIGIBLE_PACKAGE = "ineligible_package"
    COMPLETION_MEMBERSHIP_UNAVAILABLE = "completion_membership_unavailable"
    MEDIA_TIMING_UNAVAILABLE = "media_timing_unavailable"
    UNRESOLVED_REQUIRED_SLOT = "unresolved_required_slot"
    AMBIGUOUS_BINDING = "ambiguous_binding"
    INVALID_EXPLICIT_BINDING = "invalid_explicit_binding"
    MISSING_REQUIRED_METADATA = "missing_required_metadata"


class AssemblyAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class AssemblySlot:
    key: str
    role: PlacementRole
    required: bool

    def __post_init__(self) -> None:
        bounded_text(self.key, "slot key", 100)
        object.__setattr__(self, "role", PlacementRole(self.role))
        if type(self.required) is not bool:
            raise ValueError("required must be boolean")


@dataclass(frozen=True, slots=True)
class AssemblyTemplate:
    id: EntityId
    event_id: EntityId
    template_key: str
    version: int
    name: str
    slots: tuple[AssemblySlot, ...]
    required_metadata: tuple[MetadataField, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        bounded_text(self.template_key, "template_key", 100)
        bounded_text(self.name, "name", 200)
        positive(self.version, "version")
        object.__setattr__(self, "slots", tuple(self.slots))
        object.__setattr__(self, "required_metadata", tuple(sorted({
            MetadataField(item) for item in self.required_metadata
        })))
        if not 1 <= len(self.slots) <= 100:
            raise ValueError("template requires 1..100 slots")
        if len({slot.key for slot in self.slots}) != len(self.slots):
            raise ValueError("duplicate slot key")
        require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CompletionMember:
    asset_id: EntityId
    association_revision: int
    media_started_at: datetime | None

    def __post_init__(self) -> None:
        positive(self.association_revision, "association_revision")
        if self.media_started_at is not None:
            require_aware_datetime(self.media_started_at, "media_started_at")


@dataclass(frozen=True, slots=True)
class MetadataValue:
    field: MetadataField
    values: tuple[str, ...]
    source_id: EntityId
    source_revision: int
    source: Literal["program_expectation", "operator_override"] = "program_expectation"

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", MetadataField(self.field))
        object.__setattr__(self, "values", tuple(self.values))
        positive(self.source_revision, "source_revision")
        if self.source not in ("program_expectation", "operator_override"):
            raise ValueError("unsupported metadata source")


@dataclass(frozen=True, slots=True)
class AssemblyInputs:
    session_id: EntityId
    event_id: EntityId
    stage_id: EntityId
    authoritative_start: datetime
    package_revision: int
    package_complete: bool
    completion_decision_id: EntityId | None
    membership: tuple[CompletionMember, ...]
    metadata: tuple[MetadataValue, ...]

    def __post_init__(self) -> None:
        require_aware_datetime(self.authoritative_start, "authoritative_start")
        positive(self.package_revision, "package_revision")
        object.__setattr__(self, "membership", tuple(self.membership))
        object.__setattr__(self, "metadata", tuple(self.metadata))


@dataclass(frozen=True, slots=True)
class PackagingCandidate:
    asset: PackagingAsset
    revision: PackagingAssetRevision
    approval_state: ApprovalState


@dataclass(frozen=True, slots=True)
class ExplicitBinding:
    slot_key: str
    packaging_revision_id: EntityId


@dataclass(frozen=True, slots=True)
class SlotBinding:
    slot_key: str
    packaging_revision_id: EntityId | None
    outcome: Literal["bound", "unresolved", "ambiguous", "invalid_explicit", "session_media"]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: ValidationReason
    subject: str | None = None


@dataclass(frozen=True, slots=True)
class AssemblyValidation:
    issues: tuple[ValidationIssue, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def state(self) -> Literal["valid", "invalid"]:
        return "invalid" if self.issues else "valid"


@dataclass(frozen=True, slots=True)
class AssemblyRevision:
    id: EntityId
    session_id: EntityId
    event_id: EntityId
    revision_number: int
    supersedes_id: EntityId | None
    template_id: EntityId
    package_revision: int
    completion_decision_id: EntityId | None
    membership: tuple[CompletionMember, ...]
    bindings: tuple[SlotBinding, ...]
    metadata: tuple[MetadataValue, ...]
    validation: AssemblyValidation
    actor_id: EntityId
    created_at: datetime

    def __post_init__(self) -> None:
        positive(self.revision_number, "revision_number")
        positive(self.package_revision, "package_revision")
        for name in ("membership", "bindings", "metadata"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class AssemblyApprovalDecision:
    id: EntityId
    session_id: EntityId
    revision_id: EntityId
    sequence: int
    actor_id: EntityId
    decided_at: datetime
    action: AssemblyAction
    reason: str
    authority_kind: Literal["human"] = "human"

    def __post_init__(self) -> None:
        positive(self.sequence, "sequence")
        object.__setattr__(self, "action", AssemblyAction(self.action))
        bounded_text(self.reason, "reason", 500)
        require_aware_datetime(self.decided_at, "decided_at")
        if self.authority_kind != "human":
            raise ValueError("assembly authority must be human")


@dataclass(frozen=True, slots=True)
class SessionAssembly:
    """Read projection; Session ID is the stable assembly identity in this slice."""
    revision: AssemblyRevision
    current_revision_number: int
    stale: bool
    approval_state: ApprovalState
    decision_count: int
    latest_decision: AssemblyApprovalDecision | None


@dataclass(frozen=True, slots=True)
class AssemblyPage:
    items: tuple[SessionAssembly, ...]
    total_count: int
    next_after: int | None


@dataclass(frozen=True, slots=True)
class TemplatePage:
    items: tuple[AssemblyTemplate, ...]
    total_count: int
    next_after: EntityId | None
