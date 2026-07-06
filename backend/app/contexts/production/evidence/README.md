# Production Evidence

## Purpose

This package contains the foundational evidence contracts introduced by ED-0007.

Evidence organizes observations as support for a possible future conclusion. Evidence is still not a conclusion.

## Timeline, Observation, Evidence

- Timeline primitives describe where things occur.
- Observation primitives describe what was noticed.
- Evidence primitives organize observation references.

Reasoning and proposal generation come later.

## What Belongs Here

- `EvidenceItem`
- `EvidenceSet`
- `EvidenceStrength`
- `EvidencePurpose`
- `EvidenceSummary`

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

Contradictory evidence is first-class. It records that an observation works against an evidence purpose without deciding the final meaning.
