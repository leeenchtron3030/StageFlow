from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.contexts.production.completed_media_asset import CompletedMediaAssetKind
from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_enum_values,
    normalize_limitations,
    require_non_empty,
)


class RuntimeContextSource(StrEnum):
    EXPLICIT_RUNTIME_CONFIGURATION = "explicit_runtime_configuration"
    RECORDER_STRUCTURED_METADATA = "recorder_structured_metadata"
    EXTERNAL_ADAPTER_CONTEXT = "external_adapter_context"
    MANUAL_OPERATOR_ASSIGNMENT = "manual_operator_assignment"
    FILENAME_HINT_ONLY = "filename_hint_only"
    PATH_HINT_ONLY = "path_hint_only"
    UNKNOWN = "unknown"


class RuntimeTechnicalDescriptionSource(StrEnum):
    RECORDER_STRUCTURED_METADATA = "recorder_structured_metadata"
    SUPPLIED_MEDIA_HEADER_FACTS = "supplied_media_header_facts"
    EXTERNAL_ADAPTER_DECLARATION = "external_adapter_declaration"
    NONE = "none"
    UNKNOWN = "unknown"


class RuntimeIntegritySource(StrEnum):
    SUPPLIED_CHECKSUM = "supplied_checksum"
    EXTERNAL_INTEGRITY_DECLARATION = "external_integrity_declaration"
    NONE = "none"
    UNKNOWN = "unknown"


class RuntimeSourceLocationHandlingPolicy(StrEnum):
    READ_ONLY_REFERENCE = "read_only_reference"
    OPAQUE_REFERENCE_ONLY = "opaque_reference_only"
    REDACT_OUTSIDE_RUNTIME = "redact_outside_runtime"
    UNKNOWN = "unknown"


class RuntimeSummaryPrivacyPolicy(StrEnum):
    OMIT_FULL_SOURCE_PATHS = "omit_full_source_paths"
    IDENTIFIERS_ONLY = "identifiers_only"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeAssetAssemblyPlan:
    id: EntityId
    runtime_id: EntityId
    manifest_schema_name: str
    manifest_schema_version: str
    supported_asset_kinds: Sequence[CompletedMediaAssetKind]
    context_sources: Sequence[RuntimeContextSource]
    technical_description_sources: Sequence[RuntimeTechnicalDescriptionSource]
    integrity_sources: Sequence[RuntimeIntegritySource]
    source_location_handling_policy: RuntimeSourceLocationHandlingPolicy
    summary_privacy_policy: RuntimeSummaryPrivacyPolicy
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "manifest_schema_name",
            require_non_empty(
                self.manifest_schema_name,
                "RuntimeAssetAssemblyPlan.manifest_schema_name",
            ),
        )
        object.__setattr__(
            self,
            "manifest_schema_version",
            require_non_empty(
                self.manifest_schema_version,
                "RuntimeAssetAssemblyPlan.manifest_schema_version",
            ),
        )
        kinds = normalize_enum_values(self.supported_asset_kinds)
        if not kinds:
            raise ValueError("Runtime asset assembly plan requires an asset kind.")
        object.__setattr__(self, "supported_asset_kinds", kinds)
        for field_name in (
            "context_sources",
            "technical_description_sources",
            "integrity_sources",
        ):
            object.__setattr__(
                self,
                field_name,
                normalize_enum_values(getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeAssetAssemblyPlan.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeAssetAssemblyPlan.metadata"),
        )
