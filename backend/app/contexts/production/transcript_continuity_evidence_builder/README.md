# Transcript Continuity Evidence Builder

ED-0037 adds the second concrete domain-specific Evidence Builder.

ED-0038 refactors this builder to use the generic Evidence Builder semantic-selection mechanics while preserving transcript-specific meaning.

The Transcript Continuity Evidence Builder converts objective transcript activity `Observation` objects into transcript continuity `EvidenceSet` objects with first-class `EvidenceSignalReference` values.

Transcript Evidence is accumulating and time-based. A segment arriving is observable; a stream explicitly ending is observable; a session ending is not.

## Recognized Transcript Semantics

The builder recognizes structured `transcript_lifecycle` Observation metadata:

- `segment_available` -> first segment produces `speech_activity_available`; later compatible segments produce `transcript_continuity_indicated`
- `transcript_activity_began` -> `speech_activity_available`
- `transcript_content_continued` -> `transcript_continuity_indicated`
- `transcript_activity_interrupted` -> `transcript_interruption_indicated`
- `transcript_activity_ended` -> `transcript_end_indicated`

The current transcript Observation Interpreter naturally emits `segment_available` and `transcript_source_status_changed`. The latter is reported as unsupported because it is not enough by itself to distinguish interruption from ending.

The builder does not parse transcript text, inspect language meaning, infer speakers, infer session state, infer interruption from silence, or emit `unknown` as a fallback Signal.

The generic foundation performs structured key lookup, normalization, deterministic ordering, duplicate handling, input reporting, and context-key comparison. This builder still owns transcript lifecycle mappings, stream grouping, first-segment versus later-segment behavior, transcript continuity concern, support role, strength assumption, and rationale text.

## Grouping

Recognized transcript Observations are grouped by resolved recording block, stage, and
transcript stream. `Observation.context.transcript_stream_id` is authoritative; the
central resolver retains `transcript_stream_id`, `stream_id`, and `transcript_source_id`
as compatibility aliases.

If no transcript stream identifier exists, the builder uses recording block plus stage as the narrowest stable context.

Ordering is deterministic: `observed_at`, then timeline offset when available, then Observation ID.

Duplicate Observation IDs are ignored after the first deterministic occurrence and reported in the result.

## Boundary

The builder produces Evidence only. It does not call policies, create Transition Evaluations, mutate Operational State, persist Evidence, create Hypotheses, create Findings, create Verification Decisions, create Operational Products, call AI, expose APIs, use queues or workers, or add frontend behavior.
## ED-0043/ED-0045 Lineage And Context

The builder reads first-class recording-block, stage, and transcript-stream context
before legacy fields or metadata and emits aggregate first-class `EvidenceSet.context`.
Transcript stream fallback remains
`transcript_stream_id`, `stream_id`, then `transcript_source_id`. Structured source Event,
interpreter, rule, stream, and timeline traceability is retained through EvidenceItem,
EvidenceSignalReference, and EvidenceSet metadata without inspecting transcript text or
changing Evidence semantics.
