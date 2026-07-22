from __future__ import annotations

import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from uuid import UUID, uuid5

from app.contexts.production.asset_readiness import (
    MediaAssetCandidate,
    MediaAssetCandidateResource,
)
from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetContext,
    CompletedMediaAssetKind,
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetRuntimeProfile,
    CompletedMediaAssetSourceLocation,
)
from app.contexts.production.media_collection import (
    DiscoveredMediaCandidate,
    MediaCandidateDiscoveryOutcome,
    MediaCandidateDiscoveryPort,
    MediaCandidateDiscoveryRequest,
    MediaCandidateDiscoveryResult,
)
from app.contexts.production.runtime import (
    RuntimeCapabilityKind,
    RuntimeCapabilitySupportStatus,
    RuntimeCollectionPlan,
    RuntimeProfile,
    RuntimeSourceAccessMode,
    RuntimeSourceHostScope,
    RuntimeSourceLocationScheme,
    StageFlowRuntime,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
)
from app.shared.ids import EntityId

from .local_filesystem_discovery_contracts import (
    LocalFilesystemDiscoveryConfiguration,
    LocalFilesystemHiddenEntryPolicy,
    LocalFilesystemIdentityStrength,
    LocalFilesystemSourceIdentity,
    LocalFilesystemTargetBinding,
    LocalFilesystemTargetScope,
)
from .local_filesystem_discovery_reason import (
    LocalFilesystemDiscoveryLimitation,
    LocalFilesystemDiscoveryReasonCode,
    normalize_discovery_limitations,
    normalize_discovery_reasons,
)

_SUPPORTED_PROFILES = frozenset(
    {RuntimeProfile.AGENT, RuntimeProfile.NODE, RuntimeProfile.DEVELOPMENT}
)
_BASE_LIMITATIONS = (
    LocalFilesystemDiscoveryLimitation.DISCOVERY_TIMESTAMP_REQUEST_ANCHORED,
    LocalFilesystemDiscoveryLimitation.NO_COMPLETION_ASSESSMENT_PERFORMED,
    LocalFilesystemDiscoveryLimitation.NO_READINESS_ASSESSMENT_PERFORMED,
)
_BASE_REASONS = (
    LocalFilesystemDiscoveryReasonCode.NO_COMPLETION_ASSESSMENT_PERFORMED,
    LocalFilesystemDiscoveryReasonCode.NO_READINESS_ASSESSMENT_PERFORMED,
)


@dataclass(frozen=True, slots=True)
class _EligibleEntry:
    name: str
    absolute_location: str
    identity: LocalFilesystemSourceIdentity
    media_type_hint: str | None
    container_type_hint: str | None
    asset_kind_hint: CompletedMediaAssetKind | None
    limitations: tuple[str, ...]

    @property
    def order_key(self) -> tuple[str, str, str, str]:
        return (
            self.name.casefold(),
            self.name,
            self.identity.stable_object_token or "",
            self.absolute_location,
        )


