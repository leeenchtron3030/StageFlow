from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.completed_media_asset import CompletedMediaAssetKind
from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_enum_values,
    normalize_limitations,
    require_opaque_reference,
)
from .runtime_observation_capability import RuntimeObservationType
from .runtime_source_capability import RuntimeSourceLocationScheme


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeCollectionTarget:
    id: EntityId
    runtime_id: EntityId
    source_capability_id: EntityId
    source_location_scheme: RuntimeSourceLocationScheme
    opaque_location_reference: str
    source_host_id: EntityId
    enabled_observation_types: Sequence[RuntimeObservationType]
    source_volume_id: EntityId | None = None
    expected_recorder_application_id: EntityId | None = None
    configured_stage_id: EntityId | None = None
    configured_recording_block_id: EntityId | None = None
    candidate_asset_kind_hint: CompletedMediaAssetKind | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "opaque_location_reference",
            require_opaque_reference(
                self.opaque_location_reference,
                "RuntimeCollectionTarget.opaque_location_reference",
            ),
        )
        observation_types = normalize_enum_values(self.enabled_observation_types)
        if not observation_types:
            raise ValueError("Runtime collection target requires an observation type.")
        object.__setattr__(self, "enabled_observation_types", observation_types)
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeCollectionTarget.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeCollectionTarget.metadata"),
        )
