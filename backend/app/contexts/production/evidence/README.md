# Production Evidence

## Purpose

This package contains the foundational evidence contracts introduced by ED-0007 and
refined by ED-0032, ED-0035, and ED-0045.

Evidence organizes observations as support for a possible future conclusion. Evidence is still not a conclusion.

ED-0032 makes Evidence semantics first-class.

ED-0035 adds first-class Evidence Signals.

## Timeline, Observation, Evidence

- Timeline primitives describe where things occur.
- Observation primitives describe what was noticed.
- Evidence primitives organize observation references.

Reasoning and proposal generation come later.

## What Belongs Here

- `EvidenceConcern`
- `EvidenceContext`
- `EvidenceContextConflict`
- `EvidenceContextResolution`
- `EvidenceContextSource`
- `EvidenceItem`
- `EvidenceObservationReference`
- `EvidenceRole`
- `EvidenceSet`
- `EvidenceSignal`
- `EvidenceSignalReference`
- `EvidenceStrength`
- `EvidencePurpose`
- `EvidenceSummary`

## Evidence Semantics

Evidence separates six concepts:

- Concern: what operational question this Evidence is about.
- Purpose: why this Evidence is being assembled or retained.
- Role: how one Observation relates to the concern.
- Strength: how strong one Evidence contribution is.
- Signal: what operational indication the Evidence contributes.
- Weight: optional relative influence without policy meaning.

One `EvidenceSet` addresses exactly one `EvidenceConcern`.

One `EvidenceItem` references one Observation ID and carries one first-class `EvidenceRole`.

One `EvidenceSet` may carry zero or more `EvidenceSignalReference` objects. A signal indicates; it does not conclude. Signals remain distinct from concerns, roles, strengths, Operational State, Hypotheses, Findings, Verification Decisions, and Operational Products.

`EvidenceObservationReference` is the lightweight ID-only reference shape for an Observation participating in Evidence.

`EvidenceSignalReference` is the lightweight ID-only reference shape for a Signal participating in Evidence. It references EvidenceItem IDs and Observation IDs rather than embedding either object.

Metadata may carry secondary detail, but concern, role, and signal are no longer metadata-only semantics.

ED-0036 validates this model with the Recording Coverage Evidence Builder. Recording activity Observations become recording coverage Evidence with explicit Signals such as `recording_continuity_established`, `recording_pause_indicated`, `recording_continuity_restored`, and `recording_end_indicated`. The Evidence layer still does not evaluate or record state.

ED-0037 validates the same model in an accumulating transcript domain. Transcript activity Observations may become transcript continuity Evidence with Signals such as `speech_activity_available`, `transcript_continuity_indicated`, `transcript_interruption_indicated`, and `transcript_end_indicated`. Transcript interruption and ending Signals require explicit structured Observation semantics; absence of transcript activity is not Evidence of interruption.

ED-0039 validates cross-domain composition without changing the Evidence taxonomy. The
Session Boundary Evidence Builder consumes structured domain Evidence and organizes
supported Concern-and-Signal pairs under the existing `possible_session_start` and
`possible_session_end` concerns with `transition_support` purpose. It preserves source
Signals and item strength rather than creating aggregate confidence or proof. Temporal
grouping and its organizational anchor do not establish a session boundary; missing
Signals do not become contradictory Evidence.

## Authoritative Evidence Context

ED-0045 makes `EvidenceSet.context` the authoritative location contract for Evidence.
`EvidenceContext` is immutable, partial, ID-only, and deterministic. It preserves known
stage, recording block, scheduled activity, transcript streams, media artifacts,
correlations, timeline, organizational anchor, boundary composition context, and source
context references without embedding domain objects.

Context locates Evidence; it does not change what Evidence proves. Stage, recording
block, scheduled activity, transcript stream, media artifact, and correlation remain
distinct concepts. In particular:

- scheduled activity is not Session identity;
- media artifact is not recording identity;
- correlation is workflow traceability, not operational identity;
- timeline proximity does not establish shared identity;
- an organizational anchor is not a verified boundary; and
- a boundary context ID identifies composition, not a Session.

`EvidenceContextResolution` applies this precedence:

1. first-class Observation or Evidence context;
2. documented structured legacy fields;
3. documented metadata compatibility keys; and
4. absence when no source supplies a valid value.

First-class values cannot be overridden by legacy values. Conflicts remain available as
immutable `EvidenceContextConflict` records with the field, values, sources, contributing
IDs, and categorical resolution. Malformed fallbacks are recorded in `ignored_values`.
Conflicting known singular values have no arbitrary winner.

Recording Coverage and Transcript Continuity builders group using resolved first-class
context and emit it on every supported output. Session Boundary composition preserves
compatible source context, unions streams, artifacts, correlations, and source Evidence
IDs, and isolates conflicting known stage, block, or scheduled-activity values. Partial
schedule context can supplement exactly one compatible group; it cannot bridge two
incompatible groups. Evidence roles, strengths, Signals, and semantic mappings are
unchanged.

