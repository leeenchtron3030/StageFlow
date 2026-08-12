# Observation Interpreter

ED-0023 adds backend-only Observation Interpreter contracts.

Observation Interpreters transform one or more Production Events into zero or more objective Observations.

## Runtime Flow

Production Event -> Observation Interpreter -> Observation -> Evidence -> Hypothesis -> Finding -> Verification Decision -> Operational Product

A Production Event says something happened. An Observation says StageFlow noticed something objective about what happened.

## Relationship To ED-0014

ED-0014 introduced the generic `production/interpreter` package.

ED-0023 keeps that package in place and adds this more explicit AR-2.0 Observation Interpreter layer. The two packages overlap conceptually, but ED-0023 does not consolidate, delete, or rename ED-0014 contracts.

The dispatcher-owned compatibility adapter allows the six concrete Observation
Interpreters to participate in `ProductionEventDispatcher` without consolidating these
contracts. Their direct single-Event and batch APIs remain supported.

## Traceability

`ObservationInterpreterResult` preserves source Production Event IDs.

ED-0043 makes exact lineage first-class on each interpreter-produced Observation.
`Observation.provenance` preserves one exact source Event ID and type, source occurrence
time, interpreter ID and stable kind, and applied rule identity. Compatibility metadata
containing `source_production_event_ids` and `observation_interpreter_id` remains
available but is secondary.

`event_observation_lineage.py` centralizes context extraction. It evaluates every
authoritative Event reference, structured payload value, and structured metadata value
for each lineage category. Multiple equivalent values are accepted; malformed input or
disagreement fails closed instead of being resolved by precedence. Explicit interpreter
context may supply Stage and Recording Block values only when the Event value is truly
absent, and each retained value records its source in `ObservationContext.metadata`.
Transcript text is never inspected. First-class Observation context is authoritative
downstream.

Interpreters do not compare source and Observation timestamps. They preserve Event time
and assign Observation time independently, remain side-effect free, and do not mutate
Production Events.

## Exclusions

Observation Interpreters create Observations, not conclusions.

This package does not implement provider adapters, concrete interpreters, event correlation, AI analysis, OCR, transcription execution, Evidence, Hypotheses, Findings, Verification Decisions, Operational Products, persistence, APIs, queues, workers, or frontend behavior.
