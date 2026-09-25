# Assembly metadata overrides

## Status

Completed (2026-09-25).

## Execution authority

- Classification: Green autonomous. The owner resolved the plan's one Yellow decision on
  2026-09-25.
- Authority evidence:
  - [ED-0077 plan](session-assembly-foundation.md) names "operator metadata editing or
    override" as out of scope and a named follow-up.
  - `docs/architecture/post-kernel-capability-layer.md` lists operator metadata overrides
    among Assembly follow-ups.
  - The 2026-09-25 `roadmap-scout` ranking includes this item.
  - **Owner decision (2026-09-25):** an override is **local to the Session Assembly and
    provenance-tagged**. It never mutates the Kernel-owned Program Expectation (ADR-0013),
    and no participant identity model is added.
- Implementation-ready: Yes.
- Required escalation: stop if this would change Kernel, Program Expectation, or Packaging
  Asset tables or semantics; alter an existing migration or table; or add a participant
  model.
- Engineering Directive: **ED-0086**. The owner delegated ED numbering.

## Problem statement

A Session Assembly freezes its metadata snapshot (`session_title`, `participant_names`)
from the linked Program Expectation revision. If the schedule is wrong or missing a value,
the operator's only recourse today is to change the upstream schedule source. That can be
impossible, and it would rewrite what the schedule said. Rendering, which is next, needs
corrected titles and names.

## Verified current behavior

- `backend/app/contexts/assembly/session_contracts.py`:
  - `MetadataField` is `session_title` or `participant_names`.
  - `MetadataValue` allows only `source = "program_expectation"`, with `source_id` and
    `source_revision`.
  - `AssemblyRevision.metadata` is a frozen tuple.
- Migration `0013` table `assembly_metadata_snapshot`:
  - it has `CHECK (source = 'program_expectation')` and a foreign key to
    `program_expectation_revision`;
  - Assembly history tables are protected by the `assembly_history_is_immutable` trigger.
- Staleness is derived in `resolution.py:is_stale`, never stored.
- Routes live on `/api/v1/assembly` (`backend/app/api/v1/assembly.py`) with human-only,
  idempotent commands.

## Desired behavior

An operator can record, per Session, a provenance-tagged override value for a metadata
field, or clear it. New Assembly proposals take an overridden field from the latest active
override instead of the Program Expectation. Revisions show which source each value came
from. Existing revisions stay frozen, and they are reported stale when an override changes
after they were proposed.

## In scope

1. **Contracts.** An `AssemblyMetadataOverride` entry per Session and field:
   - fields: override ID, Session, field, action `set` or `clear`, `values` (for `set`),
     actor, `recorded_at` (timezone-aware, injected clock), reason, and a per-Session
     sequence;
   - append-only and immutable.

   `MetadataValue` gains the source `operator_override`, with `source_id` set to the
   override ID and `source_revision` to its sequence.
2. **Resolution.** This is pure and deterministic. For each field, the latest active
   `set` override wins; a `clear` reverts to the Program Expectation. Validation counts
   overridden values toward `missing_required_metadata`. Staleness: a revision becomes
   stale when the override that governs any field has changed since it was proposed. For
   each field, compare the override ID when the source is `operator_override`, and no
   override otherwise. Program Expectation refreshes do **not** make revisions stale.
   ED-0077 design decision 7 is preserved; the owner confirmed this on 2026-09-25.
3. **Service.** An idempotent `record_metadata_override` command, human authority only,
   using the existing `human_commands`. It rejects an empty `set`, an unknown field, a
   Session without an Assembly scope, and a stale expected sequence. Proposals use
   resolution.
4. **Persistence.** Additive migration `0014`: forward and reverse, with reverse applied
   before `0013` reverse.
   - It adds `assembly_metadata_override`: append-only, with the immutability trigger.
   - It adds `assembly_metadata_override_snapshot` (`revision_id`, `field`,
     `override_id`), holding the snapshot rows whose source is an override.
   - **Existing tables and constraints are not altered.** Program-sourced snapshot rows
     keep using `assembly_metadata_snapshot`, so a revision's metadata is the union of
     both tables.
   - In-memory and PostgreSQL repositories are updated.
