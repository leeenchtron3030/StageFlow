# Assembly media-order fallback and render slot order

## Status

Completed (2026-09-26).

## Execution authority

- Classification: Green autonomous, under the owner's decision of 2026-09-26.
- Authority evidence:
  - Owner decision 2026-09-26 on the Yellow escalation "media timing for Assembly"
    (option C now, option A later). When a completion member has no media start time, the
    proposal orders it by its infrastructure-observed registration time, then by asset ID.
    It records the ordering source per member, and human approval of the revision confirms
    the order. ADR-0027 is unchanged.
  - ED-0077 (Session Assembly), ED-0086 (metadata overrides), ED-0087 and
    [ADR-0032](../adr/ADR-0032-render-durable-operation.md) (render in template slot order).
  - Evidence: [render validation Run 001](../validation/results/render-durable-operation-001.md).
- Implementation-ready: Yes.
- Required escalation: stop if the change would alter Kernel association, Session
  boundaries, completion membership, or package authority; write Media Timing Evidence;
  change `media_started_at` in the registry; alter any `0013` column or constraint beyond
  the additive columns below; or change staleness semantics.
- Engineering Directive: **ED-0088**. The owner delegated ED numbering.

## Preserved accepted decisions

- **ADR-0027:** Media Timing Evidence stays advisory. No authoritative start or end field is
  added to Completed Media Asset, and nothing here reads or writes MTE.
- **ED-0077 design decisions:**
  - Membership stays pinned to the approved completion decision.
  - Staleness stays derived (decision 7, as preserved by ED-0086).
  - Equal sort keys still tie-break by asset ID.
  - Every other validation rule is unchanged.
- **ED-0086:** metadata snapshots and override provenance are unchanged.
- **ADR-0032 decision 5:** slots render in template order, and non-video Packaging Assets
  stay a typed ineligibility.

The only ED-0077 choice this plan changes is the bounded implementation choice "unknown
media timing … yields invalidity", recorded in ED-0077's completion record. The owner's
decision replaces it.

**Existing-assertion change authorized:** the `"timing"` case of
`tests/test_session_assembly_foundation.py::test_package_and_membership_validation`
asserts `MEDIA_TIMING_UNAVAILABLE`. This plan authorizes changing that case, and only that
case. It should instead assert that the revision is **valid**, with the member's ordering
source recorded as `registration_time`. Any other existing assertion that would need to
change is a stop-and-report condition.

## Problem statement

Discovery never supplies a media start time (`backend/app/bootstrap/media_cycle.py:570`
leaves `recorded_start_at` unset). As a result, `media_started_at` is NULL for every
discovered asset (0 of 57 completion members in the demo database). ED-0077 validation
then marks every such proposal `media_timing_unavailable`. So no Assembly over real
discovered media can be approved, and none can be rendered.

Separately, the render planner does not honour template slot order. It appends every bound
Packaging Asset first and the Session media after them. A closing bumper would therefore
render *before* the Session media.

## Verified current behavior

- `backend/app/contexts/assembly/session_contracts.py:143`: `CompletionMember` has
  `asset_id`, `association_revision`, and `media_started_at` (nullable).
- `backend/app/contexts/assembly/resolution.py`:
  - `:88-89` adds `MEDIA_TIMING_UNAVAILABLE` when any member lacks a start time;
  - `:117-120` orders members by (unknown timing last, start time or the authoritative
    Session start, asset ID).
- `backend/app/infrastructure/postgres/session_assembly_repository.py:~257` reads the
  membership from `session_completion_asset` joined to `completed_media_asset_registry`,
  which has a non-null `registered_at` (`0002`).
- `0013` `assembly_member` stores `position`, `asset_id`, `association_revision`, and
  `media_started_at`, with immutability triggers.
- `backend/app/contexts/rendering/planning.py`:
  - `:31-40` appends bound packaging in binding order;
  - it refuses any member without timing (`INPUT_MISSING`);
  - it re-sorts members by `media_started_at` instead of using the frozen position order;
  - it ignores where the `session_media` slot sits in the frozen bindings.

## Desired behavior

1. **Proposal ordering.** Each member's ordering key is:
   - its `media_started_at` when known, with ordering source `media_timing`;
   - otherwise its registry `registered_at`, with ordering source `registration_time`.

   Members are sorted by (key, asset ID). The ordering source and the key used are frozen
   on each member of the revision. A revision with no timed members is valid when the
   other rules pass. A mixed revision is valid too, with each member's source visible.
2. **Validation.** Unknown media timing no longer produces an issue. The
   `MEDIA_TIMING_UNAVAILABLE` enum value is kept for compatibility, but new revisions never
   emit it.
3. **Read models and API.** Revision members expose `order_source` and `order_key_at`, so
   a producer can see that the order came from registration time before approving.
4. **Render planning** follows the frozen revision exactly:
   - It iterates the frozen bindings in template order.
   - A `bound` packaging binding contributes its video input.
   - The `session_media` slot expands to the membership in its frozen position order.
   - It never re-sorts, and no longer refuses members without timing.
5. **Legacy rows.** Members stored before this change carry NULL ordering columns and are
   treated as `media_timing`. Such members always had timing when valid; rows without
   timing belong to invalid revisions, which can never be approved.

## In scope

1. Contracts:
   - `CompletionMember` gains `registered_at` (aware), `order_source` (a closed enum:
     `media_timing` | `registration_time`), and `order_key_at` (aware).
   - These values are immutable and validated. `order_source = media_timing` requires
     `order_key_at == media_started_at`.
