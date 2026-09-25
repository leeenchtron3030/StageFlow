# Session Assembly foundation

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: step 5 of the accepted delivery sequence in the
  [post-Kernel capability layer](../architecture/post-kernel-capability-layer.md), whose
  "Session Assembly", "Packaging assets", "Metadata-driven graphics", and "Proposal and
  approval" sections define `AssemblyTemplate`, `SessionAssembly`, `AssemblyRevision`, and
  `AssemblyApprovalDecision`, and state that rendering is a separate future Durable
  Operation; [ADR-0030](../adr/ADR-0030-packaging-asset-identity.md), under which
  Assembly owns packaging-asset applicability and an `AssemblyRevision` references
  approved packaging-asset **versions**; [ADR-0026](../adr/ADR-0026-policy-scoped-automatic-authority.md)
  (Accepted), which keeps every decision type manual until a policy is explicitly
  activated; ADR-0023 (Session and package authority Assembly must not alter). ED-0076
  landed the Packaging Asset contracts this plan builds on.
- Implementation-ready: Yes. The architecture resolves the concepts; the choices below are
  bounded implementation details.
- Required escalation or approval, if any: none. Stop and escalate if the work appears to
  require rendering, a render manifest, activating any automation policy, a participant
  identity model, operator metadata editing, or any change to Session, package, or media
  authority.

## Related findings or ADRs

- ADR: ADR-0030, ADR-0026, ADR-0023, ADR-0029, ADR-0031 (white-label: no event identity in
  templates or defaults).
- Engineering Directive: ED-0077. Builds on ED-0076.

## Problem statement

ED-0076 made packaging content durable, revisioned, and human-approved, but nothing
composes it with a Session. There is no way to describe how a Session's approved media
and its packaging content should be presented — which bumper, which title card, what
title and speaker names — and no approval point before any future render.

## Verified current behavior

- `backend/app/contexts/assembly/contracts.py` (ED-0076) defines `PackagingAsset` (Event
  scope, optional Stage, role), immutable `PackagingAssetRevision` numbered per asset, and
  append-only `PackagingAssetApprovalDecision`, with a derived per-revision
  `ApprovalState`.
- `SessionPackageState` in the Kernel is `assembling`, `ready_for_review`, `in_review`,
  `complete`, or `correction_required`, and each Session carries a `package_revision`.
- `stageflow.session_completion_asset` records, per completion decision, the exact asset
  membership (`asset_id`, `association_revision`) of a completed package revision.
- A Session carries an optional `program_expectation_id`; Program Expectation revisions
  supply a title and an unordered list of speaker display strings.
- The latest migration is `0012_packaging_asset_foundation`.

## Desired behavior

An operator can define an Assembly template, propose a Session Assembly against a
Session's completed package revision, see a deterministic validation result, and approve
or reject a valid proposal. Approved Assemblies are reproducible: they pin the package
revision, packaging-asset revisions, and a metadata snapshot. Later changes make an
Assembly visibly stale rather than silently altering it.

## Design decisions

1. **Eligibility.** A proposal requires the Session's package to be `complete` at a
   specific `package_revision`. The proposal pins that revision and its completion
   membership from `session_completion_asset`. Assembly never reads live, unapproved
   association state.
2. **Templates** are immutable and versioned by `(template_key, version)`, Event-scoped,
   and consist of an ordered list of **slots**. Each slot has a placement role —
   `opening_bumper`, `title_card`, `session_media`, `sponsor_card`, or `outro` — and a
   required flag. A template also declares which metadata fields it requires
   (`session_title`, `participant_names`). Template keys and names are configuration data,
   never code defaults (ADR-0031).
3. **Packaging binding is deterministic and conservative**, mirroring association policy.
   For each packaging slot, the candidates are *approved* revisions of Packaging Assets
   with that role whose Event matches, whose Stage is unset or matches the Session's
   Stage, and whose effective interval, if any, covers the Session's authoritative start.
   Exactly one candidate binds automatically; zero or several leave the slot unresolved.
   A proposal may name explicit bindings to resolve ambiguity, and an explicit binding
   must itself be an eligible candidate.
4. **Session media slot** references the pinned completion membership in timeline order.
   No media is read, decoded, or processed.
5. **Metadata snapshot** is frozen per revision from the Session's linked Program
   Expectation revision: title and speaker display strings, each recording its source and
   source revision. Missing required metadata is a validation failure for that template;
   it never affects package completeness. Operator overrides are out of scope.
6. **Revisions.** Each proposal for a Session creates a new, numbered, immutable
   `AssemblyRevision` that supersedes the previous one. Revisions store their validation
   result: `valid`, or `invalid` with typed reason codes (unresolved required slot,
   ambiguous binding, missing required metadata, ineligible package, and so on).
7. **Staleness is derived, not stored.** A revision is stale when the Session's current
   package revision has moved past the pinned one, or when any bound packaging revision is
   no longer approved. Staleness is computed at read time; stored rows never change.
8. **Approval.** Append-only `AssemblyApprovalDecision` (`approve` or `reject`) against
   one revision. Approval requires the revision to be valid, current, and not stale. The
   decision records authority kind `human`. No automation policy is activated.

