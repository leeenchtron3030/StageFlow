from __future__ import annotations

from abc import ABC, abstractmethod

from .asset_readiness_evaluation import AssetReadinessEvaluation
from .asset_readiness_evaluation_request import AssetReadinessEvaluationRequest
from .asset_readiness_observation_bundle import AssetReadinessObservationBundle
from .media_asset_candidate import MediaAssetCandidate


class AssetReadinessPolicy(ABC):
    """Pure policy boundary over caller-supplied immutable resource observations."""

    @abstractmethod
    def evaluate(
        self,
        candidate: MediaAssetCandidate,
        observations: AssetReadinessObservationBundle,
        request: AssetReadinessEvaluationRequest,
    ) -> AssetReadinessEvaluation:
        """Evaluate supplied facts without collecting, waiting, reading, or acting."""
