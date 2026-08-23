# Editorial Candidate Moment context

ED-0067 implements the first bounded Editorial capability: one human-declared,
unreviewed `EditorialCandidateMoment` on an authoritative Session timeline.

The context owns immutable candidate/location/provenance contracts, idempotent `Mark
Moment` orchestration, bounded per-Session reads, and explicit location-conflict
projections. PostgreSQL remains the only runtime authority. Migration 0008 supplies the
original immutable declaration record; migration 0010 adds append-only Session-boundary
location evaluations without changing Kernel tables or moving/deleting candidates.

The canonical HTTP surface is `/api/v1/editorial/*`. Existing
`/api/v1/demo/moments/*` routes and `app.contexts.editorial.moments` imports remain
deliberate transitional Demo compatibility backed by the same aggregate, service, and
repository. Their eventual deprecation/removal is a bounded future cleanup after the
Demo compatibility contract allows it; ED-0069 does not remove or redesign them.

Observed, derived, and inferred origins remain vocabulary only. Machine generation,
review decisions, Editorial Clip creation, workers, models, ranking, and automation are
not implemented here.
