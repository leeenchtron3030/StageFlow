# Production Context

## Purpose

The Production Context owns live-event production state and the temporal model for continuous stage recordings.

## ED-0005 Scope

ED-0005 adds foundational production timeline contracts only. It does not implement ingestion, transcription, workers, persistence, APIs, rendering, packages, or frontend behavior.

## Continuous Recording Blocks

Real event production often records long stage blocks rather than one file per scheduled session. A `RecordingBlock` represents one continuous stage recording period, such as a morning block or afternoon block.

A `RecordingBlock` is not a session.

## Session Windows

A `SessionWindow` represents a proposed or verified media range within one `RecordingBlock` that corresponds to scheduled session information.

This lets StageFlow reconcile planned schedule data with actual observed media time.

## Scheduled Time vs Media Time

Scheduled time belongs to external schedule sources.

Media time belongs to the continuous recording timeline and is represented by `TimelinePosition` and `TimelineRange` offsets.

These concepts must not be collapsed.

## Why Files And Chunks Are Excluded

ED-0005 intentionally excludes file paths, media chunk identifiers, codec details, and ingestion mechanics. Those belong to later ingestion and media directives.

The timeline contracts must be able to represent a session range even if that range crosses future source media chunk boundaries.

## Future Relationships

Future directives for ingestion, transcript generation, editorial review, rendering, packaging, and delivery should depend on these timeline contracts rather than treating raw recording files as sessions.
