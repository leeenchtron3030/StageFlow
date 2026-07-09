# Transcript Source Adapter

ED-0020 adds backend-only Transcript Source Adapter contracts.

A Transcript Source Adapter reports that transcript-related artifacts, segments, or text updates exist. It reports availability only.

## Runtime Flow

Transcript Source -> Transcript Source Adapter -> Production Event -> Dispatcher -> Interpreter -> Observation

Transcript sources provide words. They do not provide meaning. The adapter preserves that separation by emitting generic Production Events and leaving text interpretation to later interpreters and reasoning.

## Production Event Mapping

Transcript segment events may be mapped only to generic Production Event types:

- `transcript_segment_available`
- `system_status_changed`

`created`, `updated`, and `finalized` segment statuses map to `transcript_segment_available`. `failed`, `deleted`, and `unknown` map to `system_status_changed`.

## Exclusions

Reporting transcript activity is not transcription.

This package does not implement transcription execution, audio processing, model calls, diarization, language detection, transcript file creation, source APIs, persistence, queues, workers, dispatch execution, frontend behavior, or text interpretation.

The mapping does not create Observations, Evidence, Hypotheses, Findings, Operational Products, Sessions, RecordingBlocks, TimelinePositions, or TimelineRanges.
