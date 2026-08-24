from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime


def _text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(sorted(value.items())))


def _empty_object_mapping() -> Mapping[str, object]:
    return {}


class EpistemicKind(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    DECLARED = "declared"
    EXTERNAL = "external"


class SessionActivityState(StrEnum):
    PRESENTATION_ACTIVE = "presentation_active"
    PRESENTATION_ENDED = "presentation_ended"


class SessionPackageState(StrEnum):
    ASSEMBLING = "assembling"
    READY_FOR_REVIEW = "ready_for_review"
    IN_REVIEW = "in_review"
    COMPLETE = "complete"
    CORRECTION_REQUIRED = "correction_required"


class MediaRegistrationState(StrEnum):
    DISCOVERED = "discovered"
    STABILIZING = "stabilizing"
    READY = "ready"
    REGISTERED = "registered"


class AssociationStatus(StrEnum):
    ASSOCIATED = "associated"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"


class AssociationAuthority(StrEnum):
    DETERMINISTIC = "deterministic"
    HUMAN = "human"


class ProducerWorkDecisionType(StrEnum):
    PACKAGE_READY_FOR_REVIEW = "package_ready_for_review"
    PACKAGE_CORRECTION_REQUIRED = "package_correction_required"
    ASSOCIATION_UNRESOLVED = "association_unresolved"
    ASSOCIATION_CONFLICT = "association_conflict"


class ProducerWorkSubjectKind(StrEnum):
    SESSION_PACKAGE = "session_package"
    MEDIA_ASSOCIATION = "media_association"


class HumanCommandKind(StrEnum):
    SESSION_START = "session_start"
    SESSION_BOUNDARY_CORRECTION = "session_boundary_correction"
    MEDIA_ASSIGNMENT = "media_assignment"
    PACKAGE_READY = "package_ready"
    PACKAGE_COMPLETION = "package_completion"


class ReconciliationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StartSessionRequest:
    operation_id: EntityId
    event_id: EntityId
    stage_id: EntityId
    actor_id: EntityId
    authoritative_start: datetime
    requested_at: datetime
    program_expectation_id: EntityId | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.authoritative_start, "authoritative_start")
        require_aware_datetime(self.requested_at, "requested_at")
        if self.title is not None:
            object.__setattr__(self, "title", _text(self.title, "title"))


