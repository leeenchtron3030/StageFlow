# Production Evidence

## Purpose

This package contains the foundational evidence contracts introduced by ED-0007 and refined by ED-0032.

Evidence organizes observations as support for a possible future conclusion. Evidence is still not a conclusion.

ED-0032 makes Evidence semantics first-class.

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
- `EvidenceStrength`
- `EvidencePurpose`
- `EvidenceSummary`

## Evidence Semantics

Evidence separates five concepts:

- Concern: what operational question this Evidence is about.
- Purpose: why this Evidence is being assembled or retained.
- Role: how one Observation relates to the concern.
- Strength: how strong one Evidence contribution is.
- Weight: optional relative influence without policy meaning.

One `EvidenceSet` addresses exactly one `EvidenceConcern`.

One `EvidenceItem` references one Observation ID and carries one first-class `EvidenceRole`.

`EvidenceObservationReference` is the lightweight ID-only reference shape for an Observation participating in Evidence.

Metadata may carry secondary detail, but concern and role are no longer metadata-only semantics.

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
