# Recording Transition Policy

ED-0034 introduced the first concrete Operational State Transition Policy. ED-0035 made
first-class Evidence Signals authoritative. ED-0042 closes ED0041-F001 by making the
policy conservative about recording context before it evaluates a lifecycle rule.
ED-0045 makes first-class `EvidenceSet.context` authoritative for that context.

`RecordingTransitionPolicy.evaluate()` preserves the generic public behavior and returns
one `TransitionEvaluation`. `evaluate_result()` additionally returns a policy-local
`RecordingTransitionResult` with a descriptive context and Evidence profile. Neither
method accepts state, mutates state, executes a transition, or persists anything.

## Supported Evidence And Lifecycle

Only `EvidenceConcern.RECORDING_COVERAGE` is consumed. First-class Signals are
authoritative:

| Signal | Proposed value | Allowed current values |
| --- | --- | --- |
| `recording_continuity_established` | `active` | `inactive`, `active` |
| `recording_pause_indicated` | `paused` | `active`, `paused` |
| `recording_continuity_restored` | `active` | `paused`, `active` |
| `recording_end_indicated` | `stopped` | `active`, `paused`, `stopped` |

An absent current state is explicitly evaluated as effective `inactive`. A valid Signal
whose target is not allowed from that value returns `transition_not_supported`; its
proposed value remains visible for compatibility and explanation. Unsupported state
contracts return `unknown`. `already_current` is returned only for a validated current
recording state whose value already matches the selected supported target.

## Context Safety

Before selecting a Signal, the policy deduplicates EvidenceSet IDs, filters recording
Evidence, extracts one `RecordingTransitionContext` per qualifying set, and separates
compatible groups.

- Different known recording blocks cannot combine.
- Different known stages cannot combine.
- Correlation IDs remain workflow traceability, not recording identity.
- Different media artifacts can contribute to one context only when they share a known
  recording block, allowing segmented artifacts without treating unrelated artifacts as
  one recording.
- Timeline proximity supports ordering only; it never overrides recording-block or stage
  identity.
- A wholly unknown context never merges with a known context. Unknown contexts may
  combine only when they carry one compatible Signal; conflicting unknown Signals return
  `insufficient_evidence`.
- More than one incompatible qualifying group returns `insufficient_evidence`; no first
  set, rule declaration, Signal enum, timestamp, or strength wins.

ED-0045 projects centrally resolved `EvidenceContext` into the policy-local
`RecordingTransitionContext`. The shared resolver prefers first-class context, then the
legacy `EvidenceSet.recording_block_id`/correlation fields, then documented metadata
aliases. It also resolves stage, media artifact, and timeline context. The policy no
longer implements its own arbitrary metadata parser. First-class/legacy conflicts remain
visible on the generic evaluation and metadata cannot override first-class context.

## Conflict, Ordering, And Duplicates

Contradiction applies only when a Signal reference links to a contradictory EvidenceItem.
Unlinked contradictory items do not block a different Signal contribution. Repeated
Signal references and repeated Observation references do not create independent support.
Different EvidenceSet IDs are not content-merged.

When one compatible context contains different lifecycle Signals, the policy uses a
reliable common ordering source in this order: timeline end/anchor, aware EvidenceSet
timestamp, then aware source Observation timestamp. Equal or unavailable ordering is
insufficient. The latest reliably ordered Signal is evaluated only as one transition from
the supplied current value; the policy does not replay accumulated intermediate state
changes. If that history would require an unaccepted intermediate transition, the outcome
is `insufficient_evidence`.

## Current-State Validation

Current state must be `recording_state`, have `current` status, use a `recording_block`,
`media_artifact`, or `stageflow` subject, and use `inactive`, `active`, `paused`, or
`stopped`. A recording-block subject must contain a valid block Entity ID consistent with
the state’s first-class block reference. A known current block, stage, or media artifact
that conflicts with selected Evidence returns `transition_not_supported`; an unknown
Evidence context that cannot match a known current target returns `insufficient_evidence`.

## Compatibility And Scope

Legacy `recording_transition_marker` metadata remains readable only when an EvidenceSet
has no first-class Signals. If Signals exist, metadata cannot override them. Compatibility
use, selected context, conflicting contexts, linked EvidenceItem and Observation IDs,
Signals, applied rule ID, duplicate IDs, and current-state validation are exposed through
the result profile and structured evaluation metadata. The accepted group’s first-class
context and structured conflicts are also exposed on `TransitionEvaluation` for
Operational State Acceptance.

The policy does not implement state acceptance, successor states, supersession, transition
execution, persistence, repositories, scoring,
confidence, AI, APIs, workers, queues, or frontend behavior.
