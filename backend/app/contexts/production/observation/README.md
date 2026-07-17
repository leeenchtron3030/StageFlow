# Production Observation

## Purpose

This package contains the foundational observation contracts introduced by ED-0006,
refined by ED-0025, and given first-class lineage and operational context by ED-0043.

An Observation records something objectively noticed by StageFlow. It does not decide what that observation means.

## Provenance And Context

`ObservationProvenance` preserves the exact source Production Event ID, source Event
type, source occurrence time, stable interpreter identity, applied rule identity when
applicable, and an optional producer identifier. References remain ID-only; the source
Production Event object is never embedded.

`ObservationContext` preserves known stage, recording block, correlation, scheduled
activity, transcript stream, media artifact, and timeline context. Context may be
partial. Missing identifiers remain absent and one context field never substitutes for
another.

First-class `Observation.context` values are authoritative. ED-0045 enforces the order
`Observation.context` -> documented legacy field/location -> documented metadata ->
absent. A conflicting legacy field remains available for centralized diagnostic
resolution but cannot overwrite the first-class value. Builders consume that centralized
resolution and do not merge incompatible known context.

Legacy callers may continue constructing Observations without provenance or an explicit
context; compatible legacy fields are projected into `Observation.context`. Every
Observation produced by a concrete interpreter must include provenance. Observation
semantics, confidence, source, time, and notes are unchanged by context resolution.

## Time Semantics

`ObservationProvenance.source_event_occurred_at` records when the source reported the
Event occurred. `Observation.observed_at` records when StageFlow produced or recorded
the Observation. They may be equal, but neither is substituted for the other. Existing
timezone information is preserved, including legacy naive timestamps.

## Location Anchors

`ObservationLocation` describes where or when an Observation is anchored.

Media timeline location is one kind of Observation location, not the only kind. Recorded media remains StageFlow's primary observable reality, but not every Observation begins with a precise media offset.

Approved initial location kinds are:

- `timeline_position`
- `timeline_range`
- `recording_block`
- `wall_clock`
- `stage`
- `composite`
- `unknown`

Unknown location must be explicit. Observation location is not optional by accident.

## Timeline vs Observation

Timeline primitives describe media offsets inside continuous recording blocks. Observation primitives describe what was noticed and where or when that notice is anchored.

Recording activity, schedule boundaries, timer events, or operator input may be anchored to a recording block, wall-clock timestamp, stage, composite context, or explicit unknown location before a precise media timeline offset is available.

## Sources

Observations may come from humans, transcripts, audio, graphics, schedules, livestream systems, or generic system processes.

Source names describe categories, not providers or tools.

## Not Conclusions

Observations do not create timeline conclusions by themselves. Future reasoning directives may use many observations to propose or verify production timeline conclusions.

Do not add conclusion-oriented concepts such as session starts, session ends, clip candidates, package readiness, or reviewer decisions here.

## Out Of Scope

- AI analysis.
- Detection implementation.
- Ingestion.
- Transcription.
- File paths.
- Media chunks.
- Persistence.
- APIs.
- UI behavior.
