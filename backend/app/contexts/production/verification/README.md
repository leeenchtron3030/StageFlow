# Production Verification

## Purpose

This package contains the foundational verification protocol contracts introduced by ED-0010.

Verification records append-only judgment about findings. It does not mutate findings and does not create operational products.

## Reasoning Chain

- Timeline describes where things occur.
- Observation describes what was noticed.
- Evidence organizes observations.
- Hypothesis expresses possible meaning.
- Finding presents human-reviewable reasoning output.
- Verification records judgment about findings.

Operational products come later.

## What Belongs Here

- `VerificationDecision`
- `VerificationAction`
- `VerificationReason`
- `VerificationActor`
- `VerificationAdjustment`
- `VerificationNote`
- `VerificationSummary`

## What Does Not Belong Here

- Finding status.
- Review queues.
- Reviewer assignment.
- User or authentication logic.
- Session windows.
- Clip objects.
- Alerts or incidents.
- Operational product generation.
- Persistence.
- APIs.
- Frontend behavior.

## Append-Only Protocol

A finding may accumulate multiple verification decisions over time. Decisions may agree, disagree, defer, escalate, adjust, or supersede. Historical decisions remain intact.