@dataclass(frozen=True, slots=True)
class LocalFilesystemCandidateDiscoveryAdapter(MediaCandidateDiscoveryPort):
    """One-shot, read-only ED-0052 discovery adapter for one configured filesystem target."""

    runtime: StageFlowRuntime
    configuration: LocalFilesystemDiscoveryConfiguration
    _bindings_by_target: Mapping[str, LocalFilesystemTargetBinding] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        bindings = _validate_configuration_against_runtime(self.runtime, self.configuration)
        object.__setattr__(self, "_bindings_by_target", MappingProxyType(bindings))

    def discover(
        self,
        request: MediaCandidateDiscoveryRequest,
    ) -> MediaCandidateDiscoveryResult:
        binding, plan, rejection = self._validate_request(request)
        if rejection is not None:
            return rejection
        assert binding is not None
        assert plan is not None

        if binding.source_location_scheme not in self.configuration.supported_source_schemes:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.UNSUPPORTED,
                reasons=(LocalFilesystemDiscoveryReasonCode.UNSUPPORTED_SOURCE_SCHEME,),
                binding=binding,
            )

        accepted_reason = (
            LocalFilesystemDiscoveryReasonCode.LOCAL_FILESYSTEM_TARGET_ACCEPTED
            if binding.source_location_scheme is RuntimeSourceLocationScheme.LOCAL_FILE
            else LocalFilesystemDiscoveryReasonCode.MOUNTED_VOLUME_TARGET_ACCEPTED
        )
        try:
            ancestor_symlink = _configured_path_has_symlinked_ancestor(
                binding.configured_absolute_target_location
            )
        except PermissionError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.TARGET_INACCESSIBLE,
                ),
                binding=binding,
            )
        except OSError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.FAILED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.UNKNOWN_LOCAL_FILESYSTEM_FAILURE,
                ),
                binding=binding,
            )
        if ancestor_symlink:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.PATH_VIOLATES_CONFIGURED_SCOPE,
                ),
                limitations=(
                    LocalFilesystemDiscoveryLimitation.SYMLINK_ENTRIES_NOT_FOLLOWED,
                ),
                binding=binding,
            )
        try:
            target_stat = os.lstat(binding.configured_absolute_target_location)
        except FileNotFoundError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(accepted_reason, LocalFilesystemDiscoveryReasonCode.TARGET_MISSING),
                binding=binding,
            )
        except PermissionError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.TARGET_INACCESSIBLE,
                ),
                binding=binding,
            )
        except OSError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.FAILED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.UNKNOWN_LOCAL_FILESYSTEM_FAILURE,
                ),
                binding=binding,
            )

        if stat.S_ISLNK(target_stat.st_mode):
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.CONFIGURED_TARGET_IS_SYMLINK,
                ),
                limitations=(
                    LocalFilesystemDiscoveryLimitation.SYMLINK_ENTRIES_NOT_FOLLOWED,
                ),
                binding=binding,
            )

        if binding.target_scope is LocalFilesystemTargetScope.SINGLE_FILE:
            return self._discover_single_file(request, binding, target_stat, accepted_reason)
        return self._discover_shallow_directory(
            request,
            binding,
            target_stat,
            accepted_reason,
        )

    def _validate_request(
        self,
        request: MediaCandidateDiscoveryRequest,
    ) -> tuple[
        LocalFilesystemTargetBinding | None,
        RuntimeCollectionPlan | None,
        MediaCandidateDiscoveryResult | None,
    ]:
        checks = (
            (
                request.runtime_id != self.configuration.runtime_id,
                LocalFilesystemDiscoveryReasonCode.RUNTIME_ID_MISMATCH,
            ),
            (
                request.configuration_id != self.configuration.configuration_id,
                LocalFilesystemDiscoveryReasonCode.CONFIGURATION_ID_MISMATCH,
            ),
        )
        for invalid, reason in checks:
            if invalid:
                return None, None, self._result(
                    request,
                    MediaCandidateDiscoveryOutcome.BLOCKED,
                    reasons=(reason,),
                )
        if self.runtime.profile not in _SUPPORTED_PROFILES:
            return None, None, self._result(
                request,
                MediaCandidateDiscoveryOutcome.UNSUPPORTED,
                reasons=(LocalFilesystemDiscoveryReasonCode.UNSUPPORTED_RUNTIME_PROFILE,),
            )
        if request.execution_permission not in (
            AgentRuntimeExecutionPermission.NORMAL,
            AgentRuntimeExecutionPermission.REDUCED,
        ):
            return None, None, self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(LocalFilesystemDiscoveryReasonCode.EXECUTION_PERMISSION_DENIED,),
            )
        binding = self._bindings_by_target.get(request.collection_target_id.value)
        if binding is None:
            return None, None, self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    LocalFilesystemDiscoveryReasonCode.COLLECTION_TARGET_NOT_CONFIGURED,
                ),
            )
        plan = next(
            (
                candidate
                for candidate in self.runtime.configuration.collection_plans
                if candidate.id == binding.collection_plan_id
            ),
            None,
        )
        assert plan is not None
        binding_checks = (
            (
                request.collection_plan_id != binding.collection_plan_id,
                LocalFilesystemDiscoveryReasonCode.COLLECTION_PLAN_ID_MISMATCH,
            ),
            (
                request.source_capability_id != binding.source_capability_id,
                LocalFilesystemDiscoveryReasonCode.SOURCE_CAPABILITY_ID_MISMATCH,
            ),
            (
                request.discovery_capability_id != binding.discovery_capability_id,
                LocalFilesystemDiscoveryReasonCode.DISCOVERY_CAPABILITY_ID_MISMATCH,
            ),
            (
                request.event_mode_id != plan.event_mode_id,
                LocalFilesystemDiscoveryReasonCode.EVENT_MODE_ID_MISMATCH,
            ),
            (
                request.resource_policy_id != plan.resource_policy_id,
                LocalFilesystemDiscoveryReasonCode.RESOURCE_POLICY_ID_MISMATCH,
            ),
            (
                request.target_reference
                != binding.configured_absolute_target_location,
                LocalFilesystemDiscoveryReasonCode.TARGET_PATH_MISMATCH,
            ),
        )
        for invalid, reason in binding_checks:
            if invalid:
                return binding, plan, self._result(
                    request,
                    MediaCandidateDiscoveryOutcome.BLOCKED,
                    reasons=(reason,),
                    binding=binding,
                )
        return binding, plan, None

    def _discover_single_file(
        self,
        request: MediaCandidateDiscoveryRequest,
        binding: LocalFilesystemTargetBinding,
        target_stat: os.stat_result,
        accepted_reason: LocalFilesystemDiscoveryReasonCode,
    ) -> MediaCandidateDiscoveryResult:
        if not stat.S_ISREG(target_stat.st_mode):
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.TARGET_TYPE_MISMATCH,
                ),
                binding=binding,
            )
        reasons = [
            accepted_reason,
            LocalFilesystemDiscoveryReasonCode.SINGLE_FILE_INSPECTED,
        ]
        limitations: list[LocalFilesystemDiscoveryLimitation | str] = []
        entry = self._eligible_entry(
            binding,
            binding.configured_absolute_target_location,
            os.path.basename(binding.configured_absolute_target_location),
            target_stat,
            reasons,
            limitations,
        )
        if entry is None:
            reasons.append(LocalFilesystemDiscoveryReasonCode.NO_ELIGIBLE_CANDIDATES)
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.NO_CANDIDATES,
                reasons=reasons,
                limitations=limitations,
                binding=binding,
                entries_examined=1,
            )
        discovered = self._construct_discovered_candidate(request, binding, entry)
        reasons.append(LocalFilesystemDiscoveryReasonCode.CANDIDATES_DISCOVERED)
        return self._result(
            request,
            MediaCandidateDiscoveryOutcome.DISCOVERED,
            reasons=reasons,
            limitations=(*limitations, *entry.limitations),
            binding=binding,
            discovered_candidates=(discovered,),
            entries_examined=1,
        )

    def _discover_shallow_directory(
        self,
        request: MediaCandidateDiscoveryRequest,
        binding: LocalFilesystemTargetBinding,
        target_stat: os.stat_result,
        accepted_reason: LocalFilesystemDiscoveryReasonCode,
    ) -> MediaCandidateDiscoveryResult:
        if not stat.S_ISDIR(target_stat.st_mode):
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.TARGET_TYPE_MISMATCH,
                ),
                binding=binding,
            )
        names: list[str] = []
        try:
            with os.scandir(binding.configured_absolute_target_location) as directory_entries:
                for entry in directory_entries:
                    names.append(entry.name)
                    if len(names) > binding.maximum_directory_entries_examined:
                        break
        except FileNotFoundError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(accepted_reason, LocalFilesystemDiscoveryReasonCode.TARGET_MISSING),
                binding=binding,
            )
        except PermissionError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.TARGET_INACCESSIBLE,
                ),
                binding=binding,
            )
        except OSError:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.FAILED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.UNKNOWN_LOCAL_FILESYSTEM_FAILURE,
                ),
                binding=binding,
            )

        examined = len(names)
        if examined > binding.maximum_directory_entries_examined:
            return self._result(
                request,
                MediaCandidateDiscoveryOutcome.BLOCKED,
                reasons=(
                    accepted_reason,
                    LocalFilesystemDiscoveryReasonCode.DIRECTORY_ENTRY_LIMIT_EXCEEDED,
                ),
                limitations=(
                    LocalFilesystemDiscoveryLimitation.DIRECTORY_ENTRY_BOUND_PREVENTED_DISCOVERY,
                ),
                binding=binding,
                entries_examined=examined,
            )

        reasons: list[LocalFilesystemDiscoveryReasonCode] = [
            accepted_reason,
            LocalFilesystemDiscoveryReasonCode.SHALLOW_DIRECTORY_ENUMERATED,
        ]
        limitations: list[LocalFilesystemDiscoveryLimitation | str] = []
        entries: list[_EligibleEntry] = []
        material_partial = False
        unavailable = False
        failed_inspection = False
        for name in sorted(names, key=lambda value: (value.casefold(), value)):
            absolute_location = os.path.join(binding.configured_absolute_target_location, name)
            try:
                entry_stat = os.lstat(absolute_location)
            except FileNotFoundError:
                reasons.append(
                    LocalFilesystemDiscoveryReasonCode.ENTRY_DISAPPEARED_DURING_DISCOVERY
                )
                limitations.append(
                    LocalFilesystemDiscoveryLimitation.ENTRIES_BECAME_UNAVAILABLE
                )
                material_partial = True
                unavailable = True
                continue
            except (PermissionError, OSError):
                reasons.append(LocalFilesystemDiscoveryReasonCode.ENTRY_INSPECTION_FAILED)
                limitations.append(
                    LocalFilesystemDiscoveryLimitation.ENTRIES_COULD_NOT_BE_INSPECTED
                )
                material_partial = True
                failed_inspection = True
                continue
            if stat.S_ISLNK(entry_stat.st_mode):
                reasons.append(LocalFilesystemDiscoveryReasonCode.SYMLINK_ENTRY_SKIPPED)
                limitations.append(
                    LocalFilesystemDiscoveryLimitation.SYMLINK_ENTRIES_NOT_FOLLOWED
                )
                material_partial = True
                continue
            if stat.S_ISDIR(entry_stat.st_mode):
                reasons.append(LocalFilesystemDiscoveryReasonCode.NESTED_DIRECTORY_IGNORED)
                limitations.append(
                    LocalFilesystemDiscoveryLimitation.NESTED_DIRECTORIES_NOT_TRAVERSED
                )
                material_partial = True
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                reasons.append(LocalFilesystemDiscoveryReasonCode.SPECIAL_ENTRY_SKIPPED)
                material_partial = True
                continue
            eligible = self._eligible_entry(
                binding,
                absolute_location,
                name,
                entry_stat,
                reasons,
                limitations,
            )
            if eligible is not None:
                entries.append(eligible)

        entries.sort(key=lambda value: value.order_key)
        truncated = len(entries) > request.maximum_candidate_count
        selected = entries[: request.maximum_candidate_count]
        if truncated:
            reasons.append(LocalFilesystemDiscoveryReasonCode.CANDIDATE_RESULT_LIMIT_REACHED)
            limitations.append(
                LocalFilesystemDiscoveryLimitation.CANDIDATE_RESULT_BOUND_TRUNCATED_DISCOVERY
            )
            material_partial = True
        discovered = tuple(
            self._construct_discovered_candidate(request, binding, entry)
            for entry in selected
        )
        entry_limitations = tuple(
            limitation for entry in selected for limitation in entry.limitations
        )
        if discovered:
            reasons.append(
                LocalFilesystemDiscoveryReasonCode.PARTIAL_CANDIDATES_DISCOVERED
                if material_partial
                else LocalFilesystemDiscoveryReasonCode.CANDIDATES_DISCOVERED
            )
            outcome = (
                MediaCandidateDiscoveryOutcome.PARTIAL
                if material_partial
                else MediaCandidateDiscoveryOutcome.DISCOVERED
            )
        elif unavailable:
            outcome = MediaCandidateDiscoveryOutcome.BLOCKED
        elif failed_inspection:
            outcome = MediaCandidateDiscoveryOutcome.FAILED
        else:
            reasons.append(LocalFilesystemDiscoveryReasonCode.NO_ELIGIBLE_CANDIDATES)
            outcome = MediaCandidateDiscoveryOutcome.NO_CANDIDATES
        return self._result(
            request,
            outcome,
            reasons=reasons,
            limitations=(*limitations, *entry_limitations),
            binding=binding,
            discovered_candidates=discovered,
            entries_examined=examined,
        )

    def _eligible_entry(
        self,
        binding: LocalFilesystemTargetBinding,
        absolute_location: str,
        name: str,
        entry_stat: os.stat_result,
        reasons: list[LocalFilesystemDiscoveryReasonCode],
        limitations: list[LocalFilesystemDiscoveryLimitation | str],
    ) -> _EligibleEntry | None:
        policy = binding.eligibility_policy
        normalized_name = policy.normalized_filename(name)
        if (
            policy.hidden_entry_policy is LocalFilesystemHiddenEntryPolicy.EXCLUDE
            and name.startswith(".")
        ):
            reasons.append(LocalFilesystemDiscoveryReasonCode.HIDDEN_ENTRY_EXCLUDED)
            return None
        if any(normalized_name.endswith(suffix) for suffix in policy.excluded_suffixes):
            reasons.append(LocalFilesystemDiscoveryReasonCode.EXPLICIT_EXCLUSION_MATCHED)
            return None
        extension = policy.normalized_extension(name)
        if (
            not policy.permit_all_regular_files
            and extension not in policy.allowed_filename_extensions
        ):
            reasons.append(LocalFilesystemDiscoveryReasonCode.EXTENSION_NOT_ELIGIBLE)
            return None
        identity = _source_identity(absolute_location, entry_stat)
        entry_limitations: list[str] = []
        if identity.strength is LocalFilesystemIdentityStrength.STABLE_OBJECT_IDENTITY:
            reasons.append(
                LocalFilesystemDiscoveryReasonCode.STABLE_OBJECT_IDENTITY_AVAILABLE
            )
        elif identity.strength is LocalFilesystemIdentityStrength.LOCATION_SCOPED_IDENTITY:
            reasons.append(LocalFilesystemDiscoveryReasonCode.LOCATION_SCOPED_IDENTITY_USED)
            fallback = (
                LocalFilesystemDiscoveryLimitation.STABLE_FILESYSTEM_IDENTITY_UNAVAILABLE,
                LocalFilesystemDiscoveryLimitation.LOCATION_SCOPED_CANDIDATE_IDENTITY_USED,
            )
            limitations.extend(fallback)
            entry_limitations.extend(value.value for value in fallback)
        else:
            reasons.append(LocalFilesystemDiscoveryReasonCode.IDENTITY_UNAVAILABLE)
            return None
        media_hint = policy.extension_to_media_type_hints.get(extension)
        container_hint = policy.extension_to_container_hints.get(extension)
        mapped_asset_kind = policy.extension_to_asset_kind_hints.get(extension)
        if media_hint is not None:
            value = LocalFilesystemDiscoveryLimitation.MEDIA_TYPE_EXTENSION_DERIVED_ONLY
            limitations.append(value)
            entry_limitations.append(value.value)
        if container_hint is not None:
            value = LocalFilesystemDiscoveryLimitation.CONTAINER_TYPE_EXTENSION_DERIVED_ONLY
            limitations.append(value)
            entry_limitations.append(value.value)
        if mapped_asset_kind is not None and binding.explicit_asset_kind_hint is None:
            value = LocalFilesystemDiscoveryLimitation.ASSET_KIND_EXTENSION_DERIVED_ONLY
            limitations.append(value)
            entry_limitations.append(value.value)
        reasons.append(LocalFilesystemDiscoveryReasonCode.REGULAR_FILE_ELIGIBLE)
        return _EligibleEntry(
            name=name,
            absolute_location=absolute_location,
            identity=identity,
            media_type_hint=media_hint,
            container_type_hint=container_hint,
            asset_kind_hint=binding.explicit_asset_kind_hint or mapped_asset_kind,
            limitations=normalize_discovery_limitations(entry_limitations),
        )

    def _construct_discovered_candidate(
        self,
        request: MediaCandidateDiscoveryRequest,
        binding: LocalFilesystemTargetBinding,
        entry: _EligibleEntry,
    ) -> DiscoveredMediaCandidate:
        identity_seed = _identity_seed(binding, entry.identity)
        namespace = UUID(self.configuration.identity_namespace_id.value)
        resource_id = _derived_id(namespace, "resource", identity_seed)
        candidate_id = _derived_id(namespace, "candidate", identity_seed)
        proposed_asset_id = _derived_id(namespace, "proposed-asset", identity_seed)
        discovery_id = _derived_id(
            namespace,
            "discovery",
            identity_seed,
            request.discovery_request_id.value,
        )
        location_scheme = (
            CompletedMediaAssetLocationScheme.LOCAL_FILESYSTEM
            if binding.source_location_scheme is RuntimeSourceLocationScheme.LOCAL_FILE
            else CompletedMediaAssetLocationScheme.MOUNTED_VOLUME
        )
        source_location = CompletedMediaAssetSourceLocation(
            location_scheme=location_scheme,
            location_value=entry.absolute_location,
            volume_id=binding.source_volume_id,
            host_id=binding.source_host_id,
            metadata={
                "source_scheme": binding.source_location_scheme.value,
                "target_scope": binding.target_scope.value,
            },
        )
        resource = MediaAssetCandidateResource(
            id=resource_id,
            original_filename=entry.name,
            source_location=source_location,
            source_volume_id=binding.source_volume_id,
            source_host_id=binding.source_host_id,
            media_type_hint=entry.media_type_hint,
            container_type_hint=entry.container_type_hint,
            metadata={
                "identity_strength": entry.identity.strength.value,
                "hints_are_descriptive_only": True,
            },
        )
        candidate = MediaAssetCandidate(
            id=candidate_id,
            proposed_asset_id=proposed_asset_id,
            primary_resource=resource,
            source_runtime_id=binding.runtime_id,
            runtime_profile=_completed_asset_runtime_profile(self.runtime.profile),
            first_observed_at=request.requested_at,
            context=CompletedMediaAssetContext(
                stage_id=binding.configured_stage_id,
                recording_block_id=binding.configured_recording_block_id,
            ),
            intended_asset_kind=entry.asset_kind_hint,
            source_host_id=binding.source_host_id,
            recorder_application_id=binding.recorder_application_id,
            adapter_id=self.configuration.adapter_id,
            metadata={
                "collection_target_id": binding.collection_target_id.value,
                "discovery_only": True,
            },
        )
        source_limitations = normalize_discovery_limitations(
            (
                *self.configuration.limitations,
                *binding.limitations,
                *binding.eligibility_policy.limitations,
                *entry.limitations,
                *_BASE_LIMITATIONS,
            )
        )
        return DiscoveredMediaCandidate(
            discovery_id=discovery_id,
            discovery_request_id=request.discovery_request_id,
            cycle_id=request.collection_cycle_id,
            collection_plan_id=binding.collection_plan_id,
            collection_target_id=binding.collection_target_id,
            discovery_port_id=self.configuration.adapter_id,
            candidate=candidate,
            discovered_at=request.requested_at,
            source_limitations=source_limitations,
            metadata={
                "identity_strength": entry.identity.strength.value,
                "target_scope": binding.target_scope.value,
            },
        )

    def _result(
        self,
        request: MediaCandidateDiscoveryRequest,
        outcome: MediaCandidateDiscoveryOutcome,
        *,
        reasons: Sequence[LocalFilesystemDiscoveryReasonCode] = (),
        limitations: Sequence[LocalFilesystemDiscoveryLimitation | str] = (),
        binding: LocalFilesystemTargetBinding | None = None,
        discovered_candidates: Sequence[DiscoveredMediaCandidate] = (),
        entries_examined: int = 0,
    ) -> MediaCandidateDiscoveryResult:
        all_limitations: tuple[LocalFilesystemDiscoveryLimitation | str, ...] = (
            *self.configuration.limitations,
            *(binding.limitations if binding is not None else ()),
            *(
                binding.eligibility_policy.limitations
                if binding is not None
                else ()
            ),
            *limitations,
            *_BASE_LIMITATIONS,
        )
        return MediaCandidateDiscoveryResult(
            discovery_request_id=request.discovery_request_id,
            cycle_id=request.collection_cycle_id,
            port_id=self.configuration.adapter_id,
            outcome=outcome,
            discovered_candidates=tuple(discovered_candidates),
            reasons=normalize_discovery_reasons((*reasons, *_BASE_REASONS)),
            limitations=normalize_discovery_limitations(all_limitations),
            started_at=request.requested_at,
            completed_at=request.requested_at,
            metadata={
                "entries_examined": entries_examined,
                "candidates_returned": len(discovered_candidates),
                "target_scope": binding.target_scope.value if binding is not None else None,
                "request_anchored_timestamps": True,
            },
        )


