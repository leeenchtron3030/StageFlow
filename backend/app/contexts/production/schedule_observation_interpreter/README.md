# Schedule Observation Interpreter

ED-0028 adds a concrete Observation Interpreter for Schedule Source events.

The Schedule Observation Interpreter translates schedule-related `ProductionEvent` objects into objective `Observation` objects such as:

- `schedule_artifact_updated` -> `Scheduled activity was updated.`
- cancelled schedule artifact -> `Scheduled activity was cancelled.`
- `schedule_boundary_reached` -> `Scheduled activity entered its planned time window.`
- schedule-source `system_status_changed` -> `Schedule source status changed.`

This interpreter observes planned reality only. Schedule Observations describe the schedule; they do not describe production and do not prove that production followed the schedule.

## Boundaries

The interpreter:

- accepts only supported schedule Production Event types from the schedule source
- treats `system_status_changed` conservatively and requires the schedule adapter metadata marker
- creates only schedule activity Observations
- uses ED-0025 `ObservationLocation` anchors truthfully
- may produce zero Observations for unsupported or non-schedule events

The interpreter does not reconcile schedules with recorded media, infer production activity, infer sessions, infer recordings, infer speakers, infer audience presence, create reasoning artifacts, introduce persistence, create APIs, create queues, create workers, run AI, or introduce provider-specific behavior.

## Planned Reality

Planned reality and observed reality are allowed to disagree.

This interpreter preserves planned reality faithfully as Observations so later reasoning can compare it against observed production signals. It does not perform that comparison itself.

Generated Observations anchor to the source event's wall-clock occurrence time and never invent media timeline offsets.

## ED-0043 Provenance

Each produced Observation carries the exact schedule Production Event ID, type, and
occurrence time; stable `schedule_activity_interpreter` identity; applied mapping-rule
identity; and explicitly supplied scheduled-activity, stage, recording-block, and
correlation context. Timestamp alignment never invents schedule bindings.