Recording and Session policies call the centralized resolver and expose the accepted
first-class context on `TransitionEvaluation`. They do not independently parse arbitrary
Evidence metadata. Operational State Acceptance treats evaluation context as
authoritative, rejects known request/current-state conflicts, and retains validated
context through `OperationalStateBasis.evidence_context` on the successor state.

## Metadata Compatibility Register

Compatibility readers remain in ED-0045. All rows are removable only after every writer
and stored/transported legacy shape has migrated and a later directive explicitly
authorizes deletion.

| Legacy key or shape | Authoritative first-class field | Central read location | Conflict behavior | Removal condition | Coverage |
| --- | --- | --- | --- | --- | --- |
| `stage_id` | `EvidenceContext.stage_id` | Observation/Evidence context resolver | First-class value retained; conflicting metadata reported | All Observation/Evidence producers emit first-class stage | `test_evidence_context_resolution.py`, `test_authoritative_context_propagation.py` |
| `Observation.recording_block_id`, `ObservationLocation.recording_block_id`, `EvidenceSet.recording_block_id`, `recording_block_id` | `EvidenceContext.recording_block_id` | Observation/Evidence context resolver | First-class value retained; conflicting legacy value reported; metadata-only ambiguity unresolved | All callers construct first-class block context | Resolution and propagation suites |
| `scheduled_activity_id`, `schedule_activity_id` | `EvidenceContext.scheduled_activity_id` | Evidence context resolver | First-class value retained; incompatible boundary groups isolated | Schedule and boundary writers emit first-class activity | Resolution and propagation suites |
| `transcript_stream_ids`, `transcript_stream_id`, `stream_id`, `transcript_source_id` | `EvidenceContext.transcript_stream_ids` | Evidence context resolver | First-class collection retained; fallback conflict reported; streams remain separate in transcript building | All transcript producers emit first-class stream IDs | Resolution and propagation suites |
| `media_artifact_ids`, `media_artifact_id`, `artifact_id` | `EvidenceContext.media_artifact_ids` | Evidence context resolver | First-class collection retained; artifact never supplies recording identity | All media/recording producers emit first-class artifact IDs | Resolution and propagation suites |
| `correlation_ids`, `correlation_id`, plus legacy `EvidenceSet.correlation_id` | `EvidenceContext.correlation_ids` | Evidence context resolver | Structured field precedes metadata; differences stay diagnostic; never an identity mismatch | All producers and consumers use the first-class collection | Resolution, boundary, and policy tests |
| `timeline_offset_seconds`, `timeline_range_start_seconds`, `timeline_range_end_seconds`, including nested `observation_location` | `EvidenceContext.timeline_position` or `.timeline_range` | Evidence context resolver | First-class timeline retained; requires a known recording block; no identity inferred from proximity | All context-sensitive writers emit timeline contracts | Resolution and propagation suites |
| `organizational_anchor`, `boundary_anchor_at` | `EvidenceContext.organizational_anchor` | Evidence context resolver | First-class anchor retained; remains distinct from Evidence, evaluation, and acceptance time | All boundary writers emit the first-class datetime anchor | Resolution and propagation suites |
| `organizational_anchor_seconds`, `boundary_anchor_seconds` | `EvidenceContext.organizational_anchor_seconds` | Evidence context resolver | First-class anchor retained; remains organizational only | All boundary writers emit the first-class numeric anchor | Resolution and propagation suites |
| `boundary_context_id`, `boundary_evidence_context_id` | `EvidenceContext.boundary_context_id` | Evidence context resolver | First-class value retained; conflicting known IDs reject/isolate downstream context | All boundary outputs and legacy callers use first-class IDs | Resolution, propagation, and Session policy suites |
| Recording policy `recording_transition_marker` | First-class `EvidenceSignalReference` plus resolved `EvidenceContext` | Recording policy semantic compatibility path; context only through central resolver | Signal remains authoritative; marker is used only when Signals are absent | All callers emit first-class Signals and a later directive removes the marker | Recording policy contract suite |
| Session Boundary metadata copies (`stage_id`, `recording_block_id`, `scheduled_activity_id`, stream/artifact lists, timeline and anchor keys, `boundary_context_id`) | Boundary `EvidenceSet.context` | Evidence context resolver | First-class boundary context retained; metadata cannot override it | All downstream callers consume `EvidenceSet.context` and legacy serialized boundary Evidence is migrated | Boundary, Session policy, and propagation suites |

Compatibility metadata remains a readable projection for older callers and diagnostics;
it is no longer the sole authoritative carrier for supported operational context.

## What Does Not Belong Here

- Full Observation objects embedded in evidence items.
- Reasoning or inference.
- Proposal generation.
- Session window generation.
- Verification decisions.
- Scoring policy.
- Final confidence calculations.
- Persistence or APIs.
- Provider-specific logic.

## Contradictory Evidence

Contradictory evidence is first-class.

A contradicting Observation weakens or delays a concern, but it does not delete supporting Observations.

Supporting, contradicting, contextual, neutral, and unknown roles may coexist inside one EvidenceSet.

Evidence does not decide what happened, update Operational State, generate Hypotheses, generate Findings, create Verification Decisions, or produce Operational Products.