def _validate_configuration_against_runtime(
    runtime: StageFlowRuntime,
    configuration: LocalFilesystemDiscoveryConfiguration,
) -> dict[str, LocalFilesystemTargetBinding]:
    if runtime.identity.runtime_id != configuration.runtime_id:
        raise ValueError("Discovery configuration Runtime ID must match the Runtime.")
    if runtime.configuration.id != configuration.configuration_id:
        raise ValueError("Discovery configuration ID must match the Runtime configuration.")
    if runtime.profile not in _SUPPORTED_PROFILES:
        raise ValueError("Runtime profile is not supported by ED-0053.")
    if runtime.identity.deployment_profile is not runtime.profile:
        raise ValueError("Runtime identity and aggregate profiles must match.")
    bindings: dict[str, LocalFilesystemTargetBinding] = {}
    for binding in configuration.target_bindings:
        if binding.runtime_id != configuration.runtime_id:
            raise ValueError("Target binding Runtime ID must match discovery configuration.")
        if binding.configuration_id != configuration.configuration_id:
            raise ValueError("Target binding configuration ID must match discovery configuration.")
        plan = next(
            (
                candidate
                for candidate in runtime.configuration.collection_plans
                if candidate.id == binding.collection_plan_id
            ),
            None,
        )
        if plan is None:
            raise ValueError("Target binding collection plan is not configured.")
        target = next(
            (
                candidate
                for candidate in plan.targets
                if candidate.id == binding.collection_target_id
            ),
            None,
        )
        if target is None:
            raise ValueError("Target binding collection target is not configured.")
        expected = (
            (target.runtime_id, binding.runtime_id, "Runtime ID"),
            (target.source_capability_id, binding.source_capability_id, "source capability ID"),
            (target.source_location_scheme, binding.source_location_scheme, "source scheme"),
            (
                target.opaque_location_reference,
                binding.configured_absolute_target_location,
                "source location",
            ),
            (target.source_host_id, binding.source_host_id, "source host ID"),
            (target.source_volume_id, binding.source_volume_id, "source volume ID"),
            (target.configured_stage_id, binding.configured_stage_id, "Stage ID"),
            (
                target.configured_recording_block_id,
                binding.configured_recording_block_id,
                "recording-block ID",
            ),
            (
                target.expected_recorder_application_id,
                binding.recorder_application_id,
                "recorder application ID",
            ),
            (
                target.candidate_asset_kind_hint,
                binding.explicit_asset_kind_hint,
                "asset-kind hint",
            ),
        )
        for target_value, binding_value, label in expected:
            if target_value != binding_value:
                raise ValueError(f"Target binding {label} must match the ED-0050 target.")
        source = next(
            (
                capability
                for capability in runtime.capability_set.source_capabilities
                if capability.id == binding.source_capability_id
            ),
            None,
        )
        if source is None or source.runtime_id != binding.runtime_id:
            raise ValueError("Target binding source capability is not supported.")
        if binding.source_location_scheme not in source.supported_location_schemes:
            raise ValueError("Target binding source scheme is not supported by its capability.")
        if source.access_mode is not RuntimeSourceAccessMode.READ_ONLY:
            raise ValueError("ED-0053 requires a read-only source capability.")
        if (
            source.supported_host_scope is RuntimeSourceHostScope.LOCAL_HOST
            and binding.source_host_id != runtime.host.host_id
        ):
            raise ValueError("Target binding host must be the configured local Runtime host.")
        if (
            source.supported_host_scope is RuntimeSourceHostScope.CONFIGURED_HOSTS
            and binding.source_host_id not in source.supported_host_ids
        ):
            raise ValueError("Target binding host is not supported by its capability.")
        if source.supported_host_scope is RuntimeSourceHostScope.UNKNOWN:
            raise ValueError("Target binding host scope must be explicit.")
        if (
            binding.source_volume_id is not None
            and source.supported_volume_ids
            and binding.source_volume_id not in source.supported_volume_ids
        ):
            raise ValueError("Target binding volume is not supported by its capability.")
        if (
            source.source_adapter_id is not None
            and source.source_adapter_id != configuration.adapter_id
        ):
            raise ValueError("Discovery adapter ID must match the source capability adapter.")
        discovery = next(
            (
                capability
                for capability in runtime.capability_set.capabilities
                if capability.id == binding.discovery_capability_id
            ),
            None,
        )
        if (
            discovery is None
            or discovery.runtime_id != binding.runtime_id
            or discovery.kind is not RuntimeCapabilityKind.CANDIDATE_DISCOVERY
            or discovery.support_status is not RuntimeCapabilitySupportStatus.SUPPORTED
        ):
            raise ValueError("Target binding discovery capability is not supported.")
        bindings[binding.collection_target_id.value] = binding
    return bindings


