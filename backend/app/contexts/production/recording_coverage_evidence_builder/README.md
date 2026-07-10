# Recording Coverage Evidence Builder

ED-0036 adds the first concrete domain-specific Evidence Builder.

ED-0038 refactors this builder to use the generic Evidence Builder semantic-selection mechanics while preserving recording-specific meaning.

The Recording Coverage Evidence Builder converts objective recording activity `Observation` objects into recording-coverage `EvidenceSet` objects with first-class `EvidenceSignalReference` values.

It validates the deterministic path:

`Recording Observation` -> `Recording Coverage Evidence` -> `Evidence Signal` -> `Recording Transition Policy`

The builder itself does not call transition policies, create Operational State, mutate state, persist Evidence, infer sessions, generate Hypotheses, create Findings, create Verification Decisions, create Operational Products, call AI, expose APIs, use queues or workers, or add frontend behavior.

## Recognized Recording Semantics

The builder recognizes structured recording Observation metadata produced by the recording activity interpreter:

- `recording_activity = began` -> `recording_continuity_established`
- `recording_activity = paused` -> `recording_pause_indicated`
- `recording_activity = resumed` -> `recording_continuity_restored`
- `recording_activity = ended` -> `recording_end_indicated`

`recording_event_kind` remains a structured fallback when `recording_activity` is absent.

The builder does not parse free-form Observation notes and does not use `EvidenceSignal.UNKNOWN` as a catch-all.

The generic foundation performs structured key lookup, normalization, deterministic ordering, duplicate handling, input reporting, and context-key comparison. This builder still owns the recording mappings, recording coverage concern, transition-support purpose, support role, strength assumption, and rationale text.

## Grouping

Recognized recording Observations are grouped by recording block and stage context. Distinct recording blocks are not merged. Distinct stages are not merged.

Within a group, EvidenceItems and Signal references preserve chronological ordering by `observed_at`, then timeline position where available, then Observation ID as a stable fallback.

Duplicate Observation IDs are ignored after the first deterministic occurrence and reported in the result.

## Boundary

The builder produces Evidence only. The Recording Transition Policy consumes that Evidence separately and may return a `TransitionEvaluation`.

Session reasoning remains deferred.
