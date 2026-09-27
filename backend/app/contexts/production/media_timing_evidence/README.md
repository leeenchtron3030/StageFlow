# Media Timing Evidence

This package owns the provider-neutral advisory timing-evidence aggregate approved by
ADR-0027. It preserves immutable Observed facts, Derived candidate intervals, recorder
profile qualification state, inspection provenance, asset-scoped revisions, and exact
application replay.

ADR-0033 adds the immutable inspection profile and sanitized-field derivation policy,
idempotent asset enqueue command, and provider-neutral worker orchestration here.
The ffprobe process and JSON parsing stay in `infrastructure/media_timing`; the optional
CPU process is composed by `app.demo.media_timing_worker`. Results are written only
through the existing application boundary and remain unqualified and advisory.

This package never qualifies a recorder, mutates media/Session/package authority, or
changes association or membership policy. It introduces no scheduler, broker, provider
SDK, or distribution dependency.
