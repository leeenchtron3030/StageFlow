# Production Context

## Purpose

The Production Context owns live-event production state and the temporal model for continuous stage recordings.

## Timeline Primitives

ED-0005 adds foundational production timeline contracts only. It does not implement ingestion, transcription, workers, persistence, APIs, rendering, packages, or frontend behavior.

Timeline primitives describe where things happen on a continuous recording timeline.

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
