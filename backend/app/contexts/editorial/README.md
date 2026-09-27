# Editorial context

ED-0067 implements the first bounded Editorial capability: one human-declared,
initially unreviewed `EditorialCandidateMoment` on an authoritative Session timeline.
ED-0072 adds the human review boundary: append-only review decisions, derived review
state, immutable `EditorialClip` lineage for approvals, and an Event-scoped bounded
review queue.

The context owns immutable candidate/location/provenance contracts, idempotent `Mark
Moment` and review orchestration, bounded per-Session and Event queue reads, explicit
location-conflict projections, and append-only review history. PostgreSQL remains the
only runtime authority. Migration 0008 supplies the original immutable declaration
record; migration 0010 adds append-only Session-boundary location evaluations; migration
0011 adds only review-decision and Editorial Clip tables. None changes Kernel tables or
moves/deletes candidates.

The canonical HTTP surface is `/api/v1/editorial/*`. Existing
`/api/v1/demo/moments/*` routes and `app.contexts.editorial.moments` imports remain
deliberate transitional Demo compatibility backed by the same aggregate, service, and
repository. Their eventual deprecation/removal is a bounded future cleanup after the
Demo compatibility contract allows it; ED-0069 does not remove or redesign them.

Human-invoked transcript phrase derivation now produces `derived` candidates through
`EditorialDerivationService`. Immutable Event-scoped phrase-list versions and derivation
runs live in Editorial; transaction-bound readers supply associated assets, latest
complete transcript evidence and latest active advisory timing evidence. Matching and
placement are pure domain functions. Migration `0019` stores these aggregates, command
receipts and candidate provenance, preserving the declared-row constraints. Exact
command replay and identical input sets return the original run.

The existing review actions and Clip creation also handle derived candidates. Candidate
and queue reads expose origin and evidence provenance, including timing qualification.
Observed and inferred origins remain vocabulary only. Automatic derivation, models,
automatic review authority, rendering, export, publishing, and package or Session-boundary
changes are not implemented here.
