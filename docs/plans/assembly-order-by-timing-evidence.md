# Assembly ordering by Media Timing Evidence

## Status

Completed (2026-09-26).

## Execution authority

- Classification: Green autonomous.
- Authority evidence:
  - The owner decided on 2026-09-26: "option C now, option A later". ED-0088 implemented C.
    A is: once production Media Timing Evidence exists, it becomes the ordering source.
  - On 2026-09-26 the owner also accepted
    [ADR-0033](../adr/ADR-0033-production-media-timing-inspection.md). Its decision 5 names
    Assembly ordering as a permitted advisory consumer that must record the evidence
    revision and qualification it used.
  - ADR-0027 says MTE may be consumed by proposal workflows.
  - ED-0088 (the per-member ordering source) and ED-0090 (the production inspector, host
    Run 001).
- Implementation-ready: Yes.
- Required escalation: stop if this would:
  - write MTE, `media_started_at`, Session boundaries, association, membership, or package
    state;
  - make the ordering change staleness semantics;
  - alter any existing column's or constraint's meaning for existing rows;
  - treat `unqualified` evidence as authoritative anywhere but in the proposal's ordering,
    which a human approves.
- Engineering Directive: **ED-0091**. The owner delegated ED numbering.

## Preserved accepted decisions

- **ADR-0027 / ADR-0033:** MTE stays advisory. Assembly only reads the latest *active*
  evidence revision for each member asset, and records exactly which one it used.
- **ED-0077:**
  - Membership stays pinned.
  - Staleness stays derived (decision 7, as preserved by ED-0086 and ED-0088). A new MTE
    revision arriving after a proposal **does not** stale that revision; the next proposal
    picks it up.
  - The asset-ID tie-break is unchanged.
- **ED-0088:**
  - `media_timing` (the registry `media_started_at`) keeps first priority.
  - `registration_time` stays the last fallback.
  - Frozen members, legacy hydration, and the `0016` reverse guard are unchanged.
  - The render planner keeps following the frozen order.

If an existing assertion would have to change, stop and report it. Pre-authorized
exceptions:
- inserting `0018` into the migration-order lists;
- mechanical constructor or field additions that keep existing values.

## Problem statement

After ED-0090, every discovered recording can have an advisory start time: its Derived
`creation_time_plus_duration` interval. Assembly still orders members that lack
`media_started_at` by *registration* time. That time is when StageFlow registered the file,
not when it was recorded, so it is wrong for any batch of files registered out of order.

## Verified current behavior

- `backend/app/contexts/assembly/resolution.py`: each member's key is `media_started_at`
  if known (source `media_timing`), otherwise `registered_at` (`registration_time`).
  Members are sorted by (key, asset ID). The source and key are frozen per member (ED-0088).
- `0016`: `assembly_member.order_source IN ('media_timing','registration_time')`, a check
  that source and key are both NULL or both set, and a check that `media_timing` means
  key = `media_started_at`. The reverse is refused while `registration_time` rows exist.
- The MTE repository exposes the active evidence per asset
  (`media_timing_evidence_repository.py`, `get_active`/`history`). Evidence holds its
  Derivations (`candidate_started_at`) and its recorder qualification status.
- ED-0090 Run 001: all 12 live-run assets have one `unqualified` evidence revision with one
  Derivation.

## Desired behavior

For each completion member, choose the ordering key in this priority order:
1. **`media_timing`:** the registry `media_started_at`, when known. Unchanged.
2. **`timing_evidence` (new):** the `candidate_started_at` of the single Derivation of rule
   `creation_time_plus_duration` in the asset's latest *active* MTE revision, when that
   exists. If there are zero or several such Derivations, fall through.
3. **`registration_time`:** the registry `registered_at`. Unchanged.

The member then freezes:
- `order_source`;
- `order_key_at`;
- for `timing_evidence` only: `order_evidence_id` (the MTE evidence ID),
  `order_evidence_revision`, and `order_evidence_qualification` (for example
  `unqualified`).

Members are still sorted by (key, asset ID). Revision members in the API additively expose
the evidence reference and qualification, so a producer can see that the order rests on
unqualified recorder evidence before approving.

## In scope

1. Contracts: extend the `order_source` enum with `timing_evidence`, and add the three
   evidence fields to `CompletionMember`. Validation:
   - all three are required when the source is `timing_evidence`, and forbidden otherwise;
   - timestamps are aware;
   - the contract is immutable.
2. Reading MTE: a reader port in the Assembly context (no import of MTE infrastructure into
   the domain). The in-memory and PostgreSQL membership reads supply each member's
   latest-active derived start and evidence reference. In PostgreSQL this is one bounded
   query joined to `media_timing_evidence` and `media_timing_derivation`.
