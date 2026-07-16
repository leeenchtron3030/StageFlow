# Session Boundary Evidence Builder

ED-0039 introduces StageFlow's first cross-domain Evidence Builder. It accepts one or
more existing `EvidenceSet` objects and composes their structured Concerns and Signals
into separate `possible_session_start` and `possible_session_end` EvidenceSets.

The builder consumes Evidence, not Production Events or raw Observations. It never calls
domain Evidence Builders and does not inspect transcript text. Source EvidenceSet,
EvidenceItem, Signal, and Observation identity remains ID-only and traceable in output
items, Signal references, contexts, and metadata.

## Declarative mappings

The mapping key is always source `EvidenceConcern` plus `EvidenceSignal`; matching on a
Signal alone is not sufficient. The initial treatments are:

| Source concern | Signal | Boundary concern | Role |
| --- | --- | --- | --- |
| `schedule_alignment` | `scheduled_window_active` | `possible_session_start` | `contextualizes` |
| `schedule_alignment` | `scheduled_activity_changed` | start and end | `contextualizes` |
| `schedule_alignment` | `scheduled_activity_cancelled` | `possible_session_end` | `contextualizes` |
| `visual_transition_context` / `possible_session_start` | `speaker_introduction_indicated` | `possible_session_start` | `supports` |
| `visual_transition_context` / `possible_session_start` | `presentation_transition_indicated` | `possible_session_start` | `supports` |
| `transcript_continuity` | `speech_activity_available` | `possible_session_start` | `supports` |
| `transcript_continuity` | `transcript_continuity_indicated` | `possible_session_start` | `contextualizes` |
| `recording_coverage` | `recording_continuity_established` / `recording_continuity_restored` | `possible_session_start` | `contextualizes` |
| `possible_session_start` | `session_content_indicated` | `possible_session_start` | `supports` |
| `possible_session_start` | `operator_attention_indicated` | `possible_session_start` | `contextualizes` |
| `visual_transition_context` | `visual_activity_available` | `possible_session_start` | `contextualizes` |
| `media_availability` | `media_availability_indicated` | `possible_session_start` | `contextualizes` |
| `possible_session_end` | `session_end_indicated` | `possible_session_end` | `supports` |
| `transcript_continuity` | `transcript_end_indicated` | `possible_session_end` | `supports` |
| `recording_coverage` | `recording_end_indicated` | `possible_session_end` | `supports` |
| `recording_coverage` | `recording_pause_indicated` | `possible_session_end` | `contextualizes` |
| `media_availability` | `media_finalization_indicated` | `possible_session_end` | `contextualizes` |
| `possible_session_end` | `operator_attention_indicated` | `possible_session_end` | `contextualizes` |

All output uses `EvidencePurpose.TRANSITION_SUPPORT`. Source item strength is preserved;
several Signals never inflate strength. An explicitly contradicting source item remains
contradicting. Missing Signals never create contradiction.

## Context, time, and grouping

`SessionBoundaryEvidenceContext` carries optional recording block, stage, scheduled
activity, transcript stream, media artifact, timeline, label, and anchor references.
Metadata extraction recognizes the documented ID keys used by production Evidence:
`recording_block_id`, `stage_id`, `scheduled_activity_id`, `transcript_stream_id`, and
`media_artifact_id`, including plural stream and artifact forms. Invalid or absent IDs
are not invented, and no Session ID is required.

Start and end contributions are always separate. Compatible contributions must share
boundary orientation, correlation, recording block, stage, and known scheduled activity.
They are clustered within a configurable five-minute composition window. Contributions
without recording, stage, or schedule identity remain isolated by source EvidenceSet.
The window only prevents indefinite grouping; it is not a threshold, score, timeout, or
transition rule.

The organizational anchor is the earliest contributing timeline or wall-clock anchor for
a possible start and the latest for a possible end. It is explicitly not a verified or
final boundary timestamp.

## Input reporting and boundary

Input EvidenceSets are classified as consumed, ignored, unsupported, or duplicate.
Stable EvidenceSet ID deduplication retains the first deterministic occurrence. A source
set is consumed when at least one supported Concern-and-Signal contribution is built,
ignored when its concern is unrelated, and unsupported when its concern is boundary-
relevant but it has no supported structured combination or usable item linkage.

The builder is deterministic and side-effect-free. It does not create Session Operational
State, Transition Evaluations, transition policy, Hypotheses, Findings, Verification
Decisions, Operational Products, scores, probabilities, persistence, APIs, queues,
workers, AI behavior, or frontend behavior.
