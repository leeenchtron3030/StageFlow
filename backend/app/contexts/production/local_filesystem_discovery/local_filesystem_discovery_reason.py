from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum


class LocalFilesystemDiscoveryReasonCode(StrEnum):
    LOCAL_FILESYSTEM_TARGET_ACCEPTED = "local_filesystem_target_accepted"
    MOUNTED_VOLUME_TARGET_ACCEPTED = "mounted_volume_target_accepted"
    UNSUPPORTED_RUNTIME_PROFILE = "unsupported_runtime_profile"
    UNSUPPORTED_SOURCE_SCHEME = "unsupported_source_scheme"
    RUNTIME_ID_MISMATCH = "runtime_id_mismatch"
    CONFIGURATION_ID_MISMATCH = "configuration_id_mismatch"
    COLLECTION_PLAN_ID_MISMATCH = "collection_plan_id_mismatch"
    COLLECTION_TARGET_NOT_CONFIGURED = "collection_target_not_configured"
    SOURCE_CAPABILITY_ID_MISMATCH = "source_capability_id_mismatch"
    DISCOVERY_CAPABILITY_ID_MISMATCH = "discovery_capability_id_mismatch"
    EVENT_MODE_ID_MISMATCH = "event_mode_id_mismatch"
    RESOURCE_POLICY_ID_MISMATCH = "resource_policy_id_mismatch"
    EXECUTION_PERMISSION_DENIED = "execution_permission_denied"
    TARGET_PATH_MISMATCH = "target_path_mismatch"
    PATH_VIOLATES_CONFIGURED_SCOPE = "path_violates_configured_scope"
    TARGET_MISSING = "target_missing"
    TARGET_INACCESSIBLE = "target_inaccessible"
    TARGET_TYPE_MISMATCH = "target_type_mismatch"
    CONFIGURED_TARGET_IS_SYMLINK = "configured_target_is_symlink"
    SINGLE_FILE_INSPECTED = "single_file_inspected"
    SHALLOW_DIRECTORY_ENUMERATED = "shallow_directory_enumerated"
    NESTED_DIRECTORY_IGNORED = "nested_directory_ignored"
    SYMLINK_ENTRY_SKIPPED = "symlink_entry_skipped"
    SPECIAL_ENTRY_SKIPPED = "special_entry_skipped"
    HIDDEN_ENTRY_EXCLUDED = "hidden_entry_excluded"
    EXTENSION_NOT_ELIGIBLE = "extension_not_eligible"
    EXPLICIT_EXCLUSION_MATCHED = "explicit_exclusion_matched"
    REGULAR_FILE_ELIGIBLE = "regular_file_eligible"
    DIRECTORY_ENTRY_LIMIT_EXCEEDED = "directory_entry_limit_exceeded"
    CANDIDATE_RESULT_LIMIT_REACHED = "candidate_result_limit_reached"
    STABLE_OBJECT_IDENTITY_AVAILABLE = "stable_object_identity_available"
    LOCATION_SCOPED_IDENTITY_USED = "location_scoped_identity_used"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    ENTRY_DISAPPEARED_DURING_DISCOVERY = "entry_disappeared_during_discovery"
    ENTRY_INSPECTION_FAILED = "entry_inspection_failed"
    NO_ELIGIBLE_CANDIDATES = "no_eligible_candidates"
    CANDIDATES_DISCOVERED = "candidates_discovered"
    PARTIAL_CANDIDATES_DISCOVERED = "partial_candidates_discovered"
    NO_COMPLETION_ASSESSMENT_PERFORMED = "no_completion_assessment_performed"
    NO_READINESS_ASSESSMENT_PERFORMED = "no_readiness_assessment_performed"
    UNKNOWN_LOCAL_FILESYSTEM_FAILURE = "unknown_local_filesystem_failure"


class LocalFilesystemDiscoveryLimitation(StrEnum):
    STABLE_FILESYSTEM_IDENTITY_UNAVAILABLE = (
        "stable_filesystem_identity_unavailable"
    )
    LOCATION_SCOPED_CANDIDATE_IDENTITY_USED = (
        "location_scoped_candidate_identity_used"
    )
    SYMLINK_ENTRIES_NOT_FOLLOWED = "symlink_entries_were_not_followed"
    NESTED_DIRECTORIES_NOT_TRAVERSED = "nested_directories_were_not_traversed"
    DIRECTORY_ENTRY_BOUND_PREVENTED_DISCOVERY = (
        "directory_entry_bound_prevented_discovery"
    )
    CANDIDATE_RESULT_BOUND_TRUNCATED_DISCOVERY = (
        "candidate_result_bound_truncated_discovery"
    )
    ENTRIES_BECAME_UNAVAILABLE = "one_or_more_entries_became_unavailable"
    ENTRIES_COULD_NOT_BE_INSPECTED = "one_or_more_entries_could_not_be_inspected"
    MEDIA_TYPE_EXTENSION_DERIVED_ONLY = "media_type_is_extension_derived_only"
    CONTAINER_TYPE_EXTENSION_DERIVED_ONLY = (
        "container_type_is_extension_derived_only"
    )
    ASSET_KIND_EXTENSION_DERIVED_ONLY = "asset_kind_is_extension_derived_only"
    DISCOVERY_TIMESTAMP_REQUEST_ANCHORED = "discovery_timestamp_is_request_anchored"
    NO_COMPLETION_ASSESSMENT_PERFORMED = "no_completion_assessment_performed"
    NO_READINESS_ASSESSMENT_PERFORMED = "no_readiness_assessment_performed"


_REASON_ORDER = {
    value: index for index, value in enumerate(LocalFilesystemDiscoveryReasonCode)
}
_LIMITATION_ORDER = {
    value: index for index, value in enumerate(LocalFilesystemDiscoveryLimitation)
}
_LIMITATION_VALUE_ORDER = {
    value.value: index for value, index in _LIMITATION_ORDER.items()
}


def normalize_discovery_reasons(
    values: Sequence[LocalFilesystemDiscoveryReasonCode],
) -> tuple[str, ...]:
    return tuple(value.value for value in sorted(set(values), key=_REASON_ORDER.__getitem__))


def normalize_discovery_limitations(
    values: Sequence[LocalFilesystemDiscoveryLimitation | str],
) -> tuple[str, ...]:
    by_value: dict[str, LocalFilesystemDiscoveryLimitation | str] = {}
    for value in values:
        rendered = value.value if isinstance(value, LocalFilesystemDiscoveryLimitation) else value
        normalized = rendered.strip()
        if not normalized:
            raise ValueError("Local filesystem discovery limitations must not be empty.")
        by_value[normalized] = value
    return tuple(
        sorted(
            by_value,
            key=lambda rendered: (
                _LIMITATION_VALUE_ORDER.get(rendered, len(_LIMITATION_ORDER)),
                rendered,
            ),
        )
    )


__all__ = [
    "LocalFilesystemDiscoveryLimitation",
    "LocalFilesystemDiscoveryReasonCode",
    "normalize_discovery_limitations",
    "normalize_discovery_reasons",
]
