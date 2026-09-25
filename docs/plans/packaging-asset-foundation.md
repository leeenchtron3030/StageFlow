# Packaging Asset foundation

## Status

Completed (2026-09-24). Focused and real-PostgreSQL validation passed in the sandbox; the
owner's full-suite host validation passed (see the addendum at the end). This is not a
production-event-readiness claim.

## Execution authority

- Classification: Green autonomous
- Authority evidence: [ADR-0030](../adr/ADR-0030-packaging-asset-identity.md) (Accepted
  2026-08-28), which selects a separate `PackagingAsset` aggregate owned by Assembly and
  fixes its minimum facts; step 5 of the accepted delivery sequence in the
  [post-Kernel capability layer](../architecture/post-kernel-capability-layer.md), whose
  capability-boundary table assigns Assembly ownership of packaging-asset references;
  ADR-0022 (media blobs remain outside PostgreSQL; raw paths are not product identity);
  ADR-0023 (Session and package authority Assembly must not alter).
- Implementation-ready: Yes. ADR-0030 resolved identity and ownership. The remaining
  choices below are implementation details bounded by that ADR and are recorded, not
  escalated.
- Required escalation or approval, if any: none for this slice. Stop and escalate if the
  work appears to require Assembly templates, proposals, or revisions (ED-0077), rendering,
  any change to Completed Media Asset semantics, Session or package authority, or a
  product-level track concept.

## Related findings or ADRs

- ADR: ADR-0030 (identity), ADR-0022, ADR-0023, ADR-0029 (rendering path this ultimately
  feeds).
- Engineering Directive: ED-0076. First slice of delivery-sequence step 5; ED-0077 (Session
  Assembly) follows and depends on it.

## Problem statement

ADR-0030 decided that curated packaging content — opening bumper, title card, sponsor
card, outro — gets its own `PackagingAsset` aggregate, distinct from Completed Media Asset.
Nothing implements it. Session Assembly cannot be designed against a concrete shape until
packaging assets exist, are revisioned, and carry human approval lineage.

## Verified current behavior

- `backend/app/contexts/packaging/` is an empty boundary reserved by ED-0002 for Packaging
  & Delivery. No Assembly bounded context exists.
- The word "assembly" already appears in production runtime code
  (`contexts/production/runtime/runtime_asset_assembly_plan.py`), meaning the mapping of
  Completed Media Asset manifests. The architecture's abstraction inventory classifies it
  as "not applicable to Session Assembly." These two meanings must stay distinct.
- `stageflow.completed_media_asset_registry` requires a `candidate_id` referencing
  `stageflow.media_candidate` and a `stage_id`. A Completed Media Asset can therefore only
  originate from Stage-source discovery. A pre-produced branding file cannot become one
  without being routed through recorder discovery — the path ADR-0030 rejected.
- No domain concept of a conference "track" exists anywhere in `backend/app/contexts/`.
- The latest migration is `0011_editorial_review_foundation`.

## Desired behavior

An operator can register a packaging asset, add immutable content revisions, and record
append-only human approval decisions against a specific revision. Current approval state
is derived from decision history. Approval of one revision never approves another.

## Design decisions recorded under ADR-0030

These are implementation choices within ADR-0030's boundary, documented so ED-0077 can
build on them:

1. **New `assembly` bounded context** at `backend/app/contexts/assembly/`, matching the
   architecture's capability-boundary table. The reserved `packaging` context stays
   reserved for Packaging & Delivery.
2. **Content reference is one of two kinds**, per ADR-0030's "references a stable media
   manifest or, where appropriate, a Completed Media Asset":
   - `external_content` — a stable content key, SHA-256 digest, byte size, and declared
     media type. This is the normal case for pre-produced branding. No filesystem path is
     stored or accepted.
   - `completed_media_asset` — a reference to an existing Completed Media Asset `asset_id`,
     for the less common case of packaging content that genuinely came from a recorder.
3. **Applicability is Event (required) plus optional Stage.** ADR-0030 lists "track"
   applicability, but no track concept exists in the domain. Inventing one here would be a
   product decision; it is deferred until a real track model exists.
4. **Roles** are a closed enum for this slice: `opening_bumper`, `title_card`,
   `sponsor_card`, `outro`. Session media is a placement role owned by Assembly (ED-0077),
   not a packaging asset.
5. **Approval actions** are `approve`, `reject`, and `revoke`. `revoke` lets an approval be
   withdrawn without deleting history. Current approval state per revision is derived.
