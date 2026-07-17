from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .asset_readiness_validation import (
    freeze_readiness_metadata,
    require_aware,
    require_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AssetReadinessEvaluationRequest:
    evaluation_id: EntityId
    policy_id: EntityId
    policy_version: str
    candidate_id: EntityId
    resource_id: EntityId
    evaluated_at: datetime
    completion_declaration_id: EntityId
    readiness_declaration_id: EntityId
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.evaluated_at, "AssetReadinessEvaluationRequest.evaluated_at")
        object.__setattr__(
            self,
            "policy_version",
            require_non_empty(
                self.policy_version,
                "AssetReadinessEvaluationRequest.policy_version",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "AssetReadinessEvaluationRequest.metadata",
            ),
        )
