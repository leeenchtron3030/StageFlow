# Production Observation

## Purpose

This package contains the foundational observation contracts introduced by ED-0006 and refined by ED-0025.

An Observation records something objectively noticed by StageFlow. It does not decide what that observation means.

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
