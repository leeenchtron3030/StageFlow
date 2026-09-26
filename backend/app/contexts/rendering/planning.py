"""Pure planning from pinned Assembly facts, never metadata resolution."""
from collections.abc import Mapping

from app.contexts.assembly.contracts import ApprovalState
from app.contexts.assembly.session_contracts import SessionAssembly
from app.shared.ids import EntityId

from .contracts import (
    RenderError,
    RenderManifest,
    RenderPlan,
    RenderProfile,
    RenderReason,
    VideoInput,
    require_profile,
)


def build_render_plan(
    assembly: SessionAssembly, profile: RenderProfile,
    packaging: Mapping[EntityId, VideoInput], media: Mapping[EntityId, VideoInput],
) -> RenderPlan:
    require_profile(profile)
    revision = assembly.revision
    if assembly.approval_state != ApprovalState.APPROVED or revision.validation.state != "valid":
        raise RenderError(RenderReason.NOT_APPROVED)
    if assembly.stale:
        raise RenderError(RenderReason.STALE)
    ordered: list[VideoInput] = []
    try:
        # Bindings were frozen in template order by Assembly; no live template resolution.
        for binding in revision.bindings:
            if binding.outcome == "bound":
                if binding.packaging_revision_id is None:
                    raise RenderError(RenderReason.INPUT_MISSING)
                ordered.append(packaging[binding.packaging_revision_id])
            elif binding.outcome == "session_media":
                ordered.extend(media[member.asset_id] for member in revision.membership)
    except KeyError:
        raise RenderError(RenderReason.INPUT_MISSING) from None
    if not ordered:
        raise RenderError(RenderReason.INPUT_MISSING)
    if any(not item.media_type.casefold().startswith("video/") for item in ordered):
        raise RenderError(RenderReason.NOT_VIDEO)
    return RenderPlan(revision, profile, tuple(ordered), RenderManifest(
        revision.id, revision.session_id, revision.event_id, profile.id, profile.version,
        revision.metadata,
    ))
