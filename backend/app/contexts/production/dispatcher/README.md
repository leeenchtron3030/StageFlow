# Production Event Dispatcher

ED-0015 adds backend-only Production Event Dispatcher contracts. The approved
Dispatcher-Interpreter compatibility plan adds a structural dispatcher boundary and a
dispatcher-owned Observation Interpreter adapter.

The dispatcher routes Production Events to available Production Event Interpreters. It answers one question: which interpreters should receive this event?

## Runtime Flow

Production Event -> Dispatcher -> Interpreter -> Observation

The dispatcher routes. The interpreter interprets. Observation observes.

## Responsibility

`ProductionEventDispatcher` receives objects satisfying `DispatcherInterpreter`
directly, inspects whether each can interpret a Production Event, invokes every match in
registration order, and returns one `DispatchResult`. `ProductionEventInterpreter`
continues to satisfy this protocol structurally and remains a supported public contract.

`compatibility.ObservationInterpreterAdapter` maps a single Production Event and all
five context fields to a concrete Observation Interpreter. It preserves ordered
Observations and warnings and validates Event, correlation, provenance, and interpreter
lineage before returning them. Contract violations and exceptions become sanitized,
typed failed results; later matching interpreters still run.

Lineage validation includes source Event ID, type, occurrence time, interpreter ID,
Observation and context correlation, Event-derived first-class context references, and
source producer identity. Event lineage extraction distinguishes genuine absence, a
valid value, malformed input, and contradictory authoritative candidates. Equivalent
candidates are accepted; malformed or conflicting candidates fail before interpreter
invocation. Dispatcher-context stage or Recording Block values are used only for genuine
Event absence. Validation is atomic for one adapter invocation: if any member of a
one-to-many result is malformed, none of that result's Observations are released.

Legacy `InterpreterResult` instances are preserved. Adapted concrete results are mapped
losslessly into that contract. `DispatchStatus` explicitly classifies no match, clean
success, success with warnings or degraded behavior, partial failure, and total failure.
`READY` and `ACTIVE` are clean-capable; `DEGRADED` and legacy `EXPERIMENTAL` survive but
surface warning semantics. `UNKNOWN`, `CONFIGURED`, `FAILED`, `DISABLED`, and `ARCHIVED`
fail closed and release no Observations. Unsupported future statuses also become typed
failures rather than falling through to success. One centralized status classification
drives dispatcher sanitization, aggregate status, summary counts, and Observation
survival. Direct `DispatchResult` construction retains raw per-interpreter diagnostics,
but its aggregate `observations` output filters every non-survivable or unsupported
status so failed output cannot escape as accepted dispatcher output.

`DispatchRule` describes routing intent only. It performs no execution and does not own interpreter discovery.

## Exclusions

The dispatcher does not create Observations directly, does not interpret, does not reason, does not create Evidence, Findings, or Operational Products, and does not manage runtime infrastructure.

The compatibility adapter is not a registry or a second dispatcher. This package does
not implement batch dispatch, queues, workers, retries, scheduling, dependency
injection, plugin discovery, registries, event buses, persistence, APIs, or frontend
behavior. Durable ingress identity, replay-stable downstream effects, and restart-safe
runtime composition remain unimplemented.
