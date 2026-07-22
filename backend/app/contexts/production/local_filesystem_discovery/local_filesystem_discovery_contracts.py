from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.contexts.production.completed_media_asset import CompletedMediaAssetKind
from app.contexts.production.runtime import RuntimeSourceLocationScheme
from app.shared.ids import EntityId

from .local_filesystem_discovery_reason import normalize_discovery_limitations
from .local_filesystem_validation import (
    freeze_discovery_metadata,
    normalize_extensions,
    normalize_hint_mapping,
    require_aware,
    require_non_empty,
    validate_absolute_target_location,
)


class LocalFilesystemTargetScope(StrEnum):
    SINGLE_FILE = "single_file"
    SHALLOW_DIRECTORY = "shallow_directory"


class LocalFilesystemExtensionMatchingMode(StrEnum):
    CASE_SENSITIVE = "case_sensitive"
    CASE_INSENSITIVE = "case_insensitive"


class LocalFilesystemHiddenEntryPolicy(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


class LocalFilesystemSymlinkPolicy(StrEnum):
    REJECT_OR_SKIP = "reject_or_skip"


class LocalFilesystemIdentityStrength(StrEnum):
    STABLE_OBJECT_IDENTITY = "stable_object_identity"
    LOCATION_SCOPED_IDENTITY = "location_scoped_identity"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _empty_string_mapping() -> Mapping[str, str]:
    return {}


def _empty_kind_mapping() -> Mapping[str, CompletedMediaAssetKind]:
    return {}


@dataclass(frozen=True, slots=True)
class LocalFilesystemEligibilityPolicy:
    allowed_filename_extensions: Sequence[str]
    extension_matching_mode: LocalFilesystemExtensionMatchingMode
    hidden_entry_policy: LocalFilesystemHiddenEntryPolicy
    regular_file_required: bool
    symlink_policy: LocalFilesystemSymlinkPolicy
    permit_all_regular_files: bool
    excluded_suffixes: Sequence[str] = field(default_factory=tuple)
    extension_to_media_type_hints: Mapping[str, str] = field(
        default_factory=_empty_string_mapping
    )
    extension_to_container_hints: Mapping[str, str] = field(
        default_factory=_empty_string_mapping
    )
    extension_to_asset_kind_hints: Mapping[str, CompletedMediaAssetKind] = field(
        default_factory=_empty_kind_mapping
    )
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.regular_file_required is not True:
            raise ValueError("ED-0053 requires regular files explicitly.")
        if self.symlink_policy is not LocalFilesystemSymlinkPolicy.REJECT_OR_SKIP:
            raise ValueError("ED-0053 requires reject-or-skip symlink behavior.")
        if type(self.permit_all_regular_files) is not bool:
            raise ValueError("permit_all_regular_files must be boolean.")
        casefold = (
            self.extension_matching_mode
            is LocalFilesystemExtensionMatchingMode.CASE_INSENSITIVE
        )
        allowed = normalize_extensions(
            self.allowed_filename_extensions,
            "LocalFilesystemEligibilityPolicy.allowed_filename_extensions",
            casefold=casefold,
        )
        if not allowed and not self.permit_all_regular_files:
            raise ValueError(
                "Eligibility requires an extension allowlist or deliberate allow-all."
            )
        excluded = normalize_extensions(
            self.excluded_suffixes,
            "LocalFilesystemEligibilityPolicy.excluded_suffixes",
            casefold=casefold,
        )
        media_hints = normalize_hint_mapping(
            self.extension_to_media_type_hints,
            "LocalFilesystemEligibilityPolicy.extension_to_media_type_hints",
            casefold=casefold,
        )
        container_hints = normalize_hint_mapping(
            self.extension_to_container_hints,
            "LocalFilesystemEligibilityPolicy.extension_to_container_hints",
            casefold=casefold,
        )
        asset_hints = normalize_hint_mapping(
            self.extension_to_asset_kind_hints,
            "LocalFilesystemEligibilityPolicy.extension_to_asset_kind_hints",
            casefold=casefold,
        )
        for mapping_name, mapping in (
            ("media", media_hints),
            ("container", container_hints),
        ):
            if any(not value.strip() for value in mapping.values()):
                raise ValueError(f"{mapping_name} hints must be non-empty strings.")
        object.__setattr__(self, "allowed_filename_extensions", allowed)
        object.__setattr__(self, "excluded_suffixes", excluded)
        object.__setattr__(self, "extension_to_media_type_hints", media_hints)
        object.__setattr__(self, "extension_to_container_hints", container_hints)
        object.__setattr__(self, "extension_to_asset_kind_hints", asset_hints)
        object.__setattr__(
            self,
            "limitations",
            normalize_discovery_limitations(self.limitations),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_discovery_metadata(
                self.metadata,
                "LocalFilesystemEligibilityPolicy.metadata",
            ),
        )

    def normalized_extension(self, filename: str) -> str:
        dot_index = filename.rfind(".")
        extension = "" if dot_index < 0 else filename[dot_index:]
        if self.extension_matching_mode is LocalFilesystemExtensionMatchingMode.CASE_INSENSITIVE:
            return extension.casefold()
        return extension

    def normalized_filename(self, filename: str) -> str:
        if self.extension_matching_mode is LocalFilesystemExtensionMatchingMode.CASE_INSENSITIVE:
            return filename.casefold()
        return filename


@dataclass(frozen=True, slots=True)
class LocalFilesystemTargetBinding:
    binding_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    collection_plan_id: EntityId
    collection_target_id: EntityId
    source_capability_id: EntityId
    discovery_capability_id: EntityId
    source_location_scheme: RuntimeSourceLocationScheme
    configured_absolute_target_location: str
    target_scope: LocalFilesystemTargetScope
    maximum_directory_entries_examined: int
    eligibility_policy: LocalFilesystemEligibilityPolicy
    source_host_id: EntityId
    source_volume_id: EntityId | None = None
    configured_stage_id: EntityId | None = None
    configured_recording_block_id: EntityId | None = None
    recorder_application_id: EntityId | None = None
    explicit_asset_kind_hint: CompletedMediaAssetKind | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if (
            isinstance(self.maximum_directory_entries_examined, bool)
            or self.maximum_directory_entries_examined <= 0
        ):
            raise ValueError("maximum_directory_entries_examined must be positive.")
        object.__setattr__(
            self,
            "configured_absolute_target_location",
            validate_absolute_target_location(
                self.configured_absolute_target_location,
                "LocalFilesystemTargetBinding.configured_absolute_target_location",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_discovery_limitations(self.limitations),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_discovery_metadata(
                self.metadata,
                "LocalFilesystemTargetBinding.metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class LocalFilesystemDiscoveryConfiguration:
    adapter_id: EntityId
    adapter_version: str
    runtime_id: EntityId
    configuration_id: EntityId
    supported_source_schemes: Sequence[RuntimeSourceLocationScheme]
    target_bindings: Sequence[LocalFilesystemTargetBinding]
    identity_namespace_id: EntityId
    configured_at: datetime
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "adapter_version",
            require_non_empty(
                self.adapter_version,
                "LocalFilesystemDiscoveryConfiguration.adapter_version",
            ),
        )
        require_aware(
            self.configured_at,
            "LocalFilesystemDiscoveryConfiguration.configured_at",
        )
        schemes = tuple(
            sorted(set(self.supported_source_schemes), key=lambda value: value.value)
        )
        approved = {
            RuntimeSourceLocationScheme.LOCAL_FILE,
            RuntimeSourceLocationScheme.MOUNTED_VOLUME,
        }
        if not schemes or any(scheme not in approved for scheme in schemes):
            raise ValueError(
                "ED-0053 supports only local_file and mounted_volume schemes."
            )
        by_target: dict[str, LocalFilesystemTargetBinding] = {}
        binding_ids: set[str] = set()
        for binding in self.target_bindings:
            if binding.binding_id.value in binding_ids:
                raise ValueError("Target-binding IDs must be unique.")
            binding_ids.add(binding.binding_id.value)
            if binding.collection_target_id.value in by_target:
                raise ValueError("One collection target must map to one binding.")
            by_target[binding.collection_target_id.value] = binding
        if not by_target:
            raise ValueError("Discovery configuration requires at least one target binding.")
        object.__setattr__(self, "supported_source_schemes", schemes)
        object.__setattr__(
            self,
            "target_bindings",
            tuple(by_target[key] for key in sorted(by_target)),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_discovery_limitations(self.limitations),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_discovery_metadata(
                self.metadata,
                "LocalFilesystemDiscoveryConfiguration.metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class LocalFilesystemSourceIdentity:
    strength: LocalFilesystemIdentityStrength
    normalized_source_location: str
    stable_object_token: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "normalized_source_location",
            validate_absolute_target_location(
                self.normalized_source_location,
                "LocalFilesystemSourceIdentity.normalized_source_location",
            ),
        )
        token = (
            None
            if self.stable_object_token is None
            else require_non_empty(
                self.stable_object_token,
                "LocalFilesystemSourceIdentity.stable_object_token",
            )
        )
        if self.strength is LocalFilesystemIdentityStrength.STABLE_OBJECT_IDENTITY:
            if token is None:
                raise ValueError("Stable object identity requires an opaque token.")
        elif token is not None:
            raise ValueError("Only stable object identity may retain an object token.")
        object.__setattr__(self, "stable_object_token", token)


__all__ = [
    "LocalFilesystemDiscoveryConfiguration",
    "LocalFilesystemEligibilityPolicy",
    "LocalFilesystemExtensionMatchingMode",
    "LocalFilesystemHiddenEntryPolicy",
    "LocalFilesystemIdentityStrength",
    "LocalFilesystemSourceIdentity",
    "LocalFilesystemSymlinkPolicy",
    "LocalFilesystemTargetBinding",
    "LocalFilesystemTargetScope",
]
