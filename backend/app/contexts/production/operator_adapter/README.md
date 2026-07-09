# Operator Source Adapter

ED-0022 adds backend-only Operator Source Adapter contracts.

An Operator Source Adapter reports information intentionally supplied by a human operator. Human input is observable information; it is not automatically truth.

## Runtime Flow

Human Operator -> Operator Source Adapter -> Production Event -> Dispatcher -> Interpreter -> Observation

Operator adapters report supplied information. They emit generic Production Events and do not determine correctness, validate operator input, interpret operator intent, or bypass the reasoning pipeline.

## Production Event Mapping

Operator events may be mapped only to generic Production Event types:

- `operator_input_received`
- `system_status_changed`

`created`, `updated`, and `removed` operator event statuses map to `operator_input_received`. `cancelled` and `unknown` map to `system_status_changed`.

## Exclusions

Reporting operator input is not workflow.

This package does not implement UI, authentication, permissions, review queues, approvals, assignments, review systems, source APIs, persistence, queues, workers, dispatch execution, frontend behavior, or reasoning.

The mapping does not create Observations, Evidence, Hypotheses, Findings, Operational Products, Sessions, RecordingBlocks, TimelinePositions, or TimelineRanges.