def _source_identity(
    absolute_location: str,
    entry_stat: os.stat_result,
) -> LocalFilesystemSourceIdentity:
    device = getattr(entry_stat, "st_dev", 0)
    inode = getattr(entry_stat, "st_ino", 0)
    if isinstance(device, int) and isinstance(inode, int) and device >= 0 and inode > 0:
        return LocalFilesystemSourceIdentity(
            strength=LocalFilesystemIdentityStrength.STABLE_OBJECT_IDENTITY,
            normalized_source_location=absolute_location,
            stable_object_token=f"device:{device}|object:{inode}",
        )
    return LocalFilesystemSourceIdentity(
        strength=LocalFilesystemIdentityStrength.LOCATION_SCOPED_IDENTITY,
        normalized_source_location=absolute_location,
    )


def _configured_path_has_symlinked_ancestor(absolute_location: str) -> bool:
    target = Path(absolute_location)
    for ancestor in reversed(target.parents):
        try:
            ancestor_stat = os.lstat(ancestor)
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(ancestor_stat.st_mode):
            return True
    return False


def _identity_seed(
    binding: LocalFilesystemTargetBinding,
    identity: LocalFilesystemSourceIdentity,
) -> str:
    return "|".join(
        (
            binding.runtime_id.value,
            binding.source_host_id.value,
            binding.source_volume_id.value if binding.source_volume_id is not None else "",
            binding.collection_target_id.value,
            identity.normalized_source_location,
            identity.stable_object_token or "location-scoped",
        )
    )


def _derived_id(namespace: UUID, *parts: str) -> EntityId:
    return EntityId(str(uuid5(namespace, "|".join(parts))))


def _completed_asset_runtime_profile(
    profile: RuntimeProfile,
) -> CompletedMediaAssetRuntimeProfile:
    if profile is RuntimeProfile.AGENT:
        return CompletedMediaAssetRuntimeProfile.AGENT
    if profile is RuntimeProfile.NODE:
        return CompletedMediaAssetRuntimeProfile.NODE
    if profile is RuntimeProfile.DEVELOPMENT:
        return CompletedMediaAssetRuntimeProfile.DEVELOPMENT
    return CompletedMediaAssetRuntimeProfile.UNKNOWN


__all__ = ["LocalFilesystemCandidateDiscoveryAdapter"]
