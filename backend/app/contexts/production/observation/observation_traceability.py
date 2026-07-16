from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from app.contexts.production.observation.observation import Observation
from app.shared.ids import EntityId


def observation_recording_block_id(observation: Observation) -> EntityId | None:
    """Prefer first-class context, retaining the legacy field as fallback."""

    return observation.context.recording_block_id or observation.recording_block_id


def observation_stage_id(observation: Observation) -> EntityId | None:
    """Prefer first-class context, retaining location as fallback."""

    return observation.context.stage_id or observation.location.stage_id


def observation_traceability_metadata(observation: Observation) -> Mapping[str, Any]:
    """Flatten first-class lineage/context for generic Evidence metadata."""

    metadata: dict[str, Any] = {}
    if observation.provenance is not None:
        metadata.update(observation.provenance.traceability_metadata())
    recording_block_id = observation_recording_block_id(observation)
    stage_id = observation_stage_id(observation)
    metadata.update(
        {
            "recording_block_id": (
                recording_block_id.to_json()
                if recording_block_id is not None
                else None
            ),
            "stage_id": stage_id.to_json() if stage_id is not None else None,
            "correlation_id": observation.context.correlation_id.to_json()
            if observation.context.correlation_id is not None
            else observation.correlation_id.to_json(),
            "scheduled_activity_id": (
                observation.context.scheduled_activity_id.to_json()
                if observation.context.scheduled_activity_id is not None
                else None
            ),
            "transcript_stream_id": observation.context.transcript_stream_id,
            "media_artifact_id": observation.context.media_artifact_id,
            "timeline_reference": observation.context.timeline_reference,
        }
    )
    return MappingProxyType(metadata)
