from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.operational_state.operational_state_basis import (
    OperationalStateBasis,
)
from app.contexts.production.operational_state.operational_state_family import (
    OperationalStateFamily,
)
from app.contexts.production.operational_state.operational_state_kind import (
    OperationalStateKind,
)
from app.contexts.production.operational_state.operational_state_status import (
    OperationalStateStatus,
)
from app.contexts.production.operational_state.operational_state_subject import (
    OperationalStateSubject,
    OperationalStateSubjectType,
)
from app.contexts.production.operational_state.operational_state_value import (
    OperationalStateValue,
)
from app.contexts.production.timeline import TimelineRange
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_DIRECTLY_OBSERVABLE_FORBIDDEN_KINDS = {
    OperationalStateKind.SESSION_STATE,
    OperationalStateKind.EDITORIAL_STATE,
    OperationalStateKind.PACKAGE_STATE,
}

_STAGEFLOW_READINESS_KINDS = {
    OperationalStateKind.OBSERVATION_READINESS,
    OperationalStateKind.REASONING_READINESS,
}


@dataclass(frozen=True, slots=True)
class OperationalState:
    """One descriptive StageFlow-relevant operational state."""

    id: EntityId
    family: OperationalStateFamily
    kind: OperationalStateKind
    subject: OperationalStateSubject
    value: OperationalStateValue
    status: OperationalStateStatus
    basis: OperationalStateBasis
    observed_or_derived_at: datetime
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    timeline_range: TimelineRange | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(
            self.observed_or_derived_at, "OperationalState.observed_or_derived_at"
        )
        self._validate_family_kind_boundary()
        if self.timeline_range is not None and self.recording_block_id is None:
            object.__setattr__(
                self,
                "recording_block_id",
                self.timeline_range.recording_block_id,
            )
        elif (
            self.timeline_range is not None
            and self.recording_block_id is not None
            and self.timeline_range.recording_block_id != self.recording_block_id
        ):
            raise ValueError("OperationalState timeline_range must match recording_block_id.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def _validate_family_kind_boundary(self) -> None:
        if (
            self.family is OperationalStateFamily.DIRECTLY_OBSERVABLE
            and self.kind in _DIRECTLY_OBSERVABLE_FORBIDDEN_KINDS
        ):
            raise ValueError(
                "Session, editorial, and package states must not be directly observable."
            )

        if (
            self.family is OperationalStateFamily.STAGEFLOW_READINESS
            and self.kind not in _STAGEFLOW_READINESS_KINDS
        ):
            raise ValueError("StageFlow readiness state must use a readiness kind.")

        if (
            self.family is OperationalStateFamily.STAGEFLOW_READINESS
            and self.subject.subject_type is OperationalStateSubjectType.EXTERNAL_ENVIRONMENT
        ):
            raise ValueError(
                "StageFlow readiness must not model human or external production readiness."
            )

        if (
            self.family is OperationalStateFamily.ENVIRONMENTAL_CONTEXT
            and self.kind is not OperationalStateKind.ENVIRONMENTAL_CONDITION
        ):
            raise ValueError("Environmental context must use environmental_condition kind.")

    @property
    def is_core_stageflow_state(self) -> bool:
        return self.family is not OperationalStateFamily.ENVIRONMENTAL_CONTEXT
