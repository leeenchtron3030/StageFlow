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

## Production Event Dispatchers

ED-0015 adds foundational production event dispatcher contracts only.

The runtime path is `ProductionEvent` -> `ProductionEventDispatcher` -> `ProductionEventInterpreter` -> `Observation`.

The dispatcher routes. It receives available interpreters, determines which ones can receive a Production Event, invokes matching interpreters, and returns one dispatch result.

The dispatcher does not interpret, does not create Observations directly, does not reason, and does not create Evidence, Findings, Verification Decisions, or Operational Products.

ED-0015 does not implement queues, workers, retries, scheduling, plugin discovery, registries, event buses, persistence, APIs, adapters, or frontend behavior.

## Recording System Adapters

ED-0016 adds foundational recording system adapter contracts only.

Recording System Adapters report continuous recording activity from external or internal recording systems. They emit generic `ProductionEvent` objects that can later flow through the dispatcher and interpreter layers.

Recording System Adapters do not ingest media files, detect chunks, inspect codecs, construct timelines, dispatch events, interpret events, create Observations, or create reasoning artifacts.

Media artifact adapters and provider-specific recording integrations come later.

## Media Artifact Adapters

ED-0017 adds foundational media artifact adapter contracts only.

Media Artifact Adapters report that media-related artifacts exist, changed, finalized, failed, or became unavailable. They emit generic `ProductionEvent` objects.

Media Artifact Adapters do not ingest, validate, transcode, inspect, or process media. They do not register chunks, parse transcripts, extract thumbnails, watch filesystems, dispatch events, interpret events, create Observations, or create reasoning artifacts.

Filesystem watching, media ingestion, media validation, and provider-specific artifact integrations come later.

## Schedule Source Adapters

ED-0018 adds foundational schedule source adapter contracts only.

Schedule Source Adapters report planned activity information. They emit generic `ProductionEvent` objects for schedule changes, but they do not create Sessions, Session Window Products, Observations, Evidence, Findings, Operational Products, or RecordingBlocks.

`ScheduledActivity` represents the planned world: what is supposed to happen. It is not evidence, not an Observation, and not proof that the activity occurred.

Future reasoning may reconcile Scheduled Activities with observed reality. ED-0018 does not perform that comparison.

## Runtime Clock

ED-0019 adds foundational runtime clock contracts only.

The Runtime Clock is an ingress source. It emits generic `ProductionEvent` objects when meaningful time boundaries are crossed.

The Runtime Clock does not start StageFlow, schedule work, execute retries, execute timeouts, reconcile schedules, dispatch events, interpret events, create Observations, or decide what happened.

A crossed time boundary only means that a temporal boundary is now relevant. It is not proof that production activity occurred.

## Transcript Source Adapters

ED-0020 adds foundational transcript source adapter contracts only.

Transcript Source Adapters report that transcript-related artifacts, segments, or text updates exist. They emit generic `ProductionEvent` objects and do not perform transcription, process audio, create transcript files, call models, or interpret text.

Text meaning is handled later by interpreters and reasoning. A transcript segment becoming available is a Production Event, not an Observation, session boundary, editorial moment, speaker introduction, quote, or other production conclusion.

## Vision Source Adapters

ED-0021 adds foundational vision source adapter contracts only.

Vision Source Adapters report that visual detections or visual artifacts exist. They emit generic `ProductionEvent` objects and do not execute OCR, object detection, face recognition, logo recognition, scene understanding, model calls, or visual meaning interpretation.

Semantic interpretation belongs to later Interpreters and reasoning. A visual detection becoming available is a Production Event, not an Observation, session boundary, speaker appearance, title match, recognized logo, slide meaning, or clip-worthy moment.

## Operator Source Adapters

ED-0022 adds foundational operator source adapter contracts only.

Operator Source Adapters report information intentionally supplied by a human operator. They emit generic `ProductionEvent` objects and do not implement UI, authentication, permissions, workflows, review systems, validation, correctness determination, or reasoning.

Human input is observable information, not automatically truth. It participates in reasoning like every other observation source and does not bypass Observations, Evidence, Hypotheses, Findings, or Verification.

## Production Event Interpreters

ED-0014 adds foundational production event interpreter contracts only.

Production Event Interpreters translate Production Events into Observations. They define which event types and sources they support, may return zero or more Observations, and preserve traceability back to the source Production Event.

Interpreters do not reason. Evidence, Hypothesis, Finding, Verification Decision, and Operational Product generation all come later.

ED-0014 does not implement provider adapters, ingestion, webhook handlers, file watching, transcription, OCR, AI analysis, persistence, APIs, queues, workers, frontend behavior, or workflow execution.

## Observation Interpreters

ED-0023 adds explicit Observation Interpreter contracts for AR-2.0.

Observation Interpreters translate one or more `ProductionEvent` objects into zero or more objective `Observation` objects. Production Events are runtime facts; Observations are objective things StageFlow noticed about those facts.

Observation Interpreters may create Observations, but they do not create Evidence, Hypotheses, Findings, Verification Decisions, Operational Products, provider adapters, persistence, APIs, queues, workers, or frontend behavior.

The ED-0014 `production/interpreter` package remains in place for now. ED-0023 documents and implements the more explicit Observation Interpreter contract layer without consolidating or renaming the earlier generic interpreter primitives.

## Recording Activity Observation Interpreter

ED-0024 adds the first concrete Observation Interpreter and serves as the reference implementation pattern for future interpreters.

The Recording Activity Observation Interpreter translates recording-system `ProductionEvent` objects into objective recording activity `Observation` objects: recording activity began, paused, resumed, or ended.

It preserves source Production Event traceability and does not infer sessions, clips, schedules, speakers, performances, production readiness, Evidence, Hypotheses, Findings, Verification Decisions, Operational Products, provider behavior, persistence, APIs, queues, workers, or frontend behavior.

ED-0025 removes the original zero-offset workaround by allowing recording activity Observations to anchor to a recording block when available, or to wall-clock time when no recording block is known.

## Observation Location Refinement

ED-0025 refines `ObservationLocation` so media timeline anchors are not the only valid location kind.

Observation location describes where or when the Observation was anchored. Supported anchors include timeline positions, timeline ranges, recording blocks, wall-clock timestamps, stages, composite context, and explicit unknown locations.

Observations remain objective. A location does not explain why something matters, and it does not create Evidence, Hypotheses, Findings, Verification Decisions, Operational Products, persistence, APIs, queues, workers, or frontend behavior.

## Observation Primitives

ED-0006 adds foundational production observation contracts only.

Observation primitives describe what was noticed and where or when it was anchored. Observations may come from humans, transcripts, audio, graphics, schedules, livestream systems, or other generic sources.

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
