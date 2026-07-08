# Media Artifact Adapter

ED-0017 adds backend-only Media Artifact Adapter contracts.

A Media Artifact Adapter reports that media-related artifacts exist, changed, finalized, failed, or became unavailable. It reports availability only.

## Runtime Flow

Media Artifact Source -> Media Artifact Adapter -> Production Event -> Dispatcher -> Interpreter -> Observation

Recording activity and media artifact availability are separate concerns. Recording System Adapters report recording activity. Media Artifact Adapters report artifact availability.

## Production Event Mapping

Media artifact events may be mapped only to generic Production Event types:

- `media_file_created`
- `media_file_finalized`
- `media_file_failed`
- `system_status_changed`

`ProductionEventType` does not yet include `media_file_updated` or `media_file_deleted`, so `updating`, `deleted`, and `unknown` artifact statuses map to `system_status_changed` for now.

## Exclusions

Reporting an artifact is not ingestion.

This package does not implement filesystem watching, provider-specific adapters, media ingestion, artifact persistence, chunk registration, media validation, codec inspection, duration extraction, transcript parsing, thumbnail extraction, OCR, AI analysis, dispatch execution, APIs, queues, workers, or frontend behavior.

The mapping does not create Observations, Evidence, Findings, Operational Products, RecordingBlocks, TimelinePositions, or TimelineRanges.