## In scope

- Contracts, repository port, service, and in-memory and PostgreSQL repositories in the
  existing `assembly` context.
- `AssemblyTemplate` creation; `SessionAssembly` proposal producing `AssemblyRevision`s
  with bindings, pinned membership, metadata snapshot, and validation result;
  `AssemblyApprovalDecision`.
- Derived current-revision, staleness, and approval projections.
- Idempotent commands reusing `app/shared/human_commands.py`, with stale-revision
  rejection.
- Additive migration `0013` (forward and reverse), reversing before `0012`.
- Bounded, paginated, Event-scoped reads on the existing `/api/v1/assembly` router.
- Documentation updates and behavior-first tests.

## Out of scope

- Rendering, `RenderRequest`, render manifests, output-relative timing, graphics
  generation, or any media processing.
- Operator editing or overriding of metadata; a participant identity or ordering model.
- Activating any ADR-0026 automation policy; approval is human-only.
- Any change to Session, package, association, Completed Media Asset, or Packaging Asset
  semantics or tables.
- Track applicability (no domain track concept exists).
- Frontend work.

## Constraints

- Reproducibility: every revision pins exact package revision, membership, packaging
  revisions, and metadata source revisions. Nothing is resolved "live" after creation.
- Immutability: no `UPDATE` or `DELETE` on template, revision, binding, snapshot, or
  decision rows.
- Authority: Assembly reads Kernel and Packaging Asset state and never writes it.
- White-label: no event or organizer identity in code defaults or fixtures.
- Terminology: "Session Assembly" is distinct from `runtime_asset_assembly_plan`; update
  the glossary.

## Implementation approach

1. Add template, slot, binding, snapshot, revision, validation, and decision contracts.
2. Add migration `0013` and register it as ED-0076 registered `0012`.
3. Implement repositories with append-only writes and bounded batch projections.
4. Implement the binding resolver and validator as pure, deterministic functions with
   exhaustive tests.
5. Implement idempotent commands and derived staleness.
6. Add routes and documentation.
7. Add behavior-first tests.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/assembly/` | Session Assembly contracts, resolver, validator, service |
| `backend/app/infrastructure/postgres/session_assembly_repository.py` | PostgreSQL implementation (new) |
| `backend/app/infrastructure/postgres/sql/0013_*.sql` | Additive forward/reverse migration |
| `backend/app/infrastructure/postgres/migrations.py`, `bootstrap/event_mode_kernel.py` | Register `0013`; composition |
| `backend/app/api/v1/assembly.py` | Session Assembly routes |
| `backend/tests/test_session_assembly_foundation.py` | Behavior-first tests (new) |
| `docs/architecture/domain-glossary.md`, `persistence.md`, `post-kernel-capability-layer.md` | Directly affected documentation |

## Data or migration considerations

One additive migration `0013`, creating only new tables and indexes, reversing before
`0012`. Foreign keys to Session, completion history, and Packaging Asset revisions are
references only.

## Failure and recovery considerations

- Proposing against a Session whose package is not `complete` records an `invalid`
  revision with an ineligibility reason rather than failing silently, so the operator sees
  why.
- Approving a stale, invalid, or superseded revision is rejected explicitly.
- Exact replay returns the original result; conflicting replay raises the established
  conflict error.

## Observability requirements

Reads expose per-Session current revision, validation state and reason codes, staleness,
and approval state, without media paths or actor secrets.

## Test strategy

- Pure resolver and validator: each slot outcome (bound, unresolved, ambiguous, explicit
  binding valid and invalid), Stage and effective-interval applicability, approved-only
  candidates, metadata present and missing, ineligible package.
- Service: revision numbering and supersession; staleness after a package revision advance
  and after a packaging-revision revoke; approval preconditions; replay.
- Real-PostgreSQL persistence, restart reconstruction, and `0013` reverse/reapply.
- Full backend suite, Ruff, Pyright.

## Acceptance criteria

- [ ] Templates are immutable, versioned, Event-scoped, with ordered slots and declared
  required metadata.
- [ ] Proposals require a `complete` package and pin its revision and completion
  membership.
- [ ] Packaging binding is deterministic: exactly one eligible approved candidate binds;
  zero or several leave the slot unresolved unless a valid explicit binding is given.
- [ ] Each revision freezes its bindings, membership, and metadata snapshot with source
  revisions.
- [ ] Validation results carry typed reason codes; missing metadata never affects package
  completeness.
- [ ] Staleness is derived at read time from package-revision advance or packaging
  revocation; stored rows never change.
- [ ] Approval is human, append-only, and only for valid, current, non-stale revisions.
- [ ] Migration `0013` is additive and reverses before `0012`.
- [ ] No rendering, metadata editing, automation activation, or Kernel/Packaging Asset
  mutation is introduced.
- [ ] Full backend suite, Ruff, and Pyright pass, apart from known environmental failures.

## Rollback or reversal

Additive: reverse migration `0013` and remove the new code. Packaging Assets and the
Kernel are untouched.

## Open questions

- None blocking. Operator metadata overrides and a participant model are deliberate later
  slices.

## Completion record

_(To be filled in by whoever implements this plan.)_
