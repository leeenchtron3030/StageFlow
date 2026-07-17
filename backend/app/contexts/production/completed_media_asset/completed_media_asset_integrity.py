from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    require_aware,
    require_optional_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class CompletedMediaAssetIntegrityStatus(StrEnum):
    CONFIRMED = "confirmed"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetIntegrity:
    """Optional declared integrity facts; no checksum or probe work is performed."""

    id: EntityId
    status: CompletedMediaAssetIntegrityStatus
    assessed_at: datetime
    assessor_id: EntityId
    checksum_algorithm: str | None = None
    checksum_value: str | None = None
    checksum_byte_size: int | None = None
    container_probe_status: CompletedMediaAssetIntegrityStatus = (
        CompletedMediaAssetIntegrityStatus.NOT_ASSESSED
    )
    media_readability_status: CompletedMediaAssetIntegrityStatus = (
        CompletedMediaAssetIntegrityStatus.NOT_ASSESSED
    )
    source_consistency_status: CompletedMediaAssetIntegrityStatus = (
        CompletedMediaAssetIntegrityStatus.NOT_ASSESSED
    )
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(
            self.assessed_at,
            "CompletedMediaAssetIntegrity.assessed_at",
        )
        algorithm = require_optional_non_empty(
            self.checksum_algorithm,
            "CompletedMediaAssetIntegrity.checksum_algorithm",
        )
        checksum = require_optional_non_empty(
            self.checksum_value,
            "CompletedMediaAssetIntegrity.checksum_value",
        )
        checksum_fields = (algorithm, checksum, self.checksum_byte_size)
        if any(value is not None for value in checksum_fields) and any(
            value is None for value in checksum_fields
        ):
            raise ValueError(
                "Checksum algorithm, value, and byte size must be supplied together."
            )
        if self.checksum_byte_size is not None and self.checksum_byte_size < 0:
            raise ValueError("Checksum byte size must not be negative.")
        object.__setattr__(self, "checksum_algorithm", algorithm)
        object.__setattr__(self, "checksum_value", checksum)
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetIntegrity.metadata"),
        )
