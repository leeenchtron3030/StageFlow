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

When `[local_media_timing]` is enabled, each Demo reconciliation cycle selects at most
100 registered assets of the Event with no `media_timing` operation, in asset-ID order.
Selection includes startup and recovery registrations and requires no Session association.
Durable enqueues remove successful assets from subsequent selections, so later cycles
advance without a process-local cursor and restart safely. Any existing timing operation,
including terminal failure, excludes the asset. Concurrent selection remains idempotent
by the existing work key. Failed enqueues remain eligible for the next cycle; a failed
selection or enqueue reports `media_timing_enqueue_failed` without stopping transcription.
An absent or disabled section performs no timing selection or enqueue.

The ffprobe adapter uses `-format_whitelist` with
`mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mxf,wav` alongside its existing file-only protocol
restriction. Container contents, rather than a misleading filename suffix, determine
whether the demuxer is admitted.

This package never qualifies a recorder, mutates media/Session/package authority, or
changes association or membership policy. It introduces no scheduler, broker, provider
SDK, or distribution dependency.
