# Production Observation

## Purpose

This package contains the foundational observation contracts introduced by ED-0006.

An Observation records something noticed on a production timeline. It does not decide what that observation means.

## Timeline vs Observation

Timeline primitives describe where things happen:

- `TimelinePosition`
- `TimelineRange`

Observation primitives describe what was noticed at that point or over that range:

- `Observation`
- `ObservationType`
- `ObservationSource`
- `ObservationConfidence`
- `ObservationLocation`

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
