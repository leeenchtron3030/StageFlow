from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetRuntimeProfile,
)
from app.shared.ids import EntityId

from .asset_readiness_evaluation import AssetReadinessEvaluation
from .asset_readiness_outcome import AssetReadinessOutcome
from .asset_readiness_reason import BLOCKING_REASON_CODES, SUPPORTING_REASON_CODES
from .asset_readiness_validation import normalize_strings, require_aware
from .media_asset_candidate import MediaAssetCandidate


@dataclass(frozen=True, slots=True)
class AssetReadinessSummary:
    candidate_id: EntityId
    resource_id: EntityId
    outcome: AssetReadinessOutcome
    selected_completion_method: CompletedMediaAssetCompletionMethod | None
    stable_interval: timedelta | None
    primary_supporting_reasons: tuple[str, ...]
    primary_blocking_reasons: tuple[str, ...]
    evaluated_at: datetime
    source_runtime_id: EntityId
    runtime_profile: CompletedMediaAssetRuntimeProfile
    limitation_count: int
    warning_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        require_aware(self.evaluated_at, "AssetReadinessSummary.evaluated_at")
        if self.stable_interval is not None and self.stable_interval <= timedelta(0):
            raise ValueError("Summary stable interval must be positive when present.")
        if self.limitation_count < 0:
            raise ValueError("Summary limitation count must not be negative.")
        object.__setattr__(
            self,
            "primary_supporting_reasons",
            normalize_strings(
                self.primary_supporting_reasons,
                "AssetReadinessSummary.primary_supporting_reasons",
            ),
        )
        object.__setattr__(
            self,
            "primary_blocking_reasons",
            normalize_strings(
                self.primary_blocking_reasons,
                "AssetReadinessSummary.primary_blocking_reasons",
            ),
        )
        object.__setattr__(
            self,
            "warning_codes",
            normalize_strings(
                self.warning_codes,
                "AssetReadinessSummary.warning_codes",
            ),
        )

    @classmethod
    def from_evaluation(
        cls,
        evaluation: AssetReadinessEvaluation,
        candidate: MediaAssetCandidate,
    ) -> AssetReadinessSummary:
        if (
            evaluation.candidate_id != candidate.id
            or evaluation.resource_id != candidate.primary_resource.id
        ):
            raise ValueError("Summary candidate and resource must match the evaluation.")
        supporting = tuple(
            reason.code.value
            for reason in evaluation.reasons
            if reason.code in SUPPORTING_REASON_CODES
        )
        blocking = tuple(
            reason.code.value
            for reason in evaluation.reasons
            if reason.code in BLOCKING_REASON_CODES
        )
        warnings: set[str] = set()
        if evaluation.limitations:
            warnings.add("limitations_present")
        if evaluation.outcome is AssetReadinessOutcome.UNSUPPORTED_SOURCE:
            warnings.add("source_capability_unsupported")
        if evaluation.outcome is AssetReadinessOutcome.CONFLICTING_OBSERVATION:
            warnings.add("observation_conflict")
        return cls(
            candidate_id=candidate.id,
            resource_id=candidate.primary_resource.id,
            outcome=evaluation.outcome,
            selected_completion_method=evaluation.selected_completion_method,
            stable_interval=(
                evaluation.stability_window.elapsed
                if evaluation.stability_window is not None
                else None
            ),
            primary_supporting_reasons=supporting,
            primary_blocking_reasons=blocking,
            evaluated_at=evaluation.evaluated_at,
            source_runtime_id=candidate.source_runtime_id,
            runtime_profile=candidate.runtime_profile,
            limitation_count=len(evaluation.limitations),
            warning_codes=tuple(sorted(warnings)),
        )
