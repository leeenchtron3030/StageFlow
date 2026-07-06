# Production Hypothesis

## Purpose

This package contains the foundational hypothesis contracts introduced by ED-0008.

A Hypothesis expresses a possible interpretation of evidence. It is not verified, not actionable, and not a proposal.

## Timeline, Observation, Evidence, Hypothesis

- Timeline primitives describe where things occur.
- Observation primitives describe what was noticed.
- Evidence primitives organize observation references.
- Hypothesis primitives express possible meaning.

Proposal and verification layers come later.

## What Belongs Here

- `Hypothesis`
- `HypothesisType`
- `HypothesisStatus`
- `HypothesisConfidence`
- `HypothesisSupport`

## What Does Not Belong Here

- Proposal generation.
- Verification behavior.
- Session window generation.
- Reviewer workflows.
- Scoring policy.
- Automatic promotion to any action.
- Persistence or APIs.
- Provider-specific logic.

## Evidence References

Hypotheses reference evidence sets by generic IDs only. They do not embed full evidence set objects.

## Tentative Language

Hypothesis types use tentative language because hypotheses can be wrong, superseded, dismissed, or archived.
