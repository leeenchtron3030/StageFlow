# Production Timeline

## Purpose

This package contains the foundational production timeline contracts introduced by ED-0005.

## Core Model

StageFlow distinguishes continuous recording media from scheduled session metadata.

```text
Stage
↓
Recording Block
↓
Continuous Media Timeline
↓
Session Window
↓
Transcript / Editorial / Rendering / Package
```

## What Belongs Here

- `RecordingBlock`
- `TimelinePosition`
- `TimelineRange`
- `ScheduleReference`
- `SessionWindow`
- Generic timeline statuses approved by ED-0005

## What Does Not Belong Here

- File paths.
- Media chunks.
- Codec details.
- vMix folder watching.
- Transcription.
- AI boundary detection.
- Reviewer workflows.
- Persistence or API behavior.
- Provider-specific schedule names.

## Scheduled Time vs Media Time

Scheduled time comes from an external schedule source.

Media time is represented by offsets within a continuous `RecordingBlock`. `TimelinePosition` and `TimelineRange` model media time without knowing anything about files or chunks.

## Future Relationships

Future ingestion, transcript, editorial, rendering, and packaging directives should use these contracts to reference where a session occurred on a continuous stage recording timeline.