@dataclass(frozen=True, slots=True)
class Session:
    id: EntityId
    event_id: EntityId
    stage_id: EntityId
    program_expectation_id: EntityId | None
    title: str | None
    activity_state: SessionActivityState
    package_state: SessionPackageState
    authoritative_start: datetime
    authoritative_end: datetime | None
    package_revision: int
    revision: int
    created_by: EntityId
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        require_aware_datetime(self.authoritative_start, "authoritative_start")
        if self.authoritative_end is not None:
            require_aware_datetime(self.authoritative_end, "authoritative_end")
            if self.authoritative_end < self.authoritative_start:
                raise ValueError("Session end cannot precede start.")
        if self.package_revision < 1 or self.revision < 1:
            raise ValueError("Session revisions must be positive.")
        require_aware_datetime(self.created_at, "created_at")
        require_aware_datetime(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class BoundaryDecision:
    id: EntityId
    session_id: EntityId
    boundary_kind: str
    boundary_at: datetime
    authority: EpistemicKind
    actor_id: EntityId | None
    reason: str
    decided_at: datetime
    resulting_session_revision: int
    operation_id: EntityId

    def __post_init__(self) -> None:
        if self.boundary_kind not in {"start", "end"}:
            raise ValueError("boundary_kind must be start or end.")
        require_aware_datetime(self.boundary_at, "boundary_at")
        require_aware_datetime(self.decided_at, "decided_at")
        object.__setattr__(self, "reason", _text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class AssociationInputReference:
    record_type: str
    record_id: str
    revision: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_type", _text(self.record_type, "record_type"))
        object.__setattr__(self, "record_id", _text(self.record_id, "record_id"))
        if self.revision is not None and self.revision < 1:
            raise ValueError("Association input revision must be positive.")


@dataclass(frozen=True, slots=True)
class SessionBoundaryProposal:
    id: EntityId
    session_id: EntityId
    boundary_kind: str
    boundary_at: datetime
    epistemic_kind: EpistemicKind
    proposer_id: EntityId
    evidence_ids: Sequence[EntityId]
    policy_id: str
    policy_version: str
    reason: str
    proposed_at: datetime
    model_id: str | None = None
    model_version: str | None = None

    def __post_init__(self) -> None:
        if self.boundary_kind not in {"start", "end"}:
            raise ValueError("boundary_kind must be start or end.")
        if self.epistemic_kind not in {
            EpistemicKind.OBSERVED,
            EpistemicKind.DERIVED,
            EpistemicKind.INFERRED,
        }:
            raise ValueError("Machine proposal epistemic kind must be advisory.")
        require_aware_datetime(self.boundary_at, "boundary_at")
        require_aware_datetime(self.proposed_at, "proposed_at")
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(sorted(set(self.evidence_ids), key=lambda value: value.value)),
        )
        if not self.evidence_ids:
            raise ValueError("Machine boundary proposal requires evidence lineage.")
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        object.__setattr__(
            self, "policy_version", _text(self.policy_version, "policy_version")
        )
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        if (self.model_id is None) is not (self.model_version is None):
            raise ValueError("Model identity and version must be supplied together.")
        if self.model_id is not None:
            object.__setattr__(self, "model_id", _text(self.model_id, "model_id"))
            assert self.model_version is not None
            object.__setattr__(
                self, "model_version", _text(self.model_version, "model_version")
            )


@dataclass(frozen=True, slots=True)
class MediaCandidate:
    id: EntityId
    proposed_asset_id: EntityId
    stage_id: EntityId
    source_binding_key: str
    source_reference: str
    discovered_at: datetime
    last_observed_at: datetime
    state: MediaRegistrationState
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_binding_key", _text(self.source_binding_key, "source_binding_key")
        )
        object.__setattr__(
            self,
            "source_reference",
            _text(self.source_reference, "source_reference"),
        )
        require_aware_datetime(self.discovered_at, "discovered_at")
        require_aware_datetime(self.last_observed_at, "last_observed_at")
        if self.last_observed_at < self.discovered_at:
            raise ValueError("Last observation cannot precede discovery.")
        if self.revision < 1:
            raise ValueError("MediaCandidate.revision must be positive.")


@dataclass(frozen=True, slots=True)
class ResourceObservation:
    id: EntityId
    candidate_id: EntityId
    observation_kind: str
    epistemic_kind: EpistemicKind
    observed_at: datetime
    recorded_at: datetime
    facts: Mapping[str, object] = field(default_factory=_empty_object_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_kind",
            _text(self.observation_kind, "observation_kind"),
        )
        require_aware_datetime(self.observed_at, "observed_at")
        require_aware_datetime(self.recorded_at, "recorded_at")
        object.__setattr__(self, "facts", _mapping(self.facts))


@dataclass(frozen=True, slots=True)
class RegisteredMediaAsset:
    id: EntityId
    candidate_id: EntityId
    manifest_id: EntityId
    stage_id: EntityId
    source_binding_key: str
    registered_at: datetime
    media_started_at: datetime | None = None
    media_ended_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_binding_key", _text(self.source_binding_key, "source_binding_key")
        )
        require_aware_datetime(self.registered_at, "registered_at")
        for value, name in (
            (self.media_started_at, "media_started_at"),
            (self.media_ended_at, "media_ended_at"),
        ):
            if value is not None:
                require_aware_datetime(value, name)
        if (
            self.media_started_at is not None
            and self.media_ended_at is not None
            and self.media_ended_at < self.media_started_at
        ):
            raise ValueError("Media end cannot precede media start.")


