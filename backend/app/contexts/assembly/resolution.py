"""Pure deterministic proposal resolution and validation."""
from collections.abc import Iterable
from dataclasses import replace

from app.shared.ids import EntityId

from .contracts import ApprovalState, CommandIdentity
from .session_contracts import (
    AssemblyInputs,
    AssemblyMetadataOverride,
    AssemblyRevision,
    AssemblyTemplate,
    AssemblyValidation,
    ExplicitBinding,
    MediaOrderSource,
    MetadataField,
    MetadataOverrideAction,
    MetadataValue,
    PackagingCandidate,
    PlacementRole,
    SlotBinding,
    ValidationIssue,
    ValidationReason,
)


def resolve_metadata(
    inputs: AssemblyInputs, overrides: Iterable[AssemblyMetadataOverride],
) -> tuple[MetadataValue, ...]:
    """Resolve by append sequence, never by clocks or input iteration order."""
    latest: dict[MetadataField, AssemblyMetadataOverride] = {}
    for entry in overrides:
        if entry.session_id != inputs.session_id:
            continue
        previous = latest.get(entry.field)
        if previous is None or entry.sequence > previous.sequence:
            latest[entry.field] = entry
    selected = {value.field: value for value in inputs.metadata}
    for field, entry in latest.items():
        if entry.action == MetadataOverrideAction.SET:
            selected[field] = MetadataValue(
                field, entry.values, entry.id, entry.sequence, "operator_override",
            )
    return tuple(selected[field] for field in sorted(selected))


def resolve_bindings(
    template: AssemblyTemplate, inputs: AssemblyInputs,
    candidates: Iterable[PackagingCandidate], explicit: tuple[ExplicitBinding, ...] = (),
) -> tuple[SlotBinding, ...]:
    choices = {item.slot_key: item.packaging_revision_id for item in explicit}
    packaging_slots = {s.key for s in template.slots if s.role != PlacementRole.SESSION_MEDIA}
    if len(choices) != len(explicit) or not choices.keys() <= packaging_slots:
        raise ValueError("explicit bindings require unique packaging slot keys")
    eligible = tuple(c for c in candidates if (
        c.approval_state == ApprovalState.APPROVED
        and c.revision.packaging_asset_id == c.asset.id
        and c.asset.event_id == inputs.event_id
        and c.asset.stage_id in (None, inputs.stage_id)
        and (c.revision.content.effective_from is None
             or c.revision.content.effective_from <= inputs.authoritative_start)
        and (c.revision.content.effective_until is None
             or inputs.authoritative_start < c.revision.content.effective_until)
    ))
    result: list[SlotBinding] = []
    for slot in template.slots:
        if slot.role == PlacementRole.SESSION_MEDIA:
            result.append(SlotBinding(slot.key, None, "session_media"))
            continue
        ids = {c.revision.id for c in eligible if c.asset.role.value == slot.role.value}
        selected = choices.get(slot.key)
        if selected is not None:
            result.append(SlotBinding(slot.key, selected if selected in ids else None,
                                      "bound" if selected in ids else "invalid_explicit"))
        elif len(ids) == 1:
            result.append(SlotBinding(slot.key, next(iter(ids)), "bound"))
        else:
            result.append(SlotBinding(slot.key, None, "ambiguous" if ids else "unresolved"))
    return tuple(result)


def validate_assembly(
    template: AssemblyTemplate, inputs: AssemblyInputs, bindings: tuple[SlotBinding, ...],
) -> AssemblyValidation:
    issues: list[ValidationIssue] = []
    if not inputs.package_complete:
        issues.append(ValidationIssue(ValidationReason.INELIGIBLE_PACKAGE))
    elif inputs.completion_decision_id is None or not inputs.membership:
        issues.append(ValidationIssue(ValidationReason.COMPLETION_MEMBERSHIP_UNAVAILABLE))
    if tuple(b.slot_key for b in bindings) != tuple(s.key for s in template.slots):
        raise ValueError("bindings must match template order")
    for slot, binding in zip(template.slots, bindings, strict=True):
        if binding.outcome == "invalid_explicit":
            issues.append(ValidationIssue(ValidationReason.INVALID_EXPLICIT_BINDING, slot.key))
        if slot.required:
            if binding.outcome == "ambiguous":
                issues.append(ValidationIssue(ValidationReason.AMBIGUOUS_BINDING, slot.key))
            if binding.outcome in ("unresolved", "ambiguous", "invalid_explicit") or (
                binding.outcome == "session_media" and not inputs.membership
            ):
                issues.append(ValidationIssue(ValidationReason.UNRESOLVED_REQUIRED_SLOT, slot.key))
    present = {m.field for m in inputs.metadata if m.values and all(v.strip() for v in m.values)}
    for field in template.required_metadata:
        if field not in present:
            issues.append(ValidationIssue(ValidationReason.MISSING_REQUIRED_METADATA, field.value))
    return AssemblyValidation(tuple(issues))


def build_revision(
    command: CommandIdentity, revision_id: EntityId, number: int, previous: EntityId | None,
    template: AssemblyTemplate, inputs: AssemblyInputs, candidates: Iterable[PackagingCandidate],
    explicit: tuple[ExplicitBinding, ...],
) -> AssemblyRevision:
    if template.event_id != inputs.event_id:
        raise ValueError("template_not_in_session_event")
    bindings = resolve_bindings(template, inputs, candidates, explicit)
    keyed = tuple(replace(
        m, order_source=(MediaOrderSource.MEDIA_TIMING if m.media_started_at is not None
                         else MediaOrderSource.REGISTRATION_TIME),
        order_key_at=m.media_started_at if m.media_started_at is not None else m.registered_at,
    ) for m in inputs.membership)
    membership = tuple(sorted(keyed, key=lambda m: (
        m.order_key_at if m.order_key_at is not None else m.registered_at, m.asset_id.value,
    )))
    return AssemblyRevision(
        revision_id, inputs.session_id, inputs.event_id, number, previous, template.id,
        inputs.package_revision, inputs.completion_decision_id, membership, bindings,
        inputs.metadata, validate_assembly(template, inputs, bindings), command.actor_id,
        command.recorded_at,
    )


def is_stale(
    revision: AssemblyRevision, current_package_revision: int, approved_ids: frozenset[EntityId],
    current_metadata: tuple[MetadataValue, ...] | None = None,
) -> bool:
    # ED-0077 design decision 7 (preserved by ED-0086): Program Expectation refreshes never
    # make a revision stale. Metadata staleness compares only the operator override, if any,
    # that governs each field.
    def governing(values: tuple[MetadataValue, ...]) -> dict[MetadataField, EntityId]:
        return {m.field: m.source_id for m in values if m.source == "operator_override"}

    return (current_metadata is not None and governing(revision.metadata) != governing(
        current_metadata,
    )) or current_package_revision > revision.package_revision or any(
        b.packaging_revision_id is not None and b.packaging_revision_id not in approved_ids
        for b in revision.bindings
    )
