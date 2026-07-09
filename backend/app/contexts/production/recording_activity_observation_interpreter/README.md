# Recording Activity Observation Interpreter

ED-0024 adds the first concrete Observation Interpreter for StageFlow.

The Recording Activity Observation Interpreter translates generic recording activity `ProductionEvent` objects into objective `Observation` objects such as:

- `recording_started` -> `recording activity began`
- `recording_paused` -> `recording activity paused`
- `recording_resumed` -> `recording activity resumed`
- `recording_stopped` -> `recording activity ended`

This package is a reference implementation for future Observation Interpreters. It performs the smallest possible objective translation and preserves traceability to source Production Event IDs through the ED-0023 Observation Interpreter result contract.

## Boundaries

The interpreter:

- accepts only recording-system Production Events that match the recording activity mapping
- creates only recording activity Observations
- preserves source Production Event traceability
- may produce zero Observations for unsupported or incomplete events

The interpreter does not infer sessions, clips, speakers, performances, schedules, stream state, production readiness, Evidence, Hypotheses, Findings, Verification Decisions, or Operational Products.

## Location Note

The current `Observation` contract requires a recording timeline location. Recording activity Production Events identify a recording block but do not yet carry a precise media offset. ED-0024 therefore records the generated observation at the start of the referenced recording block and recommends a future directive for explicit event-to-timeline positioning.
