from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    require_non_empty,
    require_optional_aware,
    require_optional_non_empty,
)

_SEMANTIC_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeVersion:
    product_name: str
    semantic_version: str
    contract_compatibility_version: str
    configuration_schema_version: str
    capability_schema_version: str
    build_identifier: str | None = None
    build_timestamp: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "product_name",
            require_non_empty(self.product_name, "RuntimeVersion.product_name"),
        )
        semantic_version = require_non_empty(
            self.semantic_version,
            "RuntimeVersion.semantic_version",
        )
        if _SEMANTIC_VERSION.fullmatch(semantic_version) is None:
            raise ValueError("RuntimeVersion.semantic_version must use semantic versioning.")
        object.__setattr__(self, "semantic_version", semantic_version)
        for field_name in (
            "contract_compatibility_version",
            "configuration_schema_version",
            "capability_schema_version",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty(
                    getattr(self, field_name),
                    f"RuntimeVersion.{field_name}",
                ),
            )
        object.__setattr__(
            self,
            "build_identifier",
            require_optional_non_empty(
                self.build_identifier,
                "RuntimeVersion.build_identifier",
            ),
        )
        require_optional_aware(self.build_timestamp, "RuntimeVersion.build_timestamp")
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeVersion.metadata"),
        )
