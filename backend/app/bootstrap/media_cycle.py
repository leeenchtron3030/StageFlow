from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

from app.contexts.production.asset_readiness import (
    AssetReadAccessObservation,
    AssetReadAccessStatus,
    AssetReadinessEvaluation,
    AssetReadinessEvaluationRequest,
    AssetReadinessObservationBundle,
    AssetReadinessOutcome,
    AssetResourcePresenceObservation,
    AssetResourcePresenceStatus,
    AssetResourceSnapshot,
    ConservativeAssetReadinessPolicy,
    MediaAssetCandidate,
)
from app.contexts.production.completed_media_asset import (
    CompletedMediaAsset,
    CompletedMediaAssetContext,
    CompletedMediaAssetKind,
    CompletedMediaAssetManifest,
    CompletedMediaAssetProvenance,
    CompletedMediaAssetResource,
    CompletedMediaAssetSource,
)
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import (
    MediaRegistrationState,
    ResourceObservation,
)
from app.contexts.production.event_mode_kernel.repository import (
    KernelStorageUnavailableError,
)
from app.contexts.production.local_filesystem_discovery import (
    LocalFilesystemCandidateDiscoveryAdapter,
    LocalFilesystemDiscoveryConfiguration,
    LocalFilesystemEligibilityPolicy,
    LocalFilesystemExtensionMatchingMode,
    LocalFilesystemHiddenEntryPolicy,
    LocalFilesystemSymlinkPolicy,
    LocalFilesystemTargetBinding,
    LocalFilesystemTargetScope,
)
from app.contexts.production.media_collection import (
    MediaCandidateDiscoveryOutcome,
    MediaCandidateDiscoveryRequest,
)
from app.contexts.production.runtime import (
    RuntimeCapabilityKind,
    RuntimeSourceLocationScheme,
    StageFlowRuntime,
)
from app.contexts.production.software_agent_runtime import AgentRuntimeExecutionPermission
from app.core.config.deployment import EffectiveKernelConfiguration
from app.shared.ids import EntityId


def _id(namespace: UUID, name: str) -> EntityId:
    return EntityId(str(uuid5(namespace, name)))


@dataclass(frozen=True, slots=True)
class MediaCycleCandidateResult:
    candidate_id: EntityId
    source_binding_key: str
    state: MediaRegistrationState
    outcome: str
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class MediaCycleResult:
    scope: str
    candidates_seen: int
    assets_registered: int
    source_failures: tuple[str, ...]
    candidate_results: tuple[MediaCycleCandidateResult, ...]


@dataclass(frozen=True, slots=True)
class _FileFacts:
    size_bytes: int
    modified_at: datetime
    created_at: datetime
    identity_token: str


