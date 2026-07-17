# Operational State Acceptance

ED-0044 adds the first layer allowed to create an immutable successor
`OperationalState` from one `TransitionEvaluation`. ED-0045 makes the evaluation’s
first-class Evidence context authoritative during that acceptance.

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

Context is partial and ID-only. Acceptance compares evaluation context first, then
first-class lineage, request, and predecessor context as supplements. Known stage,
recording-block, schedule, stream, artifact, boundary-context, or organizational-anchor
conflicts cause `rejected_context_mismatch`; metadata cannot override evaluation context.
Correlation remains traceability rather than operational identity. Unknown context stays
unknown and cannot override a known conflict.

## Successor and supersession

An accepted result creates exactly one new immutable successor with status `current`.
Its basis preserves Observation, EvidenceSet, Transition Evaluation, policy, and rule
IDs plus the validated first-class `EvidenceContext`. Production Event and EvidenceItem
lineage remains in structured basis metadata.
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

## Repository handoff

ED-0046 defines a separate Operational State Repository contract. The repository
consumes one existing acceptance result; it never invokes this component or repeats its
Evidence reasoning. Only an `accepted` result with one successor and complete lineage
is commit-eligible. Invalid shape is rejected with a typed no-change repository result.

The repository is authoritative for idempotency within its own scope: one Evaluation ID
and one acceptance ID may each be committed at most once. It also compares the expected
predecessor with stored current state. A stale predecessor cannot overwrite newer state,
and an initial acceptance conflicts when that subject-kind key already has current
state.

ED-0044 supersession remains descriptive until a successful atomic repository commit.
At that point, the persisted predecessor record becomes `superseded` and the successor
becomes the sole current record. The caller's predecessor object is never mutated.
Repository commit time remains separate from evaluation time, successor state time,
acceptance time, organizational anchors, and any future verified boundary.

ED-0047 proves this handoff with one process-local in-memory repository. It consumes the
result unchanged, performs structural commit validation only, and distinguishes exact
idempotent replay from conflicting lineage reuse. It never invokes this acceptance
component. Rejected or stale commit attempts leave the repository unchanged, and the
implementation is contract-validation infrastructure rather than production storage.

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
behavior, or AI. ED-0046 gives persistence and repository-scoped idempotency to a
separate contract; execution remains later still.
