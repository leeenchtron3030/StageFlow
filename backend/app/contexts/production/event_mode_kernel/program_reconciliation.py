from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from app.contexts.events import (
    ProgramExpectation,
    ProgramExpectationChange,
    ProgramExpectationChangeKind,
    ProgramExpectationFieldChange,
    ProgramExpectationLifecycle,
    ProgramExpectationReconciliation,
    ProgramExpectationSnapshot,
)

_CHANGE_LIMIT = 100


@dataclass(frozen=True, slots=True)
class ProgramExpectationMutation:
    expectation: ProgramExpectation
    write_revision: bool


@dataclass(frozen=True, slots=True)
class ProgramReconciliationPlan:
    mutations: tuple[ProgramExpectationMutation, ...]
    result: ProgramExpectationReconciliation


def _timestamp(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _references(value: ProgramExpectation) -> str:
    return json.dumps(
        dict(value.external_references), sort_keys=True, separators=(",", ":")
    )


def _content_changes(
    existing: ProgramExpectation,
    incoming: ProgramExpectation,
) -> tuple[ProgramExpectationFieldChange, ...]:
    values: tuple[tuple[str, str | None, str | None], ...] = (
        (
            "stage",
            None if existing.stage_id is None else existing.stage_id.value,
            None if incoming.stage_id is None else incoming.stage_id.value,
        ),
        ("title", existing.title, incoming.title),
        ("speakers", " · ".join(existing.speakers), " · ".join(incoming.speakers)),
        (
            "planned start",
            _timestamp(existing.planned_start),
            _timestamp(incoming.planned_start),
        ),
        (
            "planned end",
            _timestamp(existing.planned_end),
            _timestamp(incoming.planned_end),
        ),
        ("provider references", _references(existing), _references(incoming)),
        (
            "synchronization scope",
            existing.synchronization_scope,
            incoming.synchronization_scope,
        ),
    )
    return tuple(
        ProgramExpectationFieldChange(field=field, previous=previous, current=current)
        for field, previous, current in values
        if previous != current
    )


def _change(
    kind: ProgramExpectationChangeKind,
    expectation: ProgramExpectation,
    fields: tuple[ProgramExpectationFieldChange, ...] = (),
) -> ProgramExpectationChange:
    return ProgramExpectationChange(
        kind=kind,
        expectation_id=expectation.id,
        expectation_key=expectation.key,
        title=expectation.title,
        external_session_id=expectation.external_references.get("devcon_session_id"),
        fields=fields,
    )


def _ordered(values: Iterable[ProgramExpectation]) -> tuple[ProgramExpectation, ...]:
    return tuple(
        sorted(
            values,
            key=lambda item: (
                item.planned_start is None,
                item.planned_start,
                item.key,
            ),
        )
    )


def plan_program_reconciliation(
    existing_expectations: Iterable[ProgramExpectation],
    snapshot: ProgramExpectationSnapshot,
) -> ProgramReconciliationPlan:
    existing = tuple(existing_expectations)
    existing_by_key = {item.key: item for item in existing}
    incoming_keys = {item.key for item in snapshot.expectations}
    mutations: list[ProgramExpectationMutation] = []
    current: list[ProgramExpectation] = []
    changes: list[ProgramExpectationChange] = []
    added = changed = unchanged = withdrawn = restored = 0

    for incoming in snapshot.expectations:
        prior = existing_by_key.get(incoming.key)
        if prior is None:
            saved = replace(
                incoming,
                revision=1,
                recorded_at=snapshot.observed_at,
                lifecycle_state=ProgramExpectationLifecycle.CURRENT,
                last_observed_at=snapshot.observed_at,
                lifecycle_changed_at=snapshot.observed_at,
            )
            added += 1
            changes.append(_change(ProgramExpectationChangeKind.ADDED, saved))
            mutations.append(ProgramExpectationMutation(saved, write_revision=True))
            current.append(saved)
            continue

        fields = _content_changes(prior, incoming)
        if prior.lifecycle_state is ProgramExpectationLifecycle.WITHDRAWN:
            saved = replace(
                incoming,
                id=prior.id,
                revision=prior.revision + 1,
                recorded_at=snapshot.observed_at,
                lifecycle_state=ProgramExpectationLifecycle.CURRENT,
                last_observed_at=snapshot.observed_at,
                lifecycle_changed_at=snapshot.observed_at,
            )
            restored += 1
            changes.append(
                _change(ProgramExpectationChangeKind.RESTORED, saved, fields)
            )
            mutations.append(ProgramExpectationMutation(saved, write_revision=True))
        elif fields:
            saved = replace(
                incoming,
                id=prior.id,
                revision=prior.revision + 1,
                recorded_at=snapshot.observed_at,
                lifecycle_state=ProgramExpectationLifecycle.CURRENT,
                last_observed_at=snapshot.observed_at,
                lifecycle_changed_at=prior.lifecycle_changed_at,
            )
            changed += 1
            changes.append(_change(ProgramExpectationChangeKind.CHANGED, saved, fields))
            mutations.append(ProgramExpectationMutation(saved, write_revision=True))
        else:
            saved = replace(prior, last_observed_at=snapshot.observed_at)
            unchanged += 1
            mutations.append(ProgramExpectationMutation(saved, write_revision=False))
        current.append(saved)

    for prior in sorted(existing, key=lambda item: item.key):
        if (
            prior.synchronization_scope != snapshot.synchronization_scope
            or prior.lifecycle_state is ProgramExpectationLifecycle.WITHDRAWN
            or prior.key in incoming_keys
        ):
            continue
        saved = replace(
            prior,
            lifecycle_state=ProgramExpectationLifecycle.WITHDRAWN,
            revision=prior.revision + 1,
            recorded_at=snapshot.observed_at,
            lifecycle_changed_at=snapshot.observed_at,
        )
        withdrawn += 1
        changes.append(_change(ProgramExpectationChangeKind.WITHDRAWN, saved))
        mutations.append(ProgramExpectationMutation(saved, write_revision=True))

    bounded_changes = tuple(changes[:_CHANGE_LIMIT])
    result = ProgramExpectationReconciliation(
        event_id=snapshot.event_id,
        stage_id=snapshot.stage_id,
        provider=snapshot.provider,
        synchronization_scope=snapshot.synchronization_scope,
        synchronized_at=snapshot.observed_at,
        observed=len(snapshot.expectations),
        added=added,
        changed=changed,
        unchanged=unchanged,
        withdrawn=withdrawn,
        restored=restored,
        expectations=_ordered(current),
        changes=bounded_changes,
        changes_truncated=len(changes) > _CHANGE_LIMIT,
    )
    return ProgramReconciliationPlan(mutations=tuple(mutations), result=result)


__all__ = [
    "ProgramExpectationMutation",
    "ProgramReconciliationPlan",
    "plan_program_reconciliation",
]
