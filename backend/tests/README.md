# Backend Tests

## Purpose

This directory contains backend tests.

## Current Scope

ED-0002 includes minimal coverage for application creation and the health endpoint.

ED-0004 adds shared contract tests for identifiers, results, errors, clocks, time ranges, and base domain events.

ED-0005 adds Production Context timeline contract tests under `backend/tests/`, following the existing backend test convention instead of nesting tests inside application packages.

ED-0006 adds Production Context observation contract tests under `backend/tests/`, following the same convention.

ED-0007 adds Production Context evidence contract tests under `backend/tests/`, continuing the convention that application packages do not contain test modules.

ED-0008 adds Production Context hypothesis contract tests under `backend/tests/`, preserving the same backend test convention.

ED-0009 adds Production Context finding contract tests under `backend/tests/`, keeping finding tests out of application packages.

ED-0010 adds Production Context verification protocol contract tests under `backend/tests/`, preserving append-only judgment semantics without workflow tests.

## What Does Not Belong Here

- Tests for unimplemented domain behavior.
- Tests requiring a database, object storage, workers, media processing, or external integrations.
