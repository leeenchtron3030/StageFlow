# Production Evidence

## Purpose

This package contains the foundational evidence contracts introduced by ED-0007 and refined by ED-0032 and ED-0035.

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
