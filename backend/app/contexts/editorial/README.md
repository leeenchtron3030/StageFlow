# Editorial Candidate Moment context

ED-0067 implements the first bounded Editorial capability: one human-declared,
unreviewed `EditorialCandidateMoment` on an authoritative Session timeline.

The context owns immutable candidate/location/provenance contracts, idempotent `Mark
Moment` orchestration, bounded per-Session reads, and explicit location-conflict
projections. PostgreSQL remains the only runtime authority. Migration 0008 supplies the
original immutable declaration record; migration 0010 adds append-only Session-boundary
location evaluations without changing Kernel tables or moving/deleting candidates.

Observed, derived, and inferred origins remain vocabulary only. Machine generation,
review decisions, Editorial Clip creation, workers, models, ranking, and automation are
not implemented here.
