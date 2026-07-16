# Backend Tests

## Purpose

This directory contains backend tests.

## Current Scope

The suite covers the backend foundation and implemented Production Context through
ED-0040. Coverage includes shared and timeline contracts; Production Events, adapters,
dispatch, and both interpreter foundations; concrete recording, media, clock, schedule,
transcript, and vision interpretation; Observation and Evidence semantics; generic and
concrete Evidence Builders; Operational State and transition contracts; Recording
Transition Policy; Session Boundary Evidence; and Session Transition Policy.

Tests remain under `backend/tests/` rather than inside application packages. The suite
emphasizes contract validation, negative architectural boundaries, deterministic
ordering and deduplication, compatibility behavior, context isolation, immutability, and
ID-only traceability.

ED-0041 reviews test quality without adding speculative future-behavior tests. Findings
and targeted missing regression cases are documented under `docs/reviews/`.

## What Does Not Belong Here

- Tests for unimplemented domain behavior.
- Tests requiring a database, object storage, workers, media processing, or external integrations.
