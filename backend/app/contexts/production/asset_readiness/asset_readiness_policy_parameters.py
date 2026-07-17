from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
)

from .asset_readiness_validation import (
    freeze_readiness_metadata,
    require_non_empty,
)

_APPROVED_STRONG_METHODS = frozenset(
    {
        CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
        CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION,
        CompletedMediaAssetCompletionMethod.ATOMIC_RENAME_OBSERVED,
        CompletedMediaAssetCompletionMethod.SIDECAR_COMPLETION_MARKER,
    }
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AssetReadinessPolicyParameters:
    minimum_stable_interval: timedelta
    require_read_access_for_stability: bool
    require_post_finalization_presence: bool
    accepted_strong_finalization_methods: Sequence[CompletedMediaAssetCompletionMethod]
    require_inactive_write_when_available: bool
    policy_version: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.minimum_stable_interval <= timedelta(0):
            raise ValueError("Minimum stable interval must be positive.")
        methods = tuple(
            sorted(set(self.accepted_strong_finalization_methods), key=lambda method: method.value)
        )
        if not methods:
            raise ValueError("At least one strong finalization method must be accepted.")
        if not set(methods) <= _APPROVED_STRONG_METHODS:
            raise ValueError("Strong finalization methods must use approved strong methods.")
        object.__setattr__(self, "accepted_strong_finalization_methods", methods)
        object.__setattr__(
            self,
            "policy_version",
            require_non_empty(
                self.policy_version,
                "AssetReadinessPolicyParameters.policy_version",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "AssetReadinessPolicyParameters.metadata",
            ),
        )
