# ADR-0030: Packaging Asset identity

## Status

Accepted

## Date

2026-08-28

## Context

Session Assembly composes branding and production content into a presentable output:
opening bumper, title card, Session media, sponsor card, outro. Production media already
has a durable identity — the Completed Media Asset, which proves a file is finalized and
categorically safe for StageFlow to read (ADR-0020, ED-0048). Branding content has none.

The accepted
[post-Kernel capability layer](../architecture/post-kernel-capability-layer.md) recorded
this as a Yellow decision and named its own recommended shape, but explicitly deferred it:
"The exact aggregate ownership and whether all content must first become a Completed Media
Asset require explicit approval before the Assembly persistence design." The ADR index has
carried "Packaging asset identity" as an unresolved candidate since.

That deferral has become the binding constraint on the roadmap. Assembly is step 5 of the
accepted delivery sequence, rendering is a later consumer of Assembly, and packaging speed
is a stated product priority. None of that work can begin while this decision is open.

The distinction driving the decision is that a Completed Media Asset and a packaging asset
answer different questions. A Completed Media Asset answers *is this file finished and safe
to read* — a determination about physical media, made by readiness policy from observed
facts. A packaging asset answers *is this content approved for use in this role, for this
Event, during this period* — a curatorial and editorial determination made by a human.
A sponsor card being approved for use is not the same event as a recording becoming safe
to read, and neither implies the other.

## Decision

StageFlow adopts a separate `PackagingAsset` aggregate, distinct from Completed Media
Asset, as the identity for curated packaging content.

- A `PackagingAsset` has its own stable StageFlow identity and immutable content
  revisions. A content revision references a stable media manifest or, where appropriate,
  an existing Completed Media Asset. It does not require that all packaging content first
  become a Completed Media Asset.
- Minimum packaging-asset facts are: ID; name; role/category; content reference and
  version; optional measured duration; Event/Stage/track applicability; effective
  interval; and approval/trust state with decision lineage.
- Approval of a packaging asset is a human decision with recorded lineage, separate from
  and never implied by media completion or readiness.
- Media blobs remain outside PostgreSQL. Raw filesystem paths are not product identity,
  consistent with ADR-0022.
- The Assembly context owns packaging-asset approval and applicability. Completed Media
  Asset remains the authority for production-media completion and readiness and gains no
  curatorial semantics from this decision.
- An `AssemblyRevision` references approved packaging-asset **versions**, so an approved
  Assembly remains reproducible when a packaging asset is later revised. Revising a
  packaging asset does not retroactively alter an existing Assembly revision.

This decision resolves the identity and ownership question only. Assembly templates,
proposals, revisions, validation, and approval flow remain to be designed and implemented
under their own bounded plan, now unblocked by this ADR.

## Alternatives

### Reuse Completed Media Asset for packaging content

Rejected. It requires every bumper, card, and sting to pass through production-media
readiness evaluation, which is designed to answer a question about recorder output that
does not apply to a pre-produced branding file. More seriously, it would either overload
Completed Media Asset with curatorial approval/applicability/effective-interval semantics
it does not have, or leave those facts homeless. Both outcomes conflate "finished
recording" with "approved for use," which is precisely the distinction the accepted
architecture identified as real.

### Require packaging content to become a Completed Media Asset first, then decorate it

Rejected as the general rule, though the decision explicitly permits a packaging-asset
content revision to *reference* a Completed Media Asset where that is genuinely the
right composition. Mandating it universally adds a required step with no benefit for
content that never came from a recorder and was never in a stabilizing state.

### Defer the decision again

Rejected. Deferral has already blocked Assembly, rendering, and the entire packaging-speed
workstream. The architecture's own recommended shape has been stable and unchallenged
since it was written; there is no new evidence to wait for.

### Model packaging assets as configuration rather than a domain aggregate

Rejected. Approval state, decision lineage, effective interval, and immutable content
revisions are durable domain facts with authority consequences, and Assembly revisions
must reference exact versions to stay reproducible. Configuration has no revision identity
or approval lineage and cannot carry those requirements.

## Consequences

### Positive

- Unblocks the Assembly foundation, and therefore rendering — the largest remaining
  segment of the accepted delivery sequence.
- Keeps Completed Media Asset semantically clean: it continues to mean exactly one thing.
- Human approval of packaging content is explicit, attributable, and separately recorded,
  consistent with the project's human-authority principle.
- Version-referencing keeps approved Assemblies reproducible across packaging-asset
  revisions.

### Negative

- Introduces a new aggregate and its persistence, adding surface area to the domain.
- Two content-identity concepts now exist; documentation and future contributors must keep
  the distinction clear, and the domain glossary should carry it explicitly.
- Where a packaging asset references a Completed Media Asset, that composition needs a
  defined lifecycle relationship — this ADR permits the reference but does not specify its
  failure/supersession semantics, which belongs to the Assembly persistence plan.
- No implementation exists. This is identity and ownership only; the Assembly plan must
  still resolve template resolution, validation, and approval flow.

## Validation

None yet. This ADR resolves a deferred identity/ownership question ahead of
implementation, consistent with this repository's practice of using ADRs to govern future
work rather than to record completed work. The Assembly foundation plan that follows will
carry its own acceptance criteria and tests.

## Related documents

- [Post-Kernel capability layer](../architecture/post-kernel-capability-layer.md) —
  Session Assembly, the "Packaging assets" section this ADR resolves, and delivery
  sequence step 5.
- [ADR-0022](ADR-0022-postgresql-authoritative-operational-store.md) — media blobs remain
  outside PostgreSQL.
- [ADR-0023](ADR-0023-session-authority-and-completion.md) — Session and package authority
  that Assembly layers on and must not alter.
- [ADR-0029](ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md) — the rendering
  encode path this decision ultimately unblocks.
- ADR index "Unresolved ADR candidates" — this ADR removes the "Packaging asset identity"
  row.
