# Production Finding

## Purpose

This package contains the foundational finding contracts introduced by ED-0009.

A Finding is the first human-reviewable reasoning artifact in StageFlow. It says what StageFlow found that may deserve human attention.

## Reasoning Boundary

- Timeline describes where things occur.
- Observation describes what was noticed.
- Evidence organizes observations.
- Hypothesis expresses possible meaning.
- Finding presents meaningful reasoning output for human review.
- Verification follows later.

Finding is not verification, workflow state, or an operational product.

## What Belongs Here

- `Finding`
- `FindingType`
- `FindingConfidence`
- `FindingOrigin`
- `FindingLocation`
- `FindingSupport`
- `FindingSummary`

## What Does Not Belong Here

- Review workflows.
- Verification logic.
- Session window creation.
- Clip objects.
- Alert objects.
- Persistence.
- APIs.
- Frontend behavior.
- Provider-specific implementations.

## Hypothesis References

Findings reference hypothesis IDs only. They do not embed full hypothesis objects.
