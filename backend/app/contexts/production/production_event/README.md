# Production Event

ED-0013 adds backend-only Production Event contracts.

A Production Event is the runtime boundary between outside-world inputs and StageFlow's internal reasoning model. It records that something happened; it does not decide what the event means.

## Runtime Boundary

The intended flow is:

Outside World -> Production Event -> future Observation Engine -> Observation -> Evidence -> Hypothesis -> Finding -> Verification Decision -> Operational Product

ED-0013 implements only the Production Event layer.

## Not Observations

Production Events are not Observations. A Production Event may later be interpreted into one or more Observations by an Observation Engine, but that engine is out of scope here.

Events must not create Observations, Evidence, Hypotheses, Findings, Verification Decisions, or Operational Products.

## Provider-Agnostic Inputs

Production Event types and sources are generic categories. Future adapters may emit events from schedule systems, filesystems, transcript systems, livestream systems, operators, timers, webhooks, or internal systems.

Provider and tool names do not belong in these contracts.

## Payload And References

`ProductionEventPayload` stores lightweight JSON-compatible runtime input data without requiring a provider-specific schema.

`ProductionEventReference` connects an event to an ID or external reference string without embedding target objects.

## Exclusions

This package does not implement adapters, ingestion, file watching, webhook handlers, transcription, OCR, AI analysis, observation generation, reasoning, persistence, APIs, queues, workers, or frontend behavior.
