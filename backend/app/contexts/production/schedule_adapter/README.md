# Schedule Source Adapter

ED-0018 adds backend-only Schedule Source Adapter contracts.

A Schedule Source Adapter reports planned activity information. It describes what is supposed to happen, not what actually happened.

## Runtime Flow

Schedule Source -> Schedule Source Adapter -> Scheduled Activity -> Production Event -> Dispatcher -> Interpreter -> Observation

## Planned World

`ScheduledActivity` represents planning information only. It is not evidence, not an Observation, not a verified Session, and not proof that anything occurred.

Schedule adapters emit generic Production Events for schedule changes. They do not create Sessions, Session Window Products, Observations, Evidence, Findings, Operational Products, RecordingBlocks, or media references.

## Production Event Mapping

Schedule activity changes map to generic Production Event types:

- `schedule_artifact_updated`
- `system_status_changed`

`schedule_boundary_reached` remains available for future runtime boundary events, but ED-0018 does not implement scheduling or clock-driven boundary emission.

## Exclusions

This package does not implement provider integrations, calendar synchronization, CSV parsing, schedule reconciliation, observation generation, reasoning, persistence, APIs, queues, workers, or frontend behavior.
