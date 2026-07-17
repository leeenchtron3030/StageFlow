# Operational State Acceptance

ED-0044 adds the first layer allowed to create an immutable successor
`OperationalState` from one `TransitionEvaluation`.

Policy and acceptance remain separate. A policy decides whether Evidence supports a
proposal. Acceptance does not reconsider that Evidence. It verifies that a supported
proposal has valid policy, rule, state, subject, context, lifecycle, Evidence,
Observation, Production Event, and known-history lineage before recording one
descriptive successor.

## Eligibility and lineage

Only `transition_supported` evaluations are eligible. `transition_not_supported`,
`insufficient_evidence`, `already_current`, and `unknown` outcomes cannot create state.
An eligible evaluation must contain an explicit proposed value.

Policy kind, policy ID, applied transition rule ID, supporting EvidenceSet IDs,
contributing EvidenceItem IDs, contributing Observation IDs, and exact source
Production Event IDs are first-class acceptance lineage. Blocking Evidence or unmet
mandatory requirements reject a supported evaluation. Metadata can supplement this
lineage but cannot contradict or replace it.

The request contains exactly one evaluation and an explicit target subject. It embeds
no raw Production Events, Observations, Evidence, policies, or rules. All such
references remain ID-only.

## Supported domains

ED-0044 accepts only these lifecycle graphs:

- Recording state: inactive to active, active to paused, paused to active, active to
  stopped, and paused to stopped.
- Session state: inactive to active, active to ending, active to ended, ending to
  ended, and ended to active.

Recording successors use the `directly_observable` family. Session successors use the
`evidence_derived` family. Other state kinds are deterministically rejected until an
explicit transition policy and acceptance mapping exist.

Recording subjects may be recording blocks, media artifacts, or the stable StageFlow
subject. Session subjects may be Session candidates or recording blocks. A current
state and its successor must retain the same subject; ED-0044 does not support subject
migration or invent a Session identity.

## Current state and context

When supplied, the predecessor must be the exact current state evaluated by policy. Its
kind, family, value, subject, status, and known recording-block or stage context must be
compatible. Only status `current` is authoritative.

An absent predecessor is allowed only for an explicitly recorded effective inactive
assumption and an approved inactive-to-active rule. Acceptance does not create a
synthetic inactive predecessor.

Context is partial and ID-only. Known stage, recording-block, schedule, stream,
artifact, correlation, boundary-context, or organizational-anchor conflicts cause a
rejection. Unknown context remains unknown and cannot override a known conflict.

## Successor and supersession

An accepted result creates exactly one new immutable successor with status `current`.
Its basis preserves Observation, EvidenceSet, Transition Evaluation, policy, and rule
IDs. Production Event and EvidenceItem lineage remains in structured basis metadata.
No rejected or already-accepted result contains a successor.

When a predecessor exists, the result also contains an
`OperationalStateSupersession` description. The predecessor remains unchanged. The
description is not a status update and is not persisted.

The successor's `observed_or_derived_at` is the Transition Evaluation timestamp.
`accepted_at` is separately supplied by the caller. Organizational boundary anchors
remain separate context and are not treated as verified Session or media boundaries.

## Known-history idempotency

Acceptance is idempotent relative to the supplied acceptance history. A known
Transition Evaluation ID returns `already_accepted` without a successor or
supersession. With no repository, this package does not claim global idempotency.

## Immutability note

Acceptance contracts are frozen, normalize duplicate references, convert collections
to tuples, and defensively copy metadata into read-only mapping wrappers. As with the
existing repository contracts, nested objects placed inside metadata are not
recursively frozen. Acceptance-critical meaning therefore remains in first-class
fields and does not rely on nested metadata mutability.

## Architectural boundary

This package has no persistence, repository queries, state mutation, transition
execution, policy invocation, Evidence reinterpretation, event publication, Session
aggregate creation, final boundary verification, APIs, queues, workers, frontend
behavior, or AI. Persistence and global idempotency belong to a later directive;
execution remains later still.