2. Resolution: the ordering and validation changes above, in pure domain code.
3. Repositories:
   - In-memory and PostgreSQL membership reads supply `registered_at`.
   - Persistence writes and hydrates the new member fields, and treats legacy NULLs as
     `media_timing`.
4. Additive migration `0016` on `assembly_member`:
   - nullable `order_source` with a check `IN ('media_timing','registration_time')`;
   - nullable `order_key_at timestamptz`;
   - a check that both are NULL or both are set;
   - a check that `order_source = 'media_timing'` requires `order_key_at = media_started_at`.

   Adding nullable columns fires no UPDATE trigger, and no backfill is done. The reverse
   drops the columns and checks, and is **refused while any row has `order_source =
   'registration_time'`**. Those are the only rows whose meaning would be lost; rows with
   `media_timing` hydrate identically to legacy NULL rows after a reverse. The migration is registered after `0015`, in forward and reverse
   order.
5. Render planning: slot-ordered expansion and frozen member order, as described above.
6. API: expose `order_source` and `order_key_at` on revision members, additively.
7. Tests (behaviour-first, in-memory and real PostgreSQL where the path exists):
   - an all-untimed revision is valid, ordered by `registered_at` then asset ID;
   - a mixed revision uses per-member sources;
   - an all-timed revision's order and validity are unchanged from today;
   - ordering sources are frozen and survive a reload;
   - staleness is unchanged;
   - legacy NULL rows hydrate as `media_timing`;
   - `0016` forward, reverse, and reapply, including a refused reverse when `registration_time` rows exist, and an allowed reverse with
     only `media_timing` rows;
   - render planning places intro → session media → outro in template order and keeps the
     frozen member order, with and without timing;
   - the API exposes the new fields and no paths.
8. Documentation:
   - the glossary gains "media order source";
   - the persistence document covers `0016`;
   - the capability layer's Assembly and render sections;
   - a note in the rendering README.

## Out of scope

- Production Media Timing Evidence inspection (option A, later), and any MTE read or write.
- Populating `recorded_start_at` or `media_started_at` at discovery (option B, rejected).
- Operator reordering commands, and any Producer UI.
- Kernel association, Session boundaries, completion, or package authority.
- Render profile changes (ED-0089).

## Constraints

- No new dependency. Offline. Timestamps are timezone-aware. Contracts are immutable.
- White-label naming.
- Additive only: no existing column or constraint changes.
- No existing assertion changes except the one authorized case above.

## Data or migration considerations

`0016` is additive: two nullable columns and three checks on `assembly_member`, with no
backfill. Existing revisions keep their stored positions. The reverse is valid only while
no member has `order_source = 'registration_time'`, and this is stated in the migration.

## Failure and recovery considerations

Proposal and render planning are pure and deterministic, so there is nothing new to retry.
A render of a revision approved before `0016` uses its stored positions.

## Observability requirements

Revision members show each member's ordering source and key, so a producer can see at a
glance when the order came from registration time rather than media timing.

## Test strategy

The tests are listed under In scope, item 7. The quality gate is the full host backend
suite, Ruff, and Pyright.

## Acceptance criteria

- [ ] All-untimed and mixed revisions are valid and ordered as specified, with frozen,
  visible ordering sources. Behaviour for all-timed revisions is unchanged.
- [ ] Render planning follows template slot order and the frozen member order.
- [ ] `0016` forward, reverse, and reapply tests pass, including the refused reverse.
- [ ] The only existing assertion changed is the authorized `"timing"` case.
- [ ] The full host backend suite, Ruff, and Pyright pass, and the frontend is unchanged.

## Rollback

Revert the code and apply the `0016` reverse (only while no member records a
`registration_time` ordering source).

## Completion record

- **Implemented revision:** branch `codex/ed-0088-assembly-media-order`. Codex implemented
  the change and the owner committed it.
- **Files changed:**
  - Assembly contracts, resolution, in-memory and PostgreSQL repositories, and routes;
  - render planning;
  - migration registration and additive migration `0016`, which adds `order_source` and
    `order_key_at` to `assembly_member` with three checks and no backfill;
  - `tests/test_assembly_media_order.py`;
  - authorized updates to existing tests;
  - the glossary, the persistence document, the capability layer, and the rendering README.
- **Plan clarifications during implementation** (the owner's, all Green):
  - (A) the frozen-order render assertion now expects the frozen order;
  - (B) legacy untimed members hydrate with a NULL key and stay invalid;
  - (C) mechanical `CompletionMember` constructor updates that preserve values;
  - (D) the `0016` reverse guard is narrowed to `registration_time` rows, which keeps the
    existing `0013` reverse/reapply test unchanged.
- **Existing assertions changed:** only under the plan and A–D. Details:
  - the `"timing"` validation case;
  - the frozen-order render test, renamed;
  - the migration-order lists;
  - mechanical constructor fields.
- **Review:** the `directive-reviewer` returned FIX-FIRST for a test gap. The owner added a
  pure-planner test covering a bound binding with no revision (`INPUT_MISSING`) and a
  template with no Session-media slot, which renders packaging inputs only.
- **Tests:** host full suite **2,327 passed, 0 failed, 2 skipped** before the added test;
  the new test file then passed 25 of 25. Ruff and Pyright are clean.
- **Deviations:** none. ADR-0032 decision 5 still says members render "in timeline order".
  Under this plan they render in the frozen revision order, which equals timeline order
  whenever timing is known.
- **Remaining work:**
  - Option A: once production Media Timing Evidence inspection exists, it becomes the
    ordering source.
  - A Producer UI that shows ordering sources before approval.
