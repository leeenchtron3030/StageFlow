from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from uuid import UUID, uuid5

from app.contexts.production.asset_readiness import (
    AssetFinalizationObservation,
    AssetReadAccessObservation,
    AssetReadinessObservationBundle,
    AssetResourcePresenceObservation,
    AssetResourceSnapshot,
    AssetWriteStateObservation,
)
from app.contexts.production.runtime import (
    RuntimeCollectionPlan,
    RuntimeObservationCapability,
    RuntimeObservationType,
    RuntimeReadinessPolicySelection,
)
from app.shared.ids import EntityId

from .media_collection_contracts import (
    MediaCandidateConflict,
    MediaCandidateDiscoveryResult,
    MediaCandidateRecord,
    MediaCollectionCoordinatorSnapshot,
    MediaCollectionCycleRequest,
    MediaCollectionCycleResult,
    MediaObservationCollectionResult,
)
from .media_collection_lifecycle import MediaCollectionCycleReasonCode

_ID_NAMESPACE = UUID("62a92419-4fb3-5af8-aed5-ddc946e17a72")

OBSERVATION_ORDER = {
    RuntimeObservationType.RESOURCE_PRESENCE: 0,
    RuntimeObservationType.RESOURCE_SNAPSHOT: 1,
    RuntimeObservationType.FINALIZATION: 2,
    RuntimeObservationType.WRITE_STATE: 3,
    RuntimeObservationType.READ_ACCESS: 4,
}

OBSERVATION_CLASSES: Mapping[RuntimeObservationType, type[object]] = {
    RuntimeObservationType.RESOURCE_PRESENCE: AssetResourcePresenceObservation,
    RuntimeObservationType.RESOURCE_SNAPSHOT: AssetResourceSnapshot,
    RuntimeObservationType.FINALIZATION: AssetFinalizationObservation,
    RuntimeObservationType.WRITE_STATE: AssetWriteStateObservation,
    RuntimeObservationType.READ_ACCESS: AssetReadAccessObservation,
}


def immutable_mapping[T](value: Mapping[str, T]) -> Mapping[str, T]:
    return MappingProxyType(dict(value))


def derived_id(*parts: object) -> EntityId:
    return EntityId(str(uuid5(_ID_NAMESPACE, ":".join(str(part) for part in parts))))


@dataclass(frozen=True, slots=True)
class PlanContext:
    plan: RuntimeCollectionPlan
    selection: RuntimeReadinessPolicySelection
    discovery_capability_id: EntityId
    observation_capabilities: tuple[RuntimeObservationCapability, ...]
    required_observation_capability_ids: frozenset[EntityId]


@dataclass(frozen=True, slots=True)
class ActiveReservation:
    request: MediaCollectionCycleRequest
    fingerprint: str
    previous_snapshot: MediaCollectionCoordinatorSnapshot


@dataclass(frozen=True, slots=True)
class OperationRecord:
    fingerprint: str
    result: MediaCollectionCycleResult


@dataclass(frozen=True, slots=True)
class CoordinatorState:
    snapshot: MediaCollectionCoordinatorSnapshot
    candidate_records: Mapping[str, MediaCandidateRecord]
    proposed_asset_index: Mapping[str, str]
    resource_index: Mapping[str, str]
    observation_bundles: Mapping[str, AssetReadinessObservationBundle]
    conflicts: Mapping[str, MediaCandidateConflict]
    completed_cycle_results: Mapping[str, OperationRecord]
    operation_fingerprints: Mapping[str, str]
    cycle_history: tuple[MediaCollectionCycleResult, ...]
    active_cycle_reservation: ActiveReservation | None


@dataclass(slots=True)
class CandidateCycleFacts:
    attempted: int = 0
    valid_or_empty: int = 0
    retained: int = 0
    deferred: bool = False
    blocked: bool = False
    failed: bool = False


@dataclass(slots=True)
class CycleWork:
    records: dict[str, MediaCandidateRecord]
    proposed_index: dict[str, str]
    resource_index: dict[str, str]
    bundles: dict[str, AssetReadinessObservationBundle]
    conflicts: dict[str, MediaCandidateConflict]
    discovery_results: list[MediaCandidateDiscoveryResult]
    observation_results: list[MediaObservationCollectionResult]
    affected: set[EntityId]
    new: set[EntityId]
    known: set[EntityId]
    conflicted: set[EntityId]
    deferred: set[EntityId]
    reasons: list[MediaCollectionCycleReasonCode]
    candidate_facts: dict[str, CandidateCycleFacts]
    explicit_times: list[datetime]
    considered: int = 0
    observation_calls: int = 0
    retained_observations: int = 0
    candidate_budget_exhausted: bool = False
    observation_budget_exhausted: bool = False
    interrupted: bool = False
    partial: bool = False


__all__ = [
    "ActiveReservation",
    "CandidateCycleFacts",
    "CoordinatorState",
    "CycleWork",
    "OBSERVATION_CLASSES",
    "OBSERVATION_ORDER",
    "OperationRecord",
    "PlanContext",
    "derived_id",
    "immutable_mapping",
]
