# Production Context

## Purpose

The Production Context owns live-event production state and the temporal model for continuous stage recordings.

## Timeline Primitives

ED-0005 adds foundational production timeline contracts only. It does not implement ingestion, transcription, workers, persistence, APIs, rendering, packages, or frontend behavior.

Timeline primitives describe where things happen on a continuous recording timeline.

## Production Events

ED-0013 adds foundational production event contracts only.

Production Events are the runtime boundary where outside-world inputs and internal adapter emissions enter StageFlow. A Production Event records that something happened according to a source, with an `occurred_at` timestamp for source time and a `received_at` timestamp for StageFlow receipt time.

Production Events are not Observations. They do not decide what an input means, do not create Observations, and do not create reasoning artifacts or Operational Products.

Adapters will later emit Production Events, and a future Observation Engine may interpret them into Observations. ED-0013 does not implement adapters, ingestion, webhooks, file watching, transcription, OCR, AI analysis, observation generation, persistence, APIs, queues, workers, or frontend behavior.

Production Events remain provider-agnostic. Event types, sources, references, and payloads use generic runtime language instead of provider or tool names.

## Observation Primitives

ED-0006 adds foundational production observation contracts only.

Observation primitives describe what was noticed at a timeline point or range. Observations may come from humans, transcripts, audio, graphics, schedules, livestream systems, or other generic sources.

Reasoning will later decide what observations mean. Observations do not create timeline conclusions by themselves.

## Evidence Primitives

ED-0007 adds foundational production evidence contracts only.

Evidence organizes observation references into support for a possible future conclusion. Evidence is still not a conclusion, and it must remain separate from reasoning and proposal generation.

## Hypothesis Primitives

ED-0008 adds foundational production hypothesis contracts only.

Hypothesis primitives express possible meaning based on evidence. A hypothesis is a belief, not an action. Proposal generation and verification come later.

## Finding Primitives

ED-0009 adds foundational production finding contracts only.

Findings are the first human-reviewable reasoning artifacts. A finding says what StageFlow found that may deserve attention, but it does not decide whether the finding is correct. Verification follows in ED-0010.

## Verification Protocol

ED-0010 adds foundational production verification protocol contracts only.

Verification decisions record append-only judgment about findings. Verification does not mutate findings, does not create finding status, and does not produce operational products.

## Operational Products

ED-0011 adds foundational production operational product contracts only.

Timeline, Observation, Evidence, Hypothesis, Finding, and Verification form the reasoning layer. Operational Products begin the execution layer.

Operational products are downstream of verified reasoning and stay traceable to findings and verification decisions. Specific product types will be implemented by later directives.

## Session Window Products

ED-0012 adds the first specialized Operational Product: the Session Window Product.

A `RecordingBlock` is continuous media, such as a full morning or afternoon recording for one stage.

A `ScheduleReference` points to planned session data from an external schedule source. It is not owned by Production and does not create a Session aggregate.

A `TimelineRange` identifies the actual media offsets inside a `RecordingBlock`.

A `SessionWindowProduct` is the verified product connecting planned schedule information to actual media time. It references the generic `OperationalProduct` by ID only, keeps ID-only lineage to Findings and Verification Decisions, and carries boundary confidence for the start and end of the verified media window.

Packaging comes later. Session Window Products may become inputs to packaging workflows, but ED-0012 does not create packages, clips, rendering, persistence, APIs, workers, queues, or frontend behavior.

## Continuous Recording Blocks

Real event production often records long stage blocks rather than one file per scheduled session. A `RecordingBlock` represents one continuous stage recording period, such as a morning block or afternoon block.

A `RecordingBlock` is not a session.

## Session Windows

A `SessionWindow` represents a proposed or verified media range within one `RecordingBlock` that corresponds to scheduled session information.

This lets StageFlow reconcile planned schedule data with actual observed media time.

ED-0012 leaves the ED-0005 `SessionWindow` timeline contract in place. The newer `SessionWindowProduct` is the specialized product downstream of verified reasoning. Future architecture work should decide whether the ED-0005 contract should be renamed, deprecated, or folded into the product model once full Session modeling is specified.

## Scheduled Time vs Media Time

Scheduled time belongs to external schedule sources.

Media time belongs to the continuous recording timeline and is represented by `TimelinePosition` and `TimelineRange` offsets.

These concepts must not be collapsed.

## Why Files And Chunks Are Excluded

ED-0005 intentionally excludes file paths, media chunk identifiers, codec details, and ingestion mechanics. Those belong to later ingestion and media directives.

The timeline contracts must be able to represent a session range even if that range crosses future source media chunk boundaries.

## Future Relationships

Future directives for ingestion, transcript generation, editorial review, rendering, packaging, and delivery should depend on these timeline contracts rather than treating raw recording files as sessions.
