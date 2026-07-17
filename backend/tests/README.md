# Backend Tests

## Purpose

This directory contains backend tests.

## Current Scope

The suite covers the backend foundation and implemented Production Context through
ED-0050. Coverage includes shared and timeline contracts; Production Events, adapters,
dispatch, and both interpreter foundations; concrete recording, media, clock, schedule,
transcript, and vision interpretation; Observation and Evidence semantics; generic and
concrete Evidence Builders; Operational State and transition contracts; Recording
Transition Policy context safety; Session Boundary Evidence; Session Transition Policy;
Operational State Acceptance; authoritative Observation, Evidence, evaluation, and
successor-state context propagation; and Operational State Repository contracts.
ED-0048 adds the canonical Completed Media Asset contract boundary. ED-0049 adds
deterministic candidate stability and safe-to-read readiness evaluation. ED-0050 adds
the deployment-neutral declarative StageFlow Runtime and combination validation.

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

ED-0047 adds the reusable `operational_state_repository_compliance.py` suite plus
focused in-memory behavior, atomicity, concurrency, and architecture tests. The
compliance suite is driven only by an `OperationalStateRepository` factory and can be
reused by a future persistent implementation. Implementation-specific tests prove
private-lock copy-and-swap behavior, exact snapshot preservation after rejection,
read-only internal collections, commit-ID injection, repository-instance isolation,
deployment neutrality, competing initial/successor single-winner behavior, duplicate
and conflicting replay races, and coherent queries during a controlled commit.

ED-0048 adds `completed_media_asset_fixtures.py` plus focused contract, invariant,
deployment-neutrality, and architecture suites. Coverage includes finalized segments,
full recordings and clips; manifest/resource/source/provenance identity; explicit
context and recording relationships; separate completion/readiness/integrity/technical
facts; timezone-aware timestamps; naming independence; Agent/Node peer treatment;
capability independence; deterministic normalization; deep metadata immutability;
privacy-safe summaries; and the absence of monitoring, readiness detection, checksum or
probe execution, Runtime services, transfer, queues, Production Event/Observation/state
creation, repository use, AI, APIs, workers, or frontend behavior.

ED-0049 adds `asset_readiness_fixtures.py` plus focused contract, conservative-policy,
stability, conflict, deployment-neutrality, and architecture suites. Coverage includes
candidate/resource separation; all narrow resource observation types; deterministic
bundle normalization; explicit parameters; strong, stable, and guarded-manual routes;
latest-state and outcome precedence; continued growth, replacement, identity, read,
write, presence, and timestamp conflicts; ED-0048 declaration mapping; first-class
limitations; input-order determinism; Agent/Node peer treatment; privacy-safe summaries;
and the absence of monitoring, file access, recorder access, probing, transfer, queues,
Runtime services, semantic Observation/Evidence/state, AI, APIs, workers, or frontend
behavior.

ED-0050 adds `runtime_fixtures.py` plus focused contract, capability, resource-policy,
collection-plan, readiness-selection, health, deployment-neutrality, and architecture
suites. Coverage includes one immutable Runtime graph; Agent/Node/external/development
peer profiles; versioned identity and configuration; source, observation, and readiness
capability combinations; offline-capable event constraints; production-subordinate
budgets and pressure responses; explicit ED-0049 parameters and strong/stability
routes; ED-0048 assembly declarations; first-class limitations; distinct health,
availability, and validation; deterministic precedence and summaries; multiple Runtime
identity isolation; metadata and credential safety; and the absence of services,
monitoring, collection, file or recorder access, readiness execution, asset assembly,
transfer, queues, Session identity, Production Events, semantic Observations, Evidence,
Operational State, repositories, AI, APIs, workers, or frontend behavior.

ED-0041 reviews test quality without adding speculative future-behavior tests. Findings
and targeted missing regression cases are documented under `docs/reviews/`.

## What Does Not Belong Here

- Tests for unimplemented domain behavior.
- Tests requiring a database, object storage, workers, media processing, or external integrations.
