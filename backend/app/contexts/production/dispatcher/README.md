# Production Event Dispatcher

ED-0015 adds backend-only Production Event Dispatcher contracts.

The dispatcher routes Production Events to available Production Event Interpreters. It answers one question: which interpreters should receive this event?

## Runtime Flow

Production Event -> Dispatcher -> Interpreter -> Observation

The dispatcher routes. The interpreter interprets. Observation observes.

## Responsibility

`ProductionEventDispatcher` receives interpreters directly, inspects whether each interpreter can interpret a Production Event, invokes matching interpreters, and returns one `DispatchResult`.

`DispatchResult` preserves each `InterpreterResult` unchanged.

`DispatchRule` describes routing intent only. It performs no execution and does not own interpreter discovery.

## Exclusions

The dispatcher does not create Observations directly, does not interpret, does not reason, does not create Evidence, Findings, or Operational Products, and does not manage runtime infrastructure.

This package does not implement adapters, queues, workers, retries, scheduling, dependency injection, plugin discovery, registries, event buses, persistence, APIs, or frontend behavior.
