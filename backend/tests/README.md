# Backend Tests

## Purpose

This directory contains backend tests.

## Current Scope

The suite covers the backend foundation and implemented Production Context through
ED-0046. Coverage includes shared and timeline contracts; Production Events, adapters,
dispatch, and both interpreter foundations; concrete recording, media, clock, schedule,
transcript, and vision interpretation; Observation and Evidence semantics; generic and
concrete Evidence Builders; Operational State and transition contracts; Recording
Transition Policy context safety; Session Boundary Evidence; Session Transition Policy;
Operational State Acceptance; authoritative Observation, Evidence, evaluation, and
successor-state context propagation; and Operational State Repository contracts.

Tests remain under `backend/tests/` rather than inside application packages. The suite
emphasizes contract validation, negative architectural boundaries, deterministic
ordering and deduplication, compatibility behavior, context isolation, immutability, and
ID-only traceability.

ED-0045 adds `test_evidence_context_contracts.py`,
`test_evidence_context_resolution.py`, and
`test_authoritative_context_propagation.py`. These suites cover immutable partial context,
every retained legacy alias, precedence and structured conflicts, malformed fallbacks,
input-order determinism, builder grouping/isolation, boundary composition, policy
projection, acceptance mismatch rejection, exact Event lineage, and successor context.
Architectural checks continue to exclude repositories, persistence, mutation, policy
invocation from resolution, Session identity creation, verified boundaries, scoring,
confidence, AI, APIs, workers, queues, registries, and frontend behavior.

ED-0046 adds `test_operational_state_repository_contracts.py`,
`test_operational_state_repository_commit_contracts.py`, and
`test_operational_state_repository_architecture.py`. These suites cover the abstract
interface, supported subject-kind scope, immutable ID-only records, explicit queries,
oldest-to-newest history, complete accepted lineage, timezone-aware repository times,
deterministic reasons, all-or-none commit shapes, actual persisted supersession,
duplicate Evaluation/acceptance semantics, stale predecessor and initial-state conflict
outcomes, and the absence of policy invocation, acceptance invocation, storage,
execution, APIs, workers, queues, retries, publication, frontend behavior, and AI.

ED-0041 reviews test quality without adding speculative future-behavior tests. Findings
and targeted missing regression cases are documented under `docs/reviews/`.

## What Does Not Belong Here

- Tests for unimplemented domain behavior.
- Tests requiring a database, object storage, workers, media processing, or external integrations.
