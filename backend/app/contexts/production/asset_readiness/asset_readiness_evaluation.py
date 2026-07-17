from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletion,
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetReadiness,
    CompletedMediaAssetReadinessStatus,
)
from app.shared.ids import EntityId

from .asset_readiness_outcome import AssetReadinessOutcome
from .asset_readiness_policy_parameters import AssetReadinessPolicyParameters
from .asset_readiness_reason import AssetReadinessReason, normalize_readiness_reasons
from .asset_readiness_validation import (
    freeze_readiness_metadata,
    normalize_entity_ids,
    normalize_limitations,
    require_aware,
    require_non_empty,
)
from .asset_stability_window import AssetStabilityWindow


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AssetReadinessEvaluation:
    evaluation_id: EntityId
    policy_id: EntityId
    policy_version: str
    candidate_id: EntityId
    proposed_asset_id: EntityId
    resource_id: EntityId
    outcome: AssetReadinessOutcome
    reasons: Sequence[AssetReadinessReason]
    evaluated_at: datetime
    policy_parameters: AssetReadinessPolicyParameters
    supporting_observation_ids: Sequence[EntityId] = field(default_factory=tuple)
    blocking_observation_ids: Sequence[EntityId] = field(default_factory=tuple)
    selected_completion_method: CompletedMediaAssetCompletionMethod | None = None
    stability_window: AssetStabilityWindow | None = None
    completion_declaration: CompletedMediaAssetCompletion | None = None
    readiness_declaration: CompletedMediaAssetReadiness | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        reasons = normalize_readiness_reasons(self.reasons)
        if not reasons:
            raise ValueError("Asset readiness evaluation requires at least one reason.")
        require_aware(self.evaluated_at, "AssetReadinessEvaluation.evaluated_at")
        version = require_non_empty(
            self.policy_version,
            "AssetReadinessEvaluation.policy_version",
        )
        if version != self.policy_parameters.policy_version:
            raise ValueError("Evaluation policy version must match policy parameters.")
        object.__setattr__(self, "policy_version", version)
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(
            self,
            "supporting_observation_ids",
            normalize_entity_ids(
                self.supporting_observation_ids,
                "AssetReadinessEvaluation.supporting_observation_ids",
            ),
        )
        object.__setattr__(
            self,
            "blocking_observation_ids",
            normalize_entity_ids(
                self.blocking_observation_ids,
                "AssetReadinessEvaluation.blocking_observation_ids",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AssetReadinessEvaluation.limitations",
            ),
        )
        self._validate_shape()
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(self.metadata, "AssetReadinessEvaluation.metadata"),
        )

    def _validate_shape(self) -> None:
        if self.stability_window is not None and (
            self.stability_window.candidate_id != self.candidate_id
            or self.stability_window.resource_id != self.resource_id
        ):
            raise ValueError("Evaluation stability window must match candidate and resource.")
        if self.outcome is AssetReadinessOutcome.SAFE_TO_READ:
            if self.completion_declaration is None or self.readiness_declaration is None:
                raise ValueError("Safe evaluation requires completion and readiness declarations.")
            if not self.completion_declaration.is_finalized:
                raise ValueError("Safe evaluation completion must be finalized.")
            if self.readiness_declaration.status is not (
                CompletedMediaAssetReadinessStatus.SAFE_TO_READ
            ):
                raise ValueError("Safe evaluation requires safe-to-read readiness.")
            if self.selected_completion_method is not self.completion_declaration.method:
                raise ValueError("Selected completion method must match its declaration.")
            if self.readiness_declaration.assessed_at != self.evaluated_at:
                raise ValueError("Readiness assessment time must equal evaluation time.")
            return
        if (
            self.readiness_declaration is not None
            and self.readiness_declaration.status
            is CompletedMediaAssetReadinessStatus.SAFE_TO_READ
        ):
            raise ValueError("Non-safe evaluation cannot contain safe readiness.")
        if self.completion_declaration is not None:
            raise ValueError("Non-safe evaluation does not publish completion declaration.")
        if self.selected_completion_method is not None:
            raise ValueError("Non-safe evaluation cannot select a completion method.")