6. **Completed Media Asset lifecycle coupling is not tracked in this slice.** A packaging
   revision that references a Completed Media Asset records the reference only.
   Resolvability and staleness of that reference are validated by Assembly (ED-0077),
   which is where ADR-0030 placed those semantics.

Implementation details recorded during ED-0076:

- Registration creates identity without content (current revision count zero). Revision
  commands append the next number with an expected-current-revision guard. Approval
  commands name both the target revision and expected current revision, permitting a
  fresh human decision to revoke an older revision without changing newer approval state.
- External content keys are opaque ASCII alphanumeric/hyphen/underscore tokens, 1–200
  characters, starting with an alphanumeric character; path, URI, extension, and escape
  syntax are rejected. Optional effective endpoints may be open-ended; when both are
  supplied, the end must be later than the start. Numeric facts fit signed PostgreSQL
  `bigint`. No file is opened, uploaded, or inspected.
- The canonical Editorial human-command digest helper is extracted unchanged into
  `app/shared/human_commands.py`. Migration `0012` owns a separate command-receipt table,
  following ED-0072's capability-local replay approach without widening the existing
  Kernel command-kind constraint. Receipts and immutable results commit together.
- Event-scoped assets and per-asset revision summaries have separate keyset pages
  (limits 1–100), total counts, continuation positions, and explicit API truncation.
  Revision summaries include the latest decision and a full decision count; current
  approval state derives from all decisions, never a truncated history subset.
- PostgreSQL serializes appends with the asset row lock and uses repeatable-read
  transactions for bounded batch projections. Database triggers protect revision and
  decision rows from accidental updates/deletes. Runtime composition uses PostgreSQL
  only; the in-memory repository is explicitly non-durable and intended for tests.

## In scope

- `backend/app/contexts/assembly/` with contracts, repository port, and service.
- `PackagingAsset`: stable identity, Event scope, optional Stage scope, name, role.
- `PackagingAssetRevision`: immutable, monotonically numbered per asset, carrying the
  content reference, optional measured duration, and optional timezone-aware effective
  interval.
- `PackagingAssetApprovalDecision`: append-only, carrying asset identity, **revision
  number**, actor, decision time, action, and reason.
- A derived approval-state projection per revision.
- Idempotent application commands for registration, revision, and approval decision,
  reusing the existing human-command idempotency digest mechanism, with stale-revision
  rejection.
- Additive PostgreSQL migration `0012` (forward and reverse).
- A bounded, paginated, Event-scoped read model, and authenticated routes on a new
  `/api/v1/assembly` router included behind the existing ED-0055 shared-secret dependency.
- Behavior-first tests at each changed boundary, including real-PostgreSQL persistence,
  replay, restart reconstruction, and migration reverse/reapply.

## Out of scope

- Assembly templates, Session Assembly, proposals, revisions, validation, approval flow,
  and metadata snapshots — all ED-0077.
- Rendering, encoding, upload, storage, or delivery of packaging content. Media blobs stay
  outside PostgreSQL and outside this slice.
- Any change to Completed Media Asset, media candidate, Session, package, or association
  semantics or tables.
- A track concept, participant model, or branding-template semantics.
- Automatic approval of any kind. Approval is human-only.
- Frontend work.

## Constraints

- Terminology: "Packaging Asset" and "Completed Media Asset" are different concepts and
  must stay so. Do not reuse or rename `runtime_asset_assembly_plan`. Update the domain
  glossary with the new terms.
- Immutability: revisions and approval decisions are append-only. No `UPDATE` or `DELETE`
  on revision or decision rows.
- Identity: no filesystem path is stored, accepted, or used as identity.
- Compatibility: purely additive. No existing table, route, or migration is altered.

## Implementation approach

1. Create the `assembly` context: contracts following existing immutability,
   timezone-aware timestamp, and `EntityId` conventions.
2. Add migration `0012` forward and reverse, creating only new tables and indexes, and
   register it in `migrations.py` and the bootstrap migration check, following how
   ED-0072 registered `0011`.
3. Implement the in-memory and PostgreSQL repositories, with append-only writes and a
   bounded batch projection that avoids N+1 reads.
4. Implement the idempotent commands with stale-revision rejection.
5. Add the authenticated `/api/v1/assembly` router with bounded limits and explicit
   truncation, matching ED-0068 and ED-0072 conventions.
