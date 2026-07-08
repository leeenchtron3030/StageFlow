# Runtime Clock

ED-0019 adds backend-only Runtime Clock contracts.

The Runtime Clock is an ingress source. It observes meaningful time boundaries and emits provider-agnostic Production Events.

## Runtime Flow

Clock -> Production Event -> Dispatcher -> Interpreter -> Observation

The Clock does not start StageFlow, schedule work, manage runtime lifecycle, execute retries, or decide what time means.

## Time Boundaries

`TimeBoundary` describes a moment worth noticing. A crossed scheduled boundary does not prove that a scheduled activity happened. A crossed timeout boundary does not prove that a failure occurred. A crossed retry boundary does not execute a retry.

## Production Event Mapping

Clock events may map to:

- `schedule_boundary_reached`
- `timer_elapsed`
- `system_status_changed`

The mapping is generic and creates no Observations, Evidence, Findings, Operational Products, jobs, retries, or schedule reconciliation.

## Exclusions

This package does not implement cron, schedulers, background jobs, queues, retries, timeout execution, schedule reconciliation, persistence, APIs, workers, frontend behavior, or provider-specific integrations.
