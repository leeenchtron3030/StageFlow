from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceRole,
    EvidenceSignal,
    EvidenceStrength,
)

from .session_boundary_evidence_result import SessionBoundaryEvidenceResult


def _empty_role_distribution() -> Mapping[EvidenceRole, int]:
    return {}


def _empty_strength_distribution() -> Mapping[EvidenceStrength, int]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionBoundaryEvidenceSummary:
    """Non-evaluative diagnostics for one possible-boundary build."""

    total_input_evidence_set_count: int
    consumed_count: int
    ignored_count: int
    unsupported_count: int
    duplicate_count: int
    possible_start_evidence_set_count: int
    possible_end_evidence_set_count: int
    produced_evidence_item_count: int
    contributing_signal_count: int
    contributing_signals: tuple[EvidenceSignal, ...]
    source_concern_count: int
    recording_block_count: int
    stage_count: int
    scheduled_activity_count: int
    boundary_context_count: int
    timeline_span: tuple[float, float] | None
    source_role_distribution: Mapping[EvidenceRole, int] = field(
        default_factory=_empty_role_distribution
    )
    source_strength_distribution: Mapping[EvidenceStrength, int] = field(
        default_factory=_empty_strength_distribution
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_role_distribution",
            MappingProxyType(dict(self.source_role_distribution)),
        )
        object.__setattr__(
            self,
            "source_strength_distribution",
            MappingProxyType(dict(self.source_strength_distribution)),
        )

    @classmethod
    def from_result(
        cls,
        result: SessionBoundaryEvidenceResult,
    ) -> SessionBoundaryEvidenceSummary:
        evidence_sets = result.evidence_sets
        signals = tuple(
            reference.signal for evidence_set in evidence_sets for reference in evidence_set.signals
        )
        source_concerns = {
            concern
            for evidence_set in evidence_sets
            for concern in cls._source_concerns(evidence_set.metadata)
        }
        timeline_values = tuple(
            value
            for context in result.generated_boundary_contexts
            for value in (context.timeline_start_seconds, context.timeline_end_seconds)
            if value is not None
        )
        source_roles: Counter[EvidenceRole] = Counter()
        source_strengths: Counter[EvidenceStrength] = Counter()
        for evidence_set in evidence_sets:
            for item in evidence_set.items:
                role_value = item.metadata.get("source_role")
                strength_value = item.metadata.get("source_strength")
                if isinstance(role_value, str):
                    try:
                        source_roles[EvidenceRole(role_value)] += 1
                    except ValueError:
                        pass
                if isinstance(strength_value, str):
                    try:
                        source_strengths[EvidenceStrength(strength_value)] += 1
                    except ValueError:
                        pass

        recording_blocks = {
            context.recording_block_id
            for context in result.generated_boundary_contexts
            if context.recording_block_id is not None
        }
        stages = {
            context.stage_id
            for context in result.generated_boundary_contexts
            if context.stage_id is not None
        }
        activities = {
            context.scheduled_activity_id
            for context in result.generated_boundary_contexts
            if context.scheduled_activity_id is not None
        }
        return cls(
            total_input_evidence_set_count=int(result.metadata.get("input_evidence_set_count", 0)),
            consumed_count=len(result.consumed_source_evidence_set_ids),
            ignored_count=len(result.ignored_source_evidence_set_ids),
            unsupported_count=len(result.unsupported_source_evidence_set_ids),
            duplicate_count=len(result.duplicate_source_evidence_set_ids),
            possible_start_evidence_set_count=len(result.start_boundary_evidence_sets),
            possible_end_evidence_set_count=len(result.end_boundary_evidence_sets),
            produced_evidence_item_count=sum(
                len(evidence_set.items) for evidence_set in evidence_sets
            ),
            contributing_signal_count=len(signals),
            contributing_signals=tuple(dict.fromkeys(signals)),
            source_concern_count=len(source_concerns),
            recording_block_count=len(recording_blocks),
            stage_count=len(stages),
            scheduled_activity_count=len(activities),
            boundary_context_count=len(result.generated_boundary_contexts),
            timeline_span=(min(timeline_values), max(timeline_values)) if timeline_values else None,
            source_role_distribution=source_roles,
            source_strength_distribution=source_strengths,
        )

    @staticmethod
    def _source_concerns(metadata: Mapping[str, object]) -> tuple[EvidenceConcern, ...]:
        raw = metadata.get("source_concerns", ())
        if not isinstance(raw, tuple | list):
            return ()
        values = tuple(cast(Sequence[object], raw))
        concerns: list[EvidenceConcern] = []
        for value in values:
            if not isinstance(value, str):
                continue
            try:
                concerns.append(EvidenceConcern(value))
            except ValueError:
                continue
        return tuple(concerns)