class _CandidateInspectionError(OSError):
    """Privacy-safe typed failure raised by bounded candidate inspection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BoundedMediaCycle:
    """One bounded, synchronous pass through accepted durable media contracts."""

    def __init__(
        self,
        *,
        configuration: EffectiveKernelConfiguration,
        runtime: StageFlowRuntime,
        kernel: DurableEventModeKernel,
        source_availability: dict[str, bool],
    ) -> None:
        self.configuration = configuration
        self.runtime = runtime
        self.kernel = kernel
        self.source_availability = source_availability
        self._namespace = UUID(runtime.identity.runtime_id.value)
        self._plan = runtime.configuration.collection_plans[0]
        self._selection = runtime.configuration.readiness_policy_selections[0]
        adapter_id = runtime.capability_set.source_capabilities[0].source_adapter_id
        if adapter_id is None:
            raise ValueError("runtime_source_adapter_identity_missing")
        self._adapter_id = adapter_id
        self._discovery_capability_id = next(
            capability.id
            for capability in runtime.capability_set.capabilities
            if capability.kind is RuntimeCapabilityKind.CANDIDATE_DISCOVERY
        )
        self._source_by_key = {
            source.key: source
            for stage in configuration.deployment.event.stages
            for source in stage.sources
        }
        self._target_by_key = {
            str(target.metadata["source_binding_key"]): target
            for target in self._plan.targets
        }
        self._source_key_by_target = {
            target.id: key for key, target in self._target_by_key.items()
        }
        self._discovery = LocalFilesystemCandidateDiscoveryAdapter(
            runtime,
            self._discovery_configuration(),
        )
        self._policy = ConservativeAssetReadinessPolicy(
            policy_id=self._selection.policy_id,
            parameters=self._selection.policy_parameters,
        )

    def _discovery_configuration(self) -> LocalFilesystemDiscoveryConfiguration:
        bindings: list[LocalFilesystemTargetBinding] = []
        for key, target in self._target_by_key.items():
            source = self._source_by_key[key]
            eligibility = LocalFilesystemEligibilityPolicy(
                allowed_filename_extensions=source.allowed_extensions,
                extension_matching_mode=(
                    LocalFilesystemExtensionMatchingMode.CASE_INSENSITIVE
                ),
                hidden_entry_policy=LocalFilesystemHiddenEntryPolicy.EXCLUDE,
                regular_file_required=True,
                symlink_policy=LocalFilesystemSymlinkPolicy.REJECT_OR_SKIP,
                permit_all_regular_files=False,
                excluded_suffixes=(".partial", ".tmp"),
                extension_to_media_type_hints={
                    ".mov": "video/quicktime",
                    ".mp4": "video/mp4",
                    ".mkv": "video/x-matroska",
                    ".mxf": "application/mxf",
                    ".wav": "audio/wav",
                },
                extension_to_container_hints={
                    ".mov": "quicktime",
                    ".mp4": "mp4",
                    ".mkv": "matroska",
                    ".mxf": "mxf",
                    ".wav": "wav",
                },
                extension_to_asset_kind_hints={
                    extension: CompletedMediaAssetKind.RECORDING_SEGMENT
                    for extension in source.allowed_extensions
                },
            )
            bindings.append(
                LocalFilesystemTargetBinding(
                    binding_id=_id(self._namespace, f"discovery-binding:{key}"),
                    runtime_id=self.runtime.identity.runtime_id,
                    configuration_id=self.runtime.configuration.id,
                    collection_plan_id=self._plan.id,
                    collection_target_id=target.id,
                    source_capability_id=target.source_capability_id,
                    discovery_capability_id=self._discovery_capability_id,
                    source_location_scheme=target.source_location_scheme,
                    configured_absolute_target_location=target.opaque_location_reference,
                    target_scope=LocalFilesystemTargetScope.SHALLOW_DIRECTORY,
                    maximum_directory_entries_examined=source.maximum_candidates,
                    eligibility_policy=eligibility,
                    source_host_id=target.source_host_id,
                    source_volume_id=target.source_volume_id,
                    configured_stage_id=target.configured_stage_id,
                    recorder_application_id=target.expected_recorder_application_id,
                    explicit_asset_kind_hint=target.candidate_asset_kind_hint,
                    metadata={"source_binding_key": key},
                )
            )
        return LocalFilesystemDiscoveryConfiguration(
            adapter_id=self._adapter_id,
            adapter_version="1.0.0",
            runtime_id=self.runtime.identity.runtime_id,
            configuration_id=self.runtime.configuration.id,
            supported_source_schemes=(RuntimeSourceLocationScheme.LOCAL_FILE,),
            target_bindings=tuple(bindings),
            identity_namespace_id=_id(self._namespace, "discovery-identity"),
            configured_at=self.runtime.configuration.configured_at,
        )

    def run(self, *, event_id: EntityId, scope: str) -> MediaCycleResult:
        reconciliation = self.kernel.begin_reconciliation(event_id=event_id, scope=scope)
        candidate_results: list[MediaCycleCandidateResult] = []
        source_failures: list[str] = []
        assets_registered = 0
        candidates_seen = 0
        cycle_id = EntityId.new()
        for key, target in sorted(self._target_by_key.items()):
            source = self._source_by_key[key]
            now = self.kernel.clock.now()
            request = MediaCandidateDiscoveryRequest(
                discovery_request_id=EntityId.new(),
                collection_cycle_id=cycle_id,
                runtime_id=self.runtime.identity.runtime_id,
                configuration_id=self.runtime.configuration.id,
                collection_plan_id=self._plan.id,
                collection_target_id=target.id,
                source_capability_id=target.source_capability_id,
                discovery_capability_id=self._discovery_capability_id,
                maximum_candidate_count=source.maximum_candidates,
                requested_at=now,
                execution_permission=AgentRuntimeExecutionPermission.NORMAL,
                event_mode_id=self._plan.event_mode_id,
                resource_policy_id=self._plan.resource_policy_id,
                target_reference=target.opaque_location_reference,
            )
            result = self._discovery.discover(request)
            available = result.outcome in {
                MediaCandidateDiscoveryOutcome.DISCOVERED,
                MediaCandidateDiscoveryOutcome.NO_CANDIDATES,
                MediaCandidateDiscoveryOutcome.PARTIAL,
            }
            self.source_availability[key] = available
            if not available:
                source_failures.append(f"{key}:{result.outcome.value}")
                continue
            retained = self.kernel.retain_discovery_results(
                results=(result,),
                source_bindings_by_target_id=self._source_key_by_target,
            )
            retained_by_id = {candidate.id: candidate for candidate in retained}
            candidates_seen += len(result.discovered_candidates)
            for discovered in result.discovered_candidates:
                durable = retained_by_id[discovered.candidate.id]
                try:
                    outcome = self._process_candidate(
                        discovered.candidate,
                        source_binding_key=key,
                        root=Path(source.path),
                    )
                    if outcome.outcome == "registered":
                        assets_registered += 1
                    candidate_results.append(outcome)
                except KernelStorageUnavailableError:
                    raise
                except (OSError, ValueError, RuntimeError) as exc:
                    cycle_failure_code = (
                        exc.code
                        if isinstance(exc, _CandidateInspectionError)
                        else type(exc).__name__
                    )
                    failure_at = self.kernel.clock.now()
                    self.kernel.record_resource_observation(
                        candidate_id=durable.id,
                        observation_kind="candidate_inspection_failure",
                        observed_at=failure_at,
                        facts={"failure_code": str(exc) or type(exc).__name__},
                    )
                    current = self.kernel.repository.get_candidate(durable.id)
                    assert current is not None
                    candidate_results.append(
                        MediaCycleCandidateResult(
                            candidate_id=durable.id,
                            source_binding_key=key,
                            state=current.state,
                            outcome="failed",
                            failure_code=cycle_failure_code,
                        )
                    )
        self.kernel.finish_reconciliation(
            reconciliation,
            candidates_seen=candidates_seen,
            assets_registered=assets_registered,
            failure_code=("source_discovery_failed" if source_failures else None),
        )
        return MediaCycleResult(
            scope=scope,
            candidates_seen=candidates_seen,
            assets_registered=assets_registered,
            source_failures=tuple(source_failures),
            candidate_results=tuple(candidate_results),
        )

    def _process_candidate(
        self,
        candidate: MediaAssetCandidate,
        *,
        source_binding_key: str,
        root: Path,
    ) -> MediaCycleCandidateResult:
        durable = self.kernel.repository.get_candidate(candidate.id)
        assert durable is not None
        if durable.state is MediaRegistrationState.REGISTERED:
            existing_asset = self.kernel.repository.get_asset(candidate.proposed_asset_id)
            if existing_asset is None:
                raise RuntimeError("registered_candidate_asset_missing")
            self.kernel.register_completed_asset(existing_asset)
            return MediaCycleCandidateResult(
                candidate.id,
                source_binding_key,
                durable.state,
                "registered_effects_reconciled",
            )
        observed_at = self.kernel.clock.now()
        facts = self._inspect_file(
            Path(candidate.primary_resource.source_location.location_value), root=root
        )
        self._record_snapshot(candidate, observed_at, facts)
        observations = self.kernel.repository.list_observations(candidate.id)
        bundle = self._bundle(candidate, observed_at, observations)
        request = AssetReadinessEvaluationRequest(
            evaluation_id=EntityId.new(),
            policy_id=self._selection.policy_id,
            policy_version=self._selection.policy_version,
            candidate_id=candidate.id,
            resource_id=candidate.primary_resource.id,
            evaluated_at=observed_at,
            completion_declaration_id=EntityId.new(),
            readiness_declaration_id=EntityId.new(),
            request_id=EntityId.new(),
        )
        evaluation = self._policy.evaluate(candidate, bundle, request)
        self.kernel.record_readiness_evaluation(evaluation)
        if evaluation.outcome is not AssetReadinessOutcome.SAFE_TO_READ:
            return MediaCycleCandidateResult(
                candidate.id,
                source_binding_key,
                MediaRegistrationState.STABILIZING,
                evaluation.outcome.value,
            )
        completed = self._assemble(candidate, evaluation, facts)
        self.kernel.register_completed_media_asset(
            completed,
            candidate_id=candidate.id,
            source_binding_key=source_binding_key,
        )
        return MediaCycleCandidateResult(
            candidate.id,
            source_binding_key,
            MediaRegistrationState.REGISTERED,
            "registered",
        )

    def _inspect_file(self, path: Path, *, root: Path) -> _FileFacts:
        root_resolved = root.resolve(strict=True)
        pre = path.lstat()
        if stat.S_ISLNK(pre.st_mode) or not stat.S_ISREG(pre.st_mode):
            raise _CandidateInspectionError("candidate_not_regular_file")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root_resolved):
            raise _CandidateInspectionError("candidate_outside_configured_source")
        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        descriptor = os.open(resolved, flags)
        try:
            opened = os.fstat(descriptor)
            os.read(descriptor, 1)
        finally:
            os.close(descriptor)
        post = path.lstat()
        if _stat_identity(pre) != _stat_identity(opened) or _stat_identity(
            opened
        ) != _stat_identity(post):
            raise _CandidateInspectionError("candidate_replaced_during_observation")
        return _FileFacts(
            size_bytes=opened.st_size,
            modified_at=datetime.fromtimestamp(opened.st_mtime_ns / 1_000_000_000, UTC),
            created_at=datetime.fromtimestamp(opened.st_ctime_ns / 1_000_000_000, UTC),
            identity_token=f"{opened.st_dev}:{opened.st_ino}",
        )

    def _record_snapshot(
        self,
        candidate: MediaAssetCandidate,
        observed_at: datetime,
        facts: _FileFacts,
    ) -> None:
        common = {
            "resource_id": candidate.primary_resource.id.value,
            "observer_id": self._adapter_id.value,
            "source_runtime_id": self.runtime.identity.runtime_id.value,
        }
        self.kernel.record_resource_observation(
            candidate_id=candidate.id,
            observation_kind="asset_resource_snapshot",
            observed_at=observed_at,
            facts={
                **common,
                "size_bytes": facts.size_bytes,
                "filesystem_modified_at": facts.modified_at.isoformat(),
                "stable_resource_identity_token": facts.identity_token,
            },
        )
        self.kernel.record_resource_observation(
            candidate_id=candidate.id,
            observation_kind="asset_resource_presence",
            observed_at=observed_at,
            facts={
                **common,
                "status": AssetResourcePresenceStatus.PRESENT.value,
                "observed_resource_identity_token": facts.identity_token,
            },
        )
        self.kernel.record_resource_observation(
            candidate_id=candidate.id,
            observation_kind="asset_read_access",
            observed_at=observed_at,
            facts={
                **common,
                "status": AssetReadAccessStatus.READABLE.value,
                "assessment_method_id": "bounded-open-read",
                "access_scope": "one_byte",
            },
        )

    def _bundle(
        self,
        candidate: MediaAssetCandidate,
        created_at: datetime,
        observations: tuple[ResourceObservation, ...],
    ) -> AssetReadinessObservationBundle:
        resource_id = candidate.primary_resource.id
        snapshots: list[AssetResourceSnapshot] = []
        access: list[AssetReadAccessObservation] = []
        presence: list[AssetResourcePresenceObservation] = []
        for observation in observations:
            facts = observation.facts
            if facts.get("resource_id") != resource_id.value:
                continue
            observer_id = EntityId(str(facts["observer_id"]))
            runtime_id = EntityId(str(facts["source_runtime_id"]))
            if observation.observation_kind == "asset_resource_snapshot":
                snapshots.append(
                    AssetResourceSnapshot(
                        id=observation.id,
                        candidate_id=candidate.id,
                        resource_id=resource_id,
                        observed_at=observation.observed_at,
                        size_bytes=int(str(facts["size_bytes"])),
                        observer_id=observer_id,
                        filesystem_modified_at=datetime.fromisoformat(
                            str(facts["filesystem_modified_at"])
                        ),
                        stable_resource_identity_token=str(
                            facts["stable_resource_identity_token"]
                        ),
                        source_volume_id=candidate.primary_resource.source_volume_id,
                        source_host_id=candidate.source_host_id,
                        source_runtime_id=runtime_id,
                    )
                )
            elif observation.observation_kind == "asset_read_access":
                access.append(
                    AssetReadAccessObservation(
                        id=observation.id,
                        candidate_id=candidate.id,
                        resource_id=resource_id,
                        observed_at=observation.observed_at,
                        status=AssetReadAccessStatus(str(facts["status"])),
                        assessment_method_id=str(facts["assessment_method_id"]),
                        access_scope=str(facts["access_scope"]),
                        observer_id=observer_id,
                        source_runtime_id=runtime_id,
                    )
                )
            elif observation.observation_kind == "asset_resource_presence":
                presence.append(
                    AssetResourcePresenceObservation(
                        id=observation.id,
                        candidate_id=candidate.id,
                        resource_id=resource_id,
                        observed_at=observation.observed_at,
                        status=AssetResourcePresenceStatus(str(facts["status"])),
                        observer_id=observer_id,
                        source_runtime_id=runtime_id,
                        observed_resource_identity_token=str(
                            facts["observed_resource_identity_token"]
                        ),
                    )
                )
        ordered_snapshots = sorted(
            snapshots, key=lambda value: (value.observed_at, value.id.value)
        )
        current_run: list[AssetResourceSnapshot] = []
        for snapshot in reversed(ordered_snapshots):
            if current_run and not _snapshots_match(snapshot, current_run[-1]):
                break
            current_run.append(snapshot)
        current_run.reverse()
        return AssetReadinessObservationBundle(
            id=EntityId.new(),
            candidate_id=candidate.id,
            resource_id=resource_id,
            created_at=created_at,
            resource_snapshots=current_run,
            read_access_observations=access,
            presence_observations=presence,
        )

    def _assemble(
        self,
        candidate: MediaAssetCandidate,
        evaluation: AssetReadinessEvaluation,
        facts: _FileFacts,
    ) -> CompletedMediaAsset:
        completion = evaluation.completion_declaration
        readiness = evaluation.readiness_declaration
        assert completion is not None and readiness is not None
        manifested_at = evaluation.evaluated_at
        manifest_id = EntityId.new()
        resource = CompletedMediaAssetResource(
            id=candidate.primary_resource.id,
            original_filename=candidate.primary_resource.original_filename,
            source_location=candidate.primary_resource.source_location,
            file_size_bytes=facts.size_bytes,
            media_type=candidate.primary_resource.media_type_hint,
            container_type=candidate.primary_resource.container_type_hint,
            filesystem_created_at=facts.created_at,
            filesystem_modified_at=facts.modified_at,
        )
        manifest = CompletedMediaAssetManifest(
            id=manifest_id,
            schema_name="stageflow.completed_media_asset",
            schema_version="1.0",
            asset_id=candidate.proposed_asset_id,
            created_at=manifested_at,
            producer_runtime_id=candidate.source_runtime_id,
            source_resource_id=resource.id,
        )
        source = CompletedMediaAssetSource(
            runtime_id=candidate.source_runtime_id,
            runtime_profile=candidate.runtime_profile,
            host_id=candidate.source_host_id,
            recorder_application_id=candidate.recorder_application_id,
            adapter_id=candidate.adapter_id,
        )
        provenance = CompletedMediaAssetProvenance(
            source_runtime_id=candidate.source_runtime_id,
            finalized_at=completion.finalized_at,
            readiness_declaration_id=readiness.id,
            manifest_id=manifest.id,
            source_host_id=candidate.source_host_id,
            recorder_application_id=candidate.recorder_application_id,
            adapter_id=candidate.adapter_id,
        )
        return CompletedMediaAsset(
            id=candidate.proposed_asset_id,
            kind=candidate.intended_asset_kind or CompletedMediaAssetKind.RECORDING_SEGMENT,
            manifest=manifest,
            primary_resource=resource,
            source=source,
            provenance=provenance,
            context=CompletedMediaAssetContext(stage_id=candidate.context.stage_id),
            completion=completion,
            readiness=readiness,
            finalized_at=completion.finalized_at,
            manifested_at=manifested_at,
        )


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _snapshots_match(
    first: AssetResourceSnapshot, second: AssetResourceSnapshot
) -> bool:
    return (
        first.size_bytes == second.size_bytes
        and first.filesystem_modified_at == second.filesystem_modified_at
        and first.stable_resource_identity_token
        == second.stable_resource_identity_token
    )


__all__ = ["BoundedMediaCycle", "MediaCycleCandidateResult", "MediaCycleResult"]
