from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(authorization|credential|password|private[_ -]?key|secret|token)\s*[:=]"
)
_PRIVATE_LOCATION = re.compile(
    r"(?i)(?:[A-Z]:[\\/]|[\\/]{2}|file:(?://)?|"
    r"(?:^|[\s\"'=(])/(?!/)\S+|(?:^|[\s\"'=(])\.\.?[\\/]\S+|"
    r"\.(?:mkv|mov|mp4|mxf|wav)\b)"
)


def _text(value: str, field_name: str, *, maximum: int = 512) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds its bounded length.")
    if "\x00" in normalized or "\r" in normalized or "\n" in normalized:
        raise ValueError(f"{field_name} must be one sanitized line.")
    if _SENSITIVE_ASSIGNMENT.search(normalized):
        raise ValueError(f"{field_name} must not contain credential material.")
    return normalized


def _identifier(value: str, field_name: str) -> str:
    normalized = _text(value, field_name, maximum=128)
    if not _IDENTIFIER.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a sanitized stable identifier.")
    return normalized


def _original(value: str, field_name: str) -> str:
    normalized = _text(value, field_name)
    if _PRIVATE_LOCATION.search(normalized):
        raise ValueError(f"{field_name} must not contain a private path or media filename.")
    return normalized


def _strings(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    return tuple(sorted({_original(value, field_name) for value in values}))


def _positive_revision(value: int, field_name: str) -> None:
    if value < 1:
        raise ValueError(f"{field_name} must be positive.")


class TimingTimezoneKind(StrEnum):
    EXPLICIT_UTC = "explicit_utc"
    EXPLICIT_OFFSET = "explicit_offset"
    NAIVE_UNQUALIFIED = "naive_unqualified"
    NOT_APPLICABLE = "not_applicable"


class RecorderProfileQualificationStatus(StrEnum):
    UNQUALIFIED = "unqualified"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MediaTimingEpistemicKind(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class MediaTimingInspectionProvenance:
    provider_id: str
    provider_version: str
    tool_id: str
    tool_version: str
    recorder_profile_id: str
    recorder_profile_revision: int
    inspected_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "provider_id",
            "provider_version",
            "tool_id",
            "tool_version",
            "recorder_profile_id",
        ):
            object.__setattr__(self, field_name, _identifier(getattr(self, field_name), field_name))
        _positive_revision(self.recorder_profile_revision, "recorder_profile_revision")
        require_aware_datetime(self.inspected_at, "inspected_at")


@dataclass(frozen=True, slots=True)
class MediaTimingObservation:
    id: EntityId
    kind: str
    source_field: str
    original_representation: str
    observed_at: datetime
    timezone_kind: TimingTimezoneKind
    normalized_timestamp: datetime | None = None
    normalized_duration: timedelta | None = None
    normalized_value: str | None = None
    precision: str | None = None
    stream_selector: str | None = None
    limitations: tuple[str, ...] = ()

    @property
    def epistemic_kind(self) -> MediaTimingEpistemicKind:
        return MediaTimingEpistemicKind.OBSERVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _identifier(self.kind, "observation.kind"))
        object.__setattr__(
            self,
            "source_field",
            _identifier(self.source_field, "observation.source_field"),
        )
        object.__setattr__(
            self,
            "original_representation",
            _original(self.original_representation, "observation.original_representation"),
        )
        require_aware_datetime(self.observed_at, "observation.observed_at")
        if self.normalized_timestamp is not None:
            require_aware_datetime(
                self.normalized_timestamp,
                "observation.normalized_timestamp",
            )
        if self.normalized_duration is not None and self.normalized_duration < timedelta(0):
            raise ValueError("observation.normalized_duration must not be negative.")
        normalized_count = sum(
            value is not None
            for value in (
                self.normalized_timestamp,
                self.normalized_duration,
                self.normalized_value,
            )
        )
        if normalized_count > 1:
            raise ValueError("An observation has at most one normalized value.")
        if (
            self.timezone_kind is TimingTimezoneKind.NAIVE_UNQUALIFIED
            and self.normalized_timestamp is not None
        ):
            raise ValueError("Naive timing evidence cannot have a normalized timestamp.")
        for field_name in ("normalized_value", "precision", "stream_selector"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _original(value, f"observation.{field_name}"))
        object.__setattr__(
            self,
            "limitations",
            _strings(self.limitations, "observation.limitation"),
        )