3. Resolution: the priority rule above, in pure domain code.
4. Additive migration `0018` on `assembly_member`:
   - drop and re-add `assembly_member_order_source_check` to allow `timing_evidence` (the
     existing values keep their meaning);
   - add nullable `order_evidence_id`, `order_evidence_revision`, and
     `order_evidence_qualification`;
   - a composite foreign key `(asset_id, order_evidence_id)` →
     `media_timing_evidence(asset_id, evidence_id)`;
   - a check that the three evidence columns are all set exactly when
     `order_source = 'timing_evidence'`;
   - a qualification check against MTE's closed status set;
   - no backfill and no row updates.

   The reverse is refused while `timing_evidence` rows exist, and otherwise restores the
   `0016` state exactly. It is registered after `0017` by plain chaining.
5. The API exposes the new member fields additively, with no paths.
6. Tests, behaviour-first, in memory and real PostgreSQL:
   - evidence beats registration time and loses to `media_started_at`;
   - several matching Derivations, or none, fall through to `registration_time`;
   - the latest *active* revision is used;
   - a revision with timing evidence stays approvable, and staleness is unchanged when a
     newer MTE revision arrives later;
   - the new fields are frozen and survive a reload;
   - ED-0088's all-untimed, mixed, and legacy behaviour is unchanged;
   - `0018` forward, reverse, and reapply, including the refused reverse, the foreign key,
     and negative inserts for each check;
   - the render planner renders a `timing_evidence`-ordered revision in its frozen order;
   - the API exposes the fields and no paths.
7. Documentation: glossary (the ordering-source values), the persistence document
   (`0018`), the capability layer's Assembly section, and the MTE architecture document
   (Assembly is now a consumer).

## Out of scope

- Writing MTE, recorder qualification, or `media_started_at`.
- Editorial derived candidates (ED-0092).
- Operator reordering, Producer UI, and staleness changes.

## Constraints

- No dependency. Offline. Timezone-aware times. Immutable contracts. White-label naming.
- Additive only.
- The domain does not import infrastructure.

## Data or migration considerations

`0018` widens one check and adds three nullable columns with checks and a composite foreign
key, with no backfill. The reverse is conditional on no `timing_evidence` rows.

## Acceptance criteria

- [ ] New proposals order by the timing-evidence start when it is available, and record
  which evidence was used. Every other ED-0077 and ED-0088 behaviour is unchanged.
- [ ] `0018` passes its forward, reverse, and reapply tests, including the refused reverse.
- [ ] The full host backend suite, Ruff, and Pyright pass, and the frontend is unchanged.
- [ ] Owner step: on the demo database, a new proposal for the live-run Session (after
  migrating to `0018`) orders all 11 members by `timing_evidence`, in recording order, and
  validates.

## Rollback

Revert the code and apply the `0018` reverse (only while no member records
`timing_evidence`).

## Completion record

- **Implemented revision:** branch `codex/ed-0091-assembly-order-timing`. Codex
  implemented it in one run with no escalation, and the owner committed it.
- **Files changed:**
  - Assembly contracts, resolution, and in-memory repository;
  - an Assembly-context timing reader port, with an in-memory adapter over the MTE
    repository and a PostgreSQL reader (one bounded query on the proposal's connection);
  - the PostgreSQL Assembly repository;
  - migration registration and additive migration `0018`;
  - Assembly routes;
  - `tests/test_assembly_timing_evidence.py`;
  - the glossary, persistence, capability-layer, and MTE architecture documents.
- **Existing assertions changed:** only pre-authorized or mechanical changes:
  - the three new fields added to one exact-keyset API assertion;
  - `0018` added to the migration-order lists;
  - a setup-only `0018` reverse before the refused-`0017` snapshot.
- **Review:** the `directive-reviewer` returned APPROVE. Its non-blocking notes:
  - the reverse-exactness test takes its baseline after a reverse;
  - no test checks distinct evidence keys against an independently computed order;
  - the Assembly contracts now import the pure MTE contracts module for the qualification
    enum.
- **Tests:** host full suite **2,477 passed, 0 failed, 2 skipped**; Ruff and Pyright
  are clean.
- **Owner step:** the demo database was backed up and migrated to `0018`. A new proposal
  (revision 2) for the live-run Session **validated with no issues**:
  - all 11 members are ordered by `timing_evidence`, in exact recording order (segments
    00000–00010, 60 s apart);
  - each member records evidence revision 1 and qualification `unqualified`.

  This is the first approvable Assembly revision over real discovered media. It was not
  approved during this step.
- **Deviations:** none.
- **Remaining work:**
  - ED-0092: derived Editorial candidates.
  - Optional: stronger reverse-exactness and distinct-key ordering tests.
  - Recorder-profile qualification, which would upgrade the qualification label.
