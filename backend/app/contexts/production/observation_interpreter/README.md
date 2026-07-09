# Observation Interpreter

ED-0023 adds backend-only Observation Interpreter contracts.

Observation Interpreters transform one or more Production Events into zero or more objective Observations.

## Runtime Flow

Production Event -> Observation Interpreter -> Observation -> Evidence -> Hypothesis -> Finding -> Verification Decision -> Operational Product

A Production Event says something happened. An Observation says StageFlow noticed something objective about what happened.

## Relationship To ED-0014

ED-0014 introduced the generic `production/interpreter` package.

ED-0023 keeps that package in place and adds this more explicit AR-2.0 Observation Interpreter layer. The two packages overlap conceptually, but ED-0023 does not consolidate, delete, or rename ED-0014 contracts.

Future architecture work may consolidate the generic interpreter package and this explicit Observation Interpreter package once the Production Event to Observation boundary has more concrete implementations.

## Traceability

`ObservationInterpreterResult` preserves source Production Event IDs.

When an `ObservationInterpreter` returns Observations through its helper method, the observations receive lightweight metadata containing `source_production_event_ids` and `observation_interpreter_id`. This avoids refactoring the existing Observation contract while preserving traceability.

## Exclusions

Observation Interpreters create Observations, not conclusions.

This package does not implement provider adapters, concrete interpreters, event correlation, AI analysis, OCR, transcription execution, Evidence, Hypotheses, Findings, Verification Decisions, Operational Products, persistence, APIs, queues, workers, or frontend behavior.
