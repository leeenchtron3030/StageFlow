# Producer Work Queue: Assembly approval items

## Status

Approved (2026-09-28).

## Execution authority

- Classification: Green autonomous.
- Authority evidence:
  - [`post-kernel-capability-layer.md`](../architecture/post-kernel-capability-layer.md),
    "Producer Work Queue", lists **Assembly approval** among the expected Work Queue items.
    The queue "derives from ... Assembly approval state".
  - [ED-0068's plan](producer-work-queue-kernel-derived-slice.md), Out of scope, excluded
    Assembly approval items only because Assembly did not exist yet. It said to add them
    once the capability exists.
  - ED-0077 implemented Assembly revisions, validation and human approval.
  - The owner's direction on 2026-09-28: continue with the Green roadmap candidates while
    the boundary-suggestion ADR waits for timing references.
- Implementation-ready: Yes.
- Required escalation: stop if the work needs:
  - a new item type beyond the one named here;
  - a change to Assembly, approval, staleness or Kernel semantics;
  - the Kernel to depend on the Assembly context;
  - a migration;
  - a breaking change to the Work Queue response shape;
  - any frontend work.
- Engineering Directive: **ED-0101**. The owner delegated ED numbering.

## Verified current behavior

- `backend/app/contexts/production/event_mode_kernel/work_queue.py` projects only Session
  package items (priority 3, correction required; priority 4, ready for review) and media
  association items (priority 1, conflict; priority 2, unresolved).
- `list_producer_work_queue` in both the memory and PostgreSQL Kernel repositories
  (`event_mode_kernel_repository.py:1959`) orders the queue by the keyset
  `(priority, updated_at, projection_id)`, filters by cursor, and applies `limit + 1`.
- `backend/app/api/v1/work_queue.py`, `GET /producer/events/{event_id}/work-queue`:
  - encodes a v1 cursor over that keyset;
  - `decision_type` and `subject_kind` are closed `Literal` types;
  - limit is between 1 and 100, with explicit truncation.
- The Assembly context computes whether a revision is current, valid and undecided:
  - `SessionAssembly` has `revision`, `current_revision_number`, `stale`,
    `approval_state` and `decision_count`.
  - Staleness is `is_stale` in `backend/app/contexts/assembly/resolution.py:152`. It
    compares the package revision, packaging approvals and governing metadata overrides.
    Program Expectation refreshes never make a revision stale.
- No component in the Kernel imports the Assembly context.
- No frontend code calls the Work Queue API.

## Desired behavior

- The Work Queue gains exactly one item type: **`assembly_approval_pending`**. It applies
  to a Session's Assembly revision when all of these hold:
  - it is the Session's **current** (latest) revision;
  - its validation is **valid**;
  - it is **not stale**;
  - it has **no approval decision** yet.
- An approved, rejected, invalid, stale or superseded revision produces no item. A stale
  revision needs a new proposal, not an approval, so it is not an approval item. Proposal
  and correction items are out of scope.
- Item fields:
  - `projection_id` `assembly:<session_id>`;
  - `subject_kind` `session_assembly`;
  - `subject_id` = the Assembly revision ID;
  - `subject_revision` = the revision number;
  - Event, Stage and Session IDs from the Session;
  - `priority` **5**, after package review (4), since approval follows package
    completion;
  - `reason_codes` `("assembly_approval_pending",)`;
  - `action_reference` `session:<session_id>:assembly`;
  - `created_at` and `updated_at` = the revision's aware recorded time.
- **Composition stays outside the Kernel:**
  - A Producer Work Queue application service merges the Kernel queue with the Assembly
    items under the same keyset and cursor.
  - It fetches `limit + 1` from each source after the cursor, merge-sorts them, and
    returns `limit + 1`, so the route's truncation logic is unchanged.
  - The Kernel repository methods and the Kernel projection functions do not change.
- The Assembly repository gains a bounded, Event-scoped read that returns
  current-revision candidates in keyset order after a cursor. Staleness is computed with
  the existing `is_stale` inputs, never a new rule. If stale candidates leave fewer than
  `limit + 1` items, the read continues in bounded pages until it has enough or runs out.
- API:
  - `decision_type` gains `assembly_approval_pending`, and `subject_kind` gains
    `session_assembly`. This is additive: existing values and fields are unchanged.
  - The cursor stays v1 over the same keyset.
- The route uses the application service. An error in either source returns the existing
  bounded 503.

## In scope

1. The Assembly repository's bounded pending-approval read (memory and PostgreSQL), with
   no migration.
2. The Assembly projection function for the new item. It lives in the Assembly context or
   the application layer, not in the Kernel.
3. The Producer Work Queue application service (the keyset merge) and the route using it.
4. The additive API `Literal` values.
5. Tests: see Test strategy.
6. Documentation:
   - the Work Queue row in `post-kernel-capability-layer.md` (Assembly approval items are
     implemented);
   - the glossary entry, if it lists item types.

## Out of scope

- Session-boundary review, auto-approval-withheld and policy-exception items.
- Assembly proposal or correction items (stale or invalid revisions).
- Any Work Queue frontend: the UX specification is still Draft.
- Changes to Kernel repository or projection behaviour; migrations.

## Constraints

- The Kernel must not import the Assembly context. Add or extend an import-boundary test
  to enforce this.
- Read-model only: no writes, no new authority, no task claiming.
- Aware timestamps. Bounded reads. White-label.
- No existing assertion changes, except additive `Literal` or enum membership lists. List
  each changed assertion.

## Data or migration considerations

None. This is a read-only query over existing Assembly, approval and packaging tables.
Verify during implementation that no index is required at the demo scale. If a query
plan needs one, stop and report, since that would require a migration.

## Failure and recovery considerations

Read-only. A storage error in either source maps to the existing 503. The cursor is
stateless, and replaying the same cursor returns the same page while state is unchanged.

## Test strategy

- **Appears:** a valid, current, undecided revision yields exactly one item with the
  specified fields.
- **Disappears:**
  - after approval or rejection;
  - when a newer revision supersedes it (the newer one appears if it qualifies);
  - when it becomes stale through a package revision advance, a withdrawn packaging
    approval, or a governing metadata override change;
  - when it is invalid.
- **Event isolation:** an item from another Event never appears.
- **Ordering and pagination** across mixed sources:
  - Assembly items sort after package items;
  - a cursor boundary falls exactly between Kernel and Assembly items;
  - the limit is 1;
  - truncation is signalled and there are no duplicates or gaps across pages;
  - cursors are rejected across Events.
- **Kernel-only behaviour is unchanged:** existing Work Queue tests pass unchanged when no
  Assembly items exist.
- **Import boundary:** no module in `event_mode_kernel` imports `app.contexts.assembly`.
- **PostgreSQL:** real-database tests for the pending-approval read, including staleness
  inputs.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.

## Acceptance criteria

- [ ] Assembly approval items appear exactly for current, valid, non-stale, undecided
  revisions, with the specified fields and priority.
- [ ] Mixed-source ordering, pagination and truncation are correct and deterministic.
  Kernel-only behaviour is unchanged.
- [ ] The Kernel does not depend on Assembly, and there is no migration or frontend
  change.
- [ ] All required checks pass on the host.

## Rollback or reversal

Revert the code. There is no data change.

## Completion record

- Implemented revision:
- Files and migrations actually changed:
- Commands and tests actually run:
- Results and warnings:
- Execution authority used:
- Approved deviations:
- Rollback status:
- Remaining work:
