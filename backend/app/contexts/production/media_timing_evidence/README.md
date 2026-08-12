# Media Timing Evidence

This package owns the provider-neutral advisory timing-evidence aggregate approved by
ADR-0027. It preserves immutable Observed facts, Derived candidate intervals, recorder
profile qualification state, inspection provenance, asset-scoped revisions, and exact
application replay.

It does not inspect media, parse FFmpeg output, qualify a recorder, mutate Session or
package authority, change association policy, or implement a worker/scheduler.