6. Update the domain glossary, persistence, and capability-layer documentation.
7. Add behavior-first tests.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/assembly/` | New context: contracts, repository port, service |
| `backend/app/infrastructure/postgres/packaging_asset_repository.py` | PostgreSQL implementation (new) |
| `backend/app/infrastructure/postgres/sql/0012_*.sql` | Additive forward/reverse migration |
| `backend/app/infrastructure/postgres/migrations.py` | Register migration `0012` |
| `backend/app/bootstrap/event_mode_kernel.py` | Composition and migration check |
| `backend/app/api/v1/assembly.py`, `router.py` | Authenticated routes |
| `backend/tests/test_packaging_asset_foundation.py` | Behavior-first tests (new) |
| `docs/architecture/domain-glossary.md`, `persistence.md`, `post-kernel-capability-layer.md` | Directly affected documentation |

## Data or migration considerations

One additive migration `0012`, forward and reverse, creating only new tables and indexes.
It must not alter or drop anything created by earlier migrations. The runner reverses
`0012` before `0011`. Foreign keys to `business_event`, `stage`, and
`completed_media_asset_registry` are references only.

## Failure and recovery considerations

- A revision or approval command against a stale revision number fails explicitly.
- Exact replay returns the original result; a conflicting replay raises the established
  conflict error.
- An approval decision naming a revision that does not exist is rejected.
- A `completed_media_asset` content reference to an unknown `asset_id` is rejected at
  write time by foreign key. Later staleness is ED-0077's concern.

## Observability requirements

The bounded read model exposes per-asset current revision number, per-revision approval
state, and counts, without content digests beyond what identity requires, and without
paths or actor secrets.

## Test strategy

- Behavior-first: registration; revision numbering; each approval action; approval
  applying to exactly one revision; revoke preserving history; derived approval state;
  stale-revision rejection; exact and conflicting replay; both content-reference kinds;
  path rejection; bounded pagination and truncation.
- Real-PostgreSQL: persistence, restart reconstruction, and migration `0012`
  reverse/reapply.
- Full backend suite, Ruff, Pyright. Frontend unchanged.

## Acceptance criteria

- [x] A new `assembly` bounded context holds the Packaging Asset contracts, repository
  port, and service; the reserved `packaging` context is untouched.
- [x] `PackagingAssetRevision` is immutable and numbered per asset; content references are
  either `external_content` (key, SHA-256, size, media type) or `completed_media_asset`.
- [x] No filesystem path is stored, accepted, or used as identity.
- [x] `PackagingAssetApprovalDecision` is append-only, targets exactly one revision, and
  supports `approve`, `reject`, and `revoke`.
- [x] Approval state is derived per revision; approving one revision never approves
  another.
- [x] Stale-revision commands are rejected explicitly; replay is idempotent.
- [x] Migration `0012` is additive, reverses cleanly, and reverses before `0011`.
- [x] New routes sit behind the existing ED-0055 shared-secret dependency.
- [x] Domain glossary distinguishes Packaging Asset from Completed Media Asset.
- [x] Full backend suite, Ruff, and Pyright pass, apart from known environmental failures.
- [x] No Assembly template/proposal/revision, rendering, track, automatic approval, or
  Completed Media Asset/Session/package change is introduced.

## Rollback or reversal

Additive and independently reversible: reverse migration `0012` and remove the new context,
router, and tests. No existing behavior depends on it.

## Open questions

- None blocking. Track applicability is deferred until a domain track concept exists;
  the role enum can be extended by a later plan if real branding needs another role.

## Completion record

Implemented under ED-0076 as Green autonomous work on
`codex/ed-0076-packaging-asset-foundation`, left uncommitted for owner review.

### Delivered

- New Assembly contracts, synchronous service, repository port, and thread-safe in-memory
  test implementation; PostgreSQL remains the only composed runtime authority.
- Stable Event/optional Stage identity, both content-reference kinds, immutable per-asset
  revisions, attributable append-only approve/reject/revoke decisions, and per-revision
  derived approval state. Content changes and human approval remain separate meanings.
- Atomic capability-local command receipts using the extracted, unchanged canonical
  human-command digest helper; exact delayed replay, conflicting replay, stale revision
  rejection, and serialized concurrent appends.
- Additive migration `0012` with four new tables, indexes, append-only triggers, explicit
  reversal before `0011`, migration-runner registration, and bootstrap schema check.
- Authenticated `/api/v1/assembly` commands and bounded Event-scoped asset/revision pages.
- Glossary, persistence, capability-layer, ADR implementation index, directive index,
  and plan-index updates. No dependency, existing schema/table, runtime configuration
  file, frontend, reserved Packaging context, or Runtime asset assembly plan changes.
  Production code and bootstrap composition changed; the new schema/migration is additive.

### Validation actually run

All commands ran in `C:/Dev/StageFlow-codex`; backend commands used `backend/.venv`
via `uv run --no-sync`. Final results:

| Command | Result |
| --- | --- |
| `uv run --no-sync pytest tests/test_packaging_asset_foundation.py -p no:cacheprovider --tb=short` | 33 passed, 0 failed, 0 skipped; 1 existing Starlette/httpx deprecation warning |
| `uv run --no-sync pytest -p no:cacheprovider --tb=line -r s` | 1,725 passed, 0 test assertion failures, 1 skipped, 136 setup errors, 1 warning; not a green full-suite result |
| `uv run --no-sync ruff check . --no-cache` | All checks passed |
| `uv run --no-sync pyright` | 0 errors, 0 warnings, 0 informations; tool printed an available-version notice |
| `git diff --check` | Passed |
| `git diff` and `git diff --no-index -- NUL <new-file>` | Complete tracked/new-file diff reviewed; all changes belong to ED-0076 |

The focused PostgreSQL test actually ran against the supplied isolated test DSN. It
proved persistence and service reconstruction, original-result replay after newer state,
conflicting replay, concurrent revision serialization, both content-reference kinds,
unknown Completed Media Asset rejection, approval-history preservation, source-asset
preservation, bounded revision projection, and migration reverse/reapply. Earlier
implementation-time testing found the shared command-kind constraint rejected new kinds;
the final implementation uses its own additive receipt table, with no existing constraint
change. Subsequent focused runs passed (30, then 32, then final 33 cases).

The full-suite setup errors were `PermissionError [WinError 5]` accessing
`.codex-tmp/pytest-of-jmsln`. A prior full run reported 1,724 passed, 1 skipped, and
136 setup errors before the final additional text-validation test. A retry using
`--basetemp=C:/Dev/StageFlow-codex/.codex-tmp/ed0076-full-20260924-a` also encountered
permission errors and terminated during teardown without a final summary. No test
controls or filesystem permissions were changed to bypass this sandbox limitation.
The four known parametrized turnover checkpoint tests also errored at setup; their
em-dash assertions were not reached, so no pass/fail claim is made for those assertions.
The single full-suite skip is the POSIX descriptor-bound `scandir` test on Windows.

Process-local environment adjustments: cleared inherited `STAGEFLOW_API_SHARED_SECRET`
for every pytest process so the synthetic test fixture could supply its value; set
`TMP` and `TEMP` to the requested workspace `.codex-tmp`; redirected `UV_CACHE_DIR`
to `.codex-tmp/uv-cache` after the system uv cache was denied; cleared inherited
`VIRTUAL_ENV` so it could not refer to the owner's other worktree; disabled Python
bytecode and pytest/Ruff cache output for validation. Temporary output is ignored locally
inside `.codex-tmp` and retained for owner cleanup, as requested. No dependency install,
frontend check, git metadata write, commit, push, merge, or PR action ran.

### Review and remaining qualification

A deliberate self-review covered every changed/new file. Independent Codex review
identified a signed-bigint input/storage mismatch; matching domain/API bounds and
behavioral regression tests fixed it, and independent follow-up confirmed no remaining
correctness blockers. Self-review also added NUL text validation before PostgreSQL writes.

All implementation criteria are delivered. The validation criterion is qualified by the
explicit environmental exception above: the full suite is **not claimed to pass**.
Owner full-suite verification outside the sandbox remains required. No Yellow/Red
architecture decision appeared. Track applicability and Completed Media Asset lifecycle
validation remain deliberately deferred to their approved future scopes.

### Owner validation addendum (2026-09-24)

The owner re-ran the full backend suite on the host, outside the sandbox, with the
inherited `STAGEFLOW_API_SHARED_SECRET` and `VIRTUAL_ENV` cleared and `uv run --no-sync`:
**1,856 passed, 4 failed, 2 skipped.** The 4 failures are the known Windows
console-encoding cases in
`test_validation_controller.py::test_turnover_boundaries_emit_exact_live_operation_checkpoints`,
pre-existing and unrelated. Ruff and Pyright were clean. The sandbox temporary-directory
errors recorded above do not occur on the host. Owner review also confirmed: no
`UPDATE`/`DELETE` on revision or decision tables; the reserved `packaging` context and
`runtime_asset_assembly_plan` are untouched; migration `0012` alters no existing table
(its composite Stage/Event foreign key uses the unique constraint created in `0002`); and
the shared `human_command_digest` extraction is behaviour-preserving for the editorial
context.
