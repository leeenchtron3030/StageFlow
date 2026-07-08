# Production Event Interpreter

ED-0014 adds backend-only interpreter contracts.

A Production Event Interpreter defines the boundary where generic runtime inputs may become Observations. It translates; it does not reason.

## Runtime Flow

Outside World -> Production Event -> Production Event Interpreter -> Observation -> Evidence -> Hypothesis -> Finding -> Verification Decision -> Operational Product

ED-0014 implements only the interpreter contract layer.

## Translation Boundary

`ProductionEventInterpreter` declares supported Production Event types and sources and exposes a contract for checking whether an event can be interpreted.

`InterpreterResult` preserves traceability to the source Production Event and may contain zero, one, or many Observations.

Returning zero Observations is valid because not every runtime input is meaningful.

## Declarative Rules

`InterpreterRule` describes intended event/source inputs and intended Observation types. Rules describe intent only. They do not execute logic and do not create Observations directly.

## Exclusions

Interpreters must not create Evidence, Hypotheses, Findings, Verification Decisions, or Operational Products.

This package does not implement provider adapters, filesystem watching, webhook handlers, transcription, OCR, AI analysis, persistence, APIs, queues, workers, frontend behavior, or workflow execution.