@dataclass(frozen=True, slots=True)
class MediaTimingDerivation:
    id: EntityId
    rule_id: str
    rule_version: str
    input_observation_ids: tuple[EntityId, ...]
    candidate_started_at: datetime
    candidate_ended_at: datetime
    derived_at: datetime
    limitations: tuple[str, ...] = ()

    @property
    def epistemic_kind(self) -> MediaTimingEpistemicKind:
        return MediaTimingEpistemicKind.DERIVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", _identifier(self.rule_id, "derivation.rule_id"))
        object.__setattr__(
            self,
            "rule_version",
            _identifier(self.rule_version, "derivation.rule_version"),
        )
        inputs = tuple(sorted(set(self.input_observation_ids), key=lambda value: value.value))
        if not inputs:
            raise ValueError("A derivation requires at least one observation input.")
        object.__setattr__(self, "input_observation_ids", inputs)
        require_aware_datetime(self.candidate_started_at, "candidate_started_at")
        require_aware_datetime(self.candidate_ended_at, "candidate_ended_at")
        require_aware_datetime(self.derived_at, "derived_at")
        if self.candidate_ended_at < self.candidate_started_at:
            raise ValueError("Candidate interval end must not precede its start.")
        object.__setattr__(
            self,
            "limitations",
            _strings(self.limitations, "derivation.limitation"),
        )


@dataclass(frozen=True, slots=True)
class RecorderProfileQualification:
    profile_id: str
    profile_revision: int
    status: RecorderProfileQualificationStatus
    evaluated_at: datetime
    qualification_record_id: EntityId | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _identifier(self.profile_id, "profile_id"))
        _positive_revision(self.profile_revision, "profile_revision")
        require_aware_datetime(self.evaluated_at, "qualification.evaluated_at")
        if (
            self.status is RecorderProfileQualificationStatus.QUALIFIED
            and self.qualification_record_id is None
        ):
            raise ValueError("Qualified recorder evidence requires a qualification record.")
        object.__setattr__(
            self,
            "limitations",
            _strings(self.limitations, "qualification.limitation"),
        )


@dataclass(frozen=True, slots=True)
class MediaTimingInspectionResult:
    provenance: MediaTimingInspectionProvenance
    observations: tuple[MediaTimingObservation, ...]
    derivations: tuple[MediaTimingDerivation, ...]
    qualification: RecorderProfileQualification
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        observations = tuple(sorted(self.observations, key=lambda item: item.id.value))
        derivations = tuple(sorted(self.derivations, key=lambda item: item.id.value))
        observation_ids = {item.id for item in observations}
        if len(observation_ids) != len(observations):
            raise ValueError("Observation identities must be unique within one result.")
        if len({item.id for item in derivations}) != len(derivations):
            raise ValueError("Derivation identities must be unique within one result.")
        for derivation in derivations:
            if not set(derivation.input_observation_ids).issubset(observation_ids):
                raise ValueError("Derivation inputs must reference observations in this result.")
        if self.provenance.recorder_profile_id != self.qualification.profile_id:
            raise ValueError("Inspection and qualification profile identities must match.")
        if self.provenance.recorder_profile_revision != self.qualification.profile_revision:
            raise ValueError("Inspection and qualification profile revisions must match.")
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "derivations", derivations)
        object.__setattr__(
            self,
            "limitations",
            _strings(self.limitations, "evidence.limitation"),
        )


@dataclass(frozen=True, slots=True)
class ApplyMediaTimingEvidenceRequest:
    operation_id: EntityId
    asset_id: EntityId
    manifest_id: EntityId
    manifest_version: str
    applied_at: datetime
    result: MediaTimingInspectionResult

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "manifest_version",
            _identifier(self.manifest_version, "manifest_version"),
        )
        require_aware_datetime(self.applied_at, "applied_at")
        if self.applied_at < self.result.provenance.inspected_at:
            raise ValueError("Evidence cannot be applied before inspection.")


@dataclass(frozen=True, slots=True)
class PendingMediaTimingEvidence:
    id: EntityId
    request: ApplyMediaTimingEvidenceRequest
    request_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_digest",
            _identifier(self.request_digest, "request_digest"),
        )


@dataclass(frozen=True, slots=True)
class MediaTimingEvidence:
    id: EntityId
    asset_id: EntityId
    manifest_id: EntityId
    manifest_version: str
    revision: int
    predecessor_evidence_id: EntityId | None
    operation_id: EntityId
    request_digest: str
    applied_at: datetime
    result: MediaTimingInspectionResult

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "manifest_version",
            _identifier(self.manifest_version, "manifest_version"),
        )
        _positive_revision(self.revision, "evidence.revision")
        object.__setattr__(
            self,
            "request_digest",
            _identifier(self.request_digest, "request_digest"),
        )
        require_aware_datetime(self.applied_at, "evidence.applied_at")
        if self.revision == 1 and self.predecessor_evidence_id is not None:
            raise ValueError("The first evidence revision cannot have a predecessor.")
        if self.revision > 1 and self.predecessor_evidence_id is None:
            raise ValueError("Later evidence revisions require a predecessor.")


__all__ = [
    "ApplyMediaTimingEvidenceRequest",
    "MediaTimingDerivation",
    "MediaTimingEpistemicKind",
    "MediaTimingEvidence",
    "MediaTimingInspectionProvenance",
    "MediaTimingInspectionResult",
    "MediaTimingObservation",
    "PendingMediaTimingEvidence",
    "RecorderProfileQualification",
    "RecorderProfileQualificationStatus",
    "TimingTimezoneKind",
]