@dataclass(frozen=True, slots=True)
class MediaAssociation:
    asset_id: EntityId
    status: AssociationStatus
    session_id: EntityId | None
    authority: AssociationAuthority
    reason_codes: Sequence[str]
    evidence_ids: Sequence[EntityId]
    revision: int
    decided_at: datetime
    actor_id: EntityId | None = None
    operation_id: EntityId | None = None
    policy_id: str | None = None
    policy_version: str | None = None
    input_references: Sequence[AssociationInputReference] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        reasons = tuple(sorted({_text(value, "reason_code") for value in self.reason_codes}))
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(
            self, "evidence_ids", tuple(sorted(set(self.evidence_ids), key=lambda x: x.value))
        )
        if self.status is AssociationStatus.ASSOCIATED and self.session_id is None:
            raise ValueError("Associated media requires a Session.")
        if self.status is not AssociationStatus.ASSOCIATED and self.session_id is not None:
            raise ValueError("Only associated media can carry a Session ID.")
        if self.authority is AssociationAuthority.HUMAN and self.actor_id is None:
            raise ValueError("Human association requires an actor.")
        if self.authority is AssociationAuthority.HUMAN and self.operation_id is None:
            raise ValueError("Human association requires an operation identity.")
        if self.authority is AssociationAuthority.DETERMINISTIC:
            if self.policy_id is None or self.policy_version is None:
                raise ValueError("Deterministic association requires policy identity.")
        elif self.policy_id is not None or self.policy_version is not None:
            raise ValueError("Human association must not claim deterministic policy authority.")
        if (self.policy_id is None) is not (self.policy_version is None):
            raise ValueError("Association policy identity and version must be supplied together.")
        if self.policy_id is not None:
            object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
            assert self.policy_version is not None
            object.__setattr__(
                self, "policy_version", _text(self.policy_version, "policy_version")
            )
        object.__setattr__(
            self,
            "input_references",
            tuple(
                sorted(
                    set(self.input_references),
                    key=lambda value: (
                        value.record_type,
                        value.record_id,
                        value.revision or 0,
                    ),
                )
            ),
        )
        if not self.input_references:
            raise ValueError("Association requires truthful input references.")
        if self.revision < 1:
            raise ValueError("Association revision must be positive.")
        require_aware_datetime(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class ProducerWorkQueuePosition:
    priority: int
    updated_at: datetime
    projection_id: str

    def __post_init__(self) -> None:
        if self.priority < 1:
            raise ValueError("Work Queue priority must be positive.")
        require_aware_datetime(self.updated_at, "updated_at")
        object.__setattr__(
            self, "projection_id", _text(self.projection_id, "projection_id")
        )


@dataclass(frozen=True, slots=True)
class ProducerWorkQueueSubject:
    projection_id: str
    decision_type: ProducerWorkDecisionType
    subject_kind: ProducerWorkSubjectKind
    subject_id: EntityId
    subject_revision: int
    event_id: EntityId
    stage_id: EntityId
    session_id: EntityId | None
    priority: int
    reason_codes: Sequence[str]
    action_reference: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "projection_id", _text(self.projection_id, "projection_id")
        )
        object.__setattr__(
            self, "action_reference", _text(self.action_reference, "action_reference")
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(sorted({_text(value, "reason_code") for value in self.reason_codes})),
        )
        if self.subject_revision < 1:
            raise ValueError("Work Queue subject revision must be positive.")
        if self.priority < 1:
            raise ValueError("Work Queue priority must be positive.")
        require_aware_datetime(self.created_at, "created_at")
        require_aware_datetime(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("Work Queue update cannot precede subject creation.")

    @property
    def position(self) -> ProducerWorkQueuePosition:
        return ProducerWorkQueuePosition(
            priority=self.priority,
            updated_at=self.updated_at,
            projection_id=self.projection_id,
        )


@dataclass(frozen=True, slots=True)
class CompletionDecision:
    id: EntityId
    session_id: EntityId
    package_revision: int
    actor_id: EntityId
    approved: bool
    reason: str
    decided_at: datetime
    operation_id: EntityId

    def __post_init__(self) -> None:
        if self.package_revision < 1:
            raise ValueError("package_revision must be positive.")
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        require_aware_datetime(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class PackageReadyDecision:
    id: EntityId
    session_id: EntityId
    package_revision: int
    actor_id: EntityId
    reason: str
    decided_at: datetime
    operation_id: EntityId

    def __post_init__(self) -> None:
        if self.package_revision < 1:
            raise ValueError("package_revision must be positive.")
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        require_aware_datetime(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class ReconciliationRun:
    id: EntityId
    event_id: EntityId
    status: ReconciliationStatus
    scope: str
    started_at: datetime
    completed_at: datetime | None
    candidates_seen: int
    assets_registered: int
    failure_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", _text(self.scope, "scope"))
        require_aware_datetime(self.started_at, "started_at")
        if self.completed_at is not None:
            require_aware_datetime(self.completed_at, "completed_at")
        if self.candidates_seen < 0 or self.assets_registered < 0:
            raise ValueError("Reconciliation counts cannot be negative.")


@dataclass(frozen=True, slots=True)
class SessionOperationalProjection:
    session_id: EntityId
    activity_state: SessionActivityState
    package_state: SessionPackageState
    package_revision: int
    revision: int
    authoritative_start: datetime
    authoritative_end: datetime | None
    program_expectation_id: EntityId | None = None
    program_expectation_title: str | None = None
    program_expectation_revision: int | None = None
    program_expectation_planned_start: datetime | None = None
    program_expectation_planned_end: datetime | None = None
    completion_decision_id: EntityId | None = None
    completion_actor_id: EntityId | None = None
    completion_decided_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.package_revision < 1 or self.revision < 1:
            raise ValueError("Session projection revisions must be positive.")
        require_aware_datetime(self.authoritative_start, "authoritative_start")
        if self.authoritative_end is not None:
            require_aware_datetime(self.authoritative_end, "authoritative_end")
        if self.program_expectation_title is not None:
            object.__setattr__(
                self,
                "program_expectation_title",
                _text(self.program_expectation_title, "program_expectation_title"),
            )
        if self.program_expectation_revision is not None:
            if self.program_expectation_id is None or self.program_expectation_revision < 1:
                raise ValueError("Program Expectation projection requires identity and revision.")
        for value, name in (
            (self.program_expectation_planned_start, "program_expectation_planned_start"),
            (self.program_expectation_planned_end, "program_expectation_planned_end"),
            (self.completion_decided_at, "completion_decided_at"),
        ):
            if value is not None:
                require_aware_datetime(value, name)
        if (self.completion_decision_id is None) is not (
            self.completion_actor_id is None
        ):
            raise ValueError("Completion projection identity and actor must be supplied together.")


@dataclass(frozen=True, slots=True)
class StageOperationalStatus:
    stage_id: EntityId
    stage_key: str
    stage_name: str
    source_available: bool | None
    active_or_assembling_session_id: EntityId | None
    assembling_session_ids: Sequence[EntityId]
    assembling_sessions: Sequence[SessionOperationalProjection]
    session_activity_state: SessionActivityState | None
    session_package_state: SessionPackageState | None
    session_package_revision: int | None
    session_revision: int | None
    session_authoritative_start: datetime | None
    session_authoritative_end: datetime | None
    last_media_arrived_at: datetime | None
    discovered_media: int
    stabilizing_media: int
    ready_media: int
    registered_media: int
    associated_media: int
    unresolved_media: int
    conflicting_media: int
    attention_codes: Sequence[str] = field(default_factory=tuple)
    assembling_sessions_truncated: bool = False
    recent_sessions: Sequence[SessionOperationalProjection] = field(default_factory=tuple)
    recent_sessions_truncated: bool = False
    session_limit: int = 20

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assembling_session_ids",
            tuple(sorted(set(self.assembling_session_ids), key=lambda value: value.value)),
        )
        object.__setattr__(
            self, "attention_codes", tuple(sorted(set(self.attention_codes)))
        )
        object.__setattr__(
            self,
            "assembling_sessions",
            tuple(
                sorted(
                    self.assembling_sessions,
                    key=lambda value: (
                        value.authoritative_start,
                        value.session_id.value,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "recent_sessions",
            tuple(
                sorted(
                    self.recent_sessions,
                    key=lambda value: (
                        value.authoritative_start,
                        value.session_id.value,
                    ),
                    reverse=True,
                )
            ),
        )
        if self.session_limit < 1 or self.session_limit > 100:
            raise ValueError("Session projection limit must be between 1 and 100.")
        if len(self.assembling_sessions) > self.session_limit:
            raise ValueError("Assembling Session projection exceeds its declared bound.")
        if len(self.recent_sessions) > self.session_limit:
            raise ValueError("Recent Session projection exceeds its declared bound.")
        if {value.session_id for value in self.assembling_sessions} != set(
            self.assembling_session_ids
        ):
            raise ValueError("Assembling Session identities and details must match.")


@dataclass(frozen=True, slots=True)
class MediaOperationalProjection:
    candidate_id: EntityId
    proposed_asset_id: EntityId
    asset_id: EntityId | None
    stage_id: EntityId
    source_binding_key: str
    registration_state: MediaRegistrationState
    discovered_at: datetime
    last_observed_at: datetime
    association_status: AssociationStatus | None
    association_authority: AssociationAuthority | None
    session_id: EntityId | None
    epistemic_kinds: Sequence[EpistemicKind]
    media_started_at: datetime | None = None
    media_ended_at: datetime | None = None
    diagnostic_codes: Sequence[str] = field(default_factory=tuple)
    association_reason_codes: Sequence[str] = field(default_factory=tuple)
    association_evidence_ids: Sequence[EntityId] = field(default_factory=tuple)
    association_policy_id: str | None = None
    association_policy_version: str | None = None
    association_input_references: Sequence[AssociationInputReference] = field(
        default_factory=tuple
    )
    association_actor_id: EntityId | None = None
    association_decided_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.discovered_at, "discovered_at")
        require_aware_datetime(self.last_observed_at, "last_observed_at")
        if self.media_started_at is not None:
            require_aware_datetime(self.media_started_at, "media_started_at")
        if self.media_ended_at is not None:
            require_aware_datetime(self.media_ended_at, "media_ended_at")
        if (
            self.media_started_at is not None
            and self.media_ended_at is not None
            and self.media_ended_at < self.media_started_at
        ):
            raise ValueError("Media end cannot precede media start.")
        object.__setattr__(
            self,
            "epistemic_kinds",
            tuple(sorted(set(self.epistemic_kinds), key=lambda value: value.value)),
        )
        object.__setattr__(
            self,
            "diagnostic_codes",
            tuple(
                sorted(
                    {
                        _text(value, "diagnostic_code")
                        for value in self.diagnostic_codes
                    }
                )
            ),
        )
        object.__setattr__(
            self,
            "association_reason_codes",
            tuple(
                sorted(
                    {
                        _text(value, "association_reason_code")
                        for value in self.association_reason_codes
                    }
                )
            ),
        )
        object.__setattr__(
            self,
            "association_evidence_ids",
            tuple(sorted(set(self.association_evidence_ids), key=lambda value: value.value)),
        )
        object.__setattr__(
            self,
            "association_input_references",
            tuple(self.association_input_references),
        )
        if self.association_decided_at is not None:
            require_aware_datetime(self.association_decided_at, "association_decided_at")


@dataclass(frozen=True, slots=True)
class EventOperationalStatus:
    event_id: EntityId
    event_key: str
    event_name: str
    database_available: bool
    ready: bool
    recovering: bool
    stages: Sequence[StageOperationalStatus]
    attention_codes: Sequence[str]
    latest_reconciliation: ReconciliationRun | None
    recent_media: Sequence[MediaOperationalProjection] = field(default_factory=tuple)
    boundary_proposals: Sequence[SessionBoundaryProposal] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(sorted(self.stages, key=lambda x: x.stage_key)))
        object.__setattr__(self, "attention_codes", tuple(sorted(set(self.attention_codes))))
        object.__setattr__(self, "recent_media", tuple(self.recent_media))
        object.__setattr__(self, "boundary_proposals", tuple(self.boundary_proposals))


__all__ = [
    "AssociationInputReference",
    "AssociationAuthority",
    "AssociationStatus",
    "BoundaryDecision",
    "CompletionDecision",
    "EpistemicKind",
    "EventOperationalStatus",
    "HumanCommandKind",
    "MediaAssociation",
    "MediaCandidate",
    "MediaOperationalProjection",
    "MediaRegistrationState",
    "PackageReadyDecision",
    "ProducerWorkDecisionType",
    "ProducerWorkQueuePosition",
    "ProducerWorkQueueSubject",
    "ProducerWorkSubjectKind",
    "ReconciliationRun",
    "ReconciliationStatus",
    "RegisteredMediaAsset",
    "ResourceObservation",
    "Session",
    "SessionBoundaryProposal",
    "SessionOperationalProjection",
    "SessionActivityState",
    "SessionPackageState",
    "StageOperationalStatus",
    "StartSessionRequest",
]
