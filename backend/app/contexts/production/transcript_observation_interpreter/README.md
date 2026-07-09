# Transcript Observation Interpreter

ED-0029 adds a concrete Observation Interpreter for Transcript Source events.

The Transcript Observation Interpreter translates transcript-related `ProductionEvent` objects into objective `Observation` objects such as:

- `transcript_segment_available` -> `Transcript segment became available.`
- transcript-source `system_status_changed` -> `Transcript source status changed.`

Transcript systems report words. This interpreter reports that transcript information became available. It does not interpret the words.

## Boundaries

The interpreter:

- accepts only supported transcript Production Event types from the transcript source
- treats `system_status_changed` conservatively and requires the transcript adapter metadata marker
- creates only transcript activity Observations
- preserves transcript excerpts exactly as observed data when present
- uses ED-0025 `ObservationLocation` anchors truthfully
- may produce zero Observations for unsupported or non-transcript events

The interpreter does not summarize transcript text, infer meaning, infer speakers, infer topics, infer sentiment, infer sessions, create reasoning artifacts, introduce persistence, create APIs, create queues, create workers, run AI, or introduce provider-specific behavior.

## Language

Language is observable. Meaning is reasoning.

This interpreter may carry transcript text as observed data, but it does not rewrite, summarize, normalize, classify, or interpret that text.

Generated Observations anchor to a recording block when one is available. If no recording block is known, they anchor to the source event's wall-clock occurrence time.