5. **API.** `POST /api/v1/assembly/sessions/{session_id}/metadata-overrides`, idempotent
   and authenticated. `GET /api/v1/assembly/events/{event_id}/sessions/{session_id}/metadata-overrides`,
   bounded and paginated. Revision reads expose each value's source.
6. **Tests.** Behaviour-first tests for:
   - resolution precedence and clearing;
   - validation with overrides;
   - derived staleness when an override changes;
   - immutability, idempotency, and rejection cases;
   - PostgreSQL persistence and reconstruction;
   - the `0014` forward, reverse, and reapply;
   - that the Program Expectation is never written.
7. **Documentation.**
   - Glossary: the **Assembly metadata override**.
   - The persistence document, for `0014`.
   - The capability-layer Assembly section.

## Out of scope

- A participant identity model, any Program Expectation or Kernel change, or schedule-source
  write-back.
- Frontend UI for overrides. It is a later directive; this one covers API and domain.
- Rendering, and any automatic or ADR-0026 authority.

## Constraints

- Assembly reads Kernel and Program state and never writes them.
- No `UPDATE` or `DELETE` on override or snapshot rows.
- Timestamps are timezone-aware.
- Immutable contracts protect their nested values.
- White-label: placeholder identities in fixtures.

## Data or migration considerations

Migration `0014` is additive: two new tables and one trigger. Its reverse drops only those.
There is no backfill. Existing revisions keep their snapshot semantics.

## Acceptance criteria

- [x] Override contracts, resolution, service, repositories, and API are implemented as
  above, with human-only, idempotent commands.
- [x] Proposals take overridden fields from active overrides, and revisions expose each
  value's source.
- [x] Staleness is derived when an override changes. There is no stored staleness.
- [x] Migration `0014` is additive and reversible, and alters no existing table. It is
  covered by forward, reverse, and reapply tests.
- [x] No Kernel, Program Expectation, or Packaging Asset write or semantic change.
- [x] The full backend suite, Ruff, and Pyright pass on the host; the frontend is
  unchanged.

## Rollback

Revert the code, and apply the `0014` reverse. The reverse loses override history, and
revisions proposed with an override are then rebuilt without that override-sourced field.
Nothing else is affected.

## Completion record

- **Implemented revision:** branch `codex/ed-0086-assembly-metadata-overrides`. Codex
  implemented the slice. The owner applied the review fix, because Codex's re-run failed on
  authentication, and committed it.
- **Files changed:**
  - Assembly contracts, resolution, service, in-memory and PostgreSQL repositories, and
    routes;
  - migration registration and additive migration `0014`, which creates
    `assembly_metadata_override` and `assembly_metadata_override_snapshot` with immutability
    triggers and alters no existing object;
  - `tests/test_assembly_metadata_overrides.py`;
  - the migration-order expectations in the existing Assembly and Packaging tests;
  - the glossary, the persistence document, and the capability layer.
- **Review:**
  - The `directive-reviewer` returned ESCALATE. The plan's staleness wording, which was the
    owner's error, had overturned ED-0077 design decision 7: every Program refresh would
    have made revisions stale. Codex had implemented it literally and flipped ED-0077's
    assertion.
  - **The owner decided, on 2026-09-25,** to preserve decision 7. Metadata staleness now
    compares only the governing operator override for each field. The ED-0077 assertion is
    restored, the rollback note is added, and a PostgreSQL staleness assertion is added.
  - The re-review returned APPROVE.
- **Tests:** focused Assembly and Packaging suites pass, 116 tests including real
  PostgreSQL. Host full suite: **2,192 passed, 0 failed, 2 skipped**; Ruff and Pyright
  are clean.
- **Execution authority:** Green, plus the owner's decision above.
- **Deviations:** none beyond the corrected plan wording.
- **Remaining work:**
  - Producer UI for overrides, in a later directive.
  - Optional hardening: have the database enforce that an override snapshot references a
    `set` override from the same Session. Domain code guarantees this today.
