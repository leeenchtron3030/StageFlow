# Recording System Adapter

ED-0016 adds backend-only Recording System Adapter contracts.

A Recording System Adapter represents an external or internal system capable of reporting continuous recording activity to StageFlow.

## Runtime Flow

Recording System -> Recording System Adapter -> Production Event -> Dispatcher -> Interpreter -> Observation

The adapter reports recording activity by emitting generic Production Events. It does not know how StageFlow interprets or reasons about those events.

## Adapter-Level Events

`RecordingSessionEvent` is adapter-level input before conversion into a `ProductionEvent`.

It may describe generic recording activity such as recording started, paused, resumed, stopped, failed, or status changed.

## Production Event Mapping

Recording session events may be mapped only to generic Production Event types:

- `recording_block_started`
- `recording_block_ended`
- `recording_block_status_changed`
- `system_status_changed`

The mapping does not create RecordingBlocks, TimelineRanges, TimelinePositions, Observations, Evidence, Findings, or Operational Products.

## Exclusions

This package does not implement provider-specific adapters, filesystem watching, media ingestion, media file detection, chunk registries, codec inspection, timeline construction, dispatch execution, persistence, APIs, queues, workers, transcription, OCR, AI analysis, or frontend behavior.
